"""Pure actionability rows.

Gates and H/W/M/S rows read the scan's already-built world. One subject's
row does not suppress another subject's row. H3 and H3s keep an existing
``result_unprocessed`` episode out of the send set.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

_H4_CALLBACKS = frozenset({"terminal", "failed", "absent", "not_admitted"})
_OUTAGE = frozenset({"unavailable", "conflict", "inaccessible"})
_LIVE = frozenset({"running", "absent", "unknown", "ended", "replaced"})
_DONE = frozenset({"done", "canceled"})
_ACTIVE = frozenset({"in_progress", "in_review"})
_HISTORY_VISIBILITY = frozenset({"reparented_out", "inaccessible", "unbound"})


@dataclass(frozen=True)
class Intent:
    class_name: str
    subject: dict
    workstream: str
    evidence: dict
    notice: bool
    owner: str = ""


@dataclass(frozen=True)
class RowResult:
    intents: tuple
    suppress: frozenset
    hold: frozenset
    close_workstreams: frozenset
    close_all: bool
    skip_workstreams: frozenset
    project_paused: bool


def evaluate(world) -> RowResult:
    if world.get("project_status") == "paused":
        return _empty(project_paused=True, skip=_ids(world))
    if world.get("project_status") == "closed":
        return _empty(close_all=True)
    intents = []
    suppress = set()
    hold = set()
    close_ws = set()
    skip = set()
    if not world.get("tracker_complete", True):
        intents.append(_outage("tracker_incomplete", "tracker", world))
    if world.get("receipt_outage"):
        intents.append(_outage("receipt_outage", "receipt", world))
    if _any_unknown(world):
        intents.append(_outage("liveness_unknown", "liveness", world))
    for workstream in world.get("workstreams") or []:
        status = workstream.get("status")
        if status == "paused":
            skip.add(workstream["id"])
            continue
        if status == "closed":
            close_ws.add(workstream["id"])
            continue
        handles = _for_ws(world.get("handles") or [], workstream["id"])
        members = _for_ws(world.get("members") or [], workstream["id"])
        row = _open_workstream(world, workstream, handles, members)
        intents.extend(row[0])
        suppress.update(row[1])
        hold.update(row[2])
    return RowResult(
        tuple(intents),
        frozenset(suppress),
        frozenset(hold),
        frozenset(close_ws),
        False,
        frozenset(skip),
        False,
    )


def evaluate_handles(world) -> RowResult:
    """Watchdog scope: handle rows only, with no tracker membership.

    The same handle rows the board scope uses, minus every membership,
    workstream and stall rule. Blocker and member waits cannot be resolved
    without a tracker, so they stay quiet rather than reading as missing.
    """
    if world.get("project_status") == "paused":
        return _empty(project_paused=True, skip=_ids(world))
    if world.get("project_status") == "closed":
        return _empty(close_all=True)
    intents = []
    suppress = set()
    hold = set()
    if world.get("receipt_outage"):
        intents.append(_outage("receipt_outage", "receipt", world))
    if _any_unknown(world):
        intents.append(_outage("liveness_unknown", "liveness", world))
    for handle in world.get("handles") or []:
        kind, intent = _handle_row(handle, world)
        if kind == "suppress":
            suppress.add(handle["id"])
        elif kind == "hold":
            hold.add(handle["id"])
        elif kind == "open" and intent is not None:
            intents.append(intent)
    return RowResult(
        tuple(intents),
        frozenset(suppress),
        frozenset(hold),
        frozenset(),
        False,
        frozenset(),
        False,
    )


def _empty(*, project_paused=False, close_all=False, skip=()):
    return RowResult(
        (),
        frozenset(),
        frozenset(),
        frozenset(),
        close_all,
        frozenset(skip),
        project_paused,
    )


def _ids(world):
    return [item["id"] for item in world.get("workstreams") or []]


def _outage(class_name, source, world):
    revision = world.get("binding_revision")
    return Intent(
        class_name,
        {"kind": "source", "id": source},
        "",
        {"source": source, "revision": revision},
        True,
        "",
    )


def _any_unknown(world) -> bool:
    return any(
        handle.get("liveness") == "unknown" for handle in world.get("handles") or []
    )


def _for_ws(rows, workstream):
    return [row for row in rows if row.get("workstream") == workstream]


def _open_workstream(world, workstream, handles, members):
    intents = []
    suppress = set()
    hold = set()
    for handle in handles:
        kind, intent = _handle_row(handle, world)
        if kind == "suppress":
            suppress.add(handle["id"])
        elif kind == "hold":
            hold.add(handle["id"])
        elif kind == "open" and intent is not None:
            intents.append(intent)
    member_intents = []
    if world.get("tracker_complete", True):
        for member in members:
            member_intents.extend(_member_rows(member, world, handles, workstream))
        intents.extend(member_intents)
        if workstream.get("status") == "open":
            stalled = _stalled(workstream, world, handles, member_intents)
            if stalled is not None:
                intents.append(stalled)
    return intents, suppress, hold


def _handle_row(handle, world):
    if handle.get("liveness") == "unknown":
        return "quiet", None
    if handle.get("consumed"):
        return _consumed(handle, world)
    liveness = handle.get("liveness")
    callback = handle.get("callback")
    if liveness == "running":
        return "quiet", None
    if liveness in {"ended", "replaced"} and callback == "queued":
        return "suppress", None
    if liveness in {"ended", "replaced"} and callback == "started":
        return "suppress", None
    summary = bool(handle.get("summary_ok") or handle.get("stage_ok"))
    if liveness in {"ended", "replaced"} and summary and callback in _H4_CALLBACKS:
        return "open", _result(handle, callback)
    if liveness in {"ended", "replaced"} and summary and callback in _OUTAGE:
        return "hold", None
    if liveness in {"ended", "replaced"} and not summary:
        return "open", _lost(handle, "ended")
    if (
        liveness == "absent"
        and not handle.get("output_files")
        and handle.get("in_previous")
    ):
        return "open", _lost(handle, "absent")
    return "quiet", None


def _consumed(handle, world):
    nxt = (handle.get("consumed") or {}).get("next") or {}
    if "wait" not in nxt:
        return "quiet", None
    return _wait(handle, nxt["wait"], world)


def _wait(handle, wait, world):
    kind = wait.get("kind")
    if kind in {"ask", "operator"}:
        return _ask_wait(handle, wait, world)
    if kind == "blocker":
        return _blocker_wait(handle, wait, world)
    if kind == "quota":
        return _quota_wait(handle, wait, world)
    return "quiet", None


def _ask_wait(handle, wait, world):
    if not world.get("asks_complete", True):
        return "quiet", None
    section = str(wait.get("ref") or "").split("#")[-1]
    status = (world.get("asks") or {}).get(section)
    if status is None:
        return "open", _wait_intent(handle, "wait_unresolvable", wait, "missing")
    if status == "answered":
        return "open", _wait_intent(handle, "wait_resolved", wait, status)
    return "quiet", None


def _blocker_wait(handle, wait, world):
    if not world.get("tracker_complete", True):
        return "quiet", None
    state = _member_state(world, wait.get("ref"))
    if state is None:
        return "open", _wait_intent(handle, "wait_unresolvable", wait, "missing")
    if state in _DONE:
        return "open", _wait_intent(handle, "wait_resolved", wait, state)
    return "quiet", None


def _quota_wait(handle, wait, world):
    due = _due(world.get("now"), wait.get("resume_after"))
    if due is True:
        return "open", _wait_intent(handle, "wait_resolved", wait, "due")
    return "quiet", None


def _result(handle, callback):
    return _handle_intent(
        handle,
        "result_unprocessed",
        {
            "liveness": handle.get("liveness"),
            "unit_result": handle.get("unit_result") or "",
            "summary": "present" if handle.get("summary_ok") else "absent",
            "stage": "present" if handle.get("stage_ok") else "absent",
            "consumed": False,
            "callback": callback,
        },
        False,
    )


def _lost(handle, kind):
    evidence = {
        "liveness": handle.get("liveness"),
        "unit_result": handle.get("unit_result") or kind,
        "summary": "absent",
        "stage": "absent",
        "consumed": False,
    }
    if kind == "absent":
        evidence = {"liveness": "absent", "outputs": "none", "consumed": False}
    return _handle_intent(handle, "worker_lost", evidence, False)


def _handle_intent(handle, class_name, evidence, notice):
    return Intent(
        class_name,
        {"kind": "handle", "id": handle["id"]},
        handle.get("workstream") or "",
        evidence,
        notice,
        handle.get("owner") or "",
    )


def _wait_intent(handle, class_name, wait, status):
    return _handle_intent(
        handle,
        class_name,
        {"wait": wait.get("kind"), "ref": wait.get("ref") or "", "status": status},
        False,
    )


def _member_rows(member, world, handles, workstream):
    visibility = member.get("visibility")
    if visibility in _HISTORY_VISIBILITY:
        return [_membership(member, workstream)]
    if member.get("archived") or member.get("state") in _DONE:
        return []
    if visibility != "listed":
        return []
    if member.get("state") == "backlog":
        return []
    claim = member.get("claim")
    labels = set(workstream.get("claim_labels") or [])
    if claim and claim.get("label") not in labels:
        return []
    if member.get("state") in _ACTIVE:
        return _active(member, world, handles, workstream, labels)
    if member.get("state") == "ready":
        return _ready(member, workstream)
    return []


def _membership(member, workstream):
    return Intent(
        "membership_change",
        {"kind": "member", "id": member["id"]},
        workstream.get("id") or "",
        {"visibility": member.get("visibility")},
        True,
        workstream.get("owner") or "",
    )


def _active(member, world, handles, workstream, labels):
    del labels
    if not member.get("claim"):
        return [
            _member_intent(
                member,
                workstream,
                "missing_ownership",
                {"state": member.get("state"), "claim": None},
            )
        ]
    if _covers(handles, member["id"]):
        return []
    if _open_blocker(member) or _latest_open_wait(handles, member, world):
        return []
    latest = _latest(handles, member_id=member["id"])
    if _stopped(latest):
        return []
    return [
        _member_intent(
            member, workstream, "orphaned_owned", _orphan_evidence(member, latest)
        )
    ]


def _ready(member, workstream):
    if _open_blocker(member) or member.get("claim"):
        return []
    assignee = member.get("assignee")
    accepted = workstream.get("accepted_through")
    if assignee == "unknown" or accepted != "Spec":
        return []
    if assignee not in {"none", "self"}:
        return []
    return [
        _member_intent(
            member,
            workstream,
            "ready_authorized",
            {"state": "ready", "assignee": assignee, "accepted_through": accepted},
        )
    ]


def _member_intent(member, workstream, class_name, evidence):
    return Intent(
        class_name,
        {"kind": "member", "id": member["id"]},
        workstream.get("id") or "",
        evidence,
        False,
        workstream.get("owner") or "",
    )


def _orphan_evidence(member, latest):
    claim = member.get("claim") or {}
    blockers = sorted(
        f"{item.get('id')}:{item.get('state')}" for item in member.get("blockers") or []
    )
    return {
        "state": member.get("state"),
        "claim": claim.get("label"),
        "marker": claim.get("marker"),
        "blockers": blockers,
        "latest": None if latest is None else latest.get("id"),
        "next": _next_name(latest),
    }


def _covers(handles, member_id) -> bool:
    for handle in handles:
        subject = handle.get("subject") or {}
        if subject.get("kind") != "member" or subject.get("id") != member_id:
            continue
        if handle.get("consumed"):
            continue
        if handle.get("liveness") in _LIVE:
            return True
    return False


def _open_blocker(member) -> bool:
    for blocker in member.get("blockers") or []:
        if blocker.get("state") not in _DONE:
            return True
    return False


def _latest_open_wait(handles, member, world) -> bool:
    latest = _latest(handles, member_id=member["id"])
    if latest is None:
        return False
    nxt = (latest.get("consumed") or {}).get("next") or {}
    wait = nxt.get("wait")
    if not isinstance(wait, dict):
        return False
    kind = wait.get("kind")
    if kind in {"ask", "operator"}:
        section = str(wait.get("ref") or "").split("#")[-1]
        return (world.get("asks") or {}).get(section) == "open"
    if kind == "blocker":
        state = _member_state(world, wait.get("ref"))
        return state not in _DONE and state is not None
    if kind == "quota":
        return _due(world.get("now"), wait.get("resume_after")) is False
    return False


def _latest(handles, member_id=None, workstream=None):
    chosen = None
    for handle in handles:
        if not handle.get("consumed"):
            continue
        if member_id is not None:
            subject = handle.get("subject") or {}
            if subject.get("kind") != "member" or subject.get("id") != member_id:
                continue
        if workstream is not None and handle.get("workstream") != workstream:
            continue
        if chosen is None or _later(handle, chosen):
            chosen = handle
    return chosen


def _later(handle, chosen) -> bool:
    left = (handle.get("consumed") or {}).get("at") or ""
    right = (chosen.get("consumed") or {}).get("at") or ""
    if left != right:
        return left > right
    return handle.get("id", "") > chosen.get("id", "")


def _stopped(latest) -> bool:
    if latest is None:
        return False
    return "stopped" in ((latest.get("consumed") or {}).get("next") or {})


def _next_name(latest):
    if latest is None:
        return None
    nxt = (latest.get("consumed") or {}).get("next") or {}
    if "stopped" in nxt:
        return "stopped"
    if "done" in nxt:
        return nxt.get("done")
    if "handle" in nxt:
        return nxt.get("handle")
    if "wait" in nxt:
        return "wait"
    return None


def _stalled(workstream, world, handles, member_intents):
    if not workstream.get("brief"):
        return None
    if _workstream_covered(handles):
        return None
    if _workstream_wait(world, handles, workstream["id"]):
        return None
    if any(
        not intent.notice and intent.subject.get("kind") == "member"
        for intent in member_intents
    ):
        return None
    latest = _latest(handles, workstream=workstream["id"])
    if _stopped(latest):
        return None
    if _finished(latest, workstream.get("closing_step")):
        return None
    states = sorted(
        member.get("state") or ""
        for member in _for_ws(world.get("members") or [], workstream["id"])
    )
    return Intent(
        "stalled_workstream",
        {"kind": "workstream", "id": workstream["id"]},
        workstream["id"],
        {
            "latest": None if latest is None else latest.get("id"),
            "next": _next_name(latest),
            "closing_step": workstream.get("closing_step"),
            "states": states,
        },
        False,
        workstream.get("owner") or "",
    )


def _workstream_covered(handles) -> bool:
    for handle in handles:
        if handle.get("consumed"):
            continue
        if handle.get("liveness") in _LIVE:
            return True
    return False


def _workstream_wait(world, handles, workstream) -> bool:
    for member in _for_ws(world.get("members") or [], workstream):
        if _open_blocker(member):
            return True
    for handle in handles:
        nxt = (handle.get("consumed") or {}).get("next") or {}
        wait = nxt.get("wait")
        if isinstance(wait, dict) and _wait_still_open(wait, world):
            return True
    return False


def _wait_still_open(wait, world) -> bool:
    kind = wait.get("kind")
    if kind in {"ask", "operator"}:
        section = str(wait.get("ref") or "").split("#")[-1]
        return (world.get("asks") or {}).get(section) == "open"
    if kind == "blocker":
        state = _member_state(world, wait.get("ref"))
        return state not in _DONE and state is not None
    if kind == "quota":
        return _due(world.get("now"), wait.get("resume_after")) is False
    return False


def _finished(latest, closing) -> bool:
    if latest is None:
        return False
    return ((latest.get("consumed") or {}).get("next") or {}).get("done") == closing


def _member_state(world, ref):
    if type(ref) is not str:
        return None
    for member in world.get("members") or []:
        if member.get("id") == ref:
            return member.get("state")
    return None


def _due(now, resume_after):
    if type(now) is not str or type(resume_after) is not str:
        return None
    try:
        left = datetime.fromisoformat(now)
        right = datetime.fromisoformat(resume_after)
    except ValueError:
        return None
    return left >= right
