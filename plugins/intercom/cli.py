"""``hermes intercom`` — send, list, status and log (LLD B9).

The CLI is an owner client. It runs ``route.send`` in this process with
``script=True``, starts no turn, and has no legacy-socket fallback. ``--reply``
defaults to ``none``. ``--no-reply`` is not a flag, so argparse reports it as
a usage error (exit 2).
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

try:
    from . import address, client, replies, route
except ImportError:  # loaded as a top-level module (the unittest layout)
    import address
    import client
    import replies
    import route

# Alex's sentence, word for word (ux.md, the delivery paragraph and --help).
INTERRUPT_SENTENCE = (
    "Only use interrupt when you intend to stop what the other session is doing right now "
    "(it is wrong, or the work is obsolete). Otherwise use steer (default) or queue."
)

_SINCE = re.compile(r"^(\d+)([smhd])$")
_SINCE_UNIT = {"s": 1, "m": 60, "h": 3600, "d": 86400}
_DEFAULT_SINCE = 24 * 3600

# detail -> process exit. 0 is a delivery; 1 is status's missing id; 2 is usage.
_EXIT = {
    "reply-missing": 3,
    "empty": 3,
    "ambiguous": 3,
    "unknown": 3,
    "own-session": 3,
    "project-addressing-unavailable": 3,
    "no-owner-set": 3,
    "not-addressable": 4,
    "injection-off": 4,
    "refused-by-owner": 4,
    "no-seam": 4,
    "no-owner": 5,
    "owner-restarting": 5,
    "not-reachable": 5,
    "delivery-unknown": 6,
}

_APPLIED_WORD = {
    "steer": "steered",
    "queue": "queued",
    "interrupt": "interrupted",
    "start": "started",
}

_state = {"ctx": None}


class _FallbackCtx:
    def get_config(self, key, default=None):
        return default


def register(ctx) -> None:
    """Register ``hermes intercom``. The host calls ``setup`` then the handler."""
    _state["ctx"] = ctx
    ctx.register_cli_command(
        "intercom",
        "Message another Hermes session",
        register_parser,
        intercom_command,
        description="Message another Hermes session; never send an empty message.",
    )


def _help_formatter(prog):
    # Wide enough that --delivery's help keeps Alex's sentence on one line.
    return argparse.HelpFormatter(prog, width=240)


def register_parser(parser: argparse.ArgumentParser) -> None:
    """Arguments for ``hermes intercom <verb>``."""
    parser.formatter_class = _help_formatter
    parser.set_defaults(func=intercom_command)
    subs = parser.add_subparsers(dest="intercom_command", required=True)
    send = subs.add_parser("send", help="Send a message", formatter_class=_help_formatter)
    send.add_argument("--to", required=True, help="Session id, exact title, Home, or @<project>.")
    send.add_argument("--message", default=None, help="Message text.")
    send.add_argument("--file", default=None, help="Read the message from PATH, or - for stdin.")
    send.add_argument("--reply", choices=("none", "requested", "waiting"), default="none",
                      help="none (default), requested, or waiting.")
    send.add_argument("--delivery", choices=("interrupt", "steer", "queue"), default="steer",
                      help=INTERRUPT_SENTENCE)
    send.add_argument("--from", dest="from_label", default="cli",
                      help='Script label in the header (default: cli).')
    send.add_argument("--json", action="store_true", help="Print the receipt as JSON.")
    send.set_defaults(func=intercom_command)

    listing = subs.add_parser("list", help="List sessions", formatter_class=_help_formatter)
    listing.add_argument("--include-runs", action="store_true",
                         help="Include cron, subagent and oneshot runs.")
    listing.add_argument("--query", default=None, help="Filter on title or project.")
    listing.add_argument("--limit", type=int, default=None, help="How many rows (default 30).")
    listing.add_argument("--json", action="store_true", help="Print the rows as JSON.")
    listing.set_defaults(func=intercom_command)

    status = subs.add_parser("status", help="Show one message", formatter_class=_help_formatter)
    status.add_argument("message_id", metavar="MESSAGE_ID")
    status.add_argument("--json", action="store_true", help="Print the status as JSON.")
    status.set_defaults(func=intercom_command)

    log = subs.add_parser("log", help="Show recent messages", formatter_class=_help_formatter)
    log.add_argument("--to", default=None, help="Filter on the target title, id or address.")
    log.add_argument("--from", dest="from_label", default=None,
                     help="Filter on the sender label or id.")
    log.add_argument("--since", default=None, help="Window such as 30s, 15m, 24h or 7d. Default 24h.")
    log.add_argument("--json", action="store_true", help="Print the rows as JSON.")
    log.set_defaults(func=intercom_command)


def main(argv=None) -> int:
    """Parse ``argv`` (without the ``intercom`` word) and return the exit code."""
    parser = argparse.ArgumentParser(prog="hermes intercom", formatter_class=_help_formatter)
    register_parser(parser)
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        return code if isinstance(code, int) else 2
    return int(intercom_command(args))


def intercom_command(args: argparse.Namespace) -> int:
    verb = getattr(args, "intercom_command", None)
    if verb == "send":
        return _cmd_send(args)
    if verb == "list":
        return _cmd_list(args)
    if verb == "status":
        return _cmd_status(args)
    if verb == "log":
        return _cmd_log(args)
    print("usage: hermes intercom {send,list,status,log}", file=sys.stderr)
    return 2


def _ctx():
    return _state["ctx"] if _state["ctx"] is not None else _FallbackCtx()


def _exit_for(receipt: dict) -> int:
    if receipt.get("ok") is True:
        return 0
    error = receipt.get("error")
    if error in _EXIT:
        return _EXIT[error]
    code = receipt.get("exit")
    if isinstance(code, int) and not isinstance(code, bool):
        return code
    return 4


def _print_failure(receipt: dict) -> None:
    print(receipt.get("message") or receipt.get("error") or "refused", file=sys.stderr)


def _cmd_send(args) -> int:
    text, problem = _body(args)
    if problem:
        print(problem, file=sys.stderr)
        return 2
    receipt = route.send(
        args.from_label or "cli",
        args.to,
        text,
        ctx=_ctx(),
        delivery=args.delivery,
        reply_mode=args.reply,
        script=True,
    )
    if args.json:
        print(json.dumps(receipt, ensure_ascii=False))
        if receipt.get("ok") is not True:
            _print_failure(receipt)
        return _exit_for(receipt)
    if receipt.get("ok") is True:
        title = receipt.get("target_title") or ""
        print(f'message {receipt.get("message_id")} → "{title}": {_applied_phrase(receipt)}')
        return 0
    _print_failure(receipt)
    return _exit_for(receipt)


def _body(args):
    has_message = args.message is not None
    has_file = args.file is not None
    if has_message == has_file:
        return None, "usage: pass exactly one of --message or --file"
    if has_message:
        return args.message, None
    if args.file == "-":
        return sys.stdin.read(), None
    path = Path(args.file)
    try:
        return path.read_text(encoding="utf-8-sig"), None
    except OSError:
        return None, f"usage: cannot read --file {args.file}"


def _applied_phrase(receipt: dict) -> str:
    applied = receipt.get("applied")
    requested = receipt.get("requested")
    detail = receipt.get("applied_detail")
    message = receipt.get("message") or ""
    if applied == "steer":
        return "steered (into its running turn)"
    if applied == "queue" and requested and requested != "queue":
        return (f"queued (asked: {requested}; the {requested} was refused, "
                "runs after its current turn)")
    if applied == "queue":
        return "queued (runs after its current turn)"
    if applied == "interrupt" and detail == "redirect":
        return "interrupted (redirected its running turn)"
    if applied == "interrupt":
        return "interrupted (stopped its running turn; runs next)"
    if applied == "start" and "was not open" in message:
        return "started (was not open; the gateway reopened it and a turn started there)"
    if applied == "start":
        return "started (was idle; a turn started)"
    return str(applied or "delivered")


def _cmd_list(args) -> int:
    listed = address.list_sessions(
        include_runs=bool(args.include_runs),
        query=args.query,
        limit=args.limit,
    )
    if not isinstance(listed, dict) or listed.get("ok") is not True:
        receipt = listed if isinstance(listed, dict) else {"ok": False, "error": "list-failed"}
        if args.json:
            print(json.dumps(receipt, ensure_ascii=False))
        _print_failure(receipt)
        return _exit_for(receipt)
    rows = list(listed.get("sessions") or [])
    if args.json:
        print(json.dumps(rows, ensure_ascii=False))
        return 0
    for row in rows:
        print(_list_line(row))
    return 0


def _list_line(row: dict) -> str:
    project = row.get("project")
    if not isinstance(project, str) or not project.strip():
        project = "\u2014"
    return (f"{row.get('id') or ''}  {row.get('title') or ''}  {project}  "
            f"{_relative(row.get('last_active'))}  {row.get('state') or ''}")


def _relative(last) -> str:
    if isinstance(last, bool) or not isinstance(last, (int, float)):
        return "\u2014"
    delta = max(0.0, time.time() - float(last))
    if delta < 45:
        return "now"
    if delta < 3600:
        return f"{int(delta // 60) or 1} min ago"
    if delta < 86400:
        return f"{int(delta // 3600) or 1} h ago"
    return f"{int(delta // 86400) or 1} d ago"


def _cmd_status(args) -> int:
    message_id = args.message_id
    row = _record_row(message_id)
    if row is None:
        text = f"No message with id {message_id}."
        if args.json:
            print(json.dumps({"ok": False, "error": "no such id", "message": text},
                             ensure_ascii=False))
        print(text, file=sys.stderr)
        return 1
    check = _status_check(row)
    reply_line = _status_reply(row)
    rendered = _status_text(row, reply_line, check)
    if args.json:
        print(json.dumps({
            "ok": True,
            "id": row.get("id"),
            "target_session": row.get("target_session_id"),
            "from": _from_label(row),
            "to": _to_label(row),
            "sent": _sent(row),
            "delivery": _delivery_words(row),
            "reply": reply_line,
            "check": check,
            "text": rendered,
        }, ensure_ascii=False))
        return 0
    print(rendered)
    return 0


def _status_text(row: dict, reply_line: str, check) -> str:
    lines = [
        f"message {row.get('id')}",
        f"  from      {_from_label(row)}",
        f"  to        {_to_label(row)}",
        f"  sent      {_sent(row)}",
        f"  delivery  {_delivery_words(row)}",
        f"  reply     {reply_line}",
    ]
    parent = row.get("in_reply_to")
    if isinstance(parent, str) and parent:
        # Two spaces after "to", as in ux.md.
        lines.append(f"  note      in reply to  message {parent}")
    if check:
        lines.append(f"  check     {check}")
    return "\n".join(lines)


def _from_label(row: dict) -> str:
    label = row.get("sender_label") or ""
    if row.get("sender_source") == "script" or not row.get("sender_session_id"):
        return f'script "{label}"'
    return f'session "{label}"'


def _to_label(row: dict) -> str:
    title = row.get("target_title") or ""
    session_id = row.get("target_session_id") or ""
    if session_id:
        return f'"{title}" ({session_id})'
    return f'"{title}"'


def _sent(row: dict) -> str:
    created = row.get("created_at")
    if not isinstance(created, (int, float)) or isinstance(created, bool):
        return ""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(created))


def _clock(stamp) -> str:
    if not isinstance(stamp, (int, float)) or isinstance(stamp, bool):
        return ""
    return time.strftime("%H:%M:%S", time.localtime(stamp))


def _delivery_words(row: dict) -> str:
    result = row.get("result")
    detail = row.get("detail")
    if result is None:
        return "unknown"
    if result == "refused":
        return f"refused ({detail})" if detail else "refused"
    if result == "error":
        return f"error ({detail})" if detail else "error"
    applied = row.get("applied")
    word = _APPLIED_WORD.get(applied, applied or "unknown")
    requested = row.get("requested")
    if applied == "queue" and requested and requested != "queue":
        return f"{word} (asked: {requested})"
    return word


def _needs_check(row: dict) -> bool:
    """Extra read only when the result was never written, or delivery is unknown."""
    return row.get("result") is None or row.get("detail") == "delivery-unknown"


def _status_check(row: dict):
    if not _needs_check(row):
        return None
    admission = row.get("admission_id")
    applied = row.get("applied")
    if isinstance(admission, str) and admission and applied in ("queue", "start"):
        return _admitted_line(admission, row.get("target_session_id"))
    return _transcript_line(row)


def _admitted_line(admission_id: str, session_id) -> str:
    try:
        answer = client.receipt(admission_id, session_id=session_id or "")
    except Exception:  # health: allow BLE001 -- a receipt failure is reported as not admitted
        return "not admitted"
    if not isinstance(answer, dict) or answer.get("ok") is not True:
        return "not admitted"
    return {
        "queued": "admitted: queued",
        "started": "admitted: started",
        "terminal": "admitted: finished",
    }.get(answer.get("status"), "not admitted")


def _transcript_line(row: dict) -> str:
    found = _transcript_timestamp(row.get("target_session_id"), row.get("header_sha"))
    if found is not None:
        return f"found in the target's transcript ({_clock(found)})"
    created = row.get("created_at")
    base = "not found in the target's transcript (yet)"
    if isinstance(created, (int, float)) and not isinstance(created, bool) and time.time() - created < 60:
        return f"{base}: the send ended less than a minute ago, so run status again in a minute"
    return f"{base}: sending again will not duplicate it"


def _transcript_timestamp(session_id, header_sha):
    """Read-only hash check of the recorded target session. None when it is absent.

    Matches a ``role='user'`` row with ``active=1`` or ``compacted=1`` whose framed
    span hashes to ``header_sha``. Does not open the database for writing.
    """
    if not isinstance(session_id, str) or not session_id:
        return None
    if not isinstance(header_sha, str) or not header_sha:
        return None
    path = _state_db()
    if not path.is_file():
        return None
    try:
        conn = _ro(path)
    except sqlite3.Error:
        return None
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT content, timestamp FROM messages "
            "WHERE session_id = ? AND role = 'user' AND (active = 1 OR compacted = 1)",
            (session_id,),
        ).fetchall()
    except sqlite3.Error:
        return None
    finally:
        conn.close()
    for row in rows:
        content = row["content"]
        if not isinstance(content, str):
            continue
        for span in replies.find_spans(content):
            if span.sha == header_sha:
                stamp = row["timestamp"]
                return stamp if isinstance(stamp, (int, float)) else 0
    return None


def _status_reply(row: dict) -> str:
    state = row.get("reply_state")
    when = _clock(row.get("replied_at"))
    text = row.get("reply") if isinstance(row.get("reply"), str) else ""
    extra = f" {text}" if text else ""
    if row.get("kind") == "ask":
        if state in ("sent", "silent"):
            return f"answered by reply ({when}){extra}"
        return "no reply recorded"
    if state is None:
        return "no reply recorded"
    if state == "silent":
        return f"silent ({when})"
    if state == "no-block":
        return "no reply recorded"
    child = _record_row(row.get("reply_message_id")) if row.get("reply_message_id") else None
    if state == "stored":
        reason = _undelivered(child)
        if reason and row.get("reply_message_id"):
            return (f"stored, not delivered ({when}): message {row['reply_message_id']}, "
                    f"{reason}{extra}")
        return f"stored ({when}){extra}"
    if state == "sent" and row.get("reply_message_id"):
        reason = _undelivered(child)
        if reason:
            return (f"stored, not delivered ({when}): message {row['reply_message_id']}, "
                    f"{reason}{extra}")
        applied = (child or {}).get("applied") or "steer"
        word = _APPLIED_WORD.get(applied, "steered")
        return f"sent as message {row['reply_message_id']}, {word} ({when}){extra}"
    return "no reply recorded"


def _undelivered(child) -> str | None:
    if not isinstance(child, dict):
        return None
    if child.get("result") in ("error", "refused"):
        return child.get("detail") or child.get("result")
    return None


def _cmd_log(args) -> int:
    window = _parse_since(args.since)
    if window is None:
        print(f"usage: invalid --since {args.since}", file=sys.stderr)
        return 2
    rows = _record_rows()
    if rows is None:
        if args.json:
            print("[]")
        return 0
    cutoff = time.time() - window
    kept = []
    for row in rows:
        created = row.get("created_at")
        if not isinstance(created, (int, float)) or isinstance(created, bool) or created < cutoff:
            continue
        if args.to and not _contains(args.to, row.get("target_title"), row.get("target_session_id"),
                                     row.get("address")):
            continue
        if args.from_label and not _contains(args.from_label, row.get("sender_label"),
                                             row.get("sender_session_id")):
            continue
        kept.append(row)
    kept.sort(key=lambda row: (row.get("created_at") or 0, row.get("id") or ""), reverse=True)
    by_id = {row.get("id"): row for row in rows}
    if args.json:
        print(json.dumps([_log_item(row, by_id) for row in kept], ensure_ascii=False))
        return 0
    for row in kept:
        print(_log_line(row, by_id))
    return 0


def _parse_since(text):
    if text is None or text == "":
        return _DEFAULT_SINCE
    if not isinstance(text, str):
        return None
    match = _SINCE.fullmatch(text.strip())
    if match is None:
        return None
    return int(match.group(1)) * _SINCE_UNIT[match.group(2)]


def _contains(needle, *values) -> bool:
    folded = needle.casefold()
    return any(isinstance(value, str) and folded in value.casefold() for value in values)


def _log_item(row: dict, by_id: dict) -> dict:
    return {
        "id": row.get("id"),
        "created_at": row.get("created_at"),
        "from": _from_label(row),
        "to": _to_label(row),
        "delivery": _log_delivery(row),
        "reply": _log_reply(row, by_id),
        "in_reply_to": row.get("in_reply_to"),
        "line": _log_line(row, by_id),
    }


def _log_line(row: dict, by_id: dict) -> str:
    created = row.get("created_at")
    clock = time.strftime("%H:%M", time.localtime(created)) if isinstance(created, (int, float)) else ""
    suffix = ""
    parent = row.get("in_reply_to")
    if isinstance(parent, str) and parent:
        suffix = f"  (reply to {parent})"
    target = f'session "{row.get("target_title") or row.get("target_session_id") or ""}"'
    return (f"{clock}  message {row.get('id')}  {_from_label(row)} → {target}  "
            f"{_log_delivery(row)}  {_log_reply(row, by_id)}{suffix}")


def _log_delivery(row: dict) -> str:
    result = row.get("result")
    detail = row.get("detail")
    if result == "refused":
        return f"refused ({detail})" if detail else "refused"
    if result == "error":
        return f"error ({detail})" if detail else "error"
    applied = row.get("applied")
    word = _APPLIED_WORD.get(applied, applied or (result or "unknown"))
    requested = row.get("requested")
    if applied == "queue" and requested and requested != "queue":
        return f"queued (asked {requested})"
    return word


def _log_reply(row: dict, by_id: dict) -> str:
    state = row.get("reply_state")
    detail = row.get("detail")
    if state == "stored" and detail == "shared-chat-no-block":
        return "reply: stored (shared chat, no [REPLY] block)"
    if row.get("reply_mode") == "none" and state is None:
        return "reply: none (not asked)"
    if state == "no-block":
        return "reply: none (no [REPLY] block)"
    if state == "silent":
        return "reply: silent"
    if row.get("kind") == "ask" and state in ("sent", "silent"):
        return "reply: answered"
    child_id = row.get("reply_message_id")
    child = by_id.get(child_id) if child_id else None
    reason = _undelivered(child)
    if child_id and reason:
        return f"reply: {child_id} not delivered ({reason})"
    if child_id:
        return f"reply: {child_id}"
    if state == "stored":
        return "reply: stored"
    return "reply: none recorded"


def _hermes_home() -> Path:
    from hermes_constants import get_hermes_home

    return Path(get_hermes_home())


def _record_path() -> Path:
    return _hermes_home() / "plugin-data" / "intercom" / "record.db"


def _state_db() -> Path:
    return _hermes_home() / "state.db"


def _ro(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)


def _record_rows():
    """Every record row, or None when the file does not exist.

    A missing file is left missing: this never calls ``record.connect``.
    """
    path = _record_path()
    if not path.is_file():
        return None
    try:
        conn = _ro(path)
    except sqlite3.Error:
        return []
    try:
        conn.row_factory = sqlite3.Row
        found = conn.execute("SELECT * FROM messages").fetchall()
        return [dict(row) for row in found]
    except sqlite3.Error:
        return []
    finally:
        conn.close()


def _record_row(message_id):
    if not isinstance(message_id, str) or not message_id:
        return None
    rows = _record_rows()
    if not rows:
        return None
    for row in rows:
        if row.get("id") == message_id:
            return row
    return None
