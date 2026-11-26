"""prompt.lookup_admission reads across the canonical lineage and does not submit."""
from types import SimpleNamespace

import pytest

from persistence.authority.vocabulary import admission_fingerprint
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


async def _lookup(connection, session_id, request_id, *, digest=None, extra=None):
    params = {"session_id": session_id, "request_id": request_id}
    if digest is not None:
        params["payload_digest"] = digest
    if extra:
        params.update(extra)
    return await connection.dispatch({"id": 2, "method": "prompt.lookup_admission", "params": params})


def _frame_digest(target, text="wake"):
    return admission_fingerprint(
        canonical_target=target, payload={"input": {"text": text}, "intent": "queue"})


@pytest.mark.asyncio
async def test_lookup_of_a_tip_finds_the_canonical_admission_and_does_not_submit(tmp_path, monkeypatch):
    from gateway.session_controls import AuthorityConnection

    authority = await _authority(tmp_path, monkeypatch)
    connection = AuthorityConnection(authority, object(), {"user_id": "owner"})
    subject = connection.actor.subject
    _seed_local(authority, "local-owner", subject, end_reason="compression")
    _seed_local(authority, "tip-1", subject, parent="local-owner")
    _mount(authority, "local-owner", subject)
    _mount(authority, "tip-1", subject)
    connection.subscriptions["tip-1"] = "sub"
    try:
        opened = await _submit(connection, "tip-1", "wake-open", flag=True, text="digest")
        assert opened["result"]["status"] == "queued", opened
        stored = list(authority.persistence.admissions.list(session_id="local-owner", pending_only=False))
        assert len(stored) == 1
        looked = await _lookup(connection, "tip-1", "wake-open")
        assert looked["result"]["outcome"] == "found", looked
        assert looked["result"]["admission_id"] == stored[0].admission_id
        assert looked["result"]["target_session_id"] == "local-owner"
        assert looked["result"]["payload_digest"] == _frame_digest("local-owner", "digest")
        assert looked["result"]["canonical_session_id"] == "local-owner"
        again = list(authority.persistence.admissions.list(session_id="local-owner", pending_only=False))
        assert [row.admission_id for row in again] == [stored[0].admission_id]
        assert list(authority.persistence.admissions.list(session_id="tip-1", pending_only=False)) == []
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_lookup_outcomes_and_a_foreign_session(tmp_path, monkeypatch):
    from gateway.session_controls import AuthorityConnection

    authority = await _authority(tmp_path, monkeypatch)
    connection = AuthorityConnection(authority, object(), {"user_id": "owner"})
    subject = connection.actor.subject
    _seed_local(authority, "local-owner", subject)
    _seed_local(authority, "stranger", subject)
    _mount(authority, "local-owner", subject)
    _mount(authority, "stranger", subject)
    connection.subscriptions["local-owner"] = "sub"
    try:
        opened = await _submit(connection, "local-owner", "wake-1", text="body")
        assert opened["result"]["status"] == "queued", opened
        missing = await _lookup(connection, "local-owner", "wake-other")
        assert missing["result"]["outcome"] == "proven_not_found", missing
        assert missing["result"]["canonical_session_id"] == "local-owner"
        clash = await _lookup(connection, "local-owner", "wake-1", digest="f" * 64)
        assert clash["result"]["outcome"] == "conflict", clash
        assert clash["result"]["admission_id"] is None
        extra = await _lookup(connection, "local-owner", "wake-1", extra={"principal": "other"})
        assert extra["error"]["message"] == "invalid_params", extra
        outside = await _lookup(connection, "stranger", "wake-1")
        assert outside["error"]["message"] == "owner_unreachable", outside
        assert outside["error"]["message"] != "revision_conflict"
    finally:
        await connection.close()
