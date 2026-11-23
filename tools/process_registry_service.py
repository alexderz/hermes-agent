"""Durable user-service launch, show refresh, and stop for terminal(service=...).

One transient user unit per session. The short-lived systemd-run client is not
the session process, and ``systemd_unit`` stays empty so recovery does not stop
a live service when that field's pid is gone. The worker environment is exactly
``ProcessRegistry._spawn_env`` applied through ``env -i`` and a mode-0600 file.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shlex
import shutil
import subprocess
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional

logger = logging.getLogger("tools.process_registry")

_BOOT_ID = Path("/proc/sys/kernel/random/boot_id")
_SHOW_PROPS = (
    "InvocationID", "SubState", "Result", "ExecMainCode", "ExecMainStatus",
    "LoadState", "ActiveState", "NRestarts", "Id",
)
# The gateway's existing process watcher ticks at this interval. It rechecks an
# unresolved start. It is not a deadline and it does not stop the unit.
_RECHECK_SECONDS = 5
_UNRESOLVED_NOTE = (
    "The user message has priority. The job was not stopped and is not finished. "
    "Do not run it again. This step is not done."
)
_SCRIPT = """#!/bin/sh
probe=0
if [ "${1-}" = "--probe" ]; then
  probe=1
fi
env_file=@@ENV@@
command=@@CMD@@
log_file=@@LOG@@
set --
while IFS= read -r line || [ -n "$line" ]; do
  [ -n "$line" ] || continue
  key=${line%%=*}
  raw=${line#*=}
  eval "val=$raw" || exit 97
  set -- "$@" "$key=$val"
done < "$env_file"
if [ "$probe" = 1 ]; then
  exec /usr/bin/env -i "$@" /usr/bin/env -0
fi
exec /usr/bin/env -i "$@" /bin/sh -c "$command" > "$log_file" 2>&1
"""


def read_boot_id() -> str:
    try:
        return _BOOT_ID.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def user_bus_ready() -> bool:
    from tools.process_registry import systemd_user_bus_env
    return bool(systemd_user_bus_env().get("DBUS_SESSION_BUS_ADDRESS"))


def current_tool_call_id() -> str:
    from tools.approval_context import _approval_tool_call_id
    return str(_approval_tool_call_id.get() or "")


def service_survives_stop(session, source: str) -> bool:
    """Session-owned services outlive turn cleanup, agent close, and gateway shutdown.

    A delegated child that still owns the service is stopped when that child ends.
    An explicit stop (process.kill and the operator verbs) still reaches the unit.
    ``gateway_shutdown`` is not folded into the persist_on_release exception: native
    children, including persist_on_release, still die there.
    """
    if not getattr(session, "service_unit", ""):
        return False
    if source == "gateway_shutdown":
        return True
    if source in {"kill_all", "gateway_turn_timeout", "agent_close"}:
        if source == "agent_close" and _child_still_owns(session):
            return False
        return True
    return False


def _child_still_owns(session) -> bool:
    owner = str(getattr(session, "owner_task_id", "") or "")
    if owner.startswith("sa-"):
        return True
    try:
        from agent.delegation_context import is_delegated_child_context
        return bool(is_delegated_child_context())
    except ImportError:
        return False


def refresh_polled_service(registry, session) -> None:
    """One show refresh for a live service row. ``poll`` does not hold the registry lock."""
    if getattr(session, "service_unit", "") and not session.exited:
        refresh_service_session(registry, session)


def refresh_wait_session(registry, session):
    """Show refresh for a service; the detached-pid refresh for every other row."""
    if getattr(session, "service_unit", ""):
        refresh_service_session(registry, session)
        return session
    return registry._refresh_detached_session(session)


def await_unresolved_result(registry, session) -> dict:
    """Required-result wait released by timeout, steer, or a new user message.

    The unit keeps its invocation. The note is not the auto-notify "do more work" text,
    and the status is not ``timeout`` so that policy does not rewrite it.
    """
    from tools.process_registry import _output_tail

    on_await_released(registry, session)
    return {
        "status": "unresolved", "command": session.command, "output": _output_tail(session, 1000),
        "process_running": True, "exit_code": None, "note": _UNRESOLVED_NOTE,
        "service_invocation_id": session.service_invocation_id or "",
    }


def finish_await_wait(registry, session, timeout_note):
    """One last show after the wait clock. A late exit is the real result, not unresolved."""
    if getattr(session, "service_mode", "") != "await":
        return None
    if getattr(session, "service_unit", ""):
        refresh_service_session(registry, session)
    if session.exited and not registry._reader_finalizing(session):
        registry._completion_consumed.add(session.id)
        result = registry._exit_snapshot(session, "exited")
    else:
        result = await_unresolved_result(registry, session)
    if timeout_note:
        result["timeout_note"] = timeout_note
    return result


def prepare_listed_sessions(registry, include_retained: bool, include_service_receipts: bool) -> dict:
    """Refresh service rows, then the receipt map ``list_sessions`` merges under its lock.

    Pending service receipts are extra. Settled receipts stay behind ``include_retained``.
    An empty owner makes ``load_completed_results`` return nothing; that is intentional.
    ``include_service_receipts`` is the internal process-home projection. It also
    merges this home's pending service receipts without an owner check. It does
    not scan other profiles, and it does not admit or enqueue.
    """
    refresh_service_sessions(registry)
    reconcile_from_registry(registry)
    sessions: dict = {}
    if not (include_retained or include_service_receipts):
        return sessions
    from tools.process_registry_results import load_completed_results

    loaded = load_completed_results()
    if include_retained:
        sessions.update(loaded)
    if include_service_receipts:
        _merge_service_receipt_rows(sessions, loaded)
    return sessions


def _merge_service_receipt_rows(sessions: dict, loaded: dict) -> None:
    """Owner-loaded pending rows, then this process home's pending receipts.

    Rows already chosen for an owner win. A hosted scope adds nothing here.
    """
    for sid, loaded_session in loaded.items():
        pending = getattr(loaded_session, "admission_pending", False)
        if pending and getattr(loaded_session, "service_unit", ""):
            sessions.setdefault(sid, loaded_session)
    from hermes_constants import get_hermes_home

    for record in load_pending_service_receipts(get_hermes_home()):
        sid = record.get("id")
        if not isinstance(sid, str) or sid in sessions:
            continue
        try:
            sessions[sid] = _session_from_receipt(record)
        except (KeyError, TypeError, ValueError):
            logger.debug("Skipping unreadable pending service receipt %s", sid, exc_info=True)


def attention_for(session) -> Optional[str]:
    """Roster attention. A settled exit 0 (no pending admission) omits it.

    ``killed`` is not an attention value: callers read ``completion_reason`` first so a
    stop is not painted as ``failed``.
    """
    mode = getattr(session, "service_mode", "") or ""
    if not mode:
        return None
    if not session.exited:
        return "waiting" if mode == "await" else "running"
    if session.completion_reason == "killed":
        return None
    pending = bool(getattr(session, "admission_pending", False))
    if session.completion_reason == "lost":
        return "lost" if pending else None
    if session.exit_code == 0:
        return "ready" if pending else None
    if session.exit_code is None:
        return "waiting" if mode == "await" else "running"
    return "failed" if pending else None


def service_projection(session) -> dict:
    """Fields list/snapshot rows add for a service. Empty for an ordinary process."""
    unit = getattr(session, "service_unit", "") or ""
    mode = getattr(session, "service_mode", "") or ""
    if not unit and not mode:
        return {}
    fields: dict[str, Any] = {}
    if mode:
        fields["service_mode"] = mode
    if unit:
        fields["service_unit"] = unit
    attention = attention_for(session)
    if attention:
        fields["attention"] = attention
    if getattr(session, "admission_pending", False):
        fields["admission_pending"] = True
    started = getattr(session, "started_at", None)
    if started:
        fields["started_epoch"] = started
    parent = getattr(session, "parent_session_id", "")
    if isinstance(parent, str) and parent:
        fields["parent_session_id"] = parent
    route = getattr(session, "session_key", "")
    if isinstance(route, str) and route:
        fields["session_key"] = route
    return fields


def _command_timeout() -> float:
    from tools.process_registry_wait import max_wait_timeout
    return float(max_wait_timeout())


def _bus_env() -> dict:
    from tools.process_registry import systemd_user_bus_env
    return systemd_user_bus_env()


def _run(argv: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        argv, capture_output=True, text=True, timeout=_command_timeout(),
        check=False, env=_bus_env(),
    )


def systemctl_show(unit: str) -> Optional[dict[str, str]]:
    binary = shutil.which("systemctl")
    if not binary or not unit:
        return None
    args = [binary, "--user", "show", unit, "--no-pager"]
    for prop in _SHOW_PROPS:
        args.extend(["-p", prop])
    try:
        result = _run(args)
    except (OSError, subprocess.TimeoutExpired):
        logger.debug("systemctl show %s failed", unit, exc_info=True)
        return None
    parsed: dict[str, str] = {}
    for line in (result.stdout or "").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            parsed[key] = value
    if not parsed and result.returncode != 0:
        return None
    return parsed


def _unit_absent(show: Optional[dict[str, str]]) -> bool:
    if not show:
        return True
    return show.get("LoadState") == "not-found"


def _as_int(value: Optional[str]) -> Optional[int]:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def classify_show(session, show: Optional[dict[str, str]]) -> tuple:
    """One terminal decision from a fresh show. Unknown is not success.

    Returns ``("running",)``, ``("unresolved",)``, ``("lost",)``, ``("adopt", invocation)``,
    or ``("exit", code, reason, source)``.
    """
    from tools.process_registry_output_log import recorded_exit_code

    stored = str(getattr(session, "service_invocation_id", "") or "")
    if show is None:
        return ("unresolved",)
    load = show.get("LoadState") or ""
    live = show.get("InvocationID") or ""
    sub = show.get("SubState") or ""
    result = show.get("Result") or ""
    code = _as_int(show.get("ExecMainCode"))
    status = _as_int(show.get("ExecMainStatus"))
    intent = bool(getattr(session, "service_stop_intent", False))
    terminal_sub = sub in {"exited", "failed"}
    if intent and stored and not (live and live != stored):
        if terminal_sub or load == "not-found" or not live:
            return ("exit", -15, "killed", "unit_stopped")
    if load == "not-found":
        return ("lost",) if stored else ("unresolved",)
    if not live:
        return ("unresolved",)
    if not stored:
        return ("adopt", live)
    if live != stored:
        return ("lost",)
    if code in {5, 6} or not terminal_sub:
        return ("running",)
    if intent:
        return ("exit", -15, "killed", "unit_stopped")
    trap = recorded_exit_code(session.output_log) if session.output_log else None
    if result == "signal" and code == 2:
        return ("exit", -abs(status if status is not None else 9), "killed", "unit_signal")
    if result == "exit-code":
        return ("exit", 1 if status is None else status, "exited", "")
    if result == "timeout":
        return ("exit", 124 if status in (None, 0) else status, "exited", "unit_timeout")
    if result == "oom-kill":
        return ("exit", -9, "killed", "unit_oom")
    if result == "success" and code == 1 and status in (None, 0):
        if trap not in (None, 0):
            return ("exit", trap, "exited", "")
        return ("exit", 0, "exited", "")
    return ("unresolved",)


def tail_service_output(session) -> None:
    """Append new output-log bytes. Does not take the registry lock or a subprocess."""
    path = str(getattr(session, "output_log", "") or "")
    if not path:
        return
    offset = int(getattr(session, "_service_log_offset", 0) or 0)
    try:
        with open(path, "rb") as handle:
            handle.seek(offset)
            data = handle.read()
            session._service_log_offset = handle.tell()
    except OSError:
        return
    if data:
        session.append_output(data.decode("utf-8", "replace"))


def _stamp_routing(session) -> None:
    try:
        from gateway.session_context import get_session_env
        from tools.terminal_tool_background import _stamp_gateway_routing
        _stamp_gateway_routing(session, get_session_env)
    except Exception:
        logger.debug("service routing stamp failed", exc_info=True)


def _arm_recheck(registry, session, *, notify: bool) -> None:
    session.watcher_interval = _RECHECK_SECONDS
    if any(item.get("session_id") == session.id for item in registry.pending_watchers):
        for item in registry.pending_watchers:
            if item.get("session_id") == session.id:
                item["notify_on_complete"] = notify
        return
    registry.pending_watchers.append({
        "session_id": session.id,
        "check_interval": _RECHECK_SECONDS,
        "session_key": session.session_key,
        "platform": session.watcher_platform,
        "chat_id": session.watcher_chat_id,
        "user_id": session.watcher_user_id,
        "user_name": session.watcher_user_name,
        "thread_id": session.watcher_thread_id,
        "message_id": session.watcher_message_id,
        "notify_on_complete": notify,
        "parent_session_id": session.parent_session_id,
    })


def arm_service_notify(registry, session) -> None:
    """One later completion route. Does not by itself write admission_pending."""
    if session.notify_on_complete:
        _arm_recheck(registry, session, notify=True)
        return
    session.notify_on_complete = True
    _stamp_routing(session)
    _arm_recheck(registry, session, notify=True)
    registry._write_checkpoint()


def _release_await(registry, session) -> None:
    """The blocking await gave up. Arm delivery once an invocation is stored."""
    if session.service_invocation_id:
        arm_service_notify(registry, session)
        return
    _arm_recheck(registry, session, notify=False)
    registry._write_checkpoint()


def _watcher_payload(session) -> dict:
    from tools.process_registry import _WATCHER_ROUTE_KEYS
    return {
        "session_id": session.id,
        "check_interval": session.watcher_interval,
        "session_key": session.session_key,
        **{key: getattr(session, f"watcher_{key}") for key in _WATCHER_ROUTE_KEYS},
        "notify_on_complete": session.notify_on_complete,
        "parent_session_id": session.parent_session_id,
    }


def refresh_service_session(registry, session, *, publish: bool = True) -> None:
    """The only ``mark_exited`` path for a service row. No registry lock across systemctl.

    ``publish`` is false for checkpoint recovery: startup admits the pending receipt once.
    A live finish publishes through ``_move_to_finished``.
    """
    if not getattr(session, "service_unit", "") or session.exited:
        if getattr(session, "service_unit", "") and not session.exited:
            tail_service_output(session)
        return
    tail_service_output(session)
    boot = read_boot_id()
    stored_boot = str(session.service_boot_id or "")
    if stored_boot and boot and stored_boot != boot:
        _finish_exit(registry, session, -1, "lost", "", publish=publish)
        return
    show = systemctl_show(session.service_unit)
    decision = classify_show(session, show)
    if decision[0] == "adopt":
        session.service_invocation_id = decision[1]
        if not registry._write_checkpoint(strict=True):
            session.service_invocation_id = ""
            return
        if session.watcher_interval and not session.notify_on_complete:
            arm_service_notify(registry, session)
        decision = classify_show(session, show)
    if decision[0] == "lost":
        _finish_exit(registry, session, -1, "lost", "", publish=publish)
        return
    if decision[0] != "exit":
        return
    _finish_exit(registry, session, decision[1], decision[2], decision[3], publish=publish)
    if session.exited:
        _cleanup_unit_if_match(session)


def _outcome_cv(session) -> threading.Condition:
    """Condition on the session lock. ``_stop_phase`` is process-local, not a checkpoint field."""
    cond = getattr(session, "_outcome_cv", None)
    if cond is not None:
        return cond
    with session._lock:
        cond = getattr(session, "_outcome_cv", None)
        if cond is None:
            cond = threading.Condition(session._lock)
            session._outcome_cv = cond
        return cond


def _restore_undecided(session) -> None:
    """Caller holds the session lock. The row stays running."""
    session.exit_code = None
    session.admission_pending = False
    session.completion_reason = "exited"
    session.termination_source = ""


def service_identity(record: dict) -> Optional[tuple]:
    """Unit, boot, invocation, and tool id. An empty invocation is not an identity."""
    if not isinstance(record, dict):
        return None
    unit = str(record.get("service_unit") or "")
    invocation = str(record.get("service_invocation_id") or "")
    if not unit or not invocation:
        return None
    return (
        unit,
        str(record.get("service_boot_id") or ""),
        invocation,
        str(record.get("tool_call_id") or ""),
    )


def _field_conflict(left: dict, right: dict, key: str) -> bool:
    """Both sides recorded a value and they differ. A blank does not conflict."""
    owned = str(left.get(key) or "")
    other = str(right.get(key) or "")
    return bool(owned and other and owned != other)


def _identity_relation(left: dict, right: dict) -> str:
    """Match unit and invocation. Boot and tool conflict only when both are set.

    An empty invocation is not an identity. A memory invocation patched away
    from the checkpoint row is a different launch: do not adopt that row.
    """
    if not isinstance(left, dict) or not isinstance(right, dict):
        return "incomplete"
    if service_identity(left) is None or service_identity(right) is None:
        return "incomplete"
    if str(left.get("service_unit") or "") != str(right.get("service_unit") or ""):
        return "different"
    if str(left.get("service_invocation_id") or "") != str(right.get("service_invocation_id") or ""):
        return "different"
    if _field_conflict(left, right, "service_boot_id") or _field_conflict(left, right, "tool_call_id"):
        return "different"
    return "match"


def _has_outcome(record: dict) -> bool:
    if not isinstance(record, dict) or "exit_code" not in record:
        return False
    if record.get("exit_code") is not None:
        return True
    return record.get("completion_reason") in {"lost", "killed", "exited"}


def _outcome_tuple(record: dict) -> tuple:
    return (
        record.get("exit_code"),
        record.get("completion_reason") or "",
        record.get("termination_source") or "",
    )


def _read_json_list(path: Path) -> list:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return []
    return data if isinstance(data, list) else []


def _read_receipt(session_id: str, home=None) -> Optional[dict]:
    from hermes_constants import get_hermes_home

    root = get_hermes_home() if home is None else Path(home)
    path = Path(root) / "logs" / "process-results" / f"{session_id}.json"
    try:
        record = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    if not isinstance(record, dict) or record.get("id") != session_id:
        return None
    return record


def _profile_file_lock():
    """The existing processes.json lock. A second open of it deadlocks flock."""
    from hermes_cli.active_sessions import _FileLock
    from tools.process_registry import _checkpoint_path

    path = _checkpoint_path()
    return path, _FileLock(path.with_name(path.name + ".lock"))


def decide_service_commit(proposed: dict, *, row, receipt) -> tuple:
    """Adopt one outcome. Pure: no locks and no writes.

    A matching stop row overrides a stale show of 0. A matching receipt with no
    row is already the commit. A killed receipt cannot become success. A
    different complete identity is not this service.
    """
    if isinstance(receipt, dict) and _identity_relation(proposed, receipt) == "different":
        return ("refuse", proposed)
    # A non-matching row is not adopted and is not a reason to drop our own write.
    if not isinstance(row, dict) or _identity_relation(proposed, row) != "match":
        row = None
    row_rel = "match" if isinstance(row, dict) else "absent"
    rec_rel = _identity_relation(proposed, receipt) if isinstance(receipt, dict) else "absent"
    matched_row = row if row_rel == "match" else None
    matched_receipt = receipt if rec_rel == "match" else None
    if isinstance(matched_row, dict) and matched_row.get("service_stop_intent") is True:
        killed = dict(proposed)
        killed["exit_code"] = -15
        killed["completion_reason"] = "killed"
        killed["termination_source"] = "unit_stopped"
        killed["service_stop_intent"] = True
        if (
            isinstance(matched_receipt, dict)
            and matched_receipt.get("completion_reason") == "killed"
            and matched_receipt.get("admission_pending") is False
        ):
            killed["admission_pending"] = False
        return ("write", killed)
    if isinstance(matched_receipt, dict) and _has_outcome(matched_receipt):
        authoritative = matched_row is None or matched_receipt.get("completion_reason") == "killed"
        same = _outcome_tuple(matched_receipt) == _outcome_tuple(proposed)
        settled = matched_receipt.get("admission_pending") is False and proposed.get("admission_pending") is True
        if authoritative or not same or settled:
            return ("keep", matched_receipt)
    return ("write", proposed)


def commit_service_receipt(session, record: dict) -> Optional[dict]:
    """Re-read, adopt, and write under processes.json.lock.

    Caller may already hold the session condition. This does not take it, the
    registry lock, or systemctl, and it does not call ``_write_checkpoint``
    (that opens this same lock again). None means nothing was committed.
    """
    from tools.process_registry_results import write_frozen_result
    from utils import atomic_json_write

    if service_identity(record) is None:
        if write_frozen_result(session.id, record, strict=True) is False:
            return None
        return record
    path, lock = _profile_file_lock()
    try:
        with lock:
            entries = _read_json_list(path)
            row = next(
                (item for item in entries if isinstance(item, dict) and item.get("session_id") == session.id),
                None,
            )
            receipt = _read_receipt(session.id)
            action, adopted = decide_service_commit(record, row=row, receipt=receipt)
            if action == "refuse":
                return None
            if action == "write" and write_frozen_result(session.id, adopted, strict=True) is False:
                return None
            row_rel = _identity_relation(record, row) if isinstance(row, dict) else "absent"
            drop = (action == "write" and row_rel in {"match", "absent"}) or (
                action == "keep" and row_rel == "match"
            )
            if drop and isinstance(row, dict):
                remaining = [
                    item for item in entries
                    if not (isinstance(item, dict) and item.get("session_id") == session.id)
                ]
                atomic_json_write(path, remaining)
            return adopted
    except (OSError, RuntimeError):
        logger.warning("service outcome commit failed for %s", session.id, exc_info=True)
        return None


def peek_service_authority(session) -> dict:
    """Re-read the checkpoint row and receipt. Does not write or take the session lock."""
    ident = {
        "service_unit": getattr(session, "service_unit", ""),
        "service_boot_id": getattr(session, "service_boot_id", ""),
        "service_invocation_id": getattr(session, "service_invocation_id", ""),
        "tool_call_id": getattr(session, "tool_call_id", ""),
    }
    if service_identity(ident) is None:
        return {"kind": "none"}
    path, lock = _profile_file_lock()
    try:
        with lock:
            entries = _read_json_list(path)
            row = next(
                (item for item in entries if isinstance(item, dict) and item.get("session_id") == session.id),
                None,
            )
            receipt = _read_receipt(session.id)
    except (OSError, RuntimeError):
        return {"kind": "error"}
    row_rel = _identity_relation(ident, row) if isinstance(row, dict) else "absent"
    rec_rel = _identity_relation(ident, receipt) if isinstance(receipt, dict) else "absent"
    if row_rel == "different" or rec_rel == "different":
        return {"kind": "unrelated"}
    matched_row = row if row_rel == "match" else None
    matched_receipt = receipt if rec_rel == "match" and _has_outcome(receipt) else None
    if isinstance(matched_row, dict) and matched_row.get("service_stop_intent") is True:
        if not (isinstance(matched_receipt, dict) and matched_receipt.get("completion_reason") == "killed"):
            return {"kind": "stop"}
    if isinstance(matched_receipt, dict) and (
        matched_row is None or matched_receipt.get("completion_reason") == "killed"
    ):
        return {
            "kind": "committed",
            "outcome": _outcome_tuple(matched_receipt),
            "admission_pending": matched_receipt.get("admission_pending"),
        }
    if isinstance(matched_row, dict) and matched_row.get("service_stop_intent") is True:
        return {"kind": "stop"}
    return {"kind": "none"}


def _phase_after_durable_attempt(session, cv, authority: dict):
    """Caller holds the session condition. True: do not signal. None: intent did not land."""
    if session.exited or authority.get("kind") == "committed":
        if not session.exited:
            _apply_adopted_outcome(session, authority)
        if getattr(session, "_stop_phase", None) == "inflight":
            session._stop_phase = None
            cv.notify_all()
        return True
    if authority.get("kind") not in {"stop", "error"}:
        if getattr(session, "_stop_phase", None) == "inflight":
            session.service_stop_intent = False
            session._stop_phase = None
            cv.notify_all()
        return None
    session._stop_phase = "durable"
    cv.notify_all()
    return False


def _apply_adopted_outcome(session, authority: dict) -> None:
    """Caller holds the session lock. Memory records the adopted outcome."""
    code, reason, source = authority["outcome"]
    session.exit_code = code
    session.completion_reason = reason or "exited"
    session.termination_source = source or ""
    if "admission_pending" in authority and authority["admission_pending"] is not None:
        session.admission_pending = bool(authority["admission_pending"])
    if session.completion_reason != "killed":
        session.service_stop_intent = False
    session.mark_exited(session.exit_code, session.completion_reason, session.termination_source)


def _preserve_one_service_row(entry, disk_by_id: dict):
    if not isinstance(entry, dict) or not entry.get("service_unit"):
        return entry
    disk = disk_by_id.get(entry.get("session_id"))
    if isinstance(disk, dict):
        relation = _identity_relation(entry, disk)
        if relation == "different":
            return disk
        if relation == "match" and disk.get("service_stop_intent") is True:
            kept = dict(entry)
            kept["service_stop_intent"] = True
            return kept
        # A blank invocation is not an identity. It must not replace a stored
        # launch or a durable stop. An incomplete disk row with stop false is
        # still the pre-invocation handshake, so a complete memory entry upgrades it.
        if relation == "incomplete" and (
            service_identity(disk) is not None or disk.get("service_stop_intent") is True
        ):
            return disk
        return entry
    session_id = entry.get("session_id")
    receipt = _read_receipt(session_id) if isinstance(session_id, str) else None
    if isinstance(receipt, dict) and _has_outcome(receipt) and (
        _identity_relation(entry, receipt) == "match" or service_identity(entry) is None
    ):
        return None
    return entry


def preserve_service_checkpoint_rows(entries: list) -> list:
    """Caller holds processes.json.lock. Keep a durable stop; do not put a removed row back.

    Does not take the lock again and does not call ``_write_checkpoint``.
    """
    if not any(isinstance(item, dict) and item.get("service_unit") for item in entries):
        return list(entries)
    from tools.process_registry import _checkpoint_path

    on_disk = _read_json_list(_checkpoint_path())
    disk_by_id = {
        item.get("session_id"): item
        for item in on_disk
        if isinstance(item, dict) and isinstance(item.get("session_id"), str)
    }
    kept = []
    for entry in entries:
        preserved = _preserve_one_service_row(entry, disk_by_id)
        if preserved is not None:
            kept.append(preserved)
    return kept


def _finish_exit(registry, session, code: int, reason: str, source: str, *, publish: bool = True) -> bool:
    from tools.process_registry_results import frozen_result_record, save_completed_result

    # The show can flip to exited during the systemctl call that follows an empty tail.
    # Read the log again now, before the receipt snapshot, so the tool result has those bytes.
    tail_service_output(session)
    cv = _outcome_cv(session)
    with cv:
        while getattr(session, "_stop_phase", None) == "inflight":
            cv.wait()
        if session.exited:
            return True
        # Only a durable intent (checkpoint already landed, or a recovered row) is killed.
        # The in-flight bit is waited out above so a failed checkpoint cannot fabricate it.
        if session.service_stop_intent:
            code, reason, source = -15, "killed", "unit_stopped"
        session.exit_code = code
        session.completion_reason = reason
        session.termination_source = source
        session.admission_pending = bool(session.notify_on_complete)
        record = frozen_result_record(session)
        adopted = commit_service_receipt(session, record)
        if adopted is None:
            if not session.exited:
                _restore_undecided(session)
            return False
        code = adopted.get("exit_code", code)
        reason = adopted.get("completion_reason") or reason
        source = adopted.get("termination_source") or source
        session.exit_code = code
        session.completion_reason = reason
        session.termination_source = source
        if "admission_pending" in adopted:
            session.admission_pending = bool(adopted.get("admission_pending"))
        if "service_stop_intent" in adopted:
            session.service_stop_intent = bool(adopted.get("service_stop_intent"))
        elif reason == "killed" and source == "unit_stopped":
            session.service_stop_intent = True
        session.mark_exited(code, reason, source)
    if publish:
        registry._move_to_finished(session)
        return True
    # Recovery must not queue a second completion. Startup admits the receipt.
    saved_notify = session.notify_on_complete
    session.notify_on_complete = False
    try:
        registry._move_to_finished(session)
    finally:
        session.notify_on_complete = saved_notify
    save_completed_result(session, strict=True)
    return True


def _cleanup_unit_if_match(session) -> None:
    show = systemctl_show(session.service_unit)
    if show is None or _unit_absent(show):
        return
    live = show.get("InvocationID") or ""
    boot = read_boot_id()
    if not live or live != (session.service_invocation_id or ""):
        return
    if session.service_boot_id and boot and session.service_boot_id != boot:
        return
    binary = shutil.which("systemctl")
    if not binary:
        return
    for verb in ("stop", "reset-failed"):
        try:
            _run([binary, "--user", verb, session.service_unit])
        except (OSError, subprocess.TimeoutExpired):
            logger.debug("service cleanup %s %s failed", verb, session.service_unit, exc_info=True)
            return


def refresh_service_sessions(registry) -> None:
    with registry._lock:
        rows = [session for session in registry._running.values() if session.service_unit and not session.exited]
    for session in rows:
        refresh_service_session(registry, session)


def recover_service_entry(registry, entry: dict) -> bool:
    """Reattach one checkpointed service before the pid gate. Does not start a unit or a log reader."""
    from tools.process_registry import ProcessSession, _CHECKPOINT_DEFAULTS, _CHECKPOINT_FIELDS
    from tools.process_registry_output_log import adoptable_log

    session_id = entry.get("session_id")
    if not session_id or not entry.get("service_unit"):
        return False
    with registry._lock:
        if session_id in registry._running or session_id in registry._finished:
            return False
    fields = {name: entry.get(name, _CHECKPOINT_DEFAULTS.get(name)) for name in _CHECKPOINT_FIELDS}
    fields.update(
        command=entry.get("command", "unknown"),
        owner_task_id=entry.get("owner_task_id", "") or entry.get("task_id", ""),
        started_at=entry.get("started_at") or 0.0,
        sandbox_key=entry.get("sandbox_key", ""),
    )
    fields["output_log"] = adoptable_log(entry.get("output_log"))
    fields["service_unit"] = entry.get("service_unit") or ""
    # pid is a checkpoint field and is also forced null: a service has no child pid.
    fields.pop("pid", None)
    session = ProcessSession(id=session_id, detached=True, pid=None, **fields)
    with registry._lock:
        registry._running[session.id] = session
    stored_invocation = str(entry.get("service_invocation_id") or "")
    stored_notify = bool(entry.get("notify_on_complete"))
    refresh_service_session(registry, session, publish=False)
    armed = False
    if (
        not session.exited
        and (entry.get("service_mode") or "") == "await"
        and stored_invocation
        and not stored_notify
        and not session.notify_on_complete
    ):
        # The blocking waiter died with this process. Arm the existing release path once.
        # An invocation adopted only by this show is not that stored handoff.
        _release_await(registry, session)
        armed = True
    if not armed and not session.exited and session.watcher_interval > 0:
        if not any(item.get("session_id") == session.id for item in registry.pending_watchers):
            registry.pending_watchers.append(_watcher_payload(session))
    logger.info("Recovered service %s invocation %s", session.service_unit, session.service_invocation_id or "<unset>")
    return True


def stop_owned_service(registry, session, *, source: str, consume_output: bool) -> dict:
    """Explicit stop of the registered unit. Never signals a name, an empty invocation, or a stranger."""
    if service_survives_stop(session, source):
        return {
            "status": "running", "session_id": session.id, "process_running": True,
            "exit_code": None, "service": session.service_mode,
        }
    show = systemctl_show(session.service_unit)
    boot = read_boot_id()
    if (
        show is None or _unit_absent(show)
        or (session.service_boot_id and boot and session.service_boot_id != boot)
    ):
        return _unresolved_stop(session, "service identity does not match a live unit; it was not signalled")
    live = show.get("InvocationID") or ""
    stored = session.service_invocation_id or ""
    if stored and live and stored != live:
        return _unresolved_stop(session, "service invocation does not match; it was not signalled")
    if not live:
        return _unresolved_stop(session, "service invocation is empty; it was not signalled")
    if not stored:
        session.service_invocation_id = live
        if not registry._write_checkpoint(strict=True):
            session.service_invocation_id = ""
            return _unresolved_stop(session, "service invocation could not be stored; it was not signalled")
        show = systemctl_show(session.service_unit)
        boot = read_boot_id()
        if (
            show is None or (show.get("InvocationID") or "") != live
            or (session.service_boot_id and boot and session.service_boot_id != boot)
        ):
            return _unresolved_stop(session, "service invocation changed before stop; it was not signalled")
    cv = _outcome_cv(session)
    with cv:
        if session.exited:
            committed = True
        else:
            session.service_stop_intent = True
            session._stop_phase = "inflight"
            committed = False
    if committed:
        return _committed_stop(registry, session, consume_output=consume_output)
    if not registry._write_checkpoint(strict=True):
        with cv:
            if getattr(session, "_stop_phase", None) == "inflight":
                session.service_stop_intent = False
                session._stop_phase = None
                cv.notify_all()
        return _unresolved_stop(session, "service stop intent could not be stored; it was not signalled")
    # The checkpoint lock is released. Re-read before signal: another object may
    # already have committed this identity. systemctl stays outside the lock.
    authority = peek_service_authority(session)
    with cv:
        lost = _phase_after_durable_attempt(session, cv, authority)
    if lost is None:
        return _unresolved_stop(session, "service stop intent could not be stored; it was not signalled")
    if lost:
        # Drop the not-yet-exited checkpoint row now that completion won, so a
        # later admit is not blocked by a stop intent the signal never sent.
        registry._write_checkpoint()
        return _committed_stop(registry, session, consume_output=consume_output)
    binary = shutil.which("systemctl")
    if binary:
        try:
            _run([binary, "--user", "stop", session.service_unit])
        except (OSError, subprocess.TimeoutExpired):
            logger.debug("systemctl stop %s failed", session.service_unit, exc_info=True)
    refresh_service_session(registry, session)
    if session.exited:
        if consume_output:
            registry._completion_consumed.add(session.id)
        from tools.process_registry import ProcessRegistry
        return {"status": "killed", "session_id": session.id, **ProcessRegistry._exit_snapshot(session, "killed")}
    return _unresolved_stop(session, "service stop did not record a durable outcome")


def _committed_stop(registry, session, *, consume_output: bool) -> dict:
    """The exit was already recorded. Do not signal and do not rewrite the receipt."""
    if consume_output:
        registry._completion_consumed.add(session.id)
    from tools.process_registry import ProcessRegistry
    status = "killed" if session.completion_reason == "killed" else "already_exited"
    return {"status": status, "session_id": session.id, **ProcessRegistry._exit_snapshot(session, status)}


def _unresolved_stop(session, note: str) -> dict:
    return {
        "status": "unresolved", "session_id": session.id, "process_running": True,
        "exit_code": None, "service": session.service_mode,
        "service_invocation_id": session.service_invocation_id or "",
        "note": note, "error": note,
    }


def _write_private(path: Path, text: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, text.encode("utf-8"))
    finally:
        os.close(fd)
    os.chmod(path, 0o600)


def _env_round_trip(env: dict[str, str], script: Path) -> bool:
    try:
        result = subprocess.run(
            ["/usr/bin/env", "-i", "/bin/sh", str(script), "--probe"],
            capture_output=True, timeout=_command_timeout(), check=False, env={},
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if result.returncode != 0:
        return False
    seen: dict[str, str] = {}
    for item in result.stdout.split(b"\0"):
        if not item or b"=" not in item:
            continue
        key, value = item.split(b"=", 1)
        name = key.decode("utf-8", "replace")
        if name == "_":
            continue
        seen[name] = value.decode("utf-8", "replace")
    return seen == env


def prepare_worker_files(session, env: dict[str, str], command: str) -> bool:
    """Write the mode-0600 env file and loader. False means do not call systemd-run."""
    from hermes_constants import get_hermes_home
    from hermes_dir_acl import make_user_dir
    from tools.environments.base_session_env import _SHELL_ENV_NAME_RE
    from tools.process_registry_output_log import output_dir, record_exit_command

    if any(not isinstance(key, str) or not _SHELL_ENV_NAME_RE.fullmatch(key) for key in env):
        return False
    log_dir = output_dir()
    make_user_dir(log_dir, mode=0o700, parents=True, exist_ok=True)
    log_path = log_dir / f"{session.id}.log"
    _write_private(log_path, "")
    session.output_log = str(log_path)
    directory = get_hermes_home() / "logs" / "process-env"
    make_user_dir(directory, mode=0o700, parents=True, exist_ok=True)
    env_path = directory / f"{session.id}.env"
    script_path = directory / f"{session.id}.sh"
    body = "".join(f"{key}={shlex.quote(env[key])}\n" for key in sorted(env))
    _write_private(env_path, body)
    wrapped = record_exit_command(log_path, _worker_command(command))
    script = (
        _SCRIPT.replace("@@ENV@@", shlex.quote(str(env_path)))
        .replace("@@CMD@@", shlex.quote(wrapped))
        .replace("@@LOG@@", shlex.quote(str(log_path)))
    )
    _write_private(script_path, script)
    if not _env_round_trip(env, script_path):
        return False
    session._service_script = str(script_path)
    return True


def _has_shell_syntax(command: str) -> bool:
    """True when ``command`` needs a shell. Quoted text is not syntax.

    ``$`` and escapes inside double quotes still expand, so they stay on the shell path.
    A simple command is spawned with ``env -u PWD -u SHLVL`` so it does not inherit bash's additions.
    The shell stays the main process so the exit trap still records the command status.
    """
    quote = ""
    i = 0
    length = len(command)
    while i < length:
        ch = command[i]
        if quote:
            if ch == "\\" and quote == '"':
                return True
            if ch == quote:
                quote = ""
            elif quote == '"' and ch in "$`":
                return True
            i += 1
            continue
        if ch in "\"'":
            quote = ch
        elif ch == "\\" or ch in ";|&<>()`$\n*?[]{}~#":
            return True
        i += 1
    return bool(quote)


def _worker_command(command: str) -> str:
    """Run a simple command under ``env -u`` so bash does not export ``PWD`` or ``SHLVL``.

    Compound shell syntax stays a shell command: pipes, loops, and builtins are the shell's.
    ``/bin/sh -c`` of that text is still the unit's main process.
    """
    if _has_shell_syntax(command):
        return command
    try:
        argv = shlex.split(command)
    except ValueError:
        return command
    if not argv:
        return command
    quoted = " ".join(shlex.quote(arg) for arg in argv)
    return f"/usr/bin/env -u PWD -u SHLVL -- {quoted}"


def _launch_unit(session) -> subprocess.CompletedProcess:
    from tools.process_registry import _SYSTEMD_RUN_NO_EXPAND, _worker_memory_max_bytes
    binary = shutil.which("systemd-run")
    if not binary:
        raise OSError("systemd-run is not installed")
    argv = [binary, "--user", "--no-block", f"--unit={session.service_unit}"]
    if _SYSTEMD_RUN_NO_EXPAND:
        argv.append("--expand-environment=no")
    argv.extend([
        "--property=Type=exec",
        "--property=RemainAfterExit=yes",
        "--property=MemoryAccounting=yes",
        f"--property=MemoryMax={_worker_memory_max_bytes()}",
        f"--property=WorkingDirectory={session.cwd}",
        "--",
        "/usr/bin/env", "-i", "/bin/sh", session._service_script,
    ])
    return _run(argv)


def _tool_json(session, *, status: str, note: str = "", error: Optional[str] = None) -> str:
    from agent.redact import redact_terminal_output
    tail_service_output(session)
    output = redact_terminal_output(session.output_buffer or "", session.command or "")
    body: dict[str, Any] = {
        "output": output,
        "exit_code": None if status != "exited" else session.exit_code,
        "error": error,
        "status": status,
        "service": session.service_mode,
        "session_id": session.id,
        "service_invocation_id": session.service_invocation_id or "",
        "service_boot_id": session.service_boot_id or "",
        "service_unit": session.service_unit,
        "systemd_unit": "",
        "process_running": status != "exited",
    }
    if status == "exited":
        body["completion_reason"] = session.completion_reason
        body["termination_source"] = session.termination_source
    if note:
        body["note"] = note
    return json.dumps(body, ensure_ascii=False)


def _error(message: str) -> str:
    from tools.terminal_tool import _error_json
    return _error_json(message, status="error")


def _drop_session(registry, session) -> None:
    with registry._lock:
        registry._running.pop(session.id, None)
    registry._write_checkpoint()


def find_service(registry, tool_call_id: str):
    if not tool_call_id:
        return None
    with registry._lock:
        sessions = [*registry._running.values(), *registry._finished.values()]
    for session in sessions:
        if session.tool_call_id == tool_call_id and session.service_unit:
            return session
    from tools.process_registry import _checkpoint_path
    path = _checkpoint_path()
    try:
        entries = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        entries = []
    if any(isinstance(item, dict) and item.get("tool_call_id") == tool_call_id and item.get("service_unit")
           for item in entries):
        registry.recover_from_checkpoint()
        with registry._lock:
            sessions = [*registry._running.values(), *registry._finished.values()]
        for session in sessions:
            if session.tool_call_id == tool_call_id and session.service_unit:
                return session
    record = _receipt_by_tool_call(tool_call_id)
    if record is None:
        return None
    return _session_from_receipt(record)


def _receipt_by_tool_call(tool_call_id: str) -> Optional[dict]:
    from hermes_constants import get_hermes_home
    directory = get_hermes_home() / "logs" / "process-results"
    try:
        paths = list(directory.glob("proc_*.json"))
    except OSError:
        return None
    for path in paths:
        try:
            record = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        if record.get("tool_call_id") == tool_call_id and record.get("service_unit"):
            return record
    return None


def _session_from_receipt(record: dict):
    from tools.process_registry import ProcessSession
    from tools.process_registry_results import _OPTIONAL_RESULT_FIELDS, _RESULT_FIELDS
    fields = {key: record[key] for key in _RESULT_FIELDS}
    fields.update({key: record.get(key, default) for key, default in _OPTIONAL_RESULT_FIELDS.items()})
    session = ProcessSession(**fields, exited=True, output_buffer=record.get("output") or "")
    session._completion_event.set()
    return session


def service_outcome_content(tool_call_id: str) -> Optional[str]:
    """JSON the tool would have returned for this id. Does not start a unit."""
    from tools.process_registry import process_registry
    session = find_service(process_registry, tool_call_id)
    if session is None:
        record = _receipt_by_tool_call(tool_call_id)
        if record is None:
            from tools.process_registry import _checkpoint_path
            try:
                entries = json.loads(_checkpoint_path().read_text(encoding="utf-8-sig"))
            except (OSError, ValueError):
                return None
            entry = next((item for item in entries if isinstance(item, dict)
                          and item.get("tool_call_id") == tool_call_id and item.get("service_unit")), None)
            if entry is None:
                return None
            if entry.get("notify_on_complete"):
                return json.dumps({
                    "status": "unresolved", "exit_code": None, "process_running": True,
                    "service": entry.get("service_mode") or "",
                    "service_invocation_id": entry.get("service_invocation_id") or "",
                    "service_unit": entry.get("service_unit") or "",
                    "systemd_unit": "", "output": "", "error": None,
                    "note": _UNRESOLVED_NOTE,
                })
            if entry.get("service_invocation_id"):
                return json.dumps({
                    "status": "running", "exit_code": None, "process_running": True,
                    "service": entry.get("service_mode") or "",
                    "service_invocation_id": entry.get("service_invocation_id") or "",
                    "service_unit": entry.get("service_unit") or "",
                    "systemd_unit": "", "output": "", "error": None,
                })
            return json.dumps({
                "status": "unresolved", "exit_code": None, "process_running": True,
                "service": entry.get("service_mode") or "",
                "service_invocation_id": "", "service_unit": entry.get("service_unit") or "",
                "systemd_unit": "", "output": "", "error": None,
                "note": "The service start is unresolved. Do not run it again. This step is not done.",
            })
        session = _session_from_receipt(record)
    if _handoff_pending(session):
        return _tool_json(session, status="unresolved", note=_UNRESOLVED_NOTE)
    if session.exited and session.exit_code is not None:
        return _tool_json(session, status="exited")
    if session.service_invocation_id:
        return _tool_json(session, status="running")
    return _tool_json(
        session, status="unresolved",
        note="The service start is unresolved. Do not run it again. This step is not done.",
    )


def _handoff_pending(session) -> bool:
    """Notify is armed, or the receipt still owns the one exit delivery."""
    if getattr(session, "admission_pending", False):
        return True
    return bool(getattr(session, "notify_on_complete", False) and not session.exited)


def clear_service_admission(session_id: str, profile_home=None) -> bool:
    """Drop a pending admission flag without changing the stored exit code.

    The read and the write share processes.json.lock with outcome commits, and
    the record written is the one just read. A stale copy cannot put an old
    exit or a pending flag back.
    """
    if not session_id:
        return False
    from hermes_cli.active_sessions import _FileLock
    from hermes_constants import get_hermes_home
    from tools.process_registry import process_registry
    from utils import atomic_json_write
    session = process_registry.get(session_id)
    if session is not None:
        session.admission_pending = False
    home = Path(profile_home) if profile_home is not None else get_hermes_home()
    path = home / "logs" / "process-results" / f"{session_id}.json"
    try:
        with _FileLock(home / "processes.json.lock"):
            try:
                record = json.loads(path.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError):
                return session is not None
            if not isinstance(record, dict) or "exit_code" not in record:
                return False
            record["admission_pending"] = False
            atomic_json_write(path, record, mode=0o600)
    except (OSError, RuntimeError):
        logger.warning("Could not clear service admission %s", session_id, exc_info=True)
        return False
    return True


def _authority_profile_dir(authority, profile_home):
    if profile_home is not None:
        return profile_home
    store = getattr(authority, "persistence", None)
    scope = getattr(store, "scope", None)
    return getattr(scope, "profile_dir", None)


def _settled_exit(exit_code, completion_reason) -> bool:
    if completion_reason == "lost":
        return True
    return exit_code is not None


def reconcile_service_admissions(authority, profile_home=None) -> None:
    """Clear a delivered receipt once its admission is no longer queued.

    Memory rows and this profile's disk-only receipts, including nonzero and lost.
    A missing admission stays pending. A queued admission stays pending. No
    authority store leaves the flag alone. This read does not admit or start a unit.
    """
    if authority is None:
        return
    from tools.environments.sandbox_scope import hosted_scope
    if hosted_scope() is not None:
        return
    store = getattr(authority, "persistence", None)
    list_admissions = getattr(getattr(store, "admissions", None), "list", None)
    if not callable(list_admissions):
        return
    from session_rules.automation import automation_descriptor
    from tools.process_registry import process_registry

    home = _authority_profile_dir(authority, profile_home)
    with process_registry._lock:
        memory = [
            session for session in (*process_registry._running.values(), *process_registry._finished.values())
            if getattr(session, "admission_pending", False) and session.service_unit
            and _settled_exit(session.exit_code, session.completion_reason)
        ]
    seen = {session.id for session in memory}
    disks = []
    if home is not None:
        for record in load_pending_service_receipts(home):
            sid = record.get("id")
            if sid in seen or not isinstance(sid, str):
                continue
            if _settled_exit(record.get("exit_code"), record.get("completion_reason") or ""):
                disks.append(record)
    if not memory and not disks:
        return
    cache: dict = {}

    def rows_for(parent: str):
        if parent not in cache:
            try:
                cache[parent] = list_admissions(session_id=parent, pending_only=False)
            except Exception:  # health: allow BLE001 -- a down authority store must not fail the process list
                logger.warning("service admission lookup failed for %s", parent, exc_info=True)
                cache[parent] = None
        return cache[parent]

    def settle(session_id: str, parent, started_at) -> None:
        if not isinstance(parent, str) or not parent.strip() or not session_id:
            return
        rows = rows_for(parent)
        if not rows:
            return
        identity = json.dumps(("completion", session_id, started_at), separators=(",", ":"))
        matched = []
        for row in rows:
            payload = getattr(row, "payload", None)
            if not isinstance(payload, dict):
                continue
            descriptor = automation_descriptor(payload)
            identities = descriptor.get("identities", [descriptor.get("identity")])
            if identity in identities:
                matched.append(row)
        if matched and all(str(getattr(row, "status", "")) != "queued" for row in matched):
            clear_service_admission(session_id, profile_home=home)

    for session in memory:
        settle(session.id, session.parent_session_id, session.started_at)
    for record in disks:
        settle(str(record.get("id") or ""), record.get("parent_session_id"), record.get("started_at"))


def _reconcile_profile_home(profile_home) -> None:
    """Reconcile one profile's receipts against that profile's admission store."""
    from tools.environments.sandbox_scope import hosted_scope
    if profile_home is None or hosted_scope() is not None:
        return
    from persistence_assembly import open_persistence_reader, profile_scope
    try:
        scope = profile_scope(home=Path(profile_home))
        with open_persistence_reader(scope.profile_dir) as persistence:
            reconcile_service_admissions(
                SimpleNamespace(persistence=persistence), profile_home=profile_home,
            )
    except Exception:  # health: allow BLE001 -- a closed or missing profile store leaves the flags
        logger.debug("service admission reconcile skipped", exc_info=True)


def reconcile_from_registry(registry) -> None:
    lookup = getattr(registry, "_service_authority_lookup", None)
    if not callable(lookup):
        return
    try:
        authority = lookup()
    except Exception:
        logger.debug("service admission reconcile skipped", exc_info=True)
        return
    reconcile_service_admissions(authority)


def _read_pending_service_receipt(path: Path) -> Optional[dict]:
    try:
        record = json.loads(path.read_bytes().decode("utf-8-sig"))
    except (OSError, ValueError):
        return None
    if not isinstance(record, dict):
        return None
    if record.get("admission_pending") is not True or not record.get("service_unit"):
        return None
    session_id = record.get("id")
    if session_id != path.stem or not isinstance(session_id, str):
        return None
    if re.fullmatch(r"proc_[\w]+", session_id) is None:
        return None
    return record


def load_pending_service_receipts(profile_home) -> list[dict]:
    """Pending service receipts in one profile home.

    No owner check: the caller fences them. A hosted scope sees none. Other
    homes are not scanned, and this read does not admit or enqueue anything.
    """
    from tools.environments.sandbox_scope import hosted_scope

    if profile_home is None or hosted_scope() is not None:
        return []
    directory = Path(profile_home) / "logs" / "process-results"
    found: list[dict] = []
    try:
        paths = sorted(directory.glob("proc_*.json"))
    except OSError:
        return found
    for path in paths:
        record = _read_pending_service_receipt(path)
        if record is not None:
            found.append(record)
    return found


def _receipt_attention(record: dict) -> Optional[str]:
    reason = record.get("completion_reason") or ""
    if not isinstance(reason, str):
        reason = ""
    exit_code = record.get("exit_code", None)
    exited = exit_code is not None or reason in {"exited", "lost", "killed"}
    return attention_for(SimpleNamespace(
        service_mode=record.get("service_mode") or "",
        exited=exited,
        completion_reason=reason,
        exit_code=exit_code,
        admission_pending=True,
    ))


# Unconsumed service outcomes. ``killed`` has no attention value and is not an obligation.
_OBLIGATION_ATTENTION = frozenset({"ready", "failed", "lost"})


def pending_service_obligation_owners(profile_home) -> list[tuple[str, str, str]]:
    """(session id, parent id, route) for pending receipts that still need attention.

    Ready, failed, and lost stay distinct. A missing or non-string parent stays
    unresolved. The route is not copied into the parent. A hosted scope sees none.
    """
    _reconcile_profile_home(profile_home)
    owners = []
    for record in load_pending_service_receipts(profile_home):
        parent = record.get("parent_session_id")
        if not isinstance(parent, str) or not parent.strip():
            continue
        if _receipt_attention(record) not in _OBLIGATION_ATTENTION:
            continue
        route = record.get("session_key")
        owners.append((record["id"], parent, route if isinstance(route, str) else ""))
    return owners


def _receipt_bound_to_session(record: dict, keys, targets) -> bool:
    """True when the stored route or a real parent names this conversation."""
    route = record.get("session_key")
    if isinstance(route, str) and route in keys:
        return True
    parent = record.get("parent_session_id")
    return isinstance(parent, str) and bool(parent.strip()) and parent in targets


def snapshot_pending_services(profile_home, keys, targets, seen) -> list:
    """Pending service sessions for one profile that belong to this conversation.

    The objects are not registered. This read does not admit or enqueue. A
    missing or non-string parent is not invented from the route.
    """
    found = []
    for record in load_pending_service_receipts(profile_home):
        sid = record.get("id")
        if sid in seen or not _receipt_bound_to_session(record, keys, targets):
            continue
        try:
            found.append(_session_from_receipt(record))
        except (KeyError, TypeError, ValueError):
            logger.debug("Skipping unreadable pending service receipt %s", sid, exc_info=True)
    return found


def session_pending_entries(profile_home, session_key: str) -> list[dict]:
    """List rows for pending service receipts in one home with this route.

    Another profile's directory is not read. The sessions are not registered.
    """
    if not isinstance(session_key, str) or not session_key:
        return []
    rows = []
    for record in load_pending_service_receipts(profile_home):
        if record.get("session_key") != session_key:
            continue
        try:
            rows.append(_listed_receipt_entry(record))
        except (KeyError, TypeError, ValueError):
            logger.debug(
                "Skipping unreadable pending service receipt %s",
                record.get("id"), exc_info=True,
            )
    return rows


def _listed_receipt_entry(record: dict) -> dict:
    """One ``list_sessions``-shaped row. Does not register the session."""
    import time

    session = _session_from_receipt(record)
    started = session.started_at or 0
    preview = session.output_buffer or ""
    entry = {
        "session_id": session.id,
        "command": (session.command or "")[:200],
        "cwd": session.cwd,
        "pid": session.pid,
        "owner_task_id": session.owner_task_id,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(started)) if started else "",
        "uptime_seconds": int(time.time() - started) if started else 0,
        "status": "exited" if session.exited else "running",
        "output_preview": preview[-200:],
        "output_tail": preview[-4000:],
    }
    if session.exited:
        entry["exit_code"] = session.exit_code
        entry["exited_at"] = session.exited_at or None
        entry["completion_reason"] = session.completion_reason
    if session.notify_on_complete:
        entry["notify_on_complete"] = True
    entry.update(service_projection(session))
    return entry


def _checkpoint_rows() -> dict:
    from tools.process_registry import _checkpoint_path
    try:
        entries = json.loads(_checkpoint_path().read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    rows = {}
    if isinstance(entries, list):
        for item in entries:
            if isinstance(item, dict) and isinstance(item.get("session_id"), str):
                rows[item["session_id"]] = item
    return rows


def _stop_contradicts_success(record: dict, row) -> bool:
    """A durable stop on a still-present checkpoint row contradicts an exit-0 receipt.

    The checkpoint omits exited sessions, but that rewrite is best-effort and can lag a
    committed receipt. A not-exited row without stop intent is not a contradiction: blocking
    every such receipt would drop a real exit when show is unavailable. No row means the
    receipt is the commit.
    """
    if not isinstance(row, dict) or not row.get("service_stop_intent"):
        return False
    if record.get("completion_reason") == "killed":
        return False
    return record.get("exit_code") == 0


def pending_service_events() -> list[dict]:
    """Completion events copied from admission_pending receipt bytes. ``started_at`` is not recomputed."""
    from hermes_constants import get_hermes_home
    directory = get_hermes_home() / "logs" / "process-results"
    checkpoint = _checkpoint_rows()
    events = []
    try:
        paths = sorted(directory.glob("proc_*.json"))
    except OSError:
        return events
    for path in paths:
        try:
            record = json.loads(path.read_bytes().decode("utf-8-sig"))
        except (OSError, ValueError):
            continue
        if record.get("admission_pending") is not True or not record.get("service_unit"):
            continue
        if _stop_contradicts_success(record, checkpoint.get(record.get("id") or path.stem)):
            continue
        events.append({
            "type": "completion",
            "session_id": record.get("id") or path.stem,
            "session_key": record.get("session_key") or "",
            "task_id": record.get("task_id") or "",
            "owner_task_id": record.get("owner_task_id") or "",
            "parent_session_id": record.get("parent_session_id") or "",
            "command": record.get("command") or "",
            "exit_code": record.get("exit_code"),
            "completion_reason": record.get("completion_reason") or "exited",
            "termination_source": record.get("termination_source") or "",
            "output": record.get("output") or "",
            "started_at": record.get("started_at"),
            "platform": record.get("watcher_platform") or "",
            "chat_id": record.get("watcher_chat_id") or "",
            "user_id": record.get("watcher_user_id") or "",
            "user_name": record.get("watcher_user_name") or "",
            "thread_id": record.get("watcher_thread_id") or "",
            "message_id": record.get("watcher_message_id") or None,
            "service_mode": record.get("service_mode") or "",
            "notify_on_complete": True,
        })
    return events


def run_terminal_service(
    *, command: str, mode: str, cwd: str, task_id: str, session_key: str,
    timeout: Optional[int], env_vars: Optional[dict], pty: bool, env_type: str,
) -> str:
    from tools.environments.sandbox_scope import hosted_scope
    from tools.process_registry import ProcessRegistry, _IS_LINUX, process_registry

    if mode not in {"await", "notify"}:
        return _error("service must be 'await' or 'notify'.")
    if pty:
        return _error("pty cannot be combined with service; no service was started.")
    if env_type != "local":
        return _error("service requires the local terminal backend; no service was started.")
    if not _IS_LINUX:
        return _error("service requires Linux; no service was started.")
    if hosted_scope() is not None:
        return _error("service is not available in a hosted scope; no service was started.")
    if not user_bus_ready():
        return _error("the user systemd bus is not available; no service was started.")
    boot = read_boot_id()
    if not boot:
        return _error("the kernel boot id is unreadable; no service was started.")
    tool_call_id = current_tool_call_id()
    if not tool_call_id:
        return _error("service requires a tool call id; no service was started.")
    existing = find_service(process_registry, tool_call_id)
    if existing is not None:
        return _resume_existing(process_registry, existing, mode, timeout)
    env = ProcessRegistry._spawn_env(env_vars)
    session = process_registry._new_session(
        command, task_id, task_id, session_key, cwd,
        service_mode=mode, service_boot_id=boot, tool_call_id=tool_call_id,
    )
    session.service_unit = f"hermes-bg-{session.id}.service"
    session.pid = None
    if not prepare_worker_files(session, env, command):
        return _error("the service environment could not be isolated; no service was started.")
    with process_registry._lock:
        process_registry._prune_if_needed()
        process_registry._running[session.id] = session
    if not process_registry._write_checkpoint(strict=True):
        _drop_session(process_registry, session)
        return _error("the service checkpoint could not be stored; no service was started.")
    try:
        launched = _launch_unit(session)
    except (OSError, subprocess.TimeoutExpired):
        show = systemctl_show(session.service_unit)
        if _unit_absent(show):
            _arm_recheck(process_registry, session, notify=False)
            process_registry._write_checkpoint()
            return _tool_json(
                session, status="unresolved",
                note="The service start is unresolved. Do not run it again. This step is not done.",
            )
        launched = None
    show = systemctl_show(session.service_unit)
    if launched is not None and launched.returncode != 0 and _unit_absent(show):
        _drop_session(process_registry, session)
        detail = (launched.stderr or launched.stdout or "").strip()[:300]
        return _error(f"the service was not accepted ({detail or 'systemd-run failed'}); no unit is running.")
    invocation = (show or {}).get("InvocationID") or ""
    if invocation:
        session.service_invocation_id = invocation
        if not process_registry._write_checkpoint(strict=True):
            session.service_invocation_id = ""
            _arm_recheck(process_registry, session, notify=False)
            return _tool_json(
                session, status="unresolved",
                note="The service start is unresolved. Do not run it again. This step is not done.",
            )
        if mode == "notify":
            arm_service_notify(process_registry, session)
            return json.dumps({
                "session_id": session.id, "service": "notify", "exit_code": None,
                "service_invocation_id": session.service_invocation_id,
                "service_unit": session.service_unit, "systemd_unit": "",
                "process_running": True, "output": "", "error": None, "status": "running",
            })
        return _block_for_result(process_registry, session, timeout)
    if mode == "notify":
        _arm_recheck(process_registry, session, notify=False)
        process_registry._write_checkpoint()
        return _tool_json(
            session, status="unresolved",
            note="The service start is unresolved. Do not run it again. This step is not done.",
        )
    # Blocking await rechecks from wait(). A watcher armed now would promote notify
    # as soon as an invocation appeared, before the wait released.
    return _block_for_result(process_registry, session, timeout)


def _resume_existing(registry, session, mode: str, timeout: Optional[int]) -> str:
    refresh_service_session(registry, session)
    if session.exited and session.exit_code is not None:
        return _tool_json(session, status="exited")
    if mode == "notify":
        if session.service_invocation_id and session.notify_on_complete:
            return json.dumps({
                "session_id": session.id, "service": "notify", "exit_code": None,
                "service_invocation_id": session.service_invocation_id,
                "service_unit": session.service_unit, "systemd_unit": "",
                "process_running": True, "output": "", "error": None, "status": "running",
            })
        return _tool_json(
            session, status="unresolved",
            note="The service start is unresolved. Do not run it again. This step is not done.",
        )
    return _block_for_result(registry, session, timeout)


def _block_for_result(registry, session, timeout: Optional[int]) -> str:
    result = registry.wait(session.id, timeout=timeout)
    if session.exited and session.exit_code is not None and result.get("status") == "exited":
        return _tool_json(session, status="exited")
    note = result.get("note") or _UNRESOLVED_NOTE
    return _tool_json(session, status="unresolved", note=note)


def on_await_released(registry, session) -> None:
    """``ProcessRegistry.wait`` calls this when an await service is still running."""
    if getattr(session, "service_mode", "") != "await" or session.exited:
        return
    _release_await(registry, session)
