"""Operational scan entry for one recovery directory.

``main`` is the process entry. It does not create a cron job, trust a
server, or read a credential. MCP discovery and the store resolver are
callables the process supplies: neither loader is part of the published
plugin API, and this module does not import them.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import time
from pathlib import Path

from ruamel.yaml.error import YAMLError

from plugins.intercom import address, client, profiles, record
from plugins.project_recovery import deliver, scan
from plugins.project_recovery.binding import load_binding
from plugins.project_recovery.episodes import load_episodes, write_episodes
from plugins.project_recovery.mapping import Err, Ok, load_mapping, matches_binding_id
from plugins.project_recovery.notices import (
    append_notices,
    format_notice,
    load_notices,
    notice_record,
)
from plugins.project_recovery.outbox import load_outbox
from plugins.project_recovery.snapshot import carried_owners, load_document, write_json

_WAKE_FALSE = '{"wakeAgent": false}'
_NOTICE_ONLY = "notice-only"
_WAKE = "wake"
_WATCHDOG = "watchdog"
_BOARD = "board"
_SCOPE_ENV = "PROJECT_RECOVERY_SCOPE"
_JOB_NAME = "recovery-workshop"
_JOB_SCHEDULE = "every 15m"
_ACTIVITIES = frozenset({"idle", "running", "closed"})


def selected_context(
    project_root=None,
    *,
    runtime_resolver=None,
    interpreter_resolver=None,
) -> dict:
    """Home, runtime, interpreter, and recovery cwd for this process.

    ``HERMES_RUNTIME_DIR`` wins, matching ``store_root``. A resolver runs
    only when that variable is unset. The interpreter resolver is optional;
    otherwise the interpreter is this process.
    """
    root = _project_root(project_root)
    return {
        "home": _home(),
        "runtime": _runtime_path(root, runtime_resolver),
        "interpreter": _interpreter_path(root, interpreter_resolver),
        "recovery": Path.cwd(),
    }


def job_specification(*, script: str, workdir: str, interpreter: str) -> dict:
    """Pure no-agent job fields. This does not call ``create_job``."""
    return {
        "name": _JOB_NAME,
        "schedule": _JOB_SCHEDULE,
        "prompt": "",
        "deliver": "local",
        "script": script,
        "workdir": workdir,
        "no_agent": True,
        "interpreter": interpreter,
    }


def specification_errors(spec: dict) -> list[str]:
    """Names of job fields that are not the accepted no-agent shape."""
    errors = []
    if spec.get("no_agent") is not True:
        errors.append("no_agent")
    if spec.get("deliver") != "local":
        errors.append("deliver")
    if spec.get("schedule") != _JOB_SCHEDULE:
        errors.append("schedule")
    if spec.get("prompt") not in ("", None):
        errors.append("prompt")
    if "attach_to_session" in spec:
        errors.append("attach_to_session")
    if "mirror_delivery" in spec:
        errors.append("mirror_delivery")
    if type(spec.get("script")) is not str or spec.get("script") == "":
        errors.append("script")
    workdir = spec.get("workdir")
    if type(workdir) is not str or not Path(workdir).is_absolute():
        errors.append("workdir")
    if type(spec.get("interpreter")) is not str or spec.get("interpreter") == "":
        errors.append("interpreter")
    return errors


def delivery_mode(environ=None) -> str:
    """``notice-only`` unless ``PROJECT_RECOVERY_DELIVERY`` is ``wake``."""
    source = os.environ if environ is None else environ
    raw = source.get("PROJECT_RECOVERY_DELIVERY", _NOTICE_ONLY)
    if raw is None or raw == "" or raw == _NOTICE_ONLY:
        return _NOTICE_ONLY
    if raw == _WAKE:
        return _WAKE
    return "refused"


def scan_scope(environ=None) -> str:
    """``watchdog`` (default) or ``board``; anything else is refused.

    Watchdog watches registered worker handles and their callbacks and makes
    no tracker claim, so it reads no board. Board is the full reconciliation
    and is opt-in.
    """
    source = os.environ if environ is None else environ
    raw = source.get(_SCOPE_ENV, _WATCHDOG)
    if raw is None or raw == "" or raw == _WATCHDOG:
        return _WATCHDOG
    if raw == _BOARD:
        return _BOARD
    return "refused"


def run(
    recovery_dir=None,
    *,
    discover=None,
    mode=None,
    runtime_resolver=None,
    interpreter_resolver=None,
) -> int:
    """Scan ``recovery_dir`` or the process cwd. Return the process status."""
    selected_context(
        runtime_resolver=runtime_resolver,
        interpreter_resolver=interpreter_resolver,
    )
    recovery = Path.cwd() if recovery_dir is None else Path(recovery_dir)
    chosen = delivery_mode() if mode is None else mode
    if chosen not in {_NOTICE_ONLY, _WAKE}:
        print("delivery_mode", flush=True)
        return 1
    scope = scan_scope()
    if scope == "refused":
        print("scope_invalid", flush=True)
        return 1
    loaded = _load_ready(recovery)
    if isinstance(loaded, str):
        _binding_failure(recovery, loaded)
        return 1
    if loaded.project.status == "paused":
        print(_WAKE_FALSE, flush=True)
        return 0
    if scope == _BOARD and loaded.tracker.adapter == "linear":
        # Discovery runs before the closed read. A refusal still uses the
        # accepted scan: the reader records the tracker incomplete, and
        # handle, ask, and unit rows stay on that path.
        _discovery_ok(discover, loaded)
    code, captured = _capture_scan(recovery, scope)
    if code != 0:
        _replay_failure(captured)
        return code
    if chosen == _NOTICE_ONLY:
        return _finish_notice(recovery, loaded, captured)
    return _finish_wake(recovery, loaded, captured)


def main(
    argv=None,
    *,
    discover=None,
    runtime_resolver=None,
    interpreter_resolver=None,
) -> int:
    """Script entry. ``argv`` is ignored. Discovery stays a supplied callable."""
    del argv
    return run(
        discover=discover,
        runtime_resolver=runtime_resolver,
        interpreter_resolver=interpreter_resolver,
    )


def _home():
    import hermes_constants

    return hermes_constants.get_hermes_home()


def _project_root(project_root) -> Path:
    if project_root is not None:
        return Path(project_root)
    from hermes_cli._startup_fast import project_root_str

    return Path(project_root_str())


def _runtime_path(project_root, runtime_resolver):
    override = os.environ.get("HERMES_RUNTIME_DIR", "").strip()
    if override:
        return Path(os.path.expanduser(override)).resolve()
    if runtime_resolver is None:
        return None
    try:
        found = runtime_resolver(project_root)
    except Exception:  # health: allow BLE001 -- a resolver failure means no override
        return None
    if found is None:
        return None
    return Path(found).expanduser().resolve()


def _interpreter_path(project_root, interpreter_resolver) -> Path:
    if interpreter_resolver is not None:
        try:
            found = interpreter_resolver(project_root)
        except Exception:  # health: allow BLE001 -- falls back to this interpreter
            found = None
        if found:
            return Path(found)
    return Path(sys.executable)


def _closed_verbs():
    from tools.mcp_readonly import call_mcp_tool_readonly

    return call_mcp_tool_readonly.closed_verbs


def _load_ready(recovery: Path):
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
    mapping = _mapping(recovery, tracker.get("repo_skill"))
    if mapping is None:
        return "binding_invalid"
    loaded = load_binding(
        text,
        closed_verbs=_closed_verbs(),
        mapping=mapping,
        recovery_dir=recovery,
    )
    if isinstance(loaded, Err) or not isinstance(loaded, Ok):
        return "binding_invalid"
    return loaded.value


def _mapping(recovery: Path, skill):
    if type(skill) is not str or skill == "":
        return None
    path = Path(skill)
    if not path.is_absolute():
        path = recovery / skill
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        return None
    loaded = load_mapping(text)
    if isinstance(loaded, Err) or not isinstance(loaded, Ok):
        return None
    return loaded.value


def _binding_failure(recovery: Path, reason: str) -> None:
    if reason == "binding_invalid":
        try:
            append_notices(
                recovery / "state" / "notices.jsonl",
                [{"class": "binding_invalid", "revision": None}],
            )
        except (OSError, ValueError):
            pass
    print(reason, flush=True)


def _discovery_ok(discover, binding) -> bool:
    server = binding.tracker.mcp_server
    if not callable(discover) or type(server) is not str or server == "":
        return False
    try:
        result = discover([server])
    except Exception:  # health: allow BLE001 -- a refusal is an incomplete board
        return False
    if result is True:
        return True
    return isinstance(result, list) and bool(result)


def _capture_scan(recovery: Path, scope: str):
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = scan.run_scan(
            recovery,
            admission_lookup=record.lookup_message_admission,
            receipt=client.receipt,
            scope=scope,
        )
    return code, buffer.getvalue()


def _replay_failure(captured: str) -> None:
    text = captured.strip()
    print(text or "internal", flush=True)


def _finish_notice(recovery, binding, captured: str) -> int:
    loaded = _load_rows(recovery)
    if loaded == "state_unreadable":
        print("state_unreadable", flush=True)
        return 1
    snapshot, episodes = loaded
    lines = _scan_lines(captured)
    scan_no = snapshot.get("scan") if type(snapshot.get("scan")) is int else 0
    at = snapshot.get("at") if type(snapshot.get("at")) is str else scan.utc_now()
    lines.extend(_would_be(recovery, binding.project.id, episodes, scan_no, at))
    _emit(lines)
    return 0


def _finish_wake(recovery, binding, captured: str) -> int:
    loaded = _load_rows(recovery)
    if loaded == "state_unreadable":
        print("state_unreadable", flush=True)
        return 1
    snapshot, episodes = loaded
    lines = _scan_lines(captured)
    owners = dict(carried_owners(snapshot))
    scan_no = snapshot.get("scan") if type(snapshot.get("scan")) is int else 0
    for owner, rows in _by_owner(episodes).items():
        observation = _observe_owner(recovery, binding, owner, rows)
        owners[owner] = _owner_record(observation)
        result = _deliver_owner(recovery, binding, owner, scan_no, rows, observation)
        _replace(episodes, result.get("episodes") or ())
        lines.extend(result.get("notices") or ())
    _write_owner_state(recovery, snapshot, episodes, owners)
    _emit(lines)
    return 0


def _deliver_owner(recovery, binding, owner, scan_no, rows, observation) -> dict:
    def send(target, text, *, key):
        if observation.get("activity") in {"unknown", "unreachable"}:
            return {
                "ok": False,
                "error": "not-reachable",
                "condition": "owner_unreachable",
            }
        return deliver.keyed_intercom_send(
            target,
            text,
            key=key,
            sender="recovery",
            ctx=profiles.Settings(),
            lister=client.list_sessions,
        )

    return deliver.scan_owner(
        recovery / "state",
        project=binding.project.id,
        owner=owner,
        scan=scan_no,
        intent_at=time.time(),
        episodes=rows,
        observation=observation,
        send=send,
    )


def _observe_owner(recovery, binding, owner, episodes) -> dict:
    resolved = address.resolve(owner, lister=client.list_sessions)
    listing = address.list_sessions(lister=client.list_sessions)
    activity, revision = _activity(owner, resolved, listing)
    offered, offered_message = _offered(recovery / "state", binding.project.id, owner)
    return {
        "activity": activity,
        "runtime_revision": revision,
        "binding_revision": binding.revision,
        "receipts": _receipts(episodes),
        "offered_turn": offered,
        "offered_message": offered_message,
    }


def _activity(owner, resolved, listing):
    if not isinstance(resolved, dict) or resolved.get("ok") is not True:
        return "unreachable", None
    if not isinstance(listing, dict) or listing.get("ok") is not True:
        return "unknown", None
    row = _listed(listing.get("sessions"), resolved.get("session_id"))
    if row is None:
        return "unknown", None
    state = row.get("state")
    if state not in _ACTIVITIES:
        return "unknown", None
    return state, _runtime_revision(owner, resolved.get("session_id"))


def _runtime_revision(owner, tip):
    """Physical row revision. The public list does not carry one."""
    try:
        from plugins.intercom.state import SessionReader

        reader = SessionReader()
    except Exception:  # health: allow BLE001 -- no reader means no revision
        return None
    try:
        physical = _physical_id(reader, owner, tip)
        if type(physical) is not str or physical == "":
            return None
        row = reader.get_session(physical)
    except Exception:  # health: allow BLE001 -- a failed read leaves it unknown
        return None
    finally:
        _close_reader(reader)
    if not isinstance(row, dict):
        return None
    revision = row.get("runtime_revision")
    if type(revision) is not int:
        return None
    return revision


def _physical_id(reader, owner, tip):
    """Local-receipt segment when it differs from the compression tip."""
    found = _segments(reader, owner, tip)
    if isinstance(found, dict) and type(owner) is str:
        chosen = found.get(owner)
        if type(chosen) is str and chosen:
            return chosen
    if isinstance(found, dict) and type(tip) is str:
        chosen = found.get(tip)
        if type(chosen) is str and chosen:
            return chosen
    if type(tip) is str and tip:
        return tip
    return None


def _segments(reader, owner, tip):
    store = getattr(reader, "store", None)
    lineage = getattr(store, "lineage", None)
    current = getattr(lineage, "current_segments", None)
    if not callable(current):
        return None
    ids = []
    for ident in (owner, tip):
        if type(ident) is str and ident and ident not in ids:
            ids.append(ident)
    if not ids:
        return None
    return current(ids)


def _close_reader(reader) -> None:
    close = getattr(reader, "close", None)
    if not callable(close):
        return
    try:
        close()
    except Exception:  # health: allow BLE001 -- must not mask the result
        return


def _listed(rows, session_id):
    if not isinstance(rows, list) or type(session_id) is not str:
        return None
    for row in rows:
        if isinstance(row, dict) and row.get("id") == session_id:
            return row
    return None


def _receipts(episodes) -> dict:
    found = {}
    for episode in episodes:
        delivery = episode.get("delivery") if isinstance(episode.get("delivery"), dict) else {}
        admission = delivery.get("admission")
        if type(admission) is not str or admission == "":
            continue
        target = _stored_target(delivery, admission)
        if type(target) is not str or target == "":
            continue
        body = client.receipt(admission, session_id=target)
        status = body.get("status") if isinstance(body, dict) else None
        if type(status) is str:
            found[admission] = status
    return found


def _stored_target(delivery, admission):
    """Admission target stored on the message. Not today's tip or the logical owner."""
    message = delivery.get("message")
    if type(message) is not str or message == "":
        return None
    try:
        looked = record.lookup_message_admission(message)
    except Exception:  # health: allow BLE001 -- a lookup failure skips the receipt
        return None
    if not isinstance(looked, dict) or looked.get("outcome") != "found":
        return None
    if looked.get("admission_id") != admission:
        return None
    target = looked.get("target_session_id")
    if type(target) is not str or target == "":
        return None
    return target


