"""Actionability rows. The case id names the row."""

from __future__ import annotations

from pathlib import Path

import pytest

from plugins.project_recovery.actionability import evaluate
from plugins.project_recovery.episodes import reconcile

_AT = "2026-11-22T11:00:00Z"


def _repo_root():
    root = Path(__file__).resolve()
    while not (root / "pyproject.toml").is_file():
        if root.parent == root:
            raise AssertionError("repo root")
        root = root.parent
    return root


def test_import_origin_is_this_worktree():
    import plugins.project_recovery.actionability as module

    assert Path(module.__file__).resolve().is_relative_to(_repo_root())


def _ws(**overrides):
    base = {
        "id": "ws-alpha",
        "status": "open",
        "closing_step": "Changelog",
        "claim_labels": ["ws-alpha-mgr"],
        "brief": "/briefs/brief.md",
        "accepted_through": "none",
        "owner": "owner-session",
    }
    base.update(overrides)
    return base


def _handle(**overrides):
    base = {
        "id": "h-0007",
        "workstream": "ws-alpha",
        "subject": {"kind": "stage", "step": "Spec"},
        "liveness": "ended",
        "unit_result": "oom-kill",
        "consumed": None,
        "summary_ok": False,
        "stage_ok": False,
        "callback": "absent",
        "output_files": False,
        "in_previous": True,
        "owner": "owner-session",
    }
    base.update(overrides)
    return base


def _member(**overrides):
    base = {
        "id": "linear-131",
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
        "tracker_updated": "2026-11-21T00:00:00Z",
    }
    base.update(overrides)
    return base


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
        "workstreams": [_ws()],
        "receipt_outage": False,
    }
    world.update(overrides)
    return world


def _consumed(nxt):
    return {"at": _AT, "next": nxt}


def _wait(kind, **fields):
    return _consumed({"wait": {"kind": kind, **fields}})


def _names(result):
    return [item.class_name for item in result.intents]


def _subject_names(result, ident):
    return [
        item.class_name for item in result.intents if item.subject.get("id") == ident
    ]


def _matches(result, spec):
    names = _names(result)
    kind = spec["kind"]
    if kind == "quiet":
        return _subject_names(result, spec["id"]) == []
    if kind == "opens":
        return spec["class"] in names
    if kind == "absent":
        return spec["class"] not in names
    if kind == "suppress":
        return spec["id"] in result.suppress and "result_unprocessed" not in names
    if kind == "hold":
        return spec["id"] in result.hold and "result_unprocessed" not in names
    if kind == "skip":
        return (
            spec["id"] in result.skip_workstreams
            and _subject_names(result, "linear-131") == []
        )
    if kind == "paused":
        return result.project_paused and result.intents == ()
    if kind == "close_all":
        return result.close_all and result.intents == ()
    if kind == "close_ws":
        return spec["id"] in result.close_workstreams
    if kind == "notice":
        return any(
            item.class_name == spec["class"] and item.notice for item in result.intents
        )
    if kind == "g2":
        return (
            "tracker_incomplete" in names
            and "orphaned_owned" not in names
            and "worker_lost" in names
        )
    if kind == "g7":
        return "ready_authorized" in names and "stalled_workstream" not in names
    raise AssertionError(kind)


def _rows():
    cover = _handle(
        liveness="running",
        unit_result=None,
        subject={"kind": "member", "id": "linear-131"},
    )
    ended = _handle(liveness="ended", callback="absent")
    return {**_handle_wait_rows(ended), **_member_gate_rows(cover, ended)}


