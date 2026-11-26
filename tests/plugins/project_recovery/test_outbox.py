"""Outbox files: one key, one record, no replacement while the receipt is null."""

from __future__ import annotations

import json
from pathlib import Path

from plugins.project_recovery.deliver import scan_owner
from plugins.project_recovery.mapping import Err, Ok
from plugins.project_recovery.outbox import (
    adopt_receipt,
    load_outbox,
    outbox_path,
    remember_message,
    write_intent,
)


def test_module_is_loaded_from_this_worktree():
    from plugins.project_recovery import outbox

    root = Path(__file__).resolve().parents[3]
    assert Path(outbox.__file__).resolve().is_relative_to(root / "plugins" / "project_recovery")


def test_unreceipted_intent_is_not_replaced(tmp_path):
    state = tmp_path / "state"
    first = write_intent(
        state, project="proj-example", owner="local-owner", scan=7,
        intent_at=100.5, episodes=["E-1042-1"],
    )
    assert isinstance(first, Ok)
    path = outbox_path(state, "proj-example", "local-owner")
    before = path.read_bytes()
    second = write_intent(
        state, project="proj-example", owner="local-owner", scan=8,
        intent_at=200.0, episodes=["E-2000-1"],
    )
    assert isinstance(second, Err)
    assert second.error == "unreceipted"
    assert path.read_bytes() == before
    stored = json.loads(before)
    assert stored["receipt"] is None
    assert stored["message"] is None
    assert stored["episodes"] == ["E-1042-1"]
    assert stored["key"] == "recovery:proj-example:local-owner"
    assert stored["label"] == "recovery-proj-example"


def test_adoption_writes_the_same_record_and_then_a_new_intent_may_replace(tmp_path):
    state = tmp_path / "state"
    write_intent(
        state, project="proj-example", owner="local-owner", scan=7,
        intent_at=100.0, episodes=["E-1042-1", "E-1040-2"],
    )
    remembered = remember_message(state, "proj-example", "local-owner", "m-1001")
    assert isinstance(remembered, Ok)
    assert remembered.value["receipt"] is None
    adopted = adopt_receipt(state, "proj-example", "local-owner", "adm-1")
    assert isinstance(adopted, Ok)
    assert adopted.value["receipt"] == "adm-1"
    assert adopted.value["message"] == "m-1001"
    assert adopted.value["episodes"] == ["E-1042-1", "E-1040-2"]
    assert load_outbox(state, "proj-example", "local-owner")["receipt"] == "adm-1"
    replaced = write_intent(
        state, project="proj-example", owner="local-owner", scan=9,
        intent_at=300.0, episodes=["E-3000-1"],
    )
    assert isinstance(replaced, Ok)
    assert replaced.value["receipt"] is None
    assert replaced.value["episodes"] == ["E-3000-1"]


def test_two_owners_are_two_files(tmp_path):
    state = tmp_path / "state"
    write_intent(
        state, project="proj-example", owner="local-owner", scan=1,
        intent_at=1.0, episodes=["E-1-1"],
    )
    write_intent(
        state, project="proj-example", owner="local-other", scan=1,
        intent_at=1.0, episodes=["E-1-2"],
    )
    first = outbox_path(state, "proj-example", "local-owner")
    second = outbox_path(state, "proj-example", "local-other")
    assert first.is_file() and second.is_file()
    assert first != second
    assert json.loads(first.read_text(encoding="utf-8-sig"))["episodes"] == ["E-1-1"]
    assert json.loads(second.read_text(encoding="utf-8-sig"))["owner"] == "local-other"


