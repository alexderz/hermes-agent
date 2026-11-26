"""Owner gate, one digest per logical owner, and the delivery transitions."""

from __future__ import annotations

import json
from pathlib import Path

from plugins.project_recovery.deliver import (
    _load_holds,
    _load_lines,
    _load_stalls,
    keyed_intercom_send,
    scan_owner,
)
from plugins.project_recovery.outbox import load_outbox, outbox_path


def _episode(episode_id, kind="result_unprocessed", workstream="ws-alpha", **delivery):
    body = {
        "state": "undelivered",
        "message": None,
        "admission": None,
        "carried_in_turn": None,
        "settled_scan": None,
    }
    body.update(delivery)
    return {
        "id": episode_id,
        "class": kind,
        "subject": {"kind": "handle", "id": "h-0007"},
        "workstream": workstream,
        "evidence": {"liveness": "ended", "consumed": False},
        "delivery": body,
    }


def _obs(**overrides):
    observation = {
        "activity": "idle",
        "runtime_revision": 4,
        "binding_revision": 2,
        "receipts": {},
        "offered_turn": None,
    }
    observation.update(overrides)
    return observation


def _scan(state, episodes, observation, send, owner="local-owner", scan=7):
    return scan_owner(
        state, project="proj-example", owner=owner, scan=scan, intent_at=100.0 + scan,
        episodes=episodes, observation=observation, send=send,
    )


def test_modules_load_from_this_worktree():
    from plugins.project_recovery import deliver

    root = Path(__file__).resolve().parents[3]
    assert Path(deliver.__file__).resolve().is_relative_to(root / "plugins" / "project_recovery")


def test_idle_owner_sends_one_digest_and_accepts_only_with_an_admission(tmp_path):
    state = tmp_path / "state"
    calls = []

    def send(target, text, *, key):
        calls.append({"target": target, "text": text, "key": key})
        return {"ok": True, "message_id": "m-1001", "admission_id": "adm-1"}

    result = _scan(state, [_episode("E-1042-1"), _episode("E-1040-2", workstream="ws-beta")], _obs(), send)
    assert result["sent"] is True
    assert result["admission_id"] == "adm-1"
    assert len(calls) == 1
    assert calls[0]["key"] == "recovery:proj-example:local-owner"
    assert "E-1042-1" in calls[0]["text"] and "E-1040-2" in calls[0]["text"]
    assert "ws-alpha" in calls[0]["text"] and "ws-beta" in calls[0]["text"]
    stored = load_outbox(state, "proj-example", "local-owner")
    assert stored["receipt"] == "adm-1"
    assert stored["message"] == "m-1001"
    assert {episode["delivery"]["state"] for episode in result["episodes"]} == {"accepted"}
    assert {episode["delivery"]["admission"] for episode in result["episodes"]} == {"adm-1"}


def test_a_message_id_without_an_admission_is_not_acceptance(tmp_path):
    state = tmp_path / "state"

    def send(_target, _text, *, key):
        assert key == "recovery:proj-example:local-owner"
        return {"ok": True, "message_id": "m-1001", "receipt": "held"}

    episode = _episode("E-1042-1", state="accepted", message="m-1001", admission=None)
    result = _scan(state, [episode], _obs(), send)
    assert result["admission_id"] is None
    assert result["episodes"][0]["delivery"]["state"] == "undelivered"
    assert result["episodes"][0]["delivery"]["admission"] is None
    assert load_outbox(state, "proj-example", "local-owner")["receipt"] is None


def test_notice_only_scan_does_not_submit(tmp_path):
    state = tmp_path / "state"
    calls = []
    episode = _episode("E-9-1", kind="membership_change")
    result = _scan(state, [episode], _obs(), lambda *args, **kwargs: calls.append(args))
    assert calls == []
    assert result["sent"] is False
    assert result["episodes"][0]["delivery"]["state"] == "noticed"
    assert load_outbox(state, "proj-example", "local-owner") is None


def test_running_defers_and_the_idle_scan_sends_once(tmp_path):
    state = tmp_path / "state"
    calls = []

    def send(target, text, *, key):
        calls.append(key)
        return {"ok": True, "message_id": "m-1001", "admission_id": "adm-1"}

    episode = _episode("E-1042-1")
    held = _scan(state, [episode], _obs(activity="running"), send)
    assert held["deferred"] is True
    assert calls == []
    assert load_outbox(state, "proj-example", "local-owner") is None
    sent = _scan(state, held["episodes"], _obs(), send)
    assert sent["sent"] is True
    assert calls == ["recovery:proj-example:local-owner"]
    assert sent["episodes"][0]["delivery"]["state"] == "accepted"