def _handle_wait_rows(ended):
    return {
        "H1_running_is_quiet": (
            _world(handles=[_handle(liveness="running", unit_result=None)]),
            {"kind": "quiet", "id": "h-0007"},
        ),
        "H2_stopped_handle_is_quiet": (
            _world(
                handles=[
                    _handle(
                        liveness="running",
                        consumed=_consumed({"stopped": "operator"}),
                    )
                ]
            ),
            {"kind": "quiet", "id": "h-0007"},
        ),
        "H2_done_closing_step_is_quiet": (
            _world(handles=[_handle(consumed=_consumed({"done": "Changelog"}))]),
            {"kind": "quiet", "id": "h-0007"},
        ),
        "H3_queued_callback_suppresses_send": (
            _world(handles=[_handle(liveness="ended", callback="queued")]),
            {"kind": "suppress", "id": "h-0007"},
        ),
        "H3s_started_callback_suppresses_send": (
            _world(handles=[_handle(liveness="ended", callback="started")]),
            {"kind": "suppress", "id": "h-0007"},
        ),
        "H4_terminal_summary_opens_result_unprocessed": (
            _world(
                handles=[
                    _handle(
                        liveness="ended",
                        summary_ok=True,
                        callback="terminal",
                    )
                ]
            ),
            {"kind": "opens", "class": "result_unprocessed"},
        ),
        "H4_not_admitted_opens_result_unprocessed": (
            _world(
                handles=[
                    _handle(
                        liveness="replaced",
                        summary_ok=False,
                        stage_ok=True,
                        callback="not_admitted",
                    )
                ]
            ),
            {"kind": "opens", "class": "result_unprocessed"},
        ),
        "H4_unavailable_callback_holds": (
            _world(
                handles=[
                    _handle(
                        liveness="ended",
                        summary_ok=True,
                        callback="unavailable",
                    )
                ]
            ),
            {"kind": "hold", "id": "h-0007"},
        ),
        "H5_ended_without_summary_opens_worker_lost": (
            _world(handles=[ended]),
            {"kind": "opens", "class": "worker_lost"},
        ),
        "H5_replaced_without_summary_opens_worker_lost": (
            _world(
                handles=[
                    _handle(liveness="replaced", unit_result=None, callback="absent")
                ]
            ),
            {"kind": "opens", "class": "worker_lost"},
        ),
        "H6_absent_after_previous_scan_opens_worker_lost": (
            _world(
                handles=[
                    _handle(
                        liveness="absent",
                        output_files=False,
                        in_previous=True,
                        unit_result=None,
                    )
                ]
            ),
            {"kind": "opens", "class": "worker_lost"},
        ),
        "H6_absent_on_the_registration_scan_is_quiet": (
            _world(
                handles=[
                    _handle(
                        liveness="absent",
                        output_files=False,
                        in_previous=False,
                        unit_result=None,
                    )
                ]
            ),
            {"kind": "absent", "class": "worker_lost"},
        ),
        "W1_open_ask_is_quiet": (
            _world(
                asks={"Q1": "open"},
                handles=[_handle(consumed=_wait("ask", ref="asks.md#Q1"))],
            ),
            {"kind": "quiet", "id": "h-0007"},
        ),
        "W2_answered_ask_opens_wait_resolved": (
            _world(
                asks={"Q1": "answered"},
                workstreams=[_ws(brief="")],
                handles=[_handle(consumed=_wait("ask", ref="asks.md#Q1"))],
            ),
            {"kind": "opens", "class": "wait_resolved"},
        ),
        "W3_open_blocker_is_quiet": (
            _world(
                members=[_member(id="linear-900", state="in_progress")],
                handles=[_handle(consumed=_wait("blocker", ref="linear-900"))],
            ),
            {"kind": "quiet", "id": "h-0007"},
        ),
        "W4_finished_blocker_opens_wait_resolved": (
            _world(
                workstreams=[_ws(brief="")],
                members=[_member(id="linear-900", state="done", claim=None)],
                handles=[_handle(consumed=_wait("blocker", ref="linear-900"))],
            ),
            {"kind": "opens", "class": "wait_resolved"},
        ),
        "W5_quota_before_resume_is_quiet": (
            _world(
                handles=[
                    _handle(
                        consumed=_wait("quota", resume_after="2026-11-23T00:00:00Z")
                    )
                ]
            ),
            {"kind": "quiet", "id": "h-0007"},
        ),
        "W6_quota_due_opens_wait_resolved": (
            _world(
                workstreams=[_ws(brief="")],
                handles=[
                    _handle(
                        consumed=_wait("quota", resume_after="2026-11-22T00:00:00Z")
                    )
                ],
            ),
            {"kind": "opens", "class": "wait_resolved"},
        ),
        "W7_missing_ask_opens_wait_unresolvable": (
            _world(
                workstreams=[_ws(brief="")],
                asks={},
                handles=[_handle(consumed=_wait("ask", ref="asks.md#Q1"))],
            ),
            {"kind": "opens", "class": "wait_unresolvable"},
        ),
        "W7_unreadable_asks_are_not_wait_unresolvable": (
            _world(
                asks_complete=False,
                handles=[_handle(consumed=_wait("ask", ref="asks.md#Q1"))],
            ),
            {"kind": "absent", "class": "wait_unresolvable"},
        ),
    }


