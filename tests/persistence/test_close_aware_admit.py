"""A flagged admit refuses a user-closed physical row inside the admit write.

The check runs after an exact replay returns and before INSERT. An unflagged
admit does not consult it. These are temp-database checks, not a live certification.
"""
import json

import pytest

from persistence.core.errors import AuthorityRefusal
from tests.fixtures.storage_seed import seed_session
from tests.gateway.fixtures.storage_handles import close_storage_handles, storage_handle

_USER_CLOSES = ("cli_close", "new_session", "resumed_other", "branched", "session_reset",
                "tui_shutdown", "ws_disconnect", "idle_timeout", "lru_evict")
_RECOVERABLE = ("agent_close", "ws_orphan_reap", "superseded_by_resume", "startup_orphan_reap")


def _epoch(db):
    return db.runtime.begin_epoch(instance_id="epoch-close")


def _write(db, fn):
    db.admissions._store.holder()._execute_write(fn)


def _admit(db, session_id, request_id, text="wake", *, close=None, principal="principal", epoch=None):
    kwargs = {}
    if close is not None:
        from persistence.authority.admissions import CloseAwareAdmit
        kwargs["close_aware"] = CloseAwareAdmit(logical_owner=close)
    return db.admissions.admit(
        epoch=epoch if epoch is not None else _epoch(db), principal_id=principal, session_id=session_id,
        request_id=request_id, payload={"text": text}, **kwargs)


def _found(db, session_id, request_id, principal="principal"):
    return db.admissions.find(principal_id=principal, session_id=session_id, request_id=request_id)


def test_user_close_inserts_no_row_and_names_the_physical_revision(tmp_path):
    db = storage_handle(tmp_path)
    seed_session(db, "owner", "local", end_reason="cli_close")
    physical = db.sessions.get("owner")
    with pytest.raises(AuthorityRefusal) as caught:
        _admit(db, "owner", "req-close", close="owner")
    refusal = caught.value
    assert refusal.reason == "closed-by-user"
    assert "logical_owner=owner" in (refusal.detail or "")
    assert "physical=owner" in (refusal.detail or "")
    assert f"runtime_revision={physical.runtime_revision}" in (refusal.detail or "")
    assert _found(db, "owner", "req-close") is None


@pytest.mark.parametrize("reason", _USER_CLOSES)
def test_stamped_user_close_reasons_refuse_a_new_admit(tmp_path, reason):
    db = storage_handle(tmp_path)
    seed_session(db, "owner", "local", end_reason=reason)
    with pytest.raises(AuthorityRefusal) as caught:
        _admit(db, "owner", f"req-{reason}", close="owner")
    assert caught.value.reason == "closed-by-user"
    assert _found(db, "owner", f"req-{reason}") is None


@pytest.mark.parametrize("reason", _RECOVERABLE)
def test_recoverable_end_reasons_still_admit(tmp_path, reason):
    db = storage_handle(tmp_path)
    seed_session(db, "owner", "local", end_reason=reason)
    row, created = _admit(db, "owner", f"req-{reason}", close="owner")
    assert created is True
    assert row.target_session_id == "owner"


def test_open_row_and_detach_without_end_reason_admit(tmp_path):
    db = storage_handle(tmp_path)
    seed_session(db, "owner", "local")
    row, created = _admit(db, "owner", "req-open", close="owner")
    assert created is True
    assert row.admission_id
    assert db.sessions.get("owner").ended_at is None


def test_ended_row_with_no_end_reason_is_a_user_close(tmp_path):
    db = storage_handle(tmp_path)
    seed_session(db, "owner", "local", end_reason="cli_close")

    def clear_reason(conn):
        conn.execute("UPDATE sessions SET end_reason=NULL WHERE id=?", ("owner",))

    _write(db, clear_reason)
    with pytest.raises(AuthorityRefusal) as caught:
        _admit(db, "owner", "req-null-reason", close="owner")
    assert caught.value.reason == "closed-by-user"
    assert _found(db, "owner", "req-null-reason") is None


def test_exact_replay_returns_before_the_close_gate(tmp_path):
    db = storage_handle(tmp_path)
    seed_session(db, "owner", "local")
    epoch = _epoch(db)
    first, created = _admit(db, "owner", "req-replay", text="same", epoch=epoch)
    assert created is True
    db.sessions.end("owner", "new_session")
    replay, again = _admit(db, "owner", "req-replay", text="same", close="owner", epoch=epoch)
    assert again is False
    assert replay.admission_id == first.admission_id
    assert _found(db, "owner", "req-replay").admission_id == first.admission_id


def test_digest_mismatch_is_conflict_and_does_not_mint(tmp_path):
    db = storage_handle(tmp_path)
    seed_session(db, "owner", "local")
    epoch = _epoch(db)
    first, _created = _admit(db, "owner", "req-digest", text="pinned", epoch=epoch)
    with pytest.raises(AuthorityRefusal) as caught:
        _admit(db, "owner", "req-digest", text="other", close="owner", epoch=epoch)
    assert caught.value.reason == "admission_conflict"
    assert _found(db, "owner", "req-digest").admission_id == first.admission_id


def test_unflagged_admit_stores_a_row_on_a_user_closed_session(tmp_path):
    db = storage_handle(tmp_path)
    seed_session(db, "owner", "local", end_reason="cli_close")
    row, created = _admit(db, "owner", "req-unflagged", close=None)
    assert created is True
    assert row.target_session_id == "owner"


def test_receipt_tip_closed_by_new_refuses_while_root_stays_open(tmp_path):
    db = storage_handle(tmp_path)
    seed_session(db, "owner", "local")
    seed_session(db, "tip", "local", end_reason="new_session")
    receipt = json.dumps({"entry": {"session_id": "tip"}, "session_id": "owner"})

    def write(conn):
        conn.execute(
            "INSERT INTO state_meta(key, value) VALUES(?, ?)",
            ("gateway.local_policy.v1:owner", receipt))

    _write(db, write)
    root = db.sessions.get("owner")
    tip = db.sessions.get("tip")
    assert root.ended_at is None
    with pytest.raises(AuthorityRefusal) as caught:
        _admit(db, "owner", "req-tip", close="owner")
    assert caught.value.reason == "closed-by-user"
    assert "physical=tip" in (caught.value.detail or "")
    assert f"runtime_revision={tip.runtime_revision}" in (caught.value.detail or "")
    assert _found(db, "owner", "req-tip") is None


def test_live_compression_tip_is_not_refused_because_the_root_ended_compression(tmp_path):
    db = storage_handle(tmp_path)
    seed_session(db, "owner", "local", end_reason="compression")
    seed_session(db, "tip", "local", parent_session_id="owner")
    row, created = _admit(db, "owner", "req-live-tip", close="owner")
    assert created is True
    assert row.target_session_id == "owner"