def _plant(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _wake(episode_id="E-1042-1"):
    return {
        "id": episode_id,
        "class": "result_unprocessed",
        "subject": {"kind": "handle", "id": "h-0007"},
        "workstream": "ws-alpha",
        "evidence": {"liveness": "ended", "consumed": False},
        "delivery": {
            "state": "undelivered", "message": None, "admission": None,
            "carried_in_turn": None, "settled_scan": None,
        },
    }


def _scan_planted(state, send):
    return scan_owner(
        state, project="proj-example", owner="local-owner", scan=8, intent_at=200.0,
        episodes=[_wake()], observation={
            "activity": "idle", "runtime_revision": 4, "binding_revision": 2,
            "receipts": {}, "offered_turn": None,
        }, send=send,
    )


def test_corrupt_outbox_bytes_are_not_replaced_or_sent(tmp_path):
    state = tmp_path / "state"
    path = outbox_path(state, "proj-example", "local-owner")
    raw = b"{not-json"
    _plant(path, raw)
    written = write_intent(
        state, project="proj-example", owner="local-owner", scan=8,
        intent_at=200.0, episodes=["E-2000-1"],
    )
    assert isinstance(written, Err)
    assert written.error == "invalid"
    assert path.read_bytes() == raw
    calls = []
    result = _scan_planted(state, lambda *args, **kwargs: calls.append(kwargs))
    assert calls == []
    assert result["sent"] is False
    assert result["episodes"][0]["delivery"]["state"] == "undelivered"
    assert result["episodes"][0]["delivery"]["admission"] is None
    assert path.read_bytes() == raw
    assert isinstance(remember_message(state, "proj-example", "local-owner", "m-1001"), Err)
    assert isinstance(adopt_receipt(state, "proj-example", "local-owner", "adm-1"), Err)
    assert path.read_bytes() == raw


def test_malformed_outbox_record_is_not_sent(tmp_path):
    state = tmp_path / "state"
    path = outbox_path(state, "proj-example", "local-owner")
    missing_key = (json.dumps({"receipt": None, "episodes": ["E-1042-1"]}) + "\n").encode()
    _plant(path, missing_key)
    written = write_intent(
        state, project="proj-example", owner="local-owner", scan=8,
        intent_at=200.0, episodes=["E-2000-1"],
    )
    assert isinstance(written, Err)
    assert written.error == "invalid"
    assert path.read_bytes() == missing_key
    calls = []
    result = _scan_planted(state, lambda *args, **kwargs: calls.append(1))
    assert calls == []
    assert result["sent"] is False
    assert result["episodes"][0]["delivery"]["state"] == "undelivered"
    assert path.read_bytes() == missing_key

    bad_receipt = (json.dumps({
        "key": "recovery:proj-example:local-owner", "receipt": 3, "episodes": ["E-1042-1"],
    }) + "\n").encode()
    _plant(path, bad_receipt)
    replaced = write_intent(
        state, project="proj-example", owner="local-owner", scan=9,
        intent_at=300.0, episodes=["E-3000-1"],
    )
    assert isinstance(replaced, Err)
    assert replaced.error == "invalid"
    assert path.read_bytes() == bad_receipt

    bad_episodes = (json.dumps({
        "key": "recovery:proj-example:local-owner", "receipt": None, "episodes": "E-1042-1",
    }) + "\n").encode()
    _plant(path, bad_episodes)
    calls.clear()
    scanned = _scan_planted(state, lambda *args, **kwargs: calls.append(1))
    assert calls == []
    assert scanned["sent"] is False
    assert scanned["episodes"][0]["delivery"]["state"] == "undelivered"
    assert path.read_bytes() == bad_episodes


def test_single_non_utf8_outbox_byte_is_unreadable_and_not_sent(tmp_path):
    state = tmp_path / "state"
    path = outbox_path(state, "proj-example", "local-owner")
    raw = bytes([255])
    _plant(path, raw)
    written = write_intent(
        state, project="proj-example", owner="local-owner", scan=8,
        intent_at=200.0, episodes=["E-2000-1"],
    )
    assert isinstance(written, Err)
    assert written.error == "unreadable"
    assert path.read_bytes() == raw
    calls = []
    result = _scan_planted(state, lambda *args, **kwargs: calls.append(1))
    assert calls == []
    assert result["sent"] is False
    assert result["episodes"][0]["delivery"]["state"] == "undelivered"
    assert result["episodes"][0]["delivery"]["admission"] is None
    assert path.read_bytes() == raw
    remembered = remember_message(state, "proj-example", "local-owner", "m-1001")
    adopted = adopt_receipt(state, "proj-example", "local-owner", "adm-1")
    assert isinstance(remembered, Err) and remembered.error == "unreadable"
    assert isinstance(adopted, Err) and adopted.error == "unreadable"
    assert path.read_bytes() == raw


def test_schema_less_unreceipted_record_stays(tmp_path):
    state = tmp_path / "state"
    path = outbox_path(state, "proj-example", "local-owner")
    record = {
        "episodes": ["E-1042-1"],
        "key": "recovery:proj-example:local-owner",
        "owner": "local-owner",
        "receipt": None,
    }
    raw = (json.dumps(record, sort_keys=True) + "\n").encode()
    _plant(path, raw)
    written = write_intent(
        state, project="proj-example", owner="local-owner", scan=8,
        intent_at=200.0, episodes=["E-2000-1"],
    )
    assert isinstance(written, Err)
    assert written.error == "unreceipted"
    assert path.read_bytes() == raw
    assert load_outbox(state, "proj-example", "local-owner")["episodes"] == ["E-1042-1"]
    assert "schema" not in load_outbox(state, "proj-example", "local-owner")


def test_ids_outside_the_binding_pattern_are_refused(tmp_path):
    state = tmp_path / "state"
    refused = write_intent(
        state, project="proj/example", owner="local-owner", scan=1,
        intent_at=1.0, episodes=["E-1-1"],
    )
    assert isinstance(refused, Err)
    assert refused.error == "binding_invalid"
    assert list(state.glob("outbox/*")) == []