def _member_gate_rows(cover, ended):
    return {
        "M1_done_member_stays_history": (
            _world(members=[_member(state="done")]),
            {"kind": "quiet", "id": "linear-131"},
        ),
        "M1_archived_listed_member_stays_history": (
            _world(members=[_member(state="in_progress", archived=True)]),
            {"kind": "quiet", "id": "linear-131"},
        ),
        "M2_other_claim_label_is_quiet": (
            _world(
                members=[
                    _member(claim={"label": "other-mgr", "marker": "c9", "at": _AT})
                ]
            ),
            {"kind": "quiet", "id": "linear-131"},
        ),
        "M3_backlog_is_quiet": (
            _world(members=[_member(state="backlog", claim=None)]),
            {"kind": "quiet", "id": "linear-131"},
        ),
        "M4_day_long_unchanged_state_stays_quiet": (
            _world(
                handles=[cover],
                members=[_member(tracker_updated="2026-11-18T00:00:00Z")],
            ),
            {"kind": "quiet", "id": "linear-131"},
        ),
        "M5_open_blocker_is_quiet": (
            _world(
                members=[
                    _member(blockers=[{"id": "linear-900", "state": "in_progress"}])
                ]
            ),
            {"kind": "quiet", "id": "linear-131"},
        ),
        "M5_open_wait_is_quiet": (
            _world(
                asks={"Q1": "open"},
                handles=[
                    _handle(
                        subject={"kind": "member", "id": "linear-131"},
                        consumed=_wait("ask", ref="asks.md#Q1"),
                    )
                ],
                members=[_member()],
            ),
            {"kind": "quiet", "id": "linear-131"},
        ),
        "M6_orphaned_owned_opens": (
            _world(members=[_member()]),
            {"kind": "opens", "class": "orphaned_owned"},
        ),
        "M6_stopped_member_is_quiet": (
            _world(
                handles=[
                    _handle(
                        subject={"kind": "member", "id": "linear-131"},
                        consumed=_consumed({"stopped": "operator"}),
                    )
                ],
                members=[_member()],
            ),
            {"kind": "quiet", "id": "linear-131"},
        ),
        "M7_missing_ownership_opens": (
            _world(members=[_member(claim=None)]),
            {"kind": "opens", "class": "missing_ownership"},
        ),
        "M8_ready_none_opens_ready_authorized": (
            _world(
                workstreams=[_ws(accepted_through="Spec")],
                members=[_member(state="ready", claim=None, assignee="none")],
            ),
            {"kind": "opens", "class": "ready_authorized"},
        ),
        "M8_ready_self_opens_ready_authorized": (
            _world(
                workstreams=[_ws(accepted_through="Spec")],
                members=[_member(state="ready", claim=None, assignee="self")],
            ),
            {"kind": "opens", "class": "ready_authorized"},
        ),
        "M8_ready_other_is_not_authorized": (
            _world(
                workstreams=[_ws(accepted_through="Spec")],
                members=[_member(state="ready", claim=None, assignee="other")],
            ),
            {"kind": "absent", "class": "ready_authorized"},
        ),
        "M9_unknown_assignee_is_not_a_wake": (
            _world(
                workstreams=[_ws(accepted_through="Spec")],
                members=[_member(state="ready", claim=None, assignee="unknown")],
            ),
            {"kind": "absent", "class": "ready_authorized"},
        ),
        "M9_without_spec_gate_is_not_a_wake": (
            _world(
                workstreams=[_ws(accepted_through="Brief")],
                members=[_member(state="ready", claim=None, assignee="none")],
            ),
            {"kind": "absent", "class": "ready_authorized"},
        ),
        "M10_reparented_out_is_notice_only": (
            _world(members=[_member(visibility="reparented_out")]),
            {"kind": "notice", "class": "membership_change"},
        ),
        "M10_inaccessible_is_notice_only": (
            _world(members=[_member(visibility="inaccessible")]),
            {"kind": "notice", "class": "membership_change"},
        ),
        "M10_unbound_is_notice_only": (
            _world(members=[_member(visibility="unbound")]),
            {"kind": "notice", "class": "membership_change"},
        ),
        "S1_open_brief_without_closing_done_opens_stalled_workstream": (
            _world(handles=[_handle(consumed=_consumed({"done": "Spec"}))]),
            {"kind": "opens", "class": "stalled_workstream"},
        ),
        "S1_stopped_workstream_is_quiet": (
            _world(handles=[_handle(consumed=_consumed({"stopped": "operator"}))]),
            {"kind": "absent", "class": "stalled_workstream"},
        ),
        "S1_closing_step_done_is_quiet": (
            _world(handles=[_handle(consumed=_consumed({"done": "Changelog"}))]),
            {"kind": "absent", "class": "stalled_workstream"},
        ),
        "S2_missing_brief_is_quiet": (
            _world(workstreams=[_ws(brief="")]),
            {"kind": "absent", "class": "stalled_workstream"},
        ),
        "G2_partial_tracker_skips_member_rows": (
            _world(
                tracker_complete=False,
                handles=[ended],
                members=[_member()],
            ),
            {"kind": "g2"},
        ),
        "G3_unknown_liveness_is_not_worker_lost": (
            _world(handles=[_handle(liveness="unknown", unit_result=None)]),
            {"kind": "absent", "class": "worker_lost"},
        ),
        "G4_workstream_pause_skips_rows": (
            _world(
                workstreams=[_ws(status="paused")],
                members=[_member()],
            ),
            {"kind": "skip", "id": "ws-alpha"},
        ),
        "G5_project_pause_evaluates_no_rows": (
            _world(project_status="paused", members=[_member()]),
            {"kind": "paused"},
        ),
        "G6_project_closed_closes_episodes": (
            _world(project_status="closed", members=[_member()]),
            {"kind": "close_all"},
        ),
        "G6_workstream_closed_closes_its_episodes": (
            _world(workstreams=[_ws(status="closed")], members=[_member()]),
            {"kind": "close_ws", "id": "ws-alpha"},
        ),
        "G7_done_workstream_still_runs_member_rules": (
            _world(
                workstreams=[_ws(status="done", accepted_through="Spec")],
                members=[
                    _member(id="linear-100", state="done", claim=None),
                    _member(
                        id="linear-150", state="ready", claim=None, assignee="none"
                    ),
                ],
            ),
            {"kind": "g7"},
        ),
    }