def _offered(state_dir, project, owner):
    current = load_outbox(state_dir, project, owner)
    if not isinstance(current, dict):
        return None, None
    message = current.get("message")
    if type(message) is not str or message == "":
        return None, None
    row = record.get(message)
    if not isinstance(row, dict):
        return None, message
    return row.get("offered_turn"), message


def _owner_record(observation) -> dict:
    body = {"state": observation.get("activity")}
    revision = observation.get("runtime_revision")
    if type(revision) is int:
        body["runtime_revision"] = revision
    return body


def _by_owner(episodes) -> dict:
    grouped = {}
    for episode in _actionable(episodes):
        owner = episode.get("owner")
        if not matches_binding_id(owner):
            continue
        grouped.setdefault(owner, []).append(episode)
    return grouped


def _actionable(episodes):
    rows = []
    for episode in episodes:
        if episode.get("closed_scan") is not None:
            continue
        kind = episode.get("class")
        if kind in deliver.WAKE_CLASSES or kind in deliver.NOTICE_CLASSES:
            rows.append(episode)
    return rows


def _replace(episodes, updated) -> None:
    by_id = {episode.get("id"): episode for episode in updated if isinstance(episode, dict)}
    for index, episode in enumerate(episodes):
        replacement = by_id.get(episode.get("id"))
        if replacement is not None:
            episodes[index] = replacement


