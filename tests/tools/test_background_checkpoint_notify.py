"""A background completion contract must be what a restarted host recovers.

The spawn checkpoint is written before notify, watch patterns, heartbeat, and
chat routing are set, and adoption stamps routing after its own checkpoint.
Recovery in a new registry reads only the file, so that file has to hold the
final contract.

The held command is one shell blocked on a fifo this test opens. Teardown
writes that fifo and the shell exits itself, so cleanup never signals a
process.
"""

from __future__ import annotations

import json
import os
import shlex
import threading

import pytest

from agent.interrupt_control import InterruptControlMixin
from gateway.session_context import clear_session_vars, set_session_vars
from tests.waiting import wait_until
from tools.process_registry import ProcessRegistry, _checkpoint_path, process_registry
from tools.terminal_tool import terminal_tool

pytestmark = pytest.mark.platforms("posix")

_CHAT = {
    "platform": "telegram",
    "chat_id": "42",
    "user_id": "7",
    "user_name": "ada",
    "thread_id": "99",
    "message_id": "1001",
    "session_key": "agent:main:telegram:dm:42",
    "session_id": "sess-parent",
}


class _Agent(InterruptControlMixin):
    """Enough of a turn for redirect() to ask the foreground tool to yield."""

    _executing_tools = True
    _interrupt_requested = False
    _pending_steer = None
    _pending_redirect = None
    api_mode = "chat_completions"

    def __init__(self) -> None:
        self._pending_steer_lock = threading.Lock()
        self._pending_redirect_lock = threading.Lock()
        self._tool_worker_threads: set[int] = set()
        self._tool_worker_threads_lock = threading.Lock()
        self._execution_thread_id = None


def _bind(*, async_delivery: bool = True) -> list:
    return set_session_vars(async_delivery=async_delivery, **_CHAT)


class _Hold:
    """One shell, blocked in ``read`` on a fifo this test created.

    ``exec 3<>fifo`` only opens the fifo on that shell. There is no child to
    reparent, and release writes one line so the shell exits by itself.
    """

    def __init__(self, tmp_path) -> None:
        self.ready = tmp_path / "ready"
        self.fifo = tmp_path / "release"
        os.mkfifo(self.fifo)
        ready = shlex.quote(str(self.ready))
        fifo = shlex.quote(str(self.fifo))
        self.command = f"touch {ready}; exec 3<>{fifo}; read -r -u 3 _"
        self.session_id: str | None = None

    def wait_ready(self) -> None:
        wait_until(self.ready.is_file, timeout=20, what="held command ready")

    def release(self) -> None:
        """Unblock the shell, then wait until the checkpoint no longer tracks it."""

        def _opened() -> bool:
            try:
                fd = os.open(self.fifo, os.O_WRONLY | os.O_NONBLOCK)
            except OSError:
                session = (
                    process_registry.get(self.session_id) if self.session_id else None
                )
                return session is None or session.exited
            try:
                os.write(fd, b"\n")
            finally:
                os.close(fd)
            return True

        wait_until(_opened, timeout=10, what="held command accepted release")
        if self.session_id is None:
            return
        wait_until(
            self._left_checkpoint, timeout=10, what="held command left the checkpoint"
        )

    def _left_checkpoint(self) -> bool:
        session = process_registry.get(self.session_id)
        if session is not None and not session.exited:
            return False
        path = _checkpoint_path()
        if not path.exists():
            return True
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        return all(
            not isinstance(item, dict) or item.get("session_id") != self.session_id
            for item in raw
        )


def _entry(session_id: str) -> dict:
    raw = json.loads(_checkpoint_path().read_text(encoding="utf-8"))
    return next(item for item in raw if item["session_id"] == session_id)


def _watcher(session_id: str) -> dict:
    return {
        "session_id": session_id,
        "check_interval": 5,
        "session_key": _CHAT["session_key"],
        "platform": _CHAT["platform"],
        "chat_id": _CHAT["chat_id"],
        "user_id": _CHAT["user_id"],
        "user_name": _CHAT["user_name"],
        "thread_id": _CHAT["thread_id"],
        "message_id": _CHAT["message_id"],
        "notify_on_complete": True,
        "parent_session_id": _CHAT["session_id"],
    }


