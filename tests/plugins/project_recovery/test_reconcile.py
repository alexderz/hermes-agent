"""Manager reconciliation: binding writes, consumption, and mint recheck."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from plugins.project_recovery.actionability import evaluate
from plugins.project_recovery.binding import load_binding
from plugins.project_recovery.episodes import apply_no_progress
from plugins.project_recovery.mapping import Err, Ok, load_mapping
from plugins.project_recovery.reconcile import (
    copy_invocation,
    progress_fact,
    read_worker_evidence,
    rebind_owner,
    recheck_mint,
    record_consumption,
    set_accepted_through,
    workstream_finished,
    write_binding,
    write_handle,
)
from tests.plugins.project_recovery.support import (
    CLOSED_VERBS,
    MAPPING,
    handle_document,
    linear_document,
    workspace,
    workstream,
)


def _mapping():
    loaded = load_mapping(MAPPING)
    assert isinstance(loaded, Ok)
    return loaded.value


def test_write_binding_replaces_a_temp_file_in_the_recovery_folder(
    tmp_path, monkeypatch
):
    recovery, outputs = workspace(tmp_path)
    brief = recovery / "authority.brief"
    brief.write_text("brief\n", encoding="utf-8")
    asks = tmp_path / "asks.md"
    document = linear_document(
        outputs,
        roots=[],
        stream=workstream(brief=str(brief), asks_file=str(asks)),
    )
    calls = []
    real_replace = os.replace

    def spy(src, dst):
        calls.append((str(src), str(dst)))
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", spy)
    result = write_binding(
        recovery,
        document,
        closed_verbs=CLOSED_VERBS,
        mapping=_mapping(),
    )

    assert isinstance(result, Ok)
    assert calls
    src, dst = calls[-1]
    assert Path(src).parent == Path(dst).parent
    assert Path(dst) == recovery / "binding.yaml"
    assert Path(src).name != Path(dst).name
    assert not (recovery / "state").exists()
    assert not (outputs / "binding.yaml").exists()
    stored = (recovery / "binding.yaml").read_text(encoding="utf-8")
    assert "authority.brief" in stored or str(brief) in stored
    assert asks.exists() is False


def test_invalid_binding_leaves_the_previous_file(tmp_path):
    recovery, outputs = workspace(tmp_path)
    document = linear_document(outputs, roots=[])
    written = write_binding(
        recovery, document, closed_verbs=CLOSED_VERBS, mapping=_mapping()
    )
    assert isinstance(written, Ok)
    before = (recovery / "binding.yaml").read_bytes()
    rejected = dict(document)
    rejected["schema"] = "other"
    result = write_binding(
        recovery, rejected, closed_verbs=CLOSED_VERBS, mapping=_mapping()
    )

    assert isinstance(result, Err)
    assert result.error.code == "binding_invalid"
    assert (recovery / "binding.yaml").read_bytes() == before
    assert not (recovery / "state").exists()


def test_failing_evidence_is_omitted_and_consumption_still_records(tmp_path):
    recovery, outputs = workspace(tmp_path)
    summary = outputs / "architect.1.summary.json"
    summary.mkdir()
    report = outputs / "architect.1.report.md"
    report.write_text("report-body\n", encoding="utf-8")
    document = handle_document(outputs)
    registered = write_handle(recovery, document, outputs_root=outputs)
    assert isinstance(registered, Ok)
    viewed = read_worker_evidence(registered.value, outputs_root=outputs)

    assert viewed is not None
    assert "report" in viewed.trusted
    assert "summary" in viewed.rejected
    assert viewed.rejected["summary"] == "directory"
    assert "report-body" not in repr(viewed)
    consumed = record_consumption(
        recovery,
        "h-0007",
        {"at": "2026-11-22T11:02:00Z", "next": {"stopped": "operator"}},
        outputs_root=outputs,
    )
    assert isinstance(consumed, Ok)
    stored = _stored_handle(recovery)
    assert stored["consumed"]["next"] == {"stopped": "operator"}
    assert stored["outputs"]["summary"] == str(summary)
    assert stored["outputs"]["report"] == str(report)
    assert not (recovery / "state").exists()


@pytest.mark.platforms("posix")
def test_symlink_evidence_is_not_read_or_stored(tmp_path):
    recovery, outputs = workspace(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("OUTSIDE-TOKEN\n", encoding="utf-8")
    summary = outputs / "architect.1.summary.json"
    summary.symlink_to(outside)
    report = outputs / "architect.1.report.md"
    report.write_text("kept\n", encoding="utf-8")
    registered = write_handle(recovery, handle_document(outputs), outputs_root=outputs)
    assert isinstance(registered, Ok)
    viewed = read_worker_evidence(registered.value, outputs_root=outputs)

    assert viewed is not None
    assert viewed.rejected["summary"] == "symlink"
    assert "report" in viewed.trusted
    assert "OUTSIDE-TOKEN" not in repr(viewed)
    blob = "\n".join(
        path.read_text(encoding="utf-8")
        for path in recovery.rglob("*")
        if path.is_file()
    )
    assert "OUTSIDE-TOKEN" not in blob


_NEXT_SHAPES = (
    {"handle": "h-0008"},
    {"wait": {"kind": "ask", "ref": "/asks/asks.md#Q1"}},
    {"wait": {"kind": "blocker", "ref": "linear:abc"}},
    {"wait": {"kind": "quota", "resume_after": "2026-11-22T12:00:00Z"}},
    {"wait": {"kind": "operator", "ref": "/asks/asks.md#Q1"}},
    {"done": "Build"},
    {"stopped": "operator"},
)


@pytest.mark.parametrize("nxt", _NEXT_SHAPES)
def test_consumption_records_each_accepted_next_shape(tmp_path, nxt):
    recovery, outputs = workspace(tmp_path)
    write_handle(recovery, handle_document(outputs), outputs_root=outputs)
    result = record_consumption(
        recovery,
        "h-0007",
        {"at": "2026-11-22T11:02:00Z", "next": nxt},
        outputs_root=outputs,
    )

    assert isinstance(result, Ok)
    stored = _stored_handle(recovery)
    assert stored["consumed"]["next"] == nxt
    assert not (recovery / "state").exists()


def test_bad_next_does_not_replace_the_handle(tmp_path):
    recovery, outputs = workspace(tmp_path)
    registered = write_handle(recovery, handle_document(outputs), outputs_root=outputs)
    assert isinstance(registered, Ok)
    before = (recovery / "handles" / "h-0007.json").read_bytes()
    result = record_consumption(
        recovery,
        "h-0007",
        {"at": "2026-11-22T11:02:00Z", "next": {"done": "Ship"}},
        outputs_root=outputs,
    )

    assert isinstance(result, Err)
    assert (recovery / "handles" / "h-0007.json").read_bytes() == before


def test_copy_invocation_stores_only_the_supplied_id(tmp_path):
    recovery, outputs = workspace(tmp_path)
    registered = write_handle(recovery, handle_document(outputs), outputs_root=outputs)
    assert isinstance(registered, Ok)
    before = (recovery / "handles" / "h-0007.json").read_bytes()
    refused = copy_invocation(recovery, "h-0007", "", outputs_root=outputs)
    copied = copy_invocation(recovery, "h-0007", "inv-1", outputs_root=outputs)

    assert isinstance(refused, Err)
    assert isinstance(copied, Ok)
    assert (recovery / "handles" / "h-0007.json").read_bytes() != before
    stored = _stored_handle(recovery)
    assert stored["runtime"]["invocation_id"] == "inv-1"
    assert stored["consumed"] is None
    again = copy_invocation(recovery, "h-0007", "inv-2", outputs_root=outputs)
    kept = _stored_handle(recovery)
    assert isinstance(again, Ok)
    assert kept["runtime"]["invocation_id"] == "inv-1"
    assert kept["consumed"] is None


def _stored_handle(recovery):
    path = recovery / "handles" / "h-0007.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _consume(recovery, outputs, nxt, *, at="2026-11-22T11:02:00Z", handle="h-0007"):
    return record_consumption(
        recovery,
        handle,
        {"at": at, "next": nxt},
        outputs_root=outputs,
    )


def _view(document, **overrides):
    view = {
        "id": document["handle"],
        "workstream": document["workstream"],
        "subject": document["subject"],
        "liveness": "ended",
        "unit_result": "success",
        "consumed": document["consumed"],
        "summary_ok": False,
        "stage_ok": False,
        "callback": "absent",
        "output_files": False,
        "in_previous": True,
        "owner": "owner-session",
    }
    view.update(overrides)
    return view


def _world(**overrides):
    world = {
        "project_status": "open",
        "binding_revision": 7,
        "tracker_complete": True,
        "asks_complete": True,
        "asks": {},
        "now": "2026-11-22T12:00:00Z",
        "handles": [],
        "members": [],
        "workstreams": [
            {
                "id": "ws-alpha",
                "status": "open",
                "closing_step": "Changelog",
                "claim_labels": ["ws-alpha-mgr"],
                "brief": "/briefs/brief.md",
                "accepted_through": "none",
                "owner": "owner-session",
            }
        ],
        "receipt_outage": False,
    }
    world.update(overrides)
    return world


def _member(ident, **overrides):
    row = {
        "id": ident,
        "workstream": "ws-alpha",
        "state": "in_progress",
        "visibility": "listed",
        "archived": False,
        "claim": {
            "label": "ws-alpha-mgr",
            "marker": "c1",
            "at": "2026-11-21T00:00:00Z",
        },
        "assignee": "self",
        "blockers": [],
    }
    row.update(overrides)
    return row


def _names(result):
    return [item.class_name for item in result.intents]


def test_stopped_consumption_quiets_that_member_and_s1_while_latest(tmp_path):
    recovery, outputs = workspace(tmp_path)
    stopped = handle_document(outputs)
    stopped["subject"] = {"kind": "member", "id": "linear-131"}
    write_handle(recovery, stopped, outputs_root=outputs)
    assert isinstance(
        _consume(recovery, outputs, {"stopped": "operator"}),
        Ok,
    )
    document = _stored_handle(recovery)
    quiet = evaluate(
        _world(
            handles=[_view(document)],
            members=[_member("linear-131")],
        )
    )
    assert "orphaned_owned" not in _names(quiet)
    assert "stalled_workstream" not in _names(quiet)
    assert "result_unprocessed" not in _names(quiet)

    later = handle_document(outputs)
    later["handle"] = "h-0008"
    later["subject"] = {"kind": "stage", "step": "Build"}
    write_handle(recovery, later, outputs_root=outputs)
    assert isinstance(
        _consume(
            recovery,
            outputs,
            {"done": "Build"},
            at="2026-11-22T12:00:00Z",
            handle="h-0008",
        ),
        Ok,
    )
    successor = json.loads(
        (recovery / "handles" / "h-0008.json").read_text(encoding="utf-8")
    )
    opened = evaluate(
        _world(handles=[_view(document), _view(successor)], members=[])
    )
    assert "stalled_workstream" in _names(opened)


def test_a_different_member_stays_actionable_after_a_stop(tmp_path):
    recovery, outputs = workspace(tmp_path)
    stopped = handle_document(outputs)
    stopped["subject"] = {"kind": "member", "id": "linear-131"}
    write_handle(recovery, stopped, outputs_root=outputs)
    _consume(recovery, outputs, {"stopped": "operator"})
    document = _stored_handle(recovery)
    ready = _member(
        "linear-141",
        state="ready",
        claim=None,
        assignee="none",
    )
    world = _world(
        handles=[_view(document)],
        members=[_member("linear-131"), ready],
        workstreams=[
            {
                "id": "ws-alpha",
                "status": "open",
                "closing_step": "Changelog",
                "claim_labels": ["ws-alpha-mgr"],
                "brief": "/briefs/brief.md",
                "accepted_through": "Spec",
                "owner": "owner-session",
            }
        ],
    )
    names = _names(evaluate(world))
    woken = [
        item.subject["id"]
        for item in evaluate(world).intents
        if item.class_name == "ready_authorized"
    ]

    assert "orphaned_owned" not in names
    assert woken == ["linear-141"]


def test_done_finishes_the_workstream_only_at_closing_step(tmp_path):
    recovery, outputs = workspace(tmp_path)
    write_handle(recovery, handle_document(outputs), outputs_root=outputs)
    assert isinstance(_consume(recovery, outputs, {"done": "Build"}), Ok)
    early = _stored_handle(recovery)
    assert workstream_finished(early["consumed"]["next"], "Changelog") is False
    unfinished = evaluate(_world(handles=[_view(early)], members=[]))
    assert "stalled_workstream" in _names(unfinished)

    assert isinstance(
        _consume(
            recovery,
            outputs,
            {"done": "Changelog"},
            at="2026-11-22T12:00:00Z",
        ),
        Ok,
    )
    closed = _stored_handle(recovery)
    assert workstream_finished(closed["consumed"]["next"], "Changelog") is True
    assert workstream_finished({"stopped": "operator"}, "Changelog") is False
    finished = evaluate(_world(handles=[_view(closed)], members=[]))
    assert "stalled_workstream" not in _names(finished)


def test_accepted_through_updates_only_with_a_move_and_a_cite(tmp_path):
    recovery, outputs = workspace(tmp_path)
    document = linear_document(outputs, roots=[])
    assert isinstance(
        write_binding(
            recovery, document, closed_verbs=CLOSED_VERBS, mapping=_mapping()
        ),
        Ok,
    )
    before = (recovery / "binding.yaml").read_bytes()
    missing = set_accepted_through(
        recovery,
        "ws-alpha",
        move="",
        evidence="/asks/asks.md#Q1",
        closed_verbs=CLOSED_VERBS,
        mapping=_mapping(),
    )
    no_cite = set_accepted_through(
        recovery,
        "ws-alpha",
        move="Brief",
        evidence="",
        closed_verbs=CLOSED_VERBS,
        mapping=_mapping(),
    )
    assert isinstance(missing, Err)
    assert isinstance(no_cite, Err)
    assert (recovery / "binding.yaml").read_bytes() == before

    updated = set_accepted_through(
        recovery,
        "ws-alpha",
        move="Spec",
        evidence="/asks/asks.md#Q1",
        closed_verbs=CLOSED_VERBS,
        mapping=_mapping(),
    )
    assert isinstance(updated, Ok)
    assert updated.value.revision == 7
    assert updated.value.workstreams[0].authority.accepted_through == "Spec"
    assert updated.value.workstreams[0].authority.evidence == "/asks/asks.md#Q1"
    write_handle(recovery, handle_document(outputs), outputs_root=outputs)
    _consume(recovery, outputs, {"done": "Spec"})
    reloaded = load_binding(
        (recovery / "binding.yaml").read_text(encoding="utf-8"),
        closed_verbs=CLOSED_VERBS,
        mapping=_mapping(),
        recovery_dir=recovery,
    )
    assert isinstance(reloaded, Ok)
    assert reloaded.value.workstreams[0].authority.accepted_through == "Spec"
    assert reloaded.value.revision == 7


def test_rebind_replaces_the_supplied_session_and_bumps_revision(tmp_path):
    recovery, outputs = workspace(tmp_path)
    document = linear_document(outputs, roots=[])
    write_binding(recovery, document, closed_verbs=CLOSED_VERBS, mapping=_mapping())
    before = (recovery / "binding.yaml").read_bytes()
    refused = rebind_owner(
        recovery,
        "ws-alpha",
        session=["owner-a", "owner-b"],
        closed_verbs=CLOSED_VERBS,
        mapping=_mapping(),
    )
    assert isinstance(refused, Err)
    assert (recovery / "binding.yaml").read_bytes() == before

    rebound = rebind_owner(
        recovery,
        "ws-alpha",
        session="owner-next",
        closed_verbs=CLOSED_VERBS,
        mapping=_mapping(),
    )
    assert isinstance(rebound, Ok)
    assert rebound.value.revision == 8
    owner = rebound.value.workstreams[0].owner
    assert owner.session == "owner-next"
    assert owner.claim_labels == ("ws-alpha-mgr",)


def _row(liveness, **overrides):
    row = {
        "id": "h-0007",
        "subject": {"kind": "stage", "step": "Spec"},
        "role": "architect",
        "liveness": liveness,
        "consumed": None,
        "resumable": False,
    }
    row.update(overrides)
    return row


_SPEC = {"kind": "stage", "step": "Spec"}


@pytest.mark.parametrize(
    ("liveness", "consumed", "resumable", "action", "lost", "resume"),
    [
        ("running", None, False, "refuse", False, ()),
        ("absent", None, False, "refuse", False, ()),
        ("unknown", None, False, "refuse", False, ()),
        ("ended", None, False, "refuse", True, ()),
        ("ended", None, True, "refuse", True, ("h-0007",)),
        ("replaced", None, True, "refuse", True, ()),
        (
            "ended",
            {"at": "2026-11-22T11:02:00Z", "next": {"handle": "h-0008"}},
            False,
            "clear",
            False,
            (),
        ),
        (
            "running",
            {"at": "2026-11-22T11:02:00Z", "next": {"stopped": "operator"}},
            False,
            "refuse",
            False,
            (),
        ),
    ],
)
def test_recheck_refuses_a_second_unit_for_the_same_subject_and_role(
    liveness, consumed, resumable, action, lost, resume
):
    decision = recheck_mint(
        _SPEC,
        "architect",
        [_row(liveness, consumed=consumed, resumable=resumable)],
    )

    assert decision is not None
    assert decision.action == action
    assert decision.lost_worker is lost
    assert decision.resume == resume


def test_absent_during_the_wait_is_not_a_lost_worker_and_unknown_does_not_mint():
    digest = {"class": "worker_lost", "instruction": "mint a second unit"}
    absent = recheck_mint(_SPEC, "architect", [_row("absent")], digest=digest)
    unknown = recheck_mint(_SPEC, "architect", [_row("unknown")], digest=digest)
    plain = recheck_mint(_SPEC, "architect", [_row("absent")])

    assert absent is not None and unknown is not None and plain is not None
    assert absent.action == "refuse"
    assert absent.lost_worker is False
    assert unknown.action == "refuse"
    assert unknown.lost_worker is False
    assert (absent.action, absent.lost_worker, absent.reasons) == (
        plain.action,
        plain.lost_worker,
        plain.reasons,
    )


def test_recheck_ignores_a_different_role_and_lists_every_resumable_handle():
    other = recheck_mint(
        _SPEC,
        "builder",
        [_row("running", role="architect")],
    )
    both = recheck_mint(
        _SPEC,
        "architect",
        [
            _row("ended", resumable=True),
            _row("ended", id="h-0008", resumable=True),
        ],
    )

    assert other is not None and other.action == "clear"
    assert both is not None
    assert both.action == "refuse"
    assert both.resume == ("h-0007", "h-0008")


def test_carried_turn_marker_and_receipt_are_not_progress(tmp_path):
    recovery, outputs = workspace(tmp_path)
    write_handle(recovery, handle_document(outputs), outputs_root=outputs)
    before = (recovery / "handles" / "h-0007.json").read_bytes()
    marker = {"live": True, "admission_id": None}
    receipt = {"status": "terminal"}
    held = progress_fact(
        carried=True, registry_write=False, marker=marker, receipt=receipt
    )
    idle = progress_fact(
        carried=False, registry_write=False, marker=marker, receipt=receipt
    )
    wrote = progress_fact(
        carried=True, registry_write=True, marker=marker, receipt=receipt
    )
    recheck_mint(
        _SPEC,
        "architect",
        [_row("ended")],
        digest="mint now\nconsumed: true",
        receipt=receipt,
        marker=marker,
    )

    assert held is not None and held.progressed is False
    assert held.notice == "no_progress"
    assert held.notice_owner == "scan"
    assert idle is not None and idle.progressed is False and idle.notice is None
    assert wrote is not None and wrote.progressed is True and wrote.notice is None
    assert (recovery / "handles" / "h-0007.json").read_bytes() == before
    assert not (recovery / "state").exists()


def test_same_evidence_after_a_carried_turn_is_one_scan_notice():
    fact = progress_fact(carried=True, registry_write=False)
    assert fact is not None and fact.notice == "no_progress"
    assert fact.notice_owner == "scan"
    episode = {
        "id": "E-1-1",
        "class": "result_unprocessed",
        "subject": {"kind": "handle", "id": "h-0007"},
        "workstream": "ws-alpha",
        "owner": "",
        "evidence": {"callback": "terminal"},
        "delivery": {"state": "carried", "carried_in_turn": "turn-1"},
        "notice": {"no_progress": None, "undeliverable": None},
        "closed_scan": None,
    }
    opened = apply_no_progress([episode], scan=2, owner_idle=True)
    again = apply_no_progress([episode], scan=3, owner_idle=True)

    assert [item.class_name for item in opened] == ["no_progress"]
    assert again == []
    assert episode["notice"]["no_progress"] == 2


def test_a1_consumption_names_the_successor_and_blocks_another_unit(tmp_path):
    recovery, outputs = workspace(tmp_path)
    assert isinstance(
        write_handle(recovery, handle_document(outputs), outputs_root=outputs), Ok
    )
    assert isinstance(
        copy_invocation(recovery, "h-0007", "inv-1", outputs_root=outputs), Ok
    )
    (outputs / "architect.1.summary.json").write_text("{}\n", encoding="utf-8")
    blocked = recheck_mint(
        _SPEC,
        "architect",
        [_row("ended", resumable=True)],
        receipt={"status": "terminal"},
    )
    assert blocked is not None and blocked.action == "refuse"
    assert blocked.resume == ("h-0007",)
    assert _stored_handle(recovery)["consumed"] is None
    assert isinstance(_consume(recovery, outputs, {"handle": "h-0008"}), Ok)
    successor = handle_document(outputs)
    successor["handle"] = "h-0008"
    successor["attempt"] = 2
    assert isinstance(write_handle(recovery, successor, outputs_root=outputs), Ok)
    decision = recheck_mint(
        _SPEC,
        "architect",
        [
            _row(
                "ended",
                consumed={"at": "2026-11-22T11:02:00Z", "next": {"handle": "h-0008"}},
            ),
            _row("absent", id="h-0008"),
        ],
    )
    stored = _stored_handle(recovery)
    follower = json.loads(
        (recovery / "handles" / "h-0008.json").read_text(encoding="utf-8")
    )
    names = _names(
        evaluate(
            _world(
                handles=[
                    _view(stored, summary_ok=True, callback="terminal"),
                    _view(follower, liveness="absent", in_previous=False),
                ]
            )
        )
    )

    assert decision is not None and decision.action == "refuse"
    assert decision.lost_worker is False
    assert "absent" in decision.reasons
    assert stored["consumed"]["next"] == {"handle": "h-0008"}
    assert stored["runtime"]["invocation_id"] == "inv-1"
    assert "result_unprocessed" not in names
    assert "worker_lost" not in names
    assert not (recovery / "state").exists()


def test_a2_terminal_receipt_does_not_consume_and_stop_quiets(tmp_path):
    recovery, outputs = workspace(tmp_path)
    document = handle_document(outputs)
    document["subject"] = {"kind": "member", "id": "linear-131"}
    write_handle(recovery, document, outputs_root=outputs)
    (outputs / "architect.1.summary.json").write_text("{}\n", encoding="utf-8")
    (outputs / "architect.1.delivery.json").write_text(
        '{"result": "ok", "message_id": "m-1"}\n', encoding="utf-8"
    )
    decision = recheck_mint(
        {"kind": "member", "id": "linear-131"},
        "architect",
        [_row("ended", subject={"kind": "member", "id": "linear-131"})],
        receipt={"status": "terminal"},
        marker={"live": True, "admission_id": None},
    )
    unconsumed = _stored_handle(recovery)
    loud = _names(
        evaluate(
            _world(
                handles=[
                    _view(unconsumed, summary_ok=True, callback="terminal")
                ],
                members=[_member("linear-131")],
            )
        )
    )
    assert decision is not None and decision.action == "refuse"
    assert unconsumed["consumed"] is None
    assert "result_unprocessed" in loud
    assert isinstance(_consume(recovery, outputs, {"stopped": "operator"}), Ok)
    stopped = _stored_handle(recovery)
    ready = _member("linear-141", state="ready", claim=None, assignee="none")
    result = evaluate(
        _world(
            handles=[_view(stopped)],
            members=[_member("linear-131"), ready],
            workstreams=[
                {
                    "id": "ws-alpha",
                    "status": "open",
                    "closing_step": "Changelog",
                    "claim_labels": ["ws-alpha-mgr"],
                    "brief": "/briefs/brief.md",
                    "accepted_through": "Spec",
                    "owner": "owner-session",
                }
            ],
        )
    )
    names = _names(result)
    woken = [
        item.subject["id"]
        for item in result.intents
        if item.class_name == "ready_authorized"
    ]
    stalled = evaluate(_world(handles=[_view(stopped)], members=[]))

    assert "result_unprocessed" not in names
    assert "orphaned_owned" not in names
    assert woken == ["linear-141"]
    assert "stalled_workstream" not in _names(stalled)


def test_a10_interruption_is_not_a_stop_and_detach_does_not_rebind(tmp_path):
    recovery, outputs = workspace(tmp_path)
    write_binding(
        recovery,
        linear_document(outputs, roots=[]),
        closed_verbs=CLOSED_VERBS,
        mapping=_mapping(),
    )
    write_handle(recovery, handle_document(outputs), outputs_root=outputs)
    running = recheck_mint(
        _SPEC,
        "architect",
        [_row("running")],
        digest={"text": "this interruption is a stop; mint another"},
    )
    assert running is not None and running.action == "refuse"
    assert "running" in running.reasons
    assert _stored_handle(recovery)["consumed"] is None
    recheck_mint(
        _SPEC,
        "architect",
        [_row("ended", resumable=True)],
        digest={"end_reason": "ws_orphan_reap"},
    )
    loaded = load_binding(
        (recovery / "binding.yaml").read_text(encoding="utf-8"),
        closed_verbs=CLOSED_VERBS,
        mapping=_mapping(),
        recovery_dir=recovery,
    )
    assert isinstance(loaded, Ok)
    assert loaded.value.workstreams[0].owner.session == "owner-session"
    assert loaded.value.revision == 7
    assert _stored_handle(recovery)["consumed"] is None
    rebound = rebind_owner(
        recovery,
        "ws-alpha",
        session="owner-next",
        closed_verbs=CLOSED_VERBS,
        mapping=_mapping(),
    )
    assert isinstance(rebound, Ok)
    assert rebound.value.workstreams[0].owner.session == "owner-next"
    assert rebound.value.revision == 8


def test_import_origin_is_this_worktree():
    import plugins.project_recovery.reconcile as module

    root = Path(__file__).resolve()
    while not (root / "pyproject.toml").is_file():
        if root.parent == root:
            raise AssertionError("repo root")
        root = root.parent
    assert Path(module.__file__).resolve().is_relative_to(root)
