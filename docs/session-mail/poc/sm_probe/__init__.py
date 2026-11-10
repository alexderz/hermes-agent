"""Trial probe for DER-701 session-mail. FROZEN RECORD, NEVER PRODUCT CODE.

Copied by the harness into <temp-home>/plugins/sm-probe/ of a throwaway HERMES_HOME. It provides:

- ``sm_probe_send(to, message)``: a session_message-shaped SYNC tool. It frames the text with a probe
  header and delivers it with the delivery rule at 1516a52669 (the dispatcher file the harness
  wrote into the run directory, loaded by path), on a FRESH thread running its own event loop
  (``asyncio.run``), wrapped in ``propagate_context_to_thread`` (HLD D4).
- a ``post_llm_call`` recorder. It writes what the hook sees to <home>/sm-probe-hook.jsonl, and for
  each probe mail in this turn's user rows it takes the ``[REPLY <id>]`` block (or the whole
  answer), skips ``[SILENT]``/empty, and delivers the reply to the sender from a short-lived daemon
  thread (HLD D3).

Settings come from <home>/sm-probe.json, written by the harness: dispatcher path, URL, key file.
"""
from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import re
import secrets
import threading
import time
from pathlib import Path

HEADER_RE = re.compile(r"^📨 PROBE-MAIL ([0-9a-f]{8}) from (\S+)", re.MULTILINE)
STEER_OPEN = "[OUT-OF-BAND USER MESSAGE"
_lock = threading.Lock()
_dispatch = None


def _home() -> Path:
    from hermes_constants import get_hermes_home
    return Path(get_hermes_home())


def _settings() -> dict:
    return json.loads((_home() / "sm-probe.json").read_text())


def _log(name: str, rec: dict) -> None:
    rec["t"] = time.time()
    with _lock, (_home() / name).open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, default=str) + "\n")


def _dispatcher():
    global _dispatch
    if _dispatch is None:
        spec = importlib.util.spec_from_file_location("sm_probe_dispatch", _settings()["dispatch_path"])
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _dispatch = mod
    return _dispatch


def deliver(target: str, text: str, *, steer: bool = True) -> dict:
    """The delivery rule at 1516a52669 (_main: resume, then steer / queue / start), run on a fresh
    thread with its own loop, carrying the caller's profile context."""
    from tools.thread_context import propagate_context_to_thread
    s = _settings()
    ns = argparse.Namespace(url=s["url"], key_file=s["key_file"], resume=target, prompt=text, prompt_file=None,
                            title=None, cwd=None, steer=steer, timeout=60.0, start_timeout=float(s.get("start_timeout", 60)))
    box: dict = {}

    def run():
        t0 = time.time()
        try:
            box["result"] = asyncio.run(_dispatcher()._main(ns))
        except BaseException as exc:  # trial: record everything, SystemExit included
            box["error"] = f"{type(exc).__name__}: {exc}"
        box["seconds"] = round(time.time() - t0, 3)
        box["thread"] = threading.current_thread().name

    th = threading.Thread(target=propagate_context_to_thread(run), name="sm-probe-deliver")
    th.start()
    th.join()
    return box


def frame(sender: str, body: str) -> tuple[str, str]:
    mid = secrets.token_hex(4)
    return mid, f"📨 PROBE-MAIL {mid} from {sender} (not Alex)\n{body}\n— probe footer: reply in [REPLY {mid}] … [/REPLY] or [SILENT]"


def _send(args: dict, session_id: str | None = None, **_kw) -> str:
    mid, text = frame(session_id or "unknown", str(args.get("message", "")))
    t0 = time.time()
    out = deliver(str(args.get("to")), text, steer=not args.get("no_steer"))
    _log("sm-probe-tool.jsonl", {"kind": "send", "mail": mid, "from": session_id, "to": args.get("to"),
                                 "started": t0, "outcome": out, "loop_running_on_tool_thread": _loop_running()})
    return json.dumps({"mail": mid, **out}, default=str)


def _loop_running() -> bool:
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


