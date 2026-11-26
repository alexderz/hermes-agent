"""Fixture joins of A1–A17 on the integrated library.

A pass here is a fixture pass. It is not live certification.

Each walk calls the accepted functions already covered by the component
tests named below. Tracker reads and unit shows are fixture data. The
send callable passed to ``scan_owner`` is fixture injection. No test here
starts a unit, writes a profile, or reads a credential.

| Walk | Join | Accepted component paths |
| --- | --- | --- |
| A1 | register, first observation, consume, successor scan | ``test_launcher``, ``test_invocation``, ``test_scan``, ``test_reconcile`` A1 |
| A2 | terminal wake, one deliver, stop, new member | ``test_scan`` H4, ``test_deliver``, ``test_reconcile`` A2 |
| A3 | absent, then lost, recheck refuses | ``test_scan`` A3, ``test_reconcile`` recheck |
| A4 | not-admitted result, one deliver, consumption closes | ``test_actionability`` H4, ``test_deliver``, ``test_reconcile`` |
| A5 | consumed terminal stays quiet | ``test_actionability`` H2, ``test_scan`` |
| A6 | covering handle, then one no-progress notice | ``test_actionability`` A6, ``test_scan`` A6, ``test_deliver`` carried |
| A7 | parked ask, sibling wake | ``test_actionability`` A7, ``test_scan`` |
| A8 | done workstream, then a new ready member | ``test_actionability`` A8, ``test_scan`` G7 |
| A9 | accepted digest is not sent again; recheck refuses | ``test_deliver`` resume, ``test_reconcile`` recheck |
| A10 | running defers, idle sends once, rebind is explicit | ``test_deliver`` O1, ``test_reconcile`` A10 |
| A11 | queued stall once, notice deliver does not send | ``test_scan`` O5, ``test_deliver`` notice-only |
| A12 | gather, wait, answer, unfinished close, stop | ``test_actionability`` A12, ``test_scan``, ``test_reconcile`` |
| A13 | scan does not submit; a notice does not submit | ``test_scan`` A13, ``test_deliver`` notice-only |
| A14 | incomplete notice once, then recovered | ``test_scan`` A14, ``test_deliver`` notice-only |
| A15 | reparent notice, listed history stays | ``test_readers`` A15, ``test_scan`` F8 |
| A16 | undedicated project rejected; scan keeps given members | ``test_binding`` dedicated, ``test_readers`` A16 |
| A17 | self and none wake; other and unknown do not | ``test_readers`` A17, ``test_actionability`` M8 |
"""

from __future__ import annotations

import json
from pathlib import Path

from plugins.project_recovery.binding import validate_binding
from plugins.project_recovery.deliver import scan_owner
from plugins.project_recovery.launcher import register_before_start
from plugins.project_recovery.mapping import Err, Ok, load_mapping
from plugins.project_recovery.reconcile import (
    copy_invocation,
    rebind_owner,
    recheck_mint,
    record_consumption,
    write_binding,
)
from tests.plugins.project_recovery.support import (
    CLOSED_VERBS,
    MAPPING,
    linear_document,
    workstream,
)
from tests.plugins.project_recovery.test_scan import (
    _ABSENT,
    _ENDED,
    _RUNNING,
    _UNIT,
    _classes,
    _empty_tracker,
    _found,
    _go,
    _lookup,
    _members_tracker,
    _open,
    _prepare,
    _register,
    _seed_snapshot,
    _show,
    _snapshot,
    _tracker,
    _write_json,
)

_SPEC = {"kind": "stage", "step": "Spec"}
_AT = "2026-11-22T12:00:00Z"
_GATHER = "example-gatherer.service"


def _mapping():
    loaded = load_mapping(MAPPING)
    assert isinstance(loaded, Ok)
    return loaded.value


def _member(ident, **changes):
    body = {
        "key": ident,
        "state": "in_progress",
        "visibility": "listed",
        "workstream": "ws-alpha",
        "claim": {
            "label": "ws-alpha-mgr",
            "marker": "c1",
            "at": "2026-11-21T00:00:00Z",
        },
        "assignee": "self",
        "blockers": [],
        "archived": False,
    }
    body.update(changes)
    return ident, body


def _board(rows):
    return _members_tracker(dict(rows))


