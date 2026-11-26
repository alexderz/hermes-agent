"""Flagged prompt.submit refuses a user-closed physical row and stores the canonical target.

The flag is optional. Absent, the stored session id is the one the caller passed.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from tests.fixtures.storage_seed import seed_session


async def _answer(_event):
    return "ok"


async def _authority(tmp_path, monkeypatch):
    from gateway.config import GatewayConfig
    from gateway.session import SessionStore
    from gateway.session_authority import initialize_session_authority

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    store = SessionStore(tmp_path / "sessions", GatewayConfig())
    runner = SimpleNamespace(
        _session_db=store.persistence, session_store=store, _draining=False,
        _handle_message=_answer, _adapter_for_source=lambda source: None)
    authority = await initialize_session_authority(runner, profile_id="p", instance_id="owner")
    # The admission is the claim. Starting the turn drain imports the worker stack, which
    # stats the checkout. Hold the drain so the test reads the committed row only.
    def _hold(ref):
        authority.sessions[ref.session_id].rescan = True
    authority._schedule = _hold
    return authority


def _mount(authority, session_id, subject):
    from gateway.config import Platform
    from gateway.session import SessionSource
    from gateway.session_authority import LiveSession

    authority.sessions[session_id] = LiveSession(
        SessionSource(platform=Platform.LOCAL, chat_id=session_id, user_id=subject), session_id)


def _seed_local(authority, session_id, subject, *, parent=None, end_reason=None):
    fields = {"chat_id": "local-owner", "user_id": subject}
    if parent is not None:
        fields["parent_session_id"] = parent
    seed_session(authority.persistence, session_id, "local", end_reason=end_reason, **fields)


async def _submit(connection, session_id, request_id, *, flag=None, text="wake"):
    params = {"session_id": session_id, "submission_id": request_id, "text": text}
    if flag is not None:
        params["unless_closed_by_user"] = flag
    return await connection.dispatch({"id": 1, "method": "prompt.submit", "params": params})


def _rows(authority, session_id):
    return list(authority.persistence.admissions.list(session_id=session_id, pending_only=False))


async def _finish(authority, session_id):
    task = authority.sessions[session_id].task
    if task is not None:
        await task


@pytest.mark.asyncio
async def test_flagged_user_close_inserts_no_row_and_unflagged_stores_the_caller(tmp_path, monkeypatch):
    from gateway.session_controls import AuthorityConnection

    authority = await _authority(tmp_path, monkeypatch)
    connection = AuthorityConnection(authority, object(), {"user_id": "owner"})
    subject = connection.actor.subject
    _seed_local(authority, "local-owner", subject, end_reason="compression")
    _seed_local(authority, "tip-1", subject, parent="local-owner", end_reason="new_session")
    _mount(authority, "local-owner", subject)
    _mount(authority, "tip-1", subject)
    connection.subscriptions["local-owner"] = "sub"
    connection.subscriptions["tip-1"] = "sub"
    try:
        flagged = await _submit(connection, "tip-1", "wake-closed", flag=True)
        assert flagged["error"]["message"] == "closed-by-user", flagged
        assert flagged["error"]["message"] != "revision_conflict"
        detail = flagged["error"]["data"].get("detail") or ""
        assert "logical_owner=local-owner" in detail
        assert "physical=tip-1" in detail
        assert "runtime_revision=" in detail
        assert _rows(authority, "local-owner") == []
        assert _rows(authority, "tip-1") == []

        plain = await _submit(connection, "tip-1", "wake-plain")
        assert plain["result"]["status"] == "queued", plain
        await _finish(authority, "tip-1")
        stored = _rows(authority, "tip-1")
        assert len(stored) == 1
        assert stored[0].target_session_id == "tip-1"
        assert _rows(authority, "local-owner") == []
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_flagged_open_tip_stores_the_canonical_owner_and_replays_before_a_later_close(tmp_path, monkeypatch):
    from gateway.session_controls import AuthorityConnection

    authority = await _authority(tmp_path, monkeypatch)
    connection = AuthorityConnection(authority, object(), {"user_id": "owner"})
    subject = connection.actor.subject
    _seed_local(authority, "local-owner", subject, end_reason="compression")
    _seed_local(authority, "tip-1", subject, parent="local-owner")
    _mount(authority, "local-owner", subject)
    _mount(authority, "tip-1", subject)
    connection.subscriptions["tip-1"] = "tip-sub"
    try:
        opened = await _submit(connection, "tip-1", "wake-open", flag=True, text="digest")
        assert opened["result"]["status"] == "queued", opened
        assert opened["error"]["message"] != "revision_conflict" if "error" in opened else True
        await _finish(authority, "local-owner")
        stored = _rows(authority, "local-owner")
        assert len(stored) == 1
        assert stored[0].target_session_id == "local-owner"
        assert stored[0].request_id == "wake-open"
        admission_id = stored[0].admission_id

        receipt = await connection.dispatch({
            "id": 2, "method": "prompt.receipt",
            "params": {"session_id": "local-owner", "admission_id": admission_id}})
        assert receipt["result"]["admission_id"] == admission_id, receipt
        assert receipt["result"]["ref"]["session_id"] == "local-owner"

        authority.persistence.sessions.end("tip-1", "new_session")
        replay = await _submit(connection, "tip-1", "wake-open", flag=True, text="digest")
        assert replay["result"]["admission_id"] == admission_id, replay
        assert len(_rows(authority, "local-owner")) == 1
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_session_outside_the_lineage_is_owner_unreachable(tmp_path, monkeypatch):
    from gateway.session_controls import AuthorityConnection

    authority = await _authority(tmp_path, monkeypatch)
    connection = AuthorityConnection(authority, object(), {"user_id": "owner"})
    subject = connection.actor.subject
    _seed_local(authority, "local-owner", subject)
    _seed_local(authority, "stranger", subject)
    _mount(authority, "local-owner", subject)
    _mount(authority, "stranger", subject)
    connection.subscriptions["stranger"] = "sub"
    try:
        refused = await _submit(connection, "stranger", "wake-other", flag=True)
        assert refused["error"]["message"] == "owner_unreachable", refused
        assert refused["error"]["message"] != "revision_conflict"
        assert _rows(authority, "local-owner") == []
        assert _rows(authority, "stranger") == []
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_memory_close_refuses_without_reading_a_durable_end(tmp_path, monkeypatch):
    from gateway.session_controls import AuthorityConnection

    authority = await _authority(tmp_path, monkeypatch)
    connection = AuthorityConnection(authority, object(), {"user_id": "owner"})
    subject = connection.actor.subject
    _seed_local(authority, "local-owner", subject)
    _mount(authority, "local-owner", subject)
    connection.subscriptions["local-owner"] = "sub"
    authority.pending_closes["local-owner"] = SimpleNamespace(reason="cli_close")
    try:
        refused = await _submit(connection, "local-owner", "wake-memory", flag=True)
        assert refused["error"]["message"] == "closed-by-user", refused
        assert "memory=1" in (refused["error"]["data"].get("detail") or "")
        assert _rows(authority, "local-owner") == []
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_non_bool_flag_is_invalid_and_orphan_pending_close_still_admits(tmp_path, monkeypatch):
    from gateway.session_controls import AuthorityConnection

    authority = await _authority(tmp_path, monkeypatch)
    connection = AuthorityConnection(authority, object(), {"user_id": "owner"})
    subject = connection.actor.subject
    _seed_local(authority, "local-owner", subject)
    _mount(authority, "local-owner", subject)
    connection.subscriptions["local-owner"] = "sub"
    authority.pending_closes["local-owner"] = SimpleNamespace(reason="ws_orphan_reap")
    try:
        bad = await _submit(connection, "local-owner", "wake-bad", flag="yes")
        assert bad["error"]["message"] == "invalid_params", bad
        assert _rows(authority, "local-owner") == []

        opened = await _submit(connection, "local-owner", "wake-orphan", flag=True)
        assert opened["result"]["status"] == "queued", opened
        await _finish(authority, "local-owner")
        assert len(_rows(authority, "local-owner")) == 1
    finally:
        await connection.close()