def test_closed_observation_notifies_once_and_does_not_send(tmp_path):
    state = tmp_path / "state"
    calls = []

    def send(target, text, *, key):
        calls.append(key)
        return {"ok": True, "message_id": "m-1001", "admission_id": "adm-1"}

    episode = _episode("E-1042-1")
    first = _scan(state, [episode], _obs(activity="closed", runtime_revision=9), send)
    assert calls == ["recovery:proj-example:local-owner"]
    assert first["sent"] is True
    assert first["episodes"][0]["delivery"]["state"] == "accepted"
    assert not any("owner_closed" in line for line in first["notices"])
    second = _scan(state, first["episodes"], _obs(activity="closed", runtime_revision=9), send)
    assert calls == ["recovery:proj-example:local-owner"]
    assert second["notices"] == ()


def test_unreachable_keeps_the_pin_and_notifies_once(tmp_path):
    state = tmp_path / "state"
    calls = []

    def send(target, text, *, key):
        calls.append(key)
        return {"ok": False, "message_id": "m-1001", "condition": "owner_unreachable", "lookup": "unavailable"}

    first = _scan(state, [_episode("E-1042-1")], _obs(), send)
    assert calls == ["recovery:proj-example:local-owner"]
    assert first["episodes"][0]["delivery"]["state"] == "undelivered"
    stored = load_outbox(state, "proj-example", "local-owner")
    assert stored["message"] == "m-1001"
    assert stored["receipt"] is None
    assert any("owner_unreachable" in line for line in first["notices"])
    pinned = outbox_path(state, "proj-example", "local-owner").read_bytes()
    again = _scan(state, first["episodes"], _obs(activity="unreachable"), send)
    assert len(calls) == 2
    assert again["notices"] == ()
    assert again["episodes"][0]["delivery"]["state"] == "undelivered"
    assert load_outbox(state, "proj-example", "local-owner")["message"] == "m-1001"
    assert load_outbox(state, "proj-example", "local-owner")["receipt"] is None
    assert outbox_path(state, "proj-example", "local-owner").read_bytes() == pinned


def test_one_owner_two_workstreams_then_a_second_owner_does_not_replace_the_first(tmp_path):
    state = tmp_path / "state"

    def admit(message):
        def send(target, text, *, key):
            return {"ok": True, "message_id": message, "admission_id": None, "receipt": "held"}
        return send

    first = _scan(
        state,
        [_episode("E-1042-1", workstream="ws-alpha"), _episode("E-1040-2", workstream="ws-beta")],
        _obs(),
        admit("m-1001"),
    )
    assert first["sent"] is True
    pinned = outbox_path(state, "proj-example", "local-owner").read_bytes()
    second = _scan(
        state, [_episode("E-2000-1", workstream="ws-gamma")], _obs(), admit("m-2002"), owner="local-other",
    )
    assert second["sent"] is True
    assert outbox_path(state, "proj-example", "local-owner").read_bytes() == pinned
    assert load_outbox(state, "proj-example", "local-other")["message"] == "m-2002"
    assert load_outbox(state, "proj-example", "local-owner")["episodes"] == ["E-1042-1", "E-1040-2"]


def test_resume_adopts_an_admission_and_does_not_replace_the_intent(tmp_path):
    state = tmp_path / "state"

    def hold(target, text, *, key):
        return {"ok": True, "message_id": "m-1001"}

    first = _scan(state, [_episode("E-1042-1")], _obs(), hold)
    assert load_outbox(state, "proj-example", "local-owner")["receipt"] is None
    calls = []

    def adopt(target, text, *, key):
        calls.append(text)
        return {"ok": True, "message_id": "m-1001", "admission_id": "adm-kept", "stored_target": "local-owner"}

    second = _scan(state, first["episodes"], _obs(), adopt, scan=8)
    assert len(calls) == 1
    assert "E-1042-1" in calls[0]
    assert "brand-new" not in calls[0]
    stored = load_outbox(state, "proj-example", "local-owner")
    assert stored["episodes"] == ["E-1042-1"]
    assert stored["receipt"] == "adm-kept"
    assert second["episodes"][0]["delivery"]["state"] == "accepted"
    assert second["episodes"][0]["delivery"]["admission"] == "adm-kept"


