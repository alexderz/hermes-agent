"""A detached idle session with a queued prompt survives the WS orphan reaper until the queue drains.

The turn that ended drains its queue at the idle boundary, after post-turn housekeeping. A sender that
submitted with ``queued: true`` and disconnected on the ack (``scripts/dashboard_dispatch.py``) has no
transport left, so reaping in that window silently dropped the prompt.
"""

from __future__ import annotations

import importlib
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture()
def server(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(home))
    with patch.dict("sys.modules", {"hermes_cli.env_loader": MagicMock(), "hermes_cli.banner": MagicMock()}):
        mod = importlib.import_module("tui_gateway.server")
        yield mod
        mod._sessions.clear()
        mod._pending_ws_reaps.clear()


class _Timer:
    created: list = []

    def __init__(self, delay, callback):
        self.delay, self.callback = delay, callback
        _Timer.created.append(self)

    def start(self):
        pass

    def cancel(self):
        pass


@pytest.fixture()
def detached(server, monkeypatch):
    _Timer.created = []
    monkeypatch.setattr(server.threading, "Timer", _Timer)
    monkeypatch.setattr(server, "_WS_ORPHAN_REAP_GRACE_S", 20)
    monkeypatch.setattr(server, "_session_has_active_delegations", lambda *a: False)
    monkeypatch.setattr(server, "_session_owns_live_wakeup_schedule", lambda *a: False)
    popped = []
    monkeypatch.setattr(server, "_teardown_popped_session", lambda s, **kw: popped.append(s))
    sid = "sid-detached-queue"
    session = {
        "session_key": "queued-session",
        "transport": server._detached_ws_transport,
        "running": False,
        "history_lock": threading.Lock(),
        "last_active": 0.0,
        "created_at": 0.0,
    }
    server._sessions[sid] = session
    return sid, session, popped


def _fire(server, sid):
    if sid not in server._pending_ws_reaps:
        server._schedule_ws_orphan_reap(sid)
    _Timer.created[-1].callback()


def test_queued_prompt_pins_the_detached_idle_session(server, detached):
    sid, session, popped = detached
    session["queued_prompt"] = {"text": "mail from Home", "transport": None}

    _fire(server, sid)

    assert server._sessions.get(sid) is session and not popped
    assert server._pending_ws_reaps[sid] is _Timer.created[-1]  # re-armed, re-checked each grace


def test_session_is_reaped_once_the_queue_drains(server, detached):
    sid, session, popped = detached
    session["queued_prompt"] = {"text": "mail from Home", "transport": None}
    _fire(server, sid)
    session.pop("queued_prompt")  # drained: the turn ran and settled

    _fire(server, sid)

    assert sid not in server._sessions and popped == [session]


def test_a_queue_that_never_drains_is_reaped_after_the_budget(server, detached, monkeypatch):
    sid, session, popped = detached
    monkeypatch.setattr(server, "_WS_ORPHAN_QUEUED_MAX_POLLS", 3)
    session["queued_prompt"] = {"text": "stuck", "transport": None}

    for _ in range(3):
        _fire(server, sid)
        assert server._sessions.get(sid) is session
    _fire(server, sid)

    assert sid not in server._sessions and popped == [session]


def test_idle_session_without_a_queue_is_still_reaped(server, detached):
    sid, session, popped = detached

    _fire(server, sid)

    assert sid not in server._sessions and popped == [session]


def test_running_turn_resets_the_budget(server, detached):
    sid, session, _ = detached
    session["queued_prompt"] = {"text": "mail", "transport": None}
    _fire(server, sid)
    assert session["_ws_orphan_queued_polls"] == 1

    session["running"] = True  # the queue drained into a new turn (head still set by a later queuer)
    session["_last_turn_activity_at"] = None
    server._schedule_ws_orphan_reap(sid, _expected_timer=server._pending_ws_reaps.get(sid))
    _Timer.created[-1].callback()

    assert "_ws_orphan_queued_polls" not in session


def test_leftover_steer_is_queued_before_running_is_released(server, detached):
    """The turn's release requeues a steer it never consumed, so a reap in the housekeeping window spares it."""
    sid, session, popped = detached
    result = {"final_response": "done", "pending_steer": "late mail from Home"}

    with session["history_lock"]:  # what run_body's finally does, in order
        server._requeue_leftover_steer(session, result)
        session["running"] = False
    _fire(server, sid)  # reap tick during post-turn housekeeping

    assert server._sessions.get(sid) is session and not popped
    assert session["queued_prompt"]["text"] == "late mail from Home"


def test_leftover_steer_is_requeued_once(server, detached):
    _, session, _ = detached
    result = {"pending_steer": "late mail"}
    with session["history_lock"]:
        server._requeue_leftover_steer(session, result)
        server._requeue_leftover_steer(session, result)  # the post-turn follow-ups call it again
    assert session["queued_prompt"]["text"] == "late mail"
    assert not session.get("queued_prompts")


def test_lru_and_ttl_reapers_spare_a_session_with_a_queued_prompt(server, detached, monkeypatch):
    sid, session, _ = detached
    from tui_gateway import session_reaper

    monkeypatch.setattr(server, "_session_is_lru_evictable", lambda *a: True, raising=False)
    monkeypatch.setattr(session_reaper, "_session_is_lru_evictable", lambda *a: True, raising=False)
    reapable = getattr(server, "_session_is_reapable", None) or session_reaper._session_is_reapable
    assert reapable(sid, session) is True
    session["queued_prompt"] = {"text": "mail", "transport": None}
    assert reapable(sid, session) is False
