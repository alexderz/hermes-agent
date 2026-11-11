"""DER-701 Trial round 3 (v0.23). FROZEN RECORD, NEVER PRODUCT CODE.

Copied next to an UNEDITED copy of intercom (`ae90a2a`) in a throwaway HERMES_HOME. It runs in every
Hermes process that loads plugins (the gateway owner, a standalone dashboard) and:

- records which process runs each turn (`post_llm_call`, with the pid);
- serves intercom's own socket (`inbox._serve` replaced) so the harness can ask THIS process to
  deliver a message, two ways:
  * "client": the owner's existing canonical verbs (`session.resume`, `session.steer`,
    `session.redirect`, `session.interrupt`, `prompt.submit`) over its ticketed /api/ws, opened from
    inside the process with `hermes_cli.gateway_client.connect_gateway` and
    `hermes_cli.gateway_runtime.discover_gateway_endpoint` (NOT in plugin_api.json);
  * "ctx": the published `ctx.inject_message(text, session_key=…)`;
- on a turn whose prompt carries `REPLYTO=<session id>`, sends the answer back by "client" + steer.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import secrets
import socket
import threading
import time
from pathlib import Path

_ctx = {"ctx": None, "inbox": None}
_lock = threading.Lock()
UNPUBLISHED = ["hermes_cli.gateway_client:connect_gateway", "hermes_cli.gateway_runtime:discover_gateway_endpoint",
               "tools.thread_context:propagate_context_to_thread"]


def _home() -> Path:
    from hermes_constants import get_hermes_home          # published (plugin_api.json: hermes_constants)
    return Path(get_hermes_home())


def _log(kind: str, **rec) -> None:
    rec.update(kind=kind, t=time.time(), pid=os.getpid())
    with _lock, (_home() / "r3-trial.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, default=str, ensure_ascii=False) + "\n")


def _role() -> dict:
    m = _ctx["ctx"]._manager
    return {"gateway_injector": getattr(m, "has_gateway_message_injector", False),
            "tui_injector": getattr(m, "has_tui_message_injector", False)}


# ---------------------------------------------------------------- "client": the owner's canonical verbs

async def _client_deliver(target: str, mode: str, text: str) -> dict:
    from hermes_cli.gateway_client import connect_gateway            # NOT published
    from hermes_cli.gateway_runtime import discover_gateway_endpoint  # NOT published
    ep = discover_gateway_endpoint(_home(), timeout=2.0).endpoint
    if ep is None:
        return {"ok": False, "error": "no owner"}
    calls = []

    async def rpc(c, method, **params):
        calls.append(method)
        return await c.rpc(method, **params)

    async with connect_gateway(ep) as c:
        h = await rpc(c, "session.resume", session_id=target)
        gen, running = h.get("execution_generation"), bool(h.get("running"))
        sub = lambda queued: rpc(c, "prompt.submit", session_id=target, text=text, queued=queued,
                                 submission_id=secrets.token_hex(8))
        if not running:
            r = await sub(False)
            return {"ok": True, "applied": "start", "calls": calls, "raw": r.get("status")}
        if mode == "queue":
            r = await sub(True)
            return {"ok": True, "applied": "queue", "calls": calls, "raw": r.get("status")}
        if mode == "steer":
            r = await rpc(c, "session.steer", session_id=target, text=text, execution_generation=gen)
            if r.get("status") == "queued":
                return {"ok": True, "applied": "steer", "calls": calls}
            q = await sub(True)
            return {"ok": True, "applied": "queue", "calls": calls, "steer_raw": r, "raw": q.get("status")}
        if mode == "interrupt":
            r = await rpc(c, "session.redirect", session_id=target, text=text, execution_generation=gen)
            if r.get("status") == "redirected":
                return {"ok": True, "applied": "interrupt", "detail": "redirect", "calls": calls}
            await rpc(c, "session.interrupt", session_id=target, execution_generation=gen)
            q = await sub(True)
            return {"ok": True, "applied": "interrupt", "detail": "hard-interrupt", "calls": calls,
                    "redirect_raw": r, "raw": q.get("status")}
        return {"ok": False, "error": f"mode {mode}"}


def client_deliver(target: str, mode: str, text: str) -> dict:
    from tools.thread_context import propagate_context_to_thread     # NOT published
    box = {}

    def run():
        t0 = time.time()
        try:
            box["r"] = asyncio.run(_client_deliver(target, mode, text))
        except BaseException as exc:
            box["r"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        box["r"]["seconds"] = round(time.time() - t0, 3)
    th = threading.Thread(target=propagate_context_to_thread(run))
    th.start()
    th.join()
    return box["r"]


def ctx_deliver(key: str, text: str) -> dict:
    """The published seam: ctx.inject_message (queue-only producer admission on v0.23)."""
    try:
        ok = _ctx["ctx"].inject_message(text, session_key=key)
        return {"ok": bool(ok), "applied": "queue-or-start" if ok else None, "calls": ["ctx.inject_message"]}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


# ---------------------------------------------------------------- socket (intercom's, _serve replaced)

def _serve(conn: socket.socket) -> None:
    inbox = _ctx["inbox"]
    try:
        if inbox._peer_uid(conn) != os.getuid():
            raise PermissionError("uid")
        conn.settimeout(120)
        data = b""
        while b"\n" not in data:
            chunk = conn.recv(65536)
            if not chunk:
                break
            data += chunk
        req = json.loads(data.split(b"\n", 1)[0] or b"{}")
        op = req.get("op")
        if op == "whoami":
            resp = {"ok": True, "pid": os.getpid(), **_role()}
        elif op == "deliver" and req.get("how") == "client":
            resp = client_deliver(req["target"], req["mode"], req["text"])
        elif op == "deliver" and req.get("how") == "ctx":
            resp = ctx_deliver(req["key"], req["text"])
        else:
            resp = {"ok": False, "error": "op"}
        _log("serve", req={k: req.get(k) for k in ("op", "how", "target", "key", "mode")}, resp=resp)
    except Exception as exc:
        resp = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    try:
        conn.sendall((json.dumps(resp, default=str) + "\n").encode())
    finally:
        conn.close()


# ---------------------------------------------------------------- reply route (post_llm_call)

def _text(c) -> str:
    if isinstance(c, list):
        return "\n".join(str(p.get("text", "")) for p in c if isinstance(p, dict))
    return str(c or "")


def _on_post_llm_call(session_id=None, user_message=None, assistant_response=None, conversation_history=None,
                      platform=None, **kw) -> None:
    um = _text(user_message)
    steer_rows = [_text(m.get("content")) for m in (conversation_history or [])
                  if isinstance(m, dict) and m.get("display_kind") == "steer"]
    _log("hook", session_id=session_id, platform=platform, user_message=um[:160], steer_rows=[s[:160] for s in steer_rows],
         answer=str(assistant_response or "")[:200], **_role())
    m = re.search(r"REPLYTO=(\S+)", um + "\n" + "\n".join(steer_rows))
    if m and "ISREPLY" not in um:
        target = m.group(1)

        def run():
            r = client_deliver(target, "steer", f"ISREPLY from {session_id}: {str(assistant_response or '')[:120]}")
            _log("reply", from_session=session_id, to=target, result=r)
        from tools.thread_context import propagate_context_to_thread
        threading.Thread(target=propagate_context_to_thread(run), daemon=True, name="r3-reply").start()


def install(ctx, inbox) -> None:
    _ctx["ctx"], _ctx["inbox"] = ctx, inbox
    inbox._serve = _serve
    ctx.register_hook("post_llm_call", _on_post_llm_call)
    inbox.start()
    _log("start", meta=inbox.self_meta(), **_role())