def _consume(recovery, outputs, handle_id, nxt):
    loaded = record_consumption(
        recovery,
        handle_id,
        {"at": _AT, "next": nxt},
        outputs_root=outputs,
    )
    assert isinstance(loaded, Ok)


def _receipt_file(document, message_id="msg-1"):
    path = Path(document["outputs"]["callback_receipt"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"message_id": message_id}), encoding="utf-8")


def _summary(document):
    path = Path(document["outputs"]["summary"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}\n", encoding="utf-8")


def _terminal(seen):
    def receipt(admission_id, *, session_id):
        seen.append((admission_id, session_id))
        return {"status": "terminal"}

    return receipt


def _row(handle_id, liveness, consumed=None):
    return {
        "id": handle_id,
        "subject": dict(_SPEC),
        "role": "architect",
        "liveness": liveness,
        "consumed": consumed,
        "resumable": liveness == "ended" and consumed is None,
    }


def _save_episodes(recovery, episodes):
    _write_json(recovery / "state" / "episodes.json", {"episodes": episodes})


def _owners_idle(recovery):
    snap = _snapshot(recovery)
    snap["sources"]["owners"] = {"owner-session": {"state": "idle"}}
    _write_json(recovery / "state" / "snapshot.json", snap)


def _deliver(tmp_path, episodes, send, **observation):
    observed = {
        "activity": "idle",
        "runtime_revision": 4,
        "binding_revision": 7,
        "receipts": {},
        "offered_turn": None,
    }
    observed.update(observation)
    return scan_owner(
        tmp_path / "deliver-state",
        project="proj-example",
        owner="owner-session",
        scan=2,
        intent_at=200.0,
        episodes=episodes,
        observation=observed,
        send=send,
    )


def _wake_episodes(recovery):
    return [
        row
        for row in _open(recovery)
        if row["class"] not in {"membership_change", "tracker_incomplete"}
    ]


def _asks(path, status):
    path.write_text(f"## Q1\nStatus: {status}\n", encoding="utf-8")


def test_a1_observed_invocation_then_consumed_successor_stays_quiet(
    tmp_path, monkeypatch, capsys
):
    recovery, outputs = _prepare(tmp_path, stream=workstream(brief=""))
    _tracker(monkeypatch, _empty_tracker())
    table = {_UNIT: dict(_RUNNING)}
    _show(monkeypatch, table)
    document = {
        "schema": "project-recovery-handle/1",
        "handle": "h-0007",
        "workstream": "ws-alpha",
        "subject": {"kind": "stage", "step": "Spec"},
        "role": "architect",
        "attempt": 1,
        "runtime": {
            "kind": "systemd-user-unit",
            "unit": _UNIT,
            "invocation_id": None,
        },
        "outputs": {
            "summary": f"{outputs}/architect.1.summary.json",
            "report": f"{outputs}/architect.1.report.md",
            "stage_result": None,
            "callback_receipt": f"{outputs}/architect.1.delivery.json",
        },
        "resume": {"kind": "claude-session", "ref": f"{outputs}/architect.session"},
        "registered_at": _AT,
        "consumed": None,
    }
    started = register_before_start(recovery, document, outputs_root=outputs)
    assert isinstance(started, Ok)
    assert started.value.directives[0].startswith("ReadOnlyPaths=")
    code, out = _go(capsys, recovery, admission_lookup=_lookup)
    stored = json.loads(
        (recovery / "handles" / "h-0007.json").read_text(encoding="utf-8")
    )
    assert code == 0
    assert out.out.strip() == '{"wakeAgent": false}'
    assert stored["runtime"]["invocation_id"] is None
    assert _snapshot(recovery)["units"]["h-0007"]["invocation_id"] == "inv-1"
    assert isinstance(
        copy_invocation(recovery, "h-0007", "inv-1", outputs_root=outputs), Ok
    )
    _summary(document)
    _receipt_file(document)
    _consume(recovery, outputs, "h-0007", {"handle": "h-0008"})
    _register(
        recovery,
        outputs,
        handle="h-0008",
        attempt=2,
        runtime={
            "kind": "systemd-user-unit",
            "unit": "example-architect-r2.service",
            "invocation_id": None,
        },
        outputs={
            "summary": f"{outputs}/architect.2.summary.json",
            "callback_receipt": f"{outputs}/architect.2.delivery.json",
        },
    )
    table[_UNIT] = dict(_ENDED)
    table["example-architect-r2.service"] = dict(
        _RUNNING, InvocationID="inv-2"
    )
    seen = []
    code, out = _go(
        capsys, recovery, admission_lookup=_found, receipt=_terminal(seen)
    )
    decision = recheck_mint(
        _SPEC,
        "architect",
        [
            _row(
                "h-0007",
                "ended",
                {"at": _AT, "next": {"handle": "h-0008"}},
            ),
            _row("h-0008", "running"),
        ],
    )
    assert code == 0
    assert out.out.strip() == '{"wakeAgent": false}'
    assert seen == [("adm-1", "owner-session")]
    assert "result_unprocessed" not in _classes(recovery)
    assert "worker_lost" not in _classes(recovery)
    assert decision.action == "refuse"
    assert "running" in decision.reasons
    assert decision.lost_worker is False


def test_a2_terminal_wakes_once_then_stop_lets_a_new_member_through(
    tmp_path, monkeypatch, capsys
):
    recovery, outputs = _prepare(
        tmp_path,
        stream=workstream(brief="brief.md", accepted_through="Spec"),
    )
    ident, row = _member("linear-131")
    _tracker(monkeypatch, _board([(ident, row)]))
    _show(monkeypatch, {_UNIT: dict(_ENDED)})
    document = _register(
        recovery, outputs, subject={"kind": "member", "id": "linear-131"}
    )
    _summary(document)
    _receipt_file(document)
    seen = []
    code, out = _go(
        capsys, recovery, admission_lookup=_found, receipt=_terminal(seen)
    )
    assert code == 0
    assert out.out.strip() == '{"wakeAgent": false}'
    assert seen == [("adm-1", "owner-session")]
    assert "result_unprocessed" in _classes(recovery)
    calls = []

    def send(target, text, *, key):
        calls.append(key)
        return {"ok": True, "message_id": "m-1001", "admission_id": "adm-9"}

    delivered = _deliver(tmp_path, _wake_episodes(recovery), send)
    assert delivered["sent"] is True
    assert calls == ["recovery:proj-example:owner-session"]
    _consume(recovery, outputs, "h-0007", {"stopped": "operator"})
    ready_id, ready = _member(
        "linear-141", state="ready", claim=None, assignee="none"
    )
    _tracker(monkeypatch, _board([(ident, row), (ready_id, ready)]))
    code, out = _go(
        capsys, recovery, admission_lookup=_found, receipt=_terminal(seen)
    )
    woken = [
        item["subject"]["id"]
        for item in _open(recovery)
        if item["class"] == "ready_authorized"
    ]
    assert code == 0
    assert "result_unprocessed" not in _classes(recovery)
    assert "orphaned_owned" not in _classes(recovery)
    assert "stalled_workstream" not in _classes(recovery)
    assert woken == ["linear-141"]
    assert "owner-session" not in out.out


def test_a3_absent_loss_refuses_a_second_unit(tmp_path, monkeypatch, capsys):
    recovery, outputs = _prepare(tmp_path, stream=workstream(brief=""))
    _tracker(monkeypatch, _empty_tracker())
    table = {_UNIT: dict(_ABSENT)}
    _show(monkeypatch, table)
    _register(recovery, outputs)
    first, out = _go(capsys, recovery, admission_lookup=_lookup)
    assert first == 0
    assert out.out.strip() == '{"wakeAgent": false}'
    assert "worker_lost" not in _classes(recovery)
    second, _again = _go(capsys, recovery, admission_lookup=_lookup)
    waiting = recheck_mint(_SPEC, "architect", [_row("h-0007", "absent")])
    assert second == 0
    assert "worker_lost" in _classes(recovery)
    assert waiting.action == "refuse"
    assert waiting.lost_worker is False
    table[_UNIT] = dict(_ENDED)
    third, _lost = _go(capsys, recovery, admission_lookup=_lookup)
    ended = recheck_mint(_SPEC, "architect", [_row("h-0007", "ended")])
    assert third == 0
    assert "worker_lost" in _classes(recovery)
    assert ended.action == "refuse"
    assert ended.lost_worker is True
    assert ended.resume == ("h-0007",)


def test_a4_not_admitted_result_wakes_once_then_consumption_closes_it(
    tmp_path, monkeypatch, capsys
):
    recovery, outputs = _prepare(tmp_path, stream=workstream(brief=""))
    _tracker(monkeypatch, _empty_tracker())
    _show(monkeypatch, {_UNIT: dict(_ENDED)})
    document = _register(recovery, outputs)
    _summary(document)
    _receipt_file(document)
    looked = []

    def lookup(message_id):
        looked.append(message_id)
        return {"outcome": "proven_not_found"}

    code, out = _go(capsys, recovery, admission_lookup=lookup)
    assert code == 0
    assert out.out.strip() == '{"wakeAgent": false}'
    assert looked == ["msg-1"]
    assert "result_unprocessed" in _classes(recovery)
    assert "worker_lost" not in _classes(recovery)
    calls = []

    def send(target, text, *, key):
        calls.append(1)
        return {"ok": True, "message_id": "m-1001", "admission_id": "adm-4"}

    first = _deliver(tmp_path, _wake_episodes(recovery), send)
    second = _deliver(tmp_path, first["episodes"], send)
    assert first["sent"] is True
    assert second["sent"] is False
    assert calls == [1]
    _consume(recovery, outputs, "h-0007", {"done": "Changelog"})
    code, out = _go(capsys, recovery, admission_lookup=lookup)
    assert code == 0
    assert out.out.strip() == '{"wakeAgent": false}'
    assert "result_unprocessed" not in _classes(recovery)


def test_a5_consumed_terminal_callback_does_not_wake(
    tmp_path, monkeypatch, capsys
):
    recovery, outputs = _prepare(tmp_path, stream=workstream(brief=""))
    _tracker(monkeypatch, _empty_tracker())
    _show(monkeypatch, {_UNIT: dict(_ENDED)})
    document = _register(
        recovery,
        outputs,
        consumed={"at": "2026-11-21T00:00:00Z", "next": {"done": "Changelog"}},
    )
    _summary(document)
    _receipt_file(document)
    seen = []
    code, out = _go(
        capsys, recovery, admission_lookup=_found, receipt=_terminal(seen)
    )
    assert code == 0
    assert out.out.strip() == '{"wakeAgent": false}'
    assert "result_unprocessed" not in _classes(recovery)
    assert _deliver(tmp_path, _open(recovery), lambda *_a, **_k: seen.append("sent"))[
        "sent"
    ] is False
    assert "sent" not in seen


def test_a6_covering_handle_is_quiet_then_one_no_progress_notice(
    tmp_path, monkeypatch, capsys
):
    recovery, outputs = _prepare(tmp_path, stream=workstream(brief=""))
    ident, row = _member("linear-131", tracker_updated="2026-11-18T00:00:00Z")
    _tracker(monkeypatch, _board([(ident, row)]))
    table = {_UNIT: dict(_RUNNING)}
    _show(monkeypatch, table)
    _register(
        recovery, outputs, subject={"kind": "member", "id": "linear-131"}
    )
    code, out = _go(capsys, recovery, admission_lookup=_lookup)
    assert code == 0
    assert out.out.strip() == '{"wakeAgent": false}'
    assert _classes(recovery) == []
    (recovery / "handles" / "h-0007.json").unlink()
    table.clear()
    code, out = _go(capsys, recovery, admission_lookup=_lookup)
    assert "orphaned_owned" in _classes(recovery)
    calls = []

    def send(target, text, *, key):
        calls.append(key)
        return {"ok": True, "message_id": "m-1001", "admission_id": "adm-6"}

    accepted = _deliver(tmp_path, _wake_episodes(recovery), send)

    def refuse(*_args, **_kwargs):
        raise AssertionError("second wake")

    carried = _deliver(
        tmp_path,
        accepted["episodes"],
        refuse,
        offered_turn="turn-6",
        offered_message="m-1001",
    )
    assert calls == ["recovery:proj-example:owner-session"]
    assert carried["episodes"][0]["delivery"]["state"] == "carried"
    _save_episodes(recovery, carried["episodes"])
    _owners_idle(recovery)
    _notice, notice = _go(capsys, recovery, admission_lookup=_lookup)
    assert "no_progress" in notice.out
    _again, later = _go(capsys, recovery, admission_lookup=_lookup)
    assert later.out.strip() == '{"wakeAgent": false}'
    assert "no_progress" not in later.out


def test_a7_parked_ask_hides_only_that_member(tmp_path, monkeypatch, capsys):
    asks = tmp_path / "asks.md"
    _asks(asks, "open")
    recovery, outputs = _prepare(
        tmp_path, stream=workstream(brief="", asks_file=str(asks))
    )
    parked_id, parked = _member("linear-140")
    sibling_id, sibling = _member("linear-141")
    _tracker(monkeypatch, _board([(parked_id, parked), (sibling_id, sibling)]))
    _show(monkeypatch, {})
    _register(
        recovery,
        outputs,
        handle="h-0014",
        subject={"kind": "member", "id": "linear-140"},
        consumed={
            "at": _AT,
            "next": {"wait": {"kind": "ask", "ref": "asks.md#Q1"}},
        },
    )
    code, out = _go(capsys, recovery, admission_lookup=_lookup)
    woken = [
        item["subject"]["id"]
        for item in _open(recovery)
        if item["class"] == "orphaned_owned"
    ]
    assert code == 0
    assert woken == ["linear-141"]
    assert "owner-session" not in out.out


def test_a8_done_workstream_wakes_for_a_new_ready_member(
    tmp_path, monkeypatch, capsys
):
    recovery, _outputs = _prepare(
        tmp_path,
        stream=workstream(status="done", brief="", accepted_through="Spec"),
    )
    done_id, done = _member("linear-100", state="done", claim=None, assignee="none")
    _tracker(monkeypatch, _board([(done_id, done)]))
    _show(monkeypatch, {})
    code, out = _go(capsys, recovery, admission_lookup=_lookup)
    assert code == 0
    assert out.out.strip() == '{"wakeAgent": false}'
    assert "stalled_workstream" not in _classes(recovery)
    assert "ready_authorized" not in _classes(recovery)
    ready_id, ready = _member(
        "linear-150", state="ready", claim=None, assignee="none"
    )
    _tracker(monkeypatch, _board([(done_id, done), (ready_id, ready)]))
    code, out = _go(capsys, recovery, admission_lookup=_lookup)
    woken = [
        item["subject"]["id"]
        for item in _open(recovery)
        if item["class"] == "ready_authorized"
    ]
    assert code == 0
    assert woken == ["linear-150"]
    assert "stalled_workstream" not in _classes(recovery)
    assert "owner-session" not in out.out


def test_a9_accepted_digest_is_not_sent_again_and_recheck_refuses(tmp_path):
    calls = []

    def send(target, text, *, key):
        calls.append(key)
        return {"ok": True, "message_id": "m-1001", "admission_id": "adm-kept"}

    episode = {
        "id": "E-9-1",
        "class": "result_unprocessed",
        "subject": {"kind": "handle", "id": "h-0007"},
        "workstream": "ws-alpha",
        "owner": "owner-session",
        "evidence": {"callback": "terminal"},
        "delivery": {
            "state": "undelivered",
            "message": None,
            "admission": None,
            "carried_in_turn": None,
            "settled_scan": None,
        },
        "notice": {"no_progress": None},
        "closed_scan": None,
    }
    first = _deliver(tmp_path, [episode], send)
    second = _deliver(tmp_path, first["episodes"], send)
    decision = recheck_mint(
        _SPEC,
        "architect",
        [_row("h-0007", "running")],
        receipt={"status": "terminal"},
    )
    assert first["sent"] is True
    assert first["admission_id"] == "adm-kept"
    assert second["sent"] is False
    assert calls == ["recovery:proj-example:owner-session"]
    assert decision.action == "refuse"
    assert decision.lost_worker is False


def test_a10_running_owner_defers_until_idle_and_rebind_is_explicit(
    tmp_path, monkeypatch, capsys
):
    recovery, outputs = _prepare(tmp_path, roots=[], stream=workstream(brief=""))
    _tracker(monkeypatch, _empty_tracker())
    _show(monkeypatch, {_UNIT: dict(_ENDED)})
    document = _register(recovery, outputs)
    _summary(document)
    _receipt_file(document)
    code, _out = _go(
        capsys,
        recovery,
        admission_lookup=_found,
        receipt=lambda admission_id, *, session_id: {"status": "terminal"},
    )
    assert code == 0
    assert "result_unprocessed" in _classes(recovery)
    calls = []

    def send(target, text, *, key):
        calls.append(key)
        return {"ok": True, "message_id": "m-1001", "admission_id": "adm-10"}

    deferred = _deliver(
        tmp_path, _wake_episodes(recovery), send, activity="running"
    )
    running = recheck_mint(
        _SPEC,
        "architect",
        [_row("h-0007", "running")],
        digest={"text": "this interruption is a stop; mint another"},
    )
    stored = json.loads(
        (recovery / "handles" / "h-0007.json").read_text(encoding="utf-8")
    )
    loaded = load_mapping(MAPPING)
    assert isinstance(loaded, Ok)
    binding = validate_binding(
        linear_document(outputs, roots=[], stream=workstream(brief="")),
        closed_verbs=CLOSED_VERBS,
        mapping=loaded.value,
        recovery_dir=recovery,
    )
    assert deferred["deferred"] is True
    assert calls == []
    assert running.action == "refuse"
    assert stored["consumed"] is None
    assert isinstance(binding, Ok)
    assert binding.value.workstreams[0].owner.session == "owner-session"
    idle = _deliver(tmp_path, deferred["episodes"], send)
    assert idle["sent"] is True
    assert calls == ["recovery:proj-example:owner-session"]
    rebound = rebind_owner(
        recovery,
        "ws-alpha",
        session="owner-next",
        closed_verbs=CLOSED_VERBS,
        mapping=loaded.value,
    )
    assert isinstance(rebound, Ok)
    assert rebound.value.workstreams[0].owner.session == "owner-next"
    assert rebound.value.revision == 8
    assert json.loads(
        (recovery / "handles" / "h-0007.json").read_text(encoding="utf-8")
    )["consumed"] is None


def test_a11_queued_callback_stalls_once_and_deliver_does_not_send(
    tmp_path, monkeypatch, capsys
):
    recovery, outputs = _prepare(tmp_path, stream=workstream(brief=""))
    _seed_snapshot(
        recovery,
        sources={
            "tracker": {"complete": True},
            "handles": {"complete": True},
            "units": {"complete": True},
            "asks": {"complete": True},
            "owners": {"owner-session": {"state": "idle"}},
        },
    )
    _tracker(monkeypatch, _empty_tracker())
    _show(monkeypatch, {_UNIT: dict(_ENDED)})
    document = _register(recovery, outputs)
    _receipt_file(document)

    def queued(admission_id, *, session_id):
        assert session_id == "owner-session"
        return {"status": "queued"}

    _first, quiet = _go(
        capsys, recovery, admission_lookup=_found, receipt=queued
    )
    _second, notice = _go(
        capsys, recovery, admission_lookup=_found, receipt=queued
    )
    _third, later = _go(
        capsys, recovery, admission_lookup=_found, receipt=queued
    )
    assert quiet.out.strip() == '{"wakeAgent": false}'
    assert notice.out.count("delivery_stalled") == 1
    assert later.out.strip() == '{"wakeAgent": false}'
    stalls = [row for row in _open(recovery) if row["class"] == "delivery_stalled"]
    calls = []
    delivered = _deliver(
        tmp_path, stalls, lambda *_a, **_k: calls.append("sent")
    )
    assert delivered["sent"] is False
    assert calls == []
    assert delivered["episodes"][0]["delivery"]["state"] == "noticed"


def test_a12_gather_wait_answer_then_unfinished_close(
    tmp_path, monkeypatch, capsys
):
    asks = tmp_path / "asks.md"
    _asks(asks, "open")
    recovery, outputs = _prepare(
        tmp_path,
        roots=[],
        stream=workstream(brief="", asks_file=str(asks)),
    )
    _tracker(monkeypatch, _empty_tracker())
    table = {_GATHER: dict(_RUNNING, InvocationID="inv-g")}
    _show(monkeypatch, table)
    document = _register(
        recovery,
        outputs,
        handle="h-gather",
        role="gatherer",
        subject={"kind": "stage", "step": "Brief"},
        runtime={
            "kind": "systemd-user-unit",
            "unit": _GATHER,
            "invocation_id": None,
        },
    )
    code, out = _go(capsys, recovery, admission_lookup=_lookup)
    assert code == 0
    assert out.out.strip() == '{"wakeAgent": false}'
    assert _snapshot(recovery)["units"]["h-gather"]["invocation_id"] == "inv-g"
    assert _classes(recovery) == []
    table[_GATHER] = dict(_ENDED, InvocationID="inv-g")
    _consume(
        recovery,
        outputs,
        "h-gather",
        {"wait": {"kind": "operator", "ref": f"{asks}#Q1"}},
    )
    code, out = _go(capsys, recovery, admission_lookup=_lookup)
    assert code == 0
    assert out.out.strip() == '{"wakeAgent": false}'
    assert "wait_resolved" not in _classes(recovery)
    assert "stalled_workstream" not in _classes(recovery)
    _asks(asks, "answered")
    code, out = _go(capsys, recovery, admission_lookup=_lookup)
    assert "wait_resolved" in _classes(recovery)
    assert "stalled_workstream" not in _classes(recovery)
    written = write_binding(
        recovery,
        linear_document(
            outputs,
            roots=[],
            stream=workstream(brief="brief.md", asks_file=str(asks)),
        ),
        closed_verbs=CLOSED_VERBS,
        mapping=_mapping(),
    )
    assert isinstance(written, Ok)
    _consume(recovery, outputs, "h-gather", {"done": "Spec"})
    code, out = _go(capsys, recovery, admission_lookup=_lookup)
    assert "stalled_workstream" in _classes(recovery)
    assert "wait_resolved" not in _classes(recovery)
    _consume(recovery, outputs, "h-gather", {"stopped": "operator"})
    code, out = _go(capsys, recovery, admission_lookup=_lookup)
    assert code == 0
    assert out.out.strip() == '{"wakeAgent": false}'
    assert "stalled_workstream" not in _classes(recovery)
    assert document["handle"] == "h-gather"


def test_a13_scan_leaves_a_wake_unsent_and_a_notice_does_not_submit(
    tmp_path, monkeypatch, capsys
):
    recovery, outputs = _prepare(tmp_path, stream=workstream(brief=""))
    _tracker(monkeypatch, _empty_tracker())
    _show(monkeypatch, {_UNIT: dict(_ENDED)})
    _register(recovery, outputs)
    code, out = _go(capsys, recovery, admission_lookup=_lookup)
    wake = next(row for row in _open(recovery) if row["class"] == "worker_lost")
    assert code == 0
    assert out.out.strip() == '{"wakeAgent": false}'
    assert wake["delivery"]["state"] == "undelivered"
    assert not (recovery / "state" / "outbox").exists()
    notice = {
        "id": "E-13-1",
        "class": "membership_change",
        "subject": {"kind": "member", "id": "linear-131"},
        "workstream": "ws-alpha",
        "evidence": {"visibility": "reparented_out"},
        "delivery": {
            "state": "undelivered",
            "message": None,
            "admission": None,
            "carried_in_turn": None,
            "settled_scan": None,
        },
        "notice": {"no_progress": None},
        "closed_scan": None,
    }
    calls = []
    delivered = _deliver(
        tmp_path, [notice], lambda *_a, **_k: calls.append("sent")
    )
    assert delivered["sent"] is False
    assert calls == []
    assert delivered["episodes"][0]["delivery"]["state"] == "noticed"


def test_a14_incomplete_tracker_notices_once_then_recovers(
    tmp_path, monkeypatch, capsys
):
    recovery, _outputs = _prepare(tmp_path, stream=workstream(brief=""))
    previous = {
        "linear-131": {
            "state": "in_progress",
            "visibility": "listed",
            "workstream": "ws-alpha",
            "first_seen_scan": 1,
        }
    }
    _seed_snapshot(recovery, members=previous)
    _show(monkeypatch, {})
    _tracker(
        monkeypatch,
        {
            "complete": False,
            "error": "page",
            "revision": None,
            "roots": {},
            "members": None,
        },
    )
    code, out = _go(capsys, recovery, admission_lookup=_lookup)
    assert code == 0
    assert out.out.count("tracker_incomplete") == 1
    assert _snapshot(recovery)["members"] == previous
    calls = []
    notice = [row for row in _open(recovery) if row["class"] == "tracker_incomplete"]
    delivered = _deliver(
        tmp_path, notice, lambda *_a, **_k: calls.append("sent")
    )
    assert delivered["sent"] is False
    assert calls == []
    _tracker(
        monkeypatch,
        {
            "complete": False,
            "error": "timeout",
            "revision": None,
            "roots": {},
            "members": None,
        },
    )
    _again, quiet = _go(capsys, recovery, admission_lookup=_lookup)
    assert quiet.out.strip() == '{"wakeAgent": false}'
    assert _classes(recovery).count("tracker_incomplete") == 1
    _tracker(monkeypatch, _members_tracker(dict(previous)))
    _recovered, recovered = _go(capsys, recovery, admission_lookup=_lookup)
    assert recovered.out.count("tracker_recovered") == 1
    assert _snapshot(recovery)["members"]["linear-131"]["state"] == "in_progress"


def test_a15_reparent_notices_and_listed_history_stays(
    tmp_path, monkeypatch, capsys
):
    recovery, _outputs = _prepare(tmp_path, stream=workstream(brief=""))
    moved_id, moved = _member(
        "linear-131",
        key="ABC-999",
        state="in_progress",
        visibility="reparented_out",
        claim=None,
        assignee="none",
    )
    kept_id, kept = _member(
        "linear-132",
        key="ABC-132",
        state="done",
        visibility="listed",
        claim=None,
        assignee="none",
        archived=True,
    )
    _tracker(monkeypatch, _board([(moved_id, moved), (kept_id, kept)]))
    _show(monkeypatch, {})
    code, out = _go(capsys, recovery, admission_lookup=_lookup)
    noticed = [
        item["subject"]["id"]
        for item in _open(recovery)
        if item["class"] == "membership_change"
    ]
    assert code == 0
    assert noticed == ["linear-131"]
    assert "linear-132" in _snapshot(recovery)["members"]
    assert _snapshot(recovery)["members"]["linear-131"]["key"] == "ABC-999"
    assert "owner-session" not in out.out
    _again, later = _go(capsys, recovery, admission_lookup=_lookup)
    assert later.out.strip() == '{"wakeAgent": false}'


def test_a16_undedicated_project_is_invalid_and_the_scan_keeps_only_given_members(
    tmp_path, monkeypatch, capsys
):
    recovery, outputs = _prepare(tmp_path, stream=workstream(brief=""))
    undedicated = linear_document(
        outputs,
        roots=[
            {
                "kind": "project",
                "id": "linear-project:91aa",
                "workstream": "ws-alpha",
            }
        ],
    )
    rejected = validate_binding(
        undedicated,
        closed_verbs=CLOSED_VERBS,
        mapping=_mapping(),
        recovery_dir=recovery,
    )
    assert isinstance(rejected, Err)
    assert rejected.error.reason == "dedicated"
    epic_id, epic_row = _member("linear-131", state="done", claim=None)
    label_id, label_row = _member("linear-132", state="done", claim=None)
    _tracker(monkeypatch, _board([(epic_id, epic_row), (label_id, label_row)]))
    _show(monkeypatch, {})
    code, _out = _go(capsys, recovery, admission_lookup=_lookup)
    assert code == 0
    assert set(_snapshot(recovery)["members"]) == {"linear-131", "linear-132"}


def test_a17_scan_wakes_for_self_and_none_and_not_for_unknown(
    tmp_path, monkeypatch, capsys
):
    recovery, _outputs = _prepare(
        tmp_path,
        stream=workstream(brief="", accepted_through="Spec"),
    )
    rows = [
        _member("ABC-160", claim=None, assignee="none"),
        _member("ABC-161", state="ready", claim=None, assignee="self"),
        _member("ABC-162", state="ready", claim=None, assignee="other"),
        _member("ABC-163", state="ready", claim=None, assignee="none"),
        _member("ABC-164", state="ready", claim=None, assignee="unknown"),
    ]
    _tracker(monkeypatch, _board(rows))
    _show(monkeypatch, {})
    code, out = _go(capsys, recovery, admission_lookup=_lookup)
    missing = [
        item["subject"]["id"]
        for item in _open(recovery)
        if item["class"] == "missing_ownership"
    ]
    ready = [
        item["subject"]["id"]
        for item in _open(recovery)
        if item["class"] == "ready_authorized"
    ]
    assert code == 0
    assert missing == ["ABC-160"]
    assert ready == ["ABC-161", "ABC-163"]
    assert "ABC-162" not in ready
    assert "ABC-164" not in ready
    assert "owner-session" not in out.out