@pytest.mark.parametrize("name", list(_rows()), ids=lambda name: name)
def test_row(name):
    world, spec = _rows()[name]
    assert _matches(evaluate(world), spec)


def test_a6_day_long_claimed_item_with_a_running_handle_stays_quiet():
    world = _world(
        now="2026-11-22T12:00:00Z",
        handles=[
            _handle(
                liveness="running",
                unit_result=None,
                subject={"kind": "member", "id": "linear-131"},
            )
        ],
        members=[_member(tracker_updated="2026-11-18T00:00:00Z")],
    )
    assert _names(evaluate(world)) == []


def test_a7_parked_sibling_stays_quiet_while_the_other_wakes():
    parked = _member(id="linear-140")
    sibling = _member(id="linear-141")
    handle = _handle(
        id="h-0014",
        subject={"kind": "member", "id": "linear-140"},
        consumed=_wait("ask", ref="asks.md#Q1"),
    )
    world = _world(
        asks={"Q1": "open"},
        handles=[handle],
        members=[parked, sibling],
    )
    result = evaluate(world)
    woken = [
        item.subject["id"]
        for item in result.intents
        if item.class_name == "orphaned_owned"
    ]
    assert woken == ["linear-141"]


def test_a8_done_workstream_still_authorizes_a_new_ready_member():
    world = _world(
        workstreams=[_ws(status="done", accepted_through="Spec")],
        members=[
            _member(id="linear-100", state="done", claim=None, assignee="none"),
            _member(id="linear-150", state="ready", claim=None, assignee="none"),
        ],
    )
    assert _names(evaluate(world)) == ["ready_authorized"]