def _recover(session_id: str) -> ProcessRegistry:
    restarted = ProcessRegistry()
    recovered = restarted.recover_from_checkpoint()
    assert recovered == 1, recovered
    assert restarted.get(session_id) is not None
    return restarted


def _yield(hold: _Hold, *, async_delivery: bool) -> dict:
    """Real foreground terminal entry, yielded once the held shell is ready."""
    agent = _Agent()
    box: dict = {}

    def worker() -> None:
        with agent._tool_worker_threads_lock:
            ident = threading.current_thread().ident
            assert ident is not None
            agent._tool_worker_threads.add(ident)
        tokens = _bind(async_delivery=async_delivery)
        try:
            box["result"] = json.loads(
                terminal_tool(
                    hold.command,
                    task_id="t-yield",
                    timeout=60,
                    workdir=str(hold.ready.parent),
                )
            )
        finally:
            clear_session_vars(tokens)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    try:
        hold.wait_ready()
        assert agent.redirect("status?") is True
        thread.join(timeout=20)
        assert not thread.is_alive(), "foreground command did not yield"
        result = box["result"]
        hold.session_id = result.get("session_id")
        return result
    finally:
        if thread.is_alive():
            # The tool thread is still inside the foreground command. Unblock
            # that shell so it can exit; do not signal it.
            try:
                fd = os.open(hold.fifo, os.O_WRONLY | os.O_NONBLOCK)
            except OSError:
                fd = None
            if fd is not None:
                try:
                    os.write(fd, b"\n")
                finally:
                    os.close(fd)
            thread.join(timeout=20)


def test_notified_background_recovers_route_watcher_and_heartbeat(tmp_path):
    """notify=true, its route, and the pending watcher survive a new registry."""
    tokens = _bind()
    hold = _Hold(tmp_path)
    try:
        out = json.loads(
            terminal_tool(
                hold.command,
                background=True,
                notify_on_complete=True,
                heartbeat=60,
                task_id="t-notify",
                workdir=str(tmp_path),
            )
        )
        hold.session_id = out["session_id"]
        hold.wait_ready()
        sid = hold.session_id
        assert out["notify_on_complete"] is True
        assert out["heartbeat_seconds"] == 60
        live = process_registry.get(sid)
        assert live.notify_on_complete is True
        assert live.watcher_platform == "telegram"
        assert live.watcher_chat_id == "42"
        assert live.heartbeat_seconds == 60
        assert live.watcher_interval == 5

        entry = _entry(sid)
        assert entry["notify_on_complete"] is True
        assert entry["heartbeat_seconds"] == 60
        assert entry["watcher_interval"] == 5
        assert entry["watcher_platform"] == "telegram"
        assert entry["watcher_chat_id"] == "42"
        assert entry["watcher_user_id"] == "7"
        assert entry["watcher_user_name"] == "ada"
        assert entry["watcher_thread_id"] == "99"
        assert entry["watcher_message_id"] == "1001"
        assert entry["parent_session_id"] == "sess-parent"
        assert entry["session_key"] == _CHAT["session_key"]

        restarted = _recover(sid)
        session = restarted.get(sid)
        assert session.notify_on_complete is True
        assert session.heartbeat_seconds == 60
        assert session.watcher_platform == "telegram"
        assert session.watcher_chat_id == "42"
        assert restarted.pending_watchers == [_watcher(sid)]
    finally:
        clear_session_vars(tokens)
        hold.release()


