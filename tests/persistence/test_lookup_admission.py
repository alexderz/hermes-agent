"""Owner-side request lookup is a read with four outcomes.

It is not find (one exact target, no outcome) and it does not write the id back.
Temp-database checks, not a live certification.
"""
import pytest

from persistence.authority.vocabulary import admission_fingerprint
from tests.fixtures.storage_seed import seed_session
from tests.gateway.fixtures.storage_handles import storage_handle


def _epoch(db):
    return db.runtime.begin_epoch(instance_id="epoch-lookup")


def _admit(db, session_id, request_id, text="wake", *, principal="principal", epoch=None):
    return db.admissions.admit(
        epoch=epoch if epoch is not None else _epoch(db), principal_id=principal, session_id=session_id,
        request_id=request_id, payload={"text": text})


def _digest(session_id, text="wake"):
    return admission_fingerprint(
        canonical_target=session_id, payload={"input": {"text": text}, "intent": "queue"})


def _lookup(db, request_id, targets, digest=None, *, principal="principal"):
    return db.admissions.lookup_admission_by_request(
        principal_id=principal, request_id=request_id, target_ids=targets, payload_digest=digest)


def test_found_returns_the_stored_target_and_digest_without_writing(tmp_path):
    db = storage_handle(tmp_path)
    seed_session(db, "owner", "local")
    epoch = _epoch(db)
    row, created = _admit(db, "owner", "req-1", epoch=epoch)
    assert created is True
    before = db.admissions.list(session_id="owner", pending_only=False)
    looked = _lookup(db, "req-1", ("owner",))
    assert looked.outcome == "found"
    assert looked.admission_id == row.admission_id
    assert looked.target_session_id == "owner"
    assert looked.payload_digest == _digest("owner")
    assert not hasattr(db.admissions.find(principal_id="principal", session_id="owner", request_id="req-1"), "payload_digest")
    after = db.admissions.list(session_id="owner", pending_only=False)
    assert [item.admission_id for item in after] == [item.admission_id for item in before]


def test_omitted_digest_still_finds_and_a_mismatch_is_conflict(tmp_path):
    db = storage_handle(tmp_path)
    seed_session(db, "owner", "local")
    epoch = _epoch(db)
    row, _created = _admit(db, "owner", "req-1", text="pinned", epoch=epoch)
    plain = _lookup(db, "req-1", ("owner",))
    assert plain.outcome == "found"
    assert plain.admission_id == row.admission_id
    mismatch = _lookup(db, "req-1", ("owner",), digest="0" * 64)
    assert mismatch.outcome == "conflict"
    assert mismatch.admission_id is None
    assert _lookup(db, "req-1", ("owner",)).outcome == "found"


def test_missing_request_is_proven_not_found_and_empty_targets_are_unavailable(tmp_path):
    db = storage_handle(tmp_path)
    seed_session(db, "owner", "local")
    epoch = _epoch(db)
    _admit(db, "owner", "req-1", epoch=epoch)
    missing = _lookup(db, "req-other", ("owner",))
    assert missing.outcome == "proven_not_found"
    assert missing.admission_id is None
    assert _lookup(db, "req-1", ()).outcome == "unavailable"
    assert _lookup(db, "req-1", ("owner",), principal="other").outcome == "proven_not_found"


def test_two_targets_for_one_request_are_conflict(tmp_path):
    db = storage_handle(tmp_path)
    seed_session(db, "owner", "local")
    seed_session(db, "tip", "local", parent_session_id="owner")
    epoch = _epoch(db)
    _admit(db, "owner", "req-1", epoch=epoch)
    _admit(db, "tip", "req-1", epoch=epoch)
    looked = _lookup(db, "req-1", ("owner", "tip"), digest=_digest("owner"))
    assert looked.outcome == "conflict"
    assert looked.admission_id is None
    assert len(db.admissions.list(session_id="owner", pending_only=False)) == 1
    assert len(db.admissions.list(session_id="tip", pending_only=False)) == 1


def test_terminal_row_still_counts_as_found(tmp_path):
    db = storage_handle(tmp_path)
    seed_session(db, "owner", "local")
    epoch = _epoch(db)
    row, _created = _admit(db, "owner", "req-1", epoch=epoch)

    def _end(conn):
        conn.execute(
            "UPDATE session_admissions SET status='terminal', outcome='completed' WHERE admission_id=?",
            (row.admission_id,))

    db.admissions._store.holder()._execute_write(_end)
    looked = _lookup(db, "req-1", ("owner",))
    assert looked.outcome == "found"
    assert looked.admission_id == row.admission_id


@pytest.mark.parametrize("targets", ["owner", None, (1,)])
def test_unusable_target_ids_are_unavailable(tmp_path, targets):
    db = storage_handle(tmp_path)
    assert _lookup(db, "req-1", targets).outcome == "unavailable"