def _write_owner_state(recovery, snapshot, episodes, owners) -> None:
    sources = dict(snapshot.get("sources") or {})
    sources["owners"] = owners
    updated = dict(snapshot)
    updated["sources"] = sources
    state = recovery / "state"
    write_json(state / "snapshot.json", updated)
    write_episodes(state / "episodes.json", episodes)


def _would_be(recovery, project, episodes, scan_no, at) -> list[str]:
    seen = _notice_ids(recovery)
    fresh = []
    lines = []
    for episode in _actionable(episodes):
        if episode.get("class") not in deliver.WAKE_CLASSES:
            continue
        delivery = episode.get("delivery") or {}
        if delivery.get("state") != "undelivered":
            continue
        if episode.get("id") in seen:
            continue
        lines.append(format_notice(project, episode))
        fresh.append(episode)
    if fresh:
        append_notices(
            recovery / "state" / "notices.jsonl",
            [notice_record(episode, scan_no, at) for episode in fresh],
        )
    return lines


def _notice_ids(recovery) -> set:
    text = load_notices(recovery / "state" / "notices.jsonl")
    found = set()
    if type(text) is not str:
        return found
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and type(row.get("id")) is str:
            found.add(row["id"])
    return found


def _scan_lines(captured: str) -> list[str]:
    lines = []
    for line in captured.splitlines():
        if not line.strip() or line.strip() == _WAKE_FALSE:
            continue
        lines.append(line)
    return lines


def _emit(lines) -> None:
    fresh = [line for line in lines if line and line != _WAKE_FALSE]
    if not fresh:
        print(_WAKE_FALSE, flush=True)
        return
    for line in fresh:
        print(line, flush=True)


def _load_rows(recovery: Path):
    snapshot = load_document(recovery / "state" / "snapshot.json")
    if snapshot == "state_unreadable":
        return "state_unreadable"
    if not isinstance(snapshot, dict):
        snapshot = {}
    episodes = load_episodes(recovery / "state" / "episodes.json")
    if not isinstance(episodes, list):
        return "state_unreadable"
    if load_notices(recovery / "state" / "notices.jsonl") == "state_unreadable":
        return "state_unreadable"
    return snapshot, episodes


if __name__ == "__main__":
    raise SystemExit(main())