def test_watch_patterns_and_route_survive_checkpoint_recovery(tmp_path):
    """Watch-only spawns persist patterns and chat routing, and arm no watcher."""
    tokens = _bind()
    hold = _Hold(tmp_path)
    try:
        out = json.loads(
            terminal_tool(
                hold.command,
                background=True,
                watch_patterns=["BUILD OK"],
                task_id="t-watch",
                workdir=str(tmp_path),
            )
        )
        hold.session_id = out["session_id"]
        hold.wait_ready()
        sid = hold.session_id
        assert out["watch_patterns"] == ["BUILD OK"]
        live = process_registry.get(sid)
        assert live.watch_patterns == ["BUILD OK"]
        assert live.notify_on_complete is False
        assert live.watcher_platform == "telegram"
        assert live.watcher_interval == 0

        entry = _entry(sid)
        assert entry["watch_patterns"] == ["BUILD OK"]
        assert entry["notify_on_complete"] is False
        assert entry["watcher_platform"] == "telegram"
        assert entry["watcher_chat_id"] == "42"
        assert entry["watcher_interval"] == 0

        restarted = _recover(sid)
        session = restarted.get(sid)
        assert session.watch_patterns == ["BUILD OK"]
        assert session.notify_on_complete is False
        assert session.watcher_platform == "telegram"
        assert restarted.pending_watchers == []
    finally:
        clear_session_vars(tokens)
        hold.release()


def test_silent_background_recovers_without_a_completion_watcher(tmp_path):
    """A bound chat does not turn a silent background process into a watcher."""
    tokens = _bind()
    hold = _Hold(tmp_path)
    try:
        out = json.loads(
            terminal_tool(
                hold.command,
                background=True,
                task_id="t-silent",
                workdir=str(tmp_path),
            )
        )
        hold.session_id = out["session_id"]
        hold.wait_ready()
        sid = hold.session_id
        assert out.get("notify_on_complete") is not True
        assert "hint" in out
        live = process_registry.get(sid)
        assert live.notify_on_complete is False
        assert live.watcher_platform == ""
        assert live.watch_patterns == []

        entry = _entry(sid)
        assert entry["notify_on_complete"] is False
        assert entry["watcher_platform"] == ""
        assert entry["watcher_interval"] == 0
        assert entry["watch_patterns"] == []
        assert entry["heartbeat_seconds"] == 0

        restarted = _recover(sid)
        session = restarted.get(sid)
        assert session.notify_on_complete is False
        assert session.watcher_platform == ""
        assert session.watch_patterns == []
        assert restarted.pending_watchers == []
    finally:
        clear_session_vars(tokens)
        hold.release()


def test_yielded_foreground_recovers_its_gateway_route(tmp_path):
    """Adoption stamps routing after its checkpoint; recovery must still see it."""
    hold = _Hold(tmp_path)
    try:
        out = _yield(hold, async_delivery=True)
        hold.session_id = out["session_id"]
        sid = hold.session_id
        assert out["status"] == "yielded_to_background"
        live = process_registry.get(sid)
        assert live.notify_on_complete is True
        assert live.watcher_platform == "telegram"
        assert live.watcher_interval == 5

        entry = _entry(sid)
        assert entry["notify_on_complete"] is True
        assert entry["watcher_platform"] == "telegram"
        assert entry["watcher_chat_id"] == "42"
        assert entry["watcher_user_id"] == "7"
        assert entry["watcher_thread_id"] == "99"
        assert entry["watcher_message_id"] == "1001"
        assert entry["watcher_interval"] == 5
        assert entry["session_key"] == _CHAT["session_key"]
        assert entry["parent_session_id"] == "sess-parent"

        restarted = _recover(sid)
        session = restarted.get(sid)
        assert session.notify_on_complete is True
        assert session.watcher_platform == "telegram"
        assert restarted.pending_watchers == [_watcher(sid)]
    finally:
        hold.release()


def test_yield_without_async_delivery_stays_silent_after_recovery(tmp_path):
    """Clearing notify after adopt must be the checkpoint a restart reads."""
    hold = _Hold(tmp_path)
    try:
        out = _yield(hold, async_delivery=False)
        hold.session_id = out["session_id"]
        sid = hold.session_id
        live = process_registry.get(sid)
        assert live.notify_on_complete is False
        assert live.watcher_platform == ""
        assert live.watcher_interval == 0

        entry = _entry(sid)
        assert entry["notify_on_complete"] is False
        assert entry["watcher_platform"] == ""
        assert entry["watcher_interval"] == 0

        restarted = _recover(sid)
        session = restarted.get(sid)
        assert session.notify_on_complete is False
        assert session.watcher_platform == ""
        assert restarted.pending_watchers == []
    finally:
        hold.release()
