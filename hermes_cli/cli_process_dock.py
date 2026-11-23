"""Background-process rows for the classic CLI live-work dock.

Sibling of ``cli_subagent_monitor``: the dock paints one "Processes" block under the
subagent rows from the same snapshot the ``process_manage`` tool reads, so a
``terminal(background=true)`` spawn is visible the moment it starts instead of only
when its completion notification lands.
"""

from __future__ import annotations

import time

from agent.i18n import t

# A finished process stays on the dock long enough to read its exit line, then
# leaves; the completion notification in the transcript is the durable record.
RETAIN_SECONDS = 60

# Reader-thread exits report "exited"; `kill_process` / `kill_all` stamp "killed".
_STATUS_BY_REASON = {"killed": "killed", "lost": "lost"}
_NAMED_ATTENTION = frozenset({"waiting", "running", "ready", "failed", "lost"})
_OPEN_STATUSES = frozenset({"running", "waiting", "ready"})
# Unconsumed outcomes. Not open: the heading still counts them as done.
_PENDING_OUTCOMES = frozenset({"failed", "lost"})


def process_is_open(status: str) -> bool:
    """Waiting, running, and ready are still live. Ready stays until a later snapshot settles it."""
    return status in _OPEN_STATUSES


def _named_attention(entry: dict) -> str | None:
    attention = entry.get("attention")
    if attention in _NAMED_ATTENTION:
        return attention
    if attention:
        return "unknown"
    return None


def _pending_outcome(entry: dict, status: str) -> bool:
    """Hold a failed or lost receipt until admission settles.

    The flag is omitted on a settled or legacy row, so those still leave after
    ``RETAIN_SECONDS``. Killed is not in ``status`` here: ``process_status``
    reads that reason before attention.
    """
    return entry.get("admission_pending") is True and status in _PENDING_OUTCOMES


def _unsettled_service(entry: dict) -> bool:
    if entry.get("service_mode") not in ("await", "notify"):
        return False
    if entry.get("exit_code") is not None:
        return False
    return (entry.get("completion_reason") or "") != "exited"


def _last_output_line(buffer: str) -> str:
    for line in reversed((buffer or "").splitlines()):
        text = " ".join(line.split())
        if text:
            return text
    return ""


def process_status(entry: dict) -> str:
    # Killed is not an attention value. Read it before attention so a stop is
    # not painted ready, waiting, or failed from a stale attention field.
    if (entry.get("completion_reason") or "") == "killed":
        return "killed"
    attention = _named_attention(entry)
    if attention:
        return attention
    if entry.get("status") != "exited":
        return "waiting" if entry.get("service_mode") == "await" else "running"
    reason = _STATUS_BY_REASON.get(entry.get("completion_reason") or "")
    if reason:
        return reason
    if entry.get("exit_code"):
        return "failed"
    if _unsettled_service(entry):
        return "unknown"
    return "done"


def process_rows(now: float | None = None) -> list:
    """Running processes plus those that exited within ``RETAIN_SECONDS``, newest-running first.

    The classic CLI is one conversation per OS process, so every registry entry (its own
    spawns and any a child handed back) belongs to this dock; gateway-hosted surfaces scope
    by session key in ``tui_gateway`` instead.
    """
    from hermes_cli.gateway_tools import process_registry as _registry

    process_registry = _registry()  # the gateway session's processes (rewired CLI)

    now = time.time() if now is None else now
    rows = []
    for entry in process_registry.list_sessions(include_service_receipts=True):
        proc = process_registry.get(entry["session_id"])
        status = process_status(entry)
        pending = _pending_outcome(entry, status)
        if proc is None:
            if not (process_is_open(status) or pending):
                continue
            elapsed = int(entry.get("uptime_seconds") or 0)
            rows.append(
                {
                    "kind": "process",
                    "key": entry["session_id"],
                    "id": entry["session_id"],
                    "command": " ".join((entry.get("command") or "").split())
                    or t("cli.dock.process_goal_label"),
                    "status": status,
                    "exit_code": entry.get("exit_code"),
                    "elapsed": elapsed,
                    "since_exit": 0,
                    "detail": _last_output_line(entry.get("output_preview") or ""),
                }
            )
            continue
        open_row = process_is_open(status)
        exited_at = 0.0 if open_row else (proc.exited_at or 0.0)
        if not open_row and not pending and now - exited_at > RETAIN_SECONDS:
            continue
        end = exited_at or now
        rows.append(
            {
                "kind": "process",
                "key": proc.id,
                "id": proc.id,
                "command": " ".join((proc.command or "").split())
                or t("cli.dock.process_goal_label"),
                "status": status,
                "exit_code": proc.exit_code,
                "elapsed": max(0, int(end - proc.started_at)),
                "since_exit": max(0, int(now - exited_at)) if exited_at else 0,
                "detail": _last_output_line(proc.output_buffer),
            }
        )
    rows.sort(
        key=lambda r: (
            not process_is_open(r["status"]),
            -r["elapsed"] if process_is_open(r["status"]) else r["since_exit"],
        )
    )
    return rows


_GLYPH = {
    "running": "⚙",
    "waiting": "…",
    "ready": "◆",
    "done": "✔",
    "failed": "✘",
    "killed": "✘",
    "lost": "?",
    "unknown": "?",
}
# Finished-status id → catalog key of the exit verdict (looked up at paint time).
_VERDICT_KEYS = {
    "done": "cli.dock.exit_code",
    "failed": "cli.dock.exit_code",
    "killed": "cli.dock.verdict_killed",
    "lost": "cli.dock.verdict_lost",
}


def _live_activity(row: dict) -> str:
    tail = (
        t("cli.dock.last_output", detail=row["detail"])
        if row["detail"]
        else t("cli.dock.starting")
    )
    if row["status"] == "waiting":
        return f"{row['elapsed']}s · {t('cli.dock.verdict_waiting')} · {tail}"
    return f"{row['elapsed']}s · {tail}"


def process_activity(row: dict) -> str:
    """The trailing ``· …`` part of a dock line: elapsed + latest output while the row is live,
    the exit verdict + age once finished. Ready says the result is ready and nothing more."""
    status = row["status"]
    if status in ("running", "waiting"):
        return _live_activity(row)
    if status == "ready":
        return t("cli.dock.verdict_ready")
    if status == "unknown":
        return t("cli.dock.verdict_unknown")
    verdict = t(_VERDICT_KEYS[status], code=row["exit_code"])
    return t("cli.dock.verdict_ago", verdict=verdict, seconds=row["since_exit"])


def process_glyph(row: dict) -> str:
    return _GLYPH.get(row["status"], "?")


def process_tail(process_id: str) -> str:
    from hermes_cli.gateway_tools import process_registry as _registry

    process_registry = _registry()  # the gateway session's processes (rewired CLI)

    proc = process_registry.get(process_id)
    if proc is None:
        return t("cli.dock.process_gone")
    text = (proc.output_buffer or "")[-32768:]
    text = "".join(c for c in text if c.isprintable() or c in "\n\t")
    return text or t("cli.dock.no_output")


def kill(process_id: str) -> dict:
    from hermes_cli.gateway_tools import process_registry as _registry

    process_registry = _registry()  # the gateway session's processes (rewired CLI)

    return process_registry.kill_process(process_id)