def test_carried_once_then_one_no_progress_notice(tmp_path):
    state = tmp_path / "state"
    calls = []
    episode = _episode("E-0990-1", state="accepted", message="m-1001", admission="adm-1")
    carried = _scan(state, [episode], _obs(offered_turn="turn-7", offered_message="m-1001"), lambda *a, **k: calls.append(1))
    assert calls == []
    assert carried["episodes"][0]["delivery"]["state"] == "carried"
    assert carried["episodes"][0]["delivery"]["carried_in_turn"] == "turn-7"
    listed = _scan(
        state, carried["episodes"],
        _obs(offered_turn="turn-9", offered_message="m-1001"),
        lambda *a, **k: calls.append(1), scan=8,
    )
    assert calls == []
    assert listed["episodes"][0]["delivery"]["carried_in_turn"] == "turn-7"
    settled = _scan(
        state, listed["episodes"],
        _obs(receipts={"adm-1": "terminal"}),
        lambda *a, **k: calls.append(1), scan=9,
    )
    assert settled["episodes"][0]["delivery"]["state"] == "settled"
    assert any("no_progress" in line for line in settled["notices"])
    quiet = _scan(
        state, settled["episodes"],
        _obs(receipts={"adm-1": "terminal"}),
        lambda *a, **k: calls.append(1), scan=10,
    )
    assert quiet["notices"] == ()
    assert calls == []


def test_unknown_and_queued_receipts_stall_without_a_resend(tmp_path):
    state = tmp_path / "state"
    calls = []
    unknown = _episode("E-1-1", state="accepted", message="m-1", admission="adm-unknown")
    queued = _episode("E-1-2", state="accepted", message="m-2", admission="adm-queued")
    send = lambda *a, **k: calls.append(1)
    first = _scan(state, [unknown, queued], _obs(receipts={"adm-unknown": "unknown", "adm-queued": "queued"}), send)
    assert calls == []
    assert any("admission=adm-unknown" in line for line in first["notices"])
    assert not any("admission=adm-queued" in line for line in first["notices"])
    second = _scan(
        state, first["episodes"],
        _obs(receipts={"adm-unknown": "unknown", "adm-queued": "queued"}),
        send, scan=8,
    )
    assert calls == []
    assert any("admission=adm-queued" in line for line in second["notices"])
    assert not any("admission=adm-unknown" in line for line in second["notices"])
    third = _scan(
        state, second["episodes"],
        _obs(receipts={"adm-unknown": "unknown", "adm-queued": "queued"}),
        send, scan=9,
    )
    assert third["notices"] == ()
    assert calls == []


def test_a_user_close_refusal_is_not_sent_again_for_that_revision(tmp_path):
    state = tmp_path / "state"
    calls = []

    detail = "logical_owner=local-owner physical=tip-1 runtime_revision=4"

    def send(target, text, *, key):
        calls.append(key)
        return {
            "ok": False, "error": "closed-by-user", "message_id": "m-1001",
            "data": {"reason": "closed-by-user", "field": "session", "detail": detail},
        }

    first = _scan(state, [_episode("E-1042-1")], _obs(runtime_revision=4), send)
    assert len(calls) == 1
    assert first["episodes"][0]["delivery"]["state"] == "undelivered"
    assert any(
        "owner_closed" in line and "runtime_revision=4" in line and "physical=tip-1" in line
        for line in first["notices"]
    )
    second = _scan(state, first["episodes"], _obs(runtime_revision=4), send, scan=8)
    assert len(calls) == 1
    assert second["notices"] == ()


def test_cache_loss_allows_one_later_digest(tmp_path):
    state = tmp_path / "state"
    calls = []

    def send(target, text, *, key):
        calls.append(key)
        return {"ok": True, "message_id": "m-1001", "admission_id": "adm-1"}

    _scan(state, [_episode("E-1042-1")], _obs(), send)
    assert len(calls) == 1
    for child in state.iterdir():
        if child.is_file():
            child.unlink()
        elif child.is_dir():
            for nested in child.iterdir():
                nested.unlink()
            child.rmdir()
    _scan(state, [_episode("E-1042-1")], _obs(), send, scan=8)
    assert calls == ["recovery:proj-example:local-owner", "recovery:proj-example:local-owner"]
    assert load_outbox(state, "proj-example", "local-owner")["receipt"] == "adm-1"


def test_closed_preread_sends_and_holds_the_in_write_revision(tmp_path):
    state = tmp_path / "state"
    calls = []
    detail = "logical_owner=local-owner physical=tip-1 runtime_revision=4"

    def send(target, text, *, key):
        calls.append(key)
        return {
            "ok": False,
            "error": "closed-by-user",
            "message_id": "m-1001",
            "data": {"reason": "closed-by-user", "field": "session", "detail": detail},
        }

    first = _scan(state, [_episode("E-1042-1")], _obs(activity="closed", runtime_revision=9), send)
    assert calls == ["recovery:proj-example:local-owner"]
    assert first["episodes"][0]["delivery"]["state"] == "undelivered"
    assert any(
        "owner_closed" in line and "runtime_revision=4" in line and "physical=tip-1" in line
        for line in first["notices"]
    )
    assert not any("runtime_revision=9" in line for line in first["notices"])
    second = _scan(state, first["episodes"], _obs(activity="closed", runtime_revision=4), send, scan=8)
    assert len(calls) == 1
    assert second["notices"] == ()
    _scan(state, second["episodes"], _obs(activity="idle", runtime_revision=5), send, scan=9)
    assert len(calls) == 2


