#!/usr/bin/env python3
"""Start (or continue) a chat turn INSIDE the running dashboard, then detach.

The turn runs in the dashboard process, so it survives this script exiting, and every client
attached to that dashboard (Hermes Mobile, the web app, Desktop) can open the chat and steer it
while it works. That is not possible with ``hermes chat -q``: a CLI process owns its session
until its turn ends, and other surfaces get ``SESSION_NOT_OWNED``.

Authenticates with the local agent key (``hermes_cli/dashboard_auth/agent_key.py``), which the
dashboard accepts only on a direct loopback connection.

Examples::

    dashboard_dispatch.py --title "Project — Orchestrator" --cwd ~/projects/x --prompt-file brief.txt
    dashboard_dispatch.py --resume 20261108_203430_7745d1 --prompt "Status?"

Prints the session id as JSON on stdout. Exit code 0 once the dashboard accepted the prompt.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import urllib.parse
from pathlib import Path


def _hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")


def _read_key(path: str | None) -> str:
    p = Path(os.path.expanduser(path)) if path else _hermes_home() / "dashboard-agent.key"
    try:
        return p.read_text(encoding="utf-8").strip()
    except OSError as exc:
        sys.exit(f"dashboard_dispatch: cannot read agent key {p}: {exc}")


async def _rpc(ws, rid: int, method: str, params: dict, timeout: float) -> dict:
    await ws.send(json.dumps({"jsonrpc": "2.0", "id": rid, "method": method, "params": params}))
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        remaining = deadline - loop.time()
        if remaining <= 0:
            raise TimeoutError(f"{method}: no reply within {timeout:.0f}s")
        frame = json.loads(await asyncio.wait_for(ws.recv(), remaining))
        if frame.get("id") != rid or "method" in frame:
            continue  # events / notifications / server requests
        if "error" in frame:
            err = frame["error"]
            raise RuntimeError(f"{method} failed: {err.get('code')} {err.get('message')}")
        return frame.get("result") or {}


async def _main(a: argparse.Namespace) -> dict:
    import websockets

    token = _read_key(a.key_file)
    base = a.url.rstrip("/").replace("http://", "ws://", 1).replace("https://", "wss://", 1)
    uri = f"{base}/api/ws?" + urllib.parse.urlencode({"token": token})
    text = Path(a.prompt_file).read_text(encoding="utf-8") if a.prompt_file else a.prompt
    async with websockets.connect(uri, max_size=None, open_timeout=a.timeout) as ws:
        if a.resume:
            res = await _rpc(ws, 1, "session.resume", {"session_id": a.resume}, a.timeout)
        else:
            # The title is applied when the first turn writes the row (session.create's pending_title).
            params = {"close_on_disconnect": False}
            if a.title:
                params["title"] = a.title
            if a.cwd:
                params.update(cwd=os.path.abspath(os.path.expanduser(a.cwd)), cwd_explicit=True)
            res = await _rpc(ws, 1, "session.create", params, a.timeout)
        live_id = res.get("session_id") or a.resume
        stored = res.get("stored_session_id") or live_id
        await _rpc(ws, 3, "prompt.submit", {"session_id": live_id, "text": text}, a.timeout)
        return {"session_id": live_id, "stored_session_id": stored}


def main() -> None:
    ap = argparse.ArgumentParser(description="Start a chat turn inside the running dashboard, then detach.")
    ap.add_argument("--url", default=os.environ.get("HERMES_DASHBOARD_URL", "http://127.0.0.1:9119"))
    ap.add_argument("--key-file", default=None, help="default <HERMES_HOME>/dashboard-agent.key")
    ap.add_argument("--title")
    ap.add_argument("--cwd", help="workspace / project folder for a new session")
    ap.add_argument("--resume", help="existing session id to continue instead of creating one")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--prompt")
    g.add_argument("--prompt-file")
    ap.add_argument("--timeout", type=float, default=60.0)
    a = ap.parse_args()
    print(json.dumps(asyncio.run(_main(a))))


if __name__ == "__main__":
    main()
