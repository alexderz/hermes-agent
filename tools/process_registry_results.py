"""Bounded, profile-local receipts for completed terminal processes.

Receipts are read through process_manage, never replayed as notifications or
adopted as live PIDs. Each producer writes its own file so independent one-shot
parents cannot overwrite each other's results in the running-PID checkpoint.
"""

import json
import logging
import re
import time
from hermes_dir_acl import make_user_dir

from hermes_constants import get_hermes_home
from persistence import STORE_FAILURES
from utils import atomic_json_write

logger = logging.getLogger("tools.process_registry")

RESULT_RETENTION_SECONDS = 7 * 24 * 60 * 60
MAX_RETAINED_RESULTS = 64
_RESULT_FIELDS = (
    "id", "command", "cwd", "task_id", "owner_task_id", "session_key",
    "parent_session_id", "started_at", "exit_code", "completion_reason",
    "termination_source", "notify_on_complete",
)
# Extras. Old receipts omit them; load uses these defaults and must not KeyError.
_OPTIONAL_RESULT_FIELDS = {
    "service_unit": "",
    "service_invocation_id": "",
    "service_boot_id": "",
    "service_mode": "",
    "tool_call_id": "",
    "service_stop_intent": False,
    "admission_pending": False,
    "watcher_platform": "",
    "watcher_chat_id": "",
    "watcher_user_id": "",
    "watcher_user_name": "",
    "watcher_thread_id": "",
    "watcher_message_id": "",
    "watcher_interval": 0,
}


def _receipt_pending(path) -> bool:
    try:
        record = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return False
    return record.get("admission_pending") is True


def _result_paths():
    """Prune settled receipts by completion time. Pending service receipts stay extra."""
    directory = get_hermes_home() / "logs" / "process-results"
    cutoff = time.time() - RESULT_RETENTION_SECONDS
    pending = []
    retained = []
    for path in directory.glob("proc_*.json"):
        try:
            modified = path.stat().st_mtime
        except FileNotFoundError:
            continue  # Another producer pruned it.
        if _receipt_pending(path):
            pending.append(path)
            continue
        if modified < cutoff:
            path.unlink(missing_ok=True)
            continue
        retained.append((modified, path))
    retained.sort(key=lambda item: (item[0], item[1].name), reverse=True)
    for _, path in retained[MAX_RETAINED_RESULTS:]:
        path.unlink(missing_ok=True)
    settled = [path for _, path in retained[:MAX_RETAINED_RESULTS]]
    return pending + settled


def frozen_result_record(session) -> dict:
    """Copy one receipt. A live caller already holds ``session._lock``; this does not take it."""
    from tools.process_registry import MAX_OUTPUT_CHARS

    record = {key: getattr(session, key) for key in _RESULT_FIELDS}
    record.update({
        key: getattr(session, key, default) for key, default in _OPTIONAL_RESULT_FIELDS.items()
    })
    record["output"] = session.output_buffer[-MAX_OUTPUT_CHARS:]
    return record


def write_frozen_result(session_id: str, record: dict, *, strict: bool = False):
    """Write an already-copied receipt. Does not take the session lock."""
    from agent.redact import redact_sensitive_text, redact_terminal_output

    body = dict(record)
    body["output"] = redact_terminal_output(body.get("output") or "", body.get("command") or "", force=True)
    body["command"] = redact_sensitive_text(body.get("command") or "", code_file=True, force=True)
    directory = get_hermes_home() / "logs" / "process-results"
    try:
        from hermes_constants import assert_named_profile_home_live
        assert_named_profile_home_live(directory)
        make_user_dir(directory, mode=0o700, parents=True, exist_ok=True)
        atomic_json_write(directory / f"{session_id}.json", body, mode=0o600)
        _result_paths()
    except OSError:
        logger.warning("Could not retain completed process result %s", session_id, exc_info=True)
        return False if strict else None
    return True if strict else None


def save_completed_result(session, *, strict: bool = False):
    """Retain *session*'s completion receipt under this profile's logs. A hosted agent's process
    has none on this host: its command and output are the tenant's, kept in the live registry only."""
    if session.sandbox_key:
        return False if strict else None
    with session._lock:
        record = frozen_result_record(session)
    return write_frozen_result(session.id, record, strict=strict)


def _owns_result(owner: str, parent: str | None) -> bool:
    if not parent:
        return False
    if owner == parent:
        return True
    from persistence_assembly import open_persistence_reader, profile_scope

    # Pure lineage read on the hot path of every retained-result load; a writable open here
    # was one more writer handle per call inside the gateway (#100896).
    with open_persistence_reader(profile_scope().profile_dir) as persistence:
        return persistence.lineage.tip(parent) == owner


def load_completed_results(prefix: str = "") -> dict:
    """Restore read-only snapshots; no process handles, watchers, or queue events."""
    from tools.process_registry import ProcessSession

    from gateway.session_context import get_session_env
    from tools.environments.sandbox_scope import hosted_scope

    owner = get_session_env("HERMES_SESSION_ID", "")
    # A hosted agent's processes leave no receipt here and it sees no local one: never read or prune them.
    if not owner or hosted_scope() is not None:
        return {}
    results = {}
    try:
        paths = _result_paths()
    except OSError:
        logger.warning("Could not read retained process results", exc_info=True)
        return results
    for path in paths:
        if not path.stem.startswith(prefix):
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8-sig"))
            if record["id"] != path.stem or not re.fullmatch(r"proc_[\w]+", record["id"]):
                continue
            if not _owns_result(owner, record.get("parent_session_id")):
                continue
            optional = {key: record.get(key, default) for key, default in _OPTIONAL_RESULT_FIELDS.items()}
            session = ProcessSession(
                **{key: record[key] for key in _RESULT_FIELDS},
                **optional,
                # Receipts written before processes carried a sandbox are a local activity's.
                sandbox_key=record.get("sandbox_key", ""), exited=True, output_buffer=record["output"],
            )
            session._completion_event.set()
            results[session.id] = session
        except (OSError, ValueError, KeyError, TypeError, *STORE_FAILURES):
            logger.debug("Skipping unreadable process result %s", path.name, exc_info=True)
    return results


def read_session_log(registry, session_id: str, offset: int | None = None, limit: int = 200) -> dict:
    """Read the full output log with optional pagination by lines."""
    from tools.ansi_strip import strip_ansi
    from tools.process_registry import _not_found

    session = registry.get(session_id)
    if session is None:
        return _not_found(session_id)
    with session._lock:
        full_output = strip_ansi(session.output_buffer)
        exited, finalizing = session.exited, registry._reader_finalizing(session)
    lines = full_output.splitlines()
    total_lines = len(lines)
    # An explicit offset=0 means "start from the first line" — previously it was conflated with the
    # default and silently returned the TAIL instead of the head (same falsy-coercion class as the
    # wait() timeout guard; salvaged from PR #60004, credit @isheng-eqi).
    if offset is None and limit > 0:
        selected = lines[-limit:]
        observed_completion_output = bool(selected) or total_lines == 0
    else:
        offset = offset or 0
        selected = lines[offset:offset + limit]
        stop = slice(offset, offset + limit).indices(total_lines)[1]
        observed_completion_output = total_lines == 0 or (bool(selected) and stop == total_lines)
    result = {
        **registry._status_head(session), "output": "\n".join(selected),
        "total_lines": total_lines, "showing": f"{len(selected)} lines"}
    if exited and observed_completion_output and not finalizing:
        registry._completion_consumed.add(session.id)
    return result
