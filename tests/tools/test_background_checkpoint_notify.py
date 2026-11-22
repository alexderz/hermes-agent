"""A background completion contract must be what a restarted host recovers.

The spawn checkpoint is written before notify, watch patterns, heartbeat, and
chat routing are set, and adoption stamps routing after its own checkpoint.
Recovery in a new registry reads only the file, so that file has to hold the
final contract.
"""

from __future__ import annotations

import json
import os
import shlex
import signal
import threading

import pytest

from agent.interrupt_control import InterruptControlMixin
from gateway.session_context import clear_session_vars, set_session_vars
from tests.waiting import wait_until
from tools.process_registry import ProcessRegistry, _checkpoint_path, process_registry
from tools.terminal_tool import terminal_tool

pytestmark = [
    pytest.mark.platforms("posix"),
    # The registry SIGTERMs the shell first, so a child can be reparented
    # before the descendant snapshot is signalled. That pid is no longer on
    # the test's parent chain, and the live-system guard would refuse the reap.
    pytest.mark.live_system_guard_bypass,
]

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


def _stop(session_id: str | None) -> None:
    if session_id:
        process_registry.kill_process(session_id)


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


def _yield(tmp_path, *, async_delivery: bool) -> dict:
    """Real foreground terminal entry, yielded once the shell has started."""
    pidfile = tmp_path / "pid"
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
                    f"echo $$ > {shlex.quote(str(pidfile))}; exec sleep 30",
                    task_id="t-yield",
                    timeout=60,
                    workdir=str(tmp_path),
                )
            )
        finally:
            clear_session_vars(tokens)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    try:
        wait_until(
            lambda: pidfile.is_file() and pidfile.read_text().strip().isdigit(),
            timeout=20,
            what="foreground command started",
        )
        assert agent.redirect("status?") is True
        thread.join(timeout=20)
        assert not thread.is_alive(), "foreground command did not yield"
        return box["result"]
    finally:
        if thread.is_alive() and pidfile.is_file():
            text = pidfile.read_text().strip()
            if text.isdigit():
                os.kill(int(text), signal.SIGTERM)


def test_notified_background_recovers_route_watcher_and_heartbeat(tmp_path):
    """notify=true, its route, and the pending watcher survive a new registry."""
    tokens = _bind()
    sid = None
    try:
        out = json.loads(
            terminal_tool(
                "exec sleep 30",
                background=True,
                notify_on_complete=True,
                heartbeat=60,
                task_id="t-notify",
                workdir=str(tmp_path),
            )
        )
        sid = out["session_id"]
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
        _stop(sid)


def test_watch_patterns_and_route_survive_checkpoint_recovery(tmp_path):
    """Watch-only spawns persist patterns and chat routing, and arm no watcher."""
    tokens = _bind()
    sid = None
    try:
        out = json.loads(
            terminal_tool(
                "exec sleep 30",
                background=True,
                watch_patterns=["BUILD OK"],
                task_id="t-watch",
                workdir=str(tmp_path),
            )
        )
        sid = out["session_id"]
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
        _stop(sid)


def test_silent_background_recovers_without_a_completion_watcher(tmp_path):
    """A bound chat does not turn a silent background process into a watcher."""
    tokens = _bind()
    sid = None
    try:
        out = json.loads(
            terminal_tool(
                "exec sleep 30",
                background=True,
                task_id="t-silent",
                workdir=str(tmp_path),
            )
        )
        sid = out["session_id"]
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
        _stop(sid)


def test_yielded_foreground_recovers_its_gateway_route(tmp_path):
    """Adoption stamps routing after its checkpoint; recovery must still see it."""
    sid = None
    try:
        out = _yield(tmp_path, async_delivery=True)
        sid = out["session_id"]
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
        _stop(sid)


def test_yield_without_async_delivery_stays_silent_after_recovery(tmp_path):
    """Clearing notify after adopt must be the checkpoint a restart reads."""
    sid = None
    try:
        out = _yield(tmp_path, async_delivery=False)
        sid = out["session_id"]
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
        _stop(sid)