def test_a12_gather_wait_answer_and_unfinished_close():
    quiet = evaluate(
        _world(
            asks={"Q1": "open"},
            handles=[_handle(consumed=_wait("operator", ref="asks.md#Q1"))],
        )
    )
    answered = evaluate(
        _world(
            asks={"Q1": "answered"},
            workstreams=[_ws(brief="")],
            handles=[_handle(consumed=_wait("operator", ref="asks.md#Q1"))],
        )
    )
    stopped = evaluate(
        _world(handles=[_handle(consumed=_consumed({"stopped": "operator"}))])
    )
    later = evaluate(_world(handles=[_handle(consumed=_consumed({"done": "Spec"}))]))
    assert _names(quiet) == []
    assert _names(answered) == ["wait_resolved"]
    assert "stalled_workstream" not in _names(stopped)
    assert "stalled_workstream" in _names(later)


def _episode():
    return {
        "id": "E-1-1",
        "class": "result_unprocessed",
        "subject": {"kind": "handle", "id": "h-0007"},
        "workstream": "ws-alpha",
        "owner": "",
        "evidence": {"callback": "terminal"},
        "delivery": {"state": "undelivered"},
        "notice": {"no_progress": None, "undeliverable": None},
        "closed_scan": None,
    }


def _apply(existing, result, scan):
    return reconcile(
        existing,
        result.intents,
        scan=scan,
        suppress=result.suppress,
        hold=result.hold,
        close_workstreams=result.close_workstreams,
        close_all=result.close_all,
        skip_workstreams=result.skip_workstreams,
    )


def test_h3_and_h3s_suppress_the_send_set():
    kept = []
    for callback in ("queued", "started"):
        result = evaluate(
            _world(handles=[_handle(liveness="ended", callback=callback)])
        )
        merged = _apply([_episode()], result, 2)
        open_rows = [row for row in merged if row.get("closed_scan") is None]
        kept.append(
            len(open_rows) == 1
            and open_rows[0]["id"] == "E-1-1"
            and open_rows[0]["delivery"]["state"] == "undelivered"
        )
    assert kept == [True, True]


def test_one_result_unprocessed_episode_across_callback_moves():
    base = {
        "liveness": "ended",
        "summary_ok": True,
        "callback": "terminal",
        "unit_result": "success",
    }
    opened = _apply([], evaluate(_world(handles=[_handle(**base)])), 1)
    current = opened
    same = []
    for callback in (
        "failed",
        "absent",
        "not_admitted",
        "queued",
        "started",
        "terminal",
    ):
        moved = {**base, "callback": callback}
        result = evaluate(_world(handles=[_handle(**moved)]))
        current = _apply(current, result, 2)
        rows = [
            row
            for row in current
            if row["class"] == "result_unprocessed" and row.get("closed_scan") is None
        ]
        same.append(len(rows) == 1 and rows[0]["id"] == opened[0]["id"])
    consumed = _handle(**{**base, "consumed": _consumed({"done": "Changelog"})})
    closed = _apply(current, evaluate(_world(handles=[consumed])), 3)
    left = [
        row
        for row in closed
        if row["class"] == "result_unprocessed" and row.get("closed_scan") is None
    ]
    assert same == [True, True, True, True, True, True]
    assert left == []
