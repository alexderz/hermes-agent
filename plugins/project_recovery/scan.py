"""Non-model scan entry.

Reads a validated binding, writes ``state/snapshot.json``, and appends
``state/notices.jsonl`` by temp-and-rename. It does not send a digest,
admit a turn, write a binding or handle, or enable a cron job.
``admission_lookup`` and ``receipt`` are supplied by the caller. An
absent lookup is not proof that a callback is absent and does not open H4.
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from ruamel.yaml.error import YAMLError

from plugins.project_recovery.actionability import Intent, evaluate, evaluate_handles
from plugins.project_recovery.authority import classify_authority_path
from plugins.project_recovery.binding import load_binding
from plugins.project_recovery.episodes import (
    apply_no_progress,
    load_episodes,
    notice_lines,
    reconcile,
    write_episodes,
)
from plugins.project_recovery.handles import (
    NextDone,
    NextHandle,
    NextStopped,
    NextWait,
    SubjectMember,
    load_handle,
)
from plugins.project_recovery.invocation import observe_liveness
from plugins.project_recovery.mapping import Err, Ok, load_mapping
from plugins.project_recovery.notices import append_notices, load_notices, notice_record
from plugins.project_recovery.readers import read_tracker
from plugins.project_recovery.snapshot import (
    carried_owners,
    carried_stalls,
    load_document,
    members_after,
    snapshot_document,
    tracker_was_incomplete,
    write_json,
)
from tools.mcp_readonly import call_mcp_tool_readonly

_UNIT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:_.@-]{0,200}$")
_STAGE = frozenset({"pass", "fail", "blocked", "needs_input"})
_WAKE_FALSE = '{"wakeAgent": false}'
_SCOPES = frozenset({"board", "watchdog"})


def run_scan(recovery_dir, *, admission_lookup=None, receipt=None, scope="board") -> int:
    """Return 0 after a notice or a silent line, or non-zero after a reason code."""
    try:
        code, lines, fresh_ids, scan_no, at = _run(
            Path(recovery_dir), admission_lookup, receipt, scope
        )
    except Exception:  # health: allow BLE001 -- prints internal, never a traceback
        print("internal", flush=True)
        return 1
    _emit(recovery_dir, lines, fresh_ids, scan_no, at)
    return code


def _emit(recovery, lines, fresh_ids, scan_no, at) -> None:
    """Print each line, then persist noticed for that line.

    A crash after ``print`` returns and before ``episodes.json`` is replaced
    can reprint the line. Stdout and the state file are not one transaction.
    """
    ids = list(fresh_ids)
    for index, line in enumerate(lines):
        print(line, flush=True)
        episode_id = ids[index] if index < len(ids) else None
        if episode_id:
            _mark_noticed(recovery, episode_id, scan_no, at)


def _mark_noticed(recovery, episode_id, scan_no, at) -> None:
    path = Path(recovery) / "state" / "episodes.json"
    loaded = load_episodes(path)
    if not isinstance(loaded, list):
        raise OSError("episodes")
    fresh = []
    for episode in loaded:
        if episode.get("id") != episode_id:
            continue
        delivery = episode.setdefault("delivery", {})
        if delivery.get("state") == "noticed":
            continue
        delivery["state"] = "noticed"
        fresh.append(episode)
    if not fresh:
        return
    write_episodes(path, loaded)
    append_notices(
        Path(recovery) / "state" / "notices.jsonl",
        [notice_record(episode, scan_no, at) for episode in fresh],
    )


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_unit_show(unit: str):
    """``systemctl --user show`` properties, or None when the read fails."""
    if (
        type(unit) is not str
        or not _UNIT.fullmatch(unit)
        or "/" in unit
        or ".." in unit
    ):
        return None
    try:
        proc = subprocess.run(
            [
                "systemctl",
                "--user",
                "show",
                "-p",
                "LoadState",
                "-p",
                "ActiveState",
                "-p",
                "Result",
                "-p",
                "InvocationID",
                "--",
                unit,
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return _parse_show(proc.stdout)


def _parse_show(text: str) -> dict:
    parsed = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        parsed[key] = value
    return parsed


def _run(recovery: Path, admission_lookup, receipt, scope="board"):
    if scope not in _SCOPES:
        return _outcome(1, ["scope_invalid"])
    watchdog = scope == "watchdog"
    loaded = _load_binding(recovery)
    if isinstance(loaded, str):
        _record_failure(recovery, "binding_invalid", None)
        return _outcome(1, ["binding_invalid"])
    binding, mapping = loaded
    previous = _load_snapshot(recovery)
    if previous == "state_unreadable":
        return _outcome(1, ["state_unreadable"])
    episodes = load_episodes(recovery / "state" / "episodes.json")
    if episodes == "state_unreadable":
        return _outcome(1, ["state_unreadable"])
    if load_notices(recovery / "state" / "notices.jsonl") == "state_unreadable":
        return _outcome(1, ["state_unreadable"])
    if binding.project.status == "paused":
        return _outcome(0, [_WAKE_FALSE])
    scan_no = _next_scan(previous)
    if watchdog:
        # No tracker read and no member state: handles, units and receipts only.
        tracker = _watchdog_tracker()
    else:
        _write_alias_cache(recovery, binding, mapping)
        tracker = read_tracker(
            recovery, binding, mapping, (previous or {}).get("members") or {}
        )
    asks, asks_ok = _read_asks(binding)
    views, units, handles_ok, observations, receipt_outage = _observe(
        recovery, binding, previous, admission_lookup, receipt
    )
    world = _world(binding, tracker, views, asks, asks_ok, receipt_outage)
    result = evaluate_handles(world) if watchdog else evaluate(world)
    owners = carried_owners(previous)
    stalls, due = _stalls(carried_stalls(previous), observations, _owner_idle(owners))
    intents = list(result.intents)
    intents.extend(_stall_intents(due))
    if not watchdog and tracker.get("complete"):
        if tracker_was_incomplete(previous) or _open_class(episodes, "tracker_incomplete"):
            intents.append(_recovered(binding.revision))
    if watchdog and not result.close_all:
        # Board episodes were not evaluated here, so leave them untouched.
        managed, retained = _split_board_episodes(episodes)
    else:
        managed, retained = episodes, []
    intents.extend(
        apply_no_progress(managed, scan=scan_no, owner_idle=_owner_idle(owners))
    )
    merged = reconcile(
        managed,
        intents,
        scan=scan_no,
        suppress=result.suppress,
        hold=result.hold,
        close_workstreams=result.close_workstreams,
        close_all=result.close_all,
        skip_workstreams=result.skip_workstreams,
    )
    merged = list(merged) + list(retained)
    at = utc_now()
    document = _document(
        scan_no,
        at,
        binding,
        tracker,
        handles_ok,
        asks_ok,
        owners,
        previous,
        units,
        stalls,
        watchdog=watchdog,
    )
    lines, fresh_ids = notice_lines(binding.project.id, merged, scan_no)
    state = recovery / "state"
    write_json(state / "snapshot.json", document)
    write_episodes(state / "episodes.json", merged)
    if lines:
        return _outcome(0, lines, fresh_ids, scan_no, at)
    return _outcome(0, [_WAKE_FALSE])


def _outcome(code, lines, fresh_ids=(), scan_no=None, at=None):
    return code, list(lines), list(fresh_ids), scan_no, at


_ALIAS_STATES = (
    "backlog",
    "ready",
    "in_progress",
    "in_review",
    "done",
    "canceled",
)


def _write_alias_cache(recovery: Path, binding, mapping) -> None:
    """Project already-parsed aliases before hosted enumeration. No new parser."""
    aliases = getattr(mapping, "state_aliases", None)
    projected = _alias_projection(aliases)
    if projected is None:
        return
    write_json(
        recovery / "state" / "aliases.json",
        {
            "schema": "project-recovery-aliases/1",
            "binding_revision": binding.revision,
            "state_aliases": projected,
        },
    )


def _alias_projection(aliases):
    if not isinstance(aliases, dict):
        return None
    projected = {}
    for name in _ALIAS_STATES:
        native = _native_list(aliases.get(name))
        if native is None:
            return None
        projected[name] = native
    return projected


def _native_list(values):
    if type(values) not in (tuple, list) or not values:
        return None
    native = []
    for item in values:
        if type(item) is not str or item == "":
            return None
        native.append(item)
    return native


def _load_binding(recovery: Path):
    path = recovery / "binding.yaml"
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        return "binding_invalid"
    try:
        from hermes_yaml import safe_load

        data = safe_load(text)
    except YAMLError:
        return "binding_invalid"
    if not isinstance(data, dict):
        return "binding_invalid"
    tracker = data.get("tracker") if isinstance(data.get("tracker"), dict) else {}
    mapping = _load_mapping(recovery, tracker.get("repo_skill"))
    if mapping is None:
        return "binding_invalid"
    loaded = load_binding(
        text,
        closed_verbs=call_mcp_tool_readonly.closed_verbs,
        mapping=mapping,
        recovery_dir=recovery,
    )
    if isinstance(loaded, Err):
        return "binding_invalid"
    if not isinstance(loaded, Ok):
        return "binding_invalid"
    return loaded.value, mapping


def _load_mapping(recovery: Path, skill):
    if type(skill) is not str or not skill:
        return None
    path = Path(skill)
    if not path.is_absolute():
        path = recovery / skill
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        return None
    loaded = load_mapping(text)
    if isinstance(loaded, Err):
        return None
    return loaded.value


def _load_snapshot(recovery: Path):
    loaded = load_document(recovery / "state" / "snapshot.json")
    if loaded == "state_unreadable":
        return loaded
    if loaded is not None and not isinstance(loaded, dict):
        return "state_unreadable"
    return loaded


def _next_scan(previous) -> int:
    if not isinstance(previous, dict) or type(previous.get("scan")) is not int:
        return 1
    return previous["scan"] + 1


def _record_failure(recovery: Path, class_name: str, revision) -> None:
    try:
        append_notices(
            recovery / "state" / "notices.jsonl",
            [{"class": class_name, "revision": revision}],
        )
    except (OSError, ValueError):
        return


def _read_asks(binding):
    found = {}
    complete = True
    for workstream in binding.workstreams:
        path = workstream.asks_file
        try:
            text = Path(path).read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError):
            complete = False
            continue
        found.update(_parse_asks(text))
    return found, complete


def _parse_asks(text: str) -> dict:
    current = None
    found = {}
    heading = re.compile(r"^##\s+([A-Za-z0-9_-]+)\b")
    status = re.compile(r"^(?:-\s*)?(?:\*\*)?Status(?:\*\*)?\s*:\s*([A-Za-z_]+)\s*$")
    for line in text.splitlines():
        head = heading.match(line.strip())
        if head:
            current = head.group(1)
            continue
        if current is None:
            continue
        match = status.match(line.strip())
        if match:
            found[current] = match.group(1).casefold()
    return found


def _observe(recovery, binding, previous, lookup, receipt):
    units_prior = (previous or {}).get("units") if isinstance(previous, dict) else {}
    if not isinstance(units_prior, dict):
        units_prior = {}
    handles, handles_ok = _load_handles(recovery, binding.outputs_root)
    views = []
    units = {}
    observations = []
    outage = lookup is None and bool(handles)
    for handle in handles:
        prior = (
            units_prior.get(handle.handle)
            if isinstance(units_prior.get(handle.handle), dict)
            else {}
        )
        view, unit, observed, handle_outage = _one_handle(
            handle, prior, binding.outputs_root, lookup, receipt
        )
        views.append(view)
        units[handle.handle] = unit
        observations.extend(observed)
        outage = outage or handle_outage
    return views, units, handles_ok, observations, outage


def _load_handles(recovery, outputs_root):
    directory = Path(recovery) / "handles"
    if not directory.is_dir():
        return [], True
    found = []
    ok = True
    for path in sorted(directory.glob("*.json")):
        loaded = load_handle(path, outputs_root=outputs_root)
        if isinstance(loaded, Err):
            ok = False
            continue
        found.append(loaded.value)
    return found, ok


def _one_handle(handle, prior, outputs_root, lookup, receipt):
    show = read_unit_show(handle.runtime.unit)
    recorded = prior.get("invocation_id")
    ever = bool(prior.get("ever_running"))
    if show is None:
        liveness, invocation, result, ever_running = (
            "unknown",
            _text(recorded),
            None,
            ever,
        )
    else:
        observed = observe_liveness(
            show,
            recorded_invocation_id=_text(recorded),
            ever_running=ever,
        )
        liveness = observed.state
        invocation = observed.recorded_invocation_id
        ever_running = observed.ever_running
        result = (
            show.get("Result") if liveness in {"ended", "replaced", "absent"} else None
        )
    callback, message_id, admission, outage = _callback(
        handle, prior, outputs_root, lookup, receipt
    )
    view = {
        "id": handle.handle,
        "workstream": handle.workstream,
        "subject": _subject(handle),
        "liveness": liveness,
        "unit_result": result if type(result) is str else None,
        "consumed": _consumed(handle),
        "summary_ok": _summary_ok(handle, outputs_root),
        "stage_ok": _stage_ok(handle, outputs_root),
        "callback": callback,
        "output_files": _output_files(handle, outputs_root),
        "in_previous": bool(prior),
        "owner": "",
    }
    unit = {
        "liveness": liveness,
        "invocation_id": invocation,
        "result": view["unit_result"],
        "callback_message_id": message_id,
        "ever_running": ever_running,
        "callback": callback,
    }
    observed = []
    if type(admission) is str and callback in {"queued", "started", "unknown"}:
        observed.append((admission, callback))
    return view, unit, observed, outage


def _text(value):
    if type(value) is str and value:
        return value
    return None


def _subject(handle):
    subject = handle.subject
    if isinstance(subject, SubjectMember):
        return {"kind": "member", "id": subject.id}
    return {"kind": "stage", "step": subject.step}


def _consumed(handle):
    if handle.consumed is None:
        return None
    return {"at": handle.consumed.at, "next": _next_dict(handle.consumed.next)}


def _next_dict(nxt):
    if isinstance(nxt, NextHandle):
        return {"handle": nxt.handle}
    if isinstance(nxt, NextWait):
        if nxt.kind == "quota":
            return {"wait": {"kind": "quota", "resume_after": nxt.resume_after}}
        return {"wait": {"kind": nxt.kind, "ref": nxt.ref}}
    if isinstance(nxt, NextDone):
        return {"done": nxt.step}
    if isinstance(nxt, NextStopped):
        return {"stopped": nxt.reason}
    return {}


def _summary_ok(handle, outputs_root) -> bool:
    return classify_authority_path(handle.outputs.summary, outputs_root).evidence


def _stage_ok(handle, outputs_root) -> bool:
    path = handle.outputs.stage_result
    if type(path) is not str:
        return False
    classified = classify_authority_path(path, outputs_root)
    if not classified.evidence or classified.resolved is None:
        return False
    try:
        data = json.loads(Path(classified.resolved).read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    return isinstance(data, dict) and data.get("status") in _STAGE


def _output_files(handle, outputs_root) -> bool:
    paths = (handle.outputs.summary, handle.outputs.report, handle.outputs.stage_result)
    return any(
        type(path) is str and classify_authority_path(path, outputs_root).evidence
        for path in paths
    )


def _callback(handle, prior, outputs_root, lookup, receipt):
    cached = (
        prior.get("callback_message_id")
        if type(prior.get("callback_message_id")) is str
        else None
    )
    if lookup is None:
        return "unavailable", cached, None, True
    path = handle.outputs.callback_receipt
    classified = classify_authority_path(path, outputs_root)
    if not classified.evidence:
        if cached:
            name, admission, outage = _from_lookup(cached, lookup, receipt)
            return name, cached, admission, outage
        if classified.reason == "missing":
            return "absent", None, None, False
        return "inaccessible", None, None, True
    body = _receipt_body(classified.resolved)
    if body == "failed":
        return "failed", cached, None, False
    if isinstance(body, str):
        name, admission, outage = _from_lookup(body, lookup, receipt)
        return name, body, admission, outage
    if cached:
        name, admission, outage = _from_lookup(cached, lookup, receipt)
        return name, cached, admission, outage
    return "inaccessible", cached, None, True


def _receipt_body(resolved):
    try:
        data = json.loads(Path(resolved).read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("result") in {"refused", "error"}:
        return "failed"
    message = data.get("message_id")
    if type(message) is str and message:
        return message
    return None


def _from_lookup(message, lookup, receipt):
    try:
        found = lookup(message)
    except Exception:  # health: allow BLE001 -- injected lookup failure is an outage
        return "unavailable", None, True
    if not isinstance(found, dict):
        return "unavailable", None, True
    outcome = found.get("outcome")
    if outcome == "proven_not_found":
        return "not_admitted", None, False
    if outcome == "conflict":
        return "conflict", None, True
    if outcome != "found":
        return "unavailable", None, True
    admission = found.get("admission_id")
    target = found.get("target_session_id")
    if receipt is None or type(admission) is not str:
        return "unavailable", None, True
    try:
        body = receipt(admission, session_id=target)
    except Exception:  # health: allow BLE001 -- injected receipt failure is an outage
        return "unavailable", None, True
    status = body.get("status") if isinstance(body, dict) else None
    if status in {"queued", "started", "terminal", "unknown"}:
        return status, admission, False
    return "unavailable", None, True


def _world(binding, tracker, views, asks, asks_ok, receipt_outage):
    owners = {item.id: item.owner.session for item in binding.workstreams}
    for view in views:
        view["owner"] = owners.get(view["workstream"], "")
    members = []
    if tracker.get("complete") and isinstance(tracker.get("members"), dict):
        for ident, record in tracker["members"].items():
            body = dict(record)
            body["id"] = ident
            members.append(body)
    return {
        "project_status": binding.project.status,
        "binding_revision": binding.revision,
        "tracker_complete": bool(tracker.get("complete")),
        "asks_complete": asks_ok,
        "asks": asks,
        "now": utc_now(),
        "handles": views,
        "members": members,
        "workstreams": [_workstream(item) for item in binding.workstreams],
        "receipt_outage": receipt_outage,
    }


def _workstream(item):
    return {
        "id": item.id,
        "status": item.status,
        "closing_step": item.closing_step,
        "claim_labels": list(item.owner.claim_labels),
        "brief": item.authority.brief,
        "accepted_through": item.authority.accepted_through,
        "owner": item.owner.session,
    }


def _owner_idle(owners):
    if not isinstance(owners, dict) or not owners:
        return None
    states = [
        body.get("state")
        for body in owners.values()
        if isinstance(body, dict) and type(body.get("state")) is str
    ]
    if not states:
        return None
    if any(state != "idle" for state in states):
        return False
    return True


def _stalls(previous, observations, owner_idle):
    updated = dict(previous)
    due = []
    seen = set()
    for admission, status in observations:
        if type(admission) is not str or admission in seen:
            continue
        seen.add(admission)
        prior = (
            updated.get(admission) if isinstance(updated.get(admission), dict) else {}
        )
        count = prior.get("idle_scans") if type(prior.get("idle_scans")) is int else 0
        if status in {"queued", "started"} and owner_idle is True:
            count += 1
        elif status in {"queued", "started"} and owner_idle is False:
            count = 0
        updated[admission] = {"status": status, "idle_scans": count}
        if status == "unknown" or count >= 2:
            due.append((admission, status))
    return updated, due


def _stall_intents(due):
    return [
        Intent(
            "delivery_stalled",
            {"kind": "admission", "id": admission},
            "",
            {"admission": admission, "status": status},
            True,
            "",
        )
        for admission, status in due
    ]


def _recovered(revision):
    return Intent(
        "tracker_recovered",
        {"kind": "source", "id": "tracker"},
        "",
        {"source": "tracker", "revision": revision},
        True,
        "",
    )


_BOARD_ONLY = frozenset(
    {
        "orphaned_owned",
        "missing_ownership",
        "ready_authorized",
        "stalled_workstream",
        "membership_change",
        "tracker_incomplete",
        "tracker_recovered",
    }
)

_TRACKER_WAITS = frozenset({"wait_resolved", "wait_unresolvable"})


def _board_owned(episode) -> bool:
    """True when the board scope, not the watchdog, resolves this episode."""
    class_name = episode.get("class")
    if class_name in _BOARD_ONLY:
        return True
    if class_name in _TRACKER_WAITS:
        # A blocker wait needs member state the watchdog never reads.
        return (episode.get("evidence") or {}).get("wait") == "blocker"
    return False


def _split_board_episodes(episodes):
    """Separate episodes this scan evaluated from the ones it did not."""
    managed = []
    retained = []
    for episode in episodes:
        if _board_owned(episode):
            retained.append(episode)
        else:
            managed.append(episode)
    return managed, retained


def _open_class(episodes, class_name) -> bool:
    return any(
        episode.get("class") == class_name and episode.get("closed_scan") is None
        for episode in episodes
    )


def _watchdog_tracker():
    """Not an observed board: the watchdog scope makes no tracker claim."""
    return {
        "complete": None,
        "error": None,
        "revision": None,
        "roots": {},
        "members": {},
        "scope": "watchdog",
    }


def _document(
    scan_no,
    at,
    binding,
    tracker,
    handles_ok,
    asks_ok,
    owners,
    previous,
    units,
    stalls,
    watchdog=False,
):
    prior = previous.get("members") if isinstance(previous, dict) else {}
    if watchdog:
        # A watchdog scan must not prune or invent membership it never read.
        members = prior if isinstance(prior, dict) else {}
    else:
        members = members_after(prior, tracker, scan_no)
    source = {
        "complete": bool(tracker.get("complete")),
        "revision": tracker.get("revision"),
        "roots": tracker.get("roots") or {},
        "error": tracker.get("error"),
    }
    if watchdog:
        source["scope"] = "watchdog"
        source["complete"] = None
    return snapshot_document(
        scan=scan_no,
        at=at,
        binding_revision=binding.revision,
        tracker=source,
        handles_complete=handles_ok,
        units_complete=True,
        asks_complete=asks_ok,
        owners=owners,
        members=members,
        units=units,
        stalls=stalls,
    )