def _text(content) -> str:
    if isinstance(content, list):
        return "\n".join(str(p.get("text", "")) for p in content if isinstance(p, dict))
    return str(content or "")


def _turn_user_rows(user_message, history) -> tuple[list[dict], bool]:
    """The turn's own user rows: from the last non-steer row holding the turn's prompt, onward."""
    rows = [m for m in (history or []) if isinstance(m, dict) and m.get("role") == "user"]
    start, found, um = 0, False, _text(user_message).strip()
    for i, m in enumerate(rows):
        if m.get("display_kind") != "steer" and um and um in _text(m.get("content")):
            start, found = i, True
    return [{"display_kind": m.get("display_kind"), "text": _text(m.get("content"))} for m in rows[start:]], found


def _claim_reply(mid: str) -> bool:
    """The outbox's 'no reply yet' check: one reply per mail id, ever."""
    p = _home() / "sm-probe-replied.json"
    with _lock:
        done = set(json.loads(p.read_text())) if p.exists() else set()
        if mid in done:
            return False
        done.add(mid)
        p.write_text(json.dumps(sorted(done)))
        return True


def _reply_for(mid: str, answer: str) -> str:
    m = re.search(rf"\[REPLY {mid}\](.*?)\[/REPLY\]", answer or "", re.DOTALL)
    return (m.group(1) if m else (answer or "")).strip()


def _post_llm_call(session_id=None, turn_id=None, user_message=None, assistant_response=None,
                   conversation_history=None, platform=None, **_kw) -> None:
    t0 = time.time()
    rows, found = _turn_user_rows(user_message, conversation_history)
    mails = []
    for r in rows:
        for mid, sender in HEADER_RE.findall(r["text"]):
            mails.append({"mail": mid, "from": sender, "row_kind": r["display_kind"]})
    rec = {"kind": "hook", "session_id": session_id, "turn_id": turn_id, "platform": platform,
           "prompt_row_found": found,
           "thread": threading.current_thread().name, "user_message": _text(user_message),
           "assistant_response": assistant_response, "turn_user_rows": rows, "mails": mails,
           "history_len": len(conversation_history or [])}
    replies = []
    for m in mails:
        if not _claim_reply(m["mail"]):
            replies.append({"to_mail": m["mail"], "sent": False, "reason": "already-replied"})
            continue
        body = _reply_for(m["mail"], assistant_response)
        if not body or body == "[SILENT]":
            replies.append({"to_mail": m["mail"], "sent": False, "reason": "silent"})
            continue
        if m["from"] == "cli":  # a CLI sender has no session: store only (brief A4)
            replies.append({"to_mail": m["mail"], "sent": False, "reason": "cli-sender", "reply": body})
            continue
        replies.append({"to_mail": m["mail"], "sent": True})
        _spawn_reply(session_id, m, body)
    rec["replies"] = replies
    rec["hook_seconds"] = round(time.time() - t0, 4)
    _log("sm-probe-hook.jsonl", rec)


def _spawn_reply(session_id, mail, body):
    from tools.thread_context import propagate_context_to_thread

    def run():
        mid, text = frame(session_id, f"re {mail['mail']}: {body}")
        out = deliver(mail["from"], text)
        _log("sm-probe-tool.jsonl", {"kind": "reply", "mail": mid, "in_reply_to": mail["mail"],
                                     "from": session_id, "to": mail["from"], "outcome": out})

    threading.Thread(target=propagate_context_to_thread(run), name="sm-probe-reply", daemon=True).start()


SCHEMA = {
    "name": "sm_probe_send",
    "description": "Trial probe: send a message to another session (session_message-shaped).",
    "parameters": {"type": "object", "additionalProperties": False, "required": ["to", "message"],
                   "properties": {"to": {"type": "string"}, "message": {"type": "string"},
                                  "no_steer": {"type": "boolean"}}},
}


def register(ctx) -> None:
    ctx.register_tool(name="sm_probe_send", toolset="sm_probe", schema=SCHEMA, handler=_send, is_async=False)
    ctx.register_hook("post_llm_call", _post_llm_call)