def test_a_close_without_owner_metadata_does_not_invent_a_revision(tmp_path):
    state = tmp_path / "state"
    calls = []

    def send(target, text, *, key):
        calls.append(key)
        return {"ok": False, "error": "closed-by-user", "message_id": "m-1001"}

    first = _scan(state, [_episode("E-1042-1")], _obs(activity="idle", runtime_revision=9), send)
    assert calls == ["recovery:proj-example:local-owner"]
    assert first["notices"] == ()
    assert first["episodes"][0]["delivery"]["state"] == "undelivered"
    _scan(state, first["episodes"], _obs(runtime_revision=9), send, scan=8)
    assert len(calls) == 2


def test_unreachable_preread_still_attempts_the_send(tmp_path):
    state = tmp_path / "state"
    calls = []

    def send(target, text, *, key):
        calls.append(key)
        return {
            "ok": False, "message_id": "m-1001",
            "condition": "owner_unreachable", "lookup": "unavailable",
        }

    first = _scan(state, [_episode("E-1042-1")], _obs(activity="unreachable"), send)
    assert calls == ["recovery:proj-example:local-owner"]
    assert first["episodes"][0]["delivery"]["state"] == "undelivered"
    assert any("owner_unreachable" in line for line in first["notices"])
    stored = load_outbox(state, "proj-example", "local-owner")
    assert stored["receipt"] is None
    assert stored["message"] == "m-1001"
    again = _scan(state, first["episodes"], _obs(activity="unreachable"), send, scan=8)
    assert len(calls) == 2
    assert again["notices"] == ()
    assert again["episodes"][0]["delivery"]["state"] == "undelivered"
    assert load_outbox(state, "proj-example", "local-owner")["receipt"] is None
    pinned = outbox_path(state, "proj-example", "local-owner").read_bytes()
    assert load_outbox(state, "proj-example", "local-owner")["message"] == "m-1001"
    assert outbox_path(state, "proj-example", "local-owner").read_bytes() == pinned


def test_keyed_send_sets_the_close_flag(monkeypatch):
    captured = {}

    def fake_send(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return {"ok": True, "message_id": "m-1001", "admission_id": "adm-1"}

    monkeypatch.setattr("plugins.intercom.route.send", fake_send)
    result = keyed_intercom_send(
        "local-owner", "digest", key="recovery:proj-example:local-owner",
        sender="recovery-proj-example", ctx=object(),
    )
    assert result["admission_id"] == "adm-1"
    assert captured["kwargs"]["unless_closed_by_user"] is True
    assert captured["kwargs"]["delivery"] == "queue"
    assert captured["kwargs"]["key"] == "recovery:proj-example:local-owner"
    assert captured["kwargs"]["reply_mode"] == "none"


def test_a_settled_episode_does_not_wake_again(tmp_path):
    state = tmp_path / "state"
    calls = []
    episode = _episode(
        "E-1042-1", state="settled", message="m-1001", admission="adm-1",
        carried_in_turn="turn-1", settled_scan=3,
    )
    result = _scan(state, [episode], _obs(receipts={"adm-1": "terminal"}), lambda *a, **k: calls.append(1))
    assert calls == []
    assert result["sent"] is False
    stored = json.loads((state / "notices.jsonl").read_text(encoding="utf-8-sig"))
    assert "no_progress" in stored["line"]


def test_non_utf8_notice_hold_and_stall_reads_stay_empty(tmp_path):
    state = tmp_path / "state"
    raw = bytes([255])
    notices = state / "notices.jsonl"
    holds = state / "close-holds.json"
    stalls = state / "stalls.json"
    state.mkdir()
    for path in (notices, holds, stalls):
        path.write_bytes(raw)
    assert _load_lines(state) == []
    assert _load_holds(state) == {}
    assert _load_stalls(state) == {}
    assert notices.read_bytes() == raw
    assert holds.read_bytes() == raw
    assert stalls.read_bytes() == raw
    calls = []

    def _send(*_args, **_kwargs):
        calls.append(1)
        return {"admission_id": "adm-1", "message_id": "m-1001"}

    result = _scan(state, [_episode("E-1042-1")], _obs(), _send)
    assert calls == [1]
    assert result["sent"] is True
    assert notices.read_bytes() == raw
    assert holds.read_bytes() == raw
