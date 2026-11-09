#!/usr/bin/env python3
"""Start (or continue) a chat turn INSIDE the running dashboard, then detach.

The turn runs in the dashboard process, so it survives this script exiting, and every client
attached to that dashboard (Hermes Mobile, the web app, Desktop) can open the chat and steer it
while it works. That is not possible with ``hermes chat -q``: a CLI process owns its session
until its turn ends, and other surfaces get ``SESSION_NOT_OWNED``.

Authenticates with the local agent key (``hermes_cli/dashboard_auth/agent_key.py``), which the
dashboard accepts only on a direct loopback connection. Run it with the Hermes venv's python so
it resolves the same key file as the dashboard (``dashboard.agent_key.file``).

Examples::

    dashboard_dispatch.py --title "Project — Orchestrator" --cwd ~/projects/x --prompt-file brief.txt
    dashboard_dispatch.py --resume 20261108_203430_7745d1 --prompt "Status?"

Disconnects only once the turn has visibly started (first agent event), so the dashboard's
detached-turn reaper sees a live, producing turn. Prints the session ids as JSON on stdout.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import urllib.parse
from pathlib import Path

# Events that prove the agent is running the turn (built and producing).
_STARTED = {"message.start", "message.delta", "thinking.delta", "reasoning.delta", "tool.start",
            "tool.progress", "message.complete", "error"}


def _key_path(explicit: str | None) -> Path:
    if explicit:
        return Path(os.path.expanduser(explicit))
    try:  # the dashboard's own resolution (config override, profile home)
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from hermes_cli.dashboard_auth.agent_key import key_path

        return key_path()
    except Exception:
        home = os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes")
        return Path(home) / "dashboard-agent.key"


def _read_key(explicit: str | None) -> str:
    p = _key_path(explicit)
    try:
        key = p.read_text(encoding="utf-8").strip()
    except (OSError, ValueError) as exc:
        sys.exit(f"dashboard_dispatch: cannot read agent key {p}: {type(exc).__name__}")
    if not key:
        sys.exit(f"dashboard_dispatch: agent key {p} is empty")
    return key


def _err_text(err) -> str:
    if isinstance(err, dict):
        return f"{err.get('code')} {err.get('message')}"
    return str(err)


async def _recv(ws, deadline: float) -> dict:
    remaining = deadline - asyncio.get_running_loop().time()
    if remaining <= 0:
        raise TimeoutError
    return json.loads(await asyncio.wait_for(ws.recv(), remaining))


async def _rpc(ws, rid: int, method: str, params: dict, timeout: float) -> dict:
    await ws.send(json.dumps({"jsonrpc": "2.0", "id": rid, "method": method, "params": params}))
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        try:
            frame = await _recv(ws, deadline)
        except TimeoutError:
            raise TimeoutError(f"{method}: no reply within {timeout:.0f}s") from None
        if frame.get("id") != rid or "method" in frame:
            continue  # events / notifications / server requests
        if "error" in frame:
            raise RuntimeError(f"{method} failed: {_err_text(frame['error'])}")
        return frame.get("result") or {}


async def _wait_started(ws, sid: str, timeout: float) -> str:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        try:
            frame = await _recv(ws, deadline)
        except TimeoutError:
            return ""
        params = frame.get("params") if frame.get("method") == "event" else None
        if isinstance(params, dict) and params.get("session_id") == sid and params.get("type") in _STARTED:
            return str(params["type"])


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
                params.update(cwd=a.cwd, cwd_explicit=True)
            res = await _rpc(ws, 1, "session.create", params, a.timeout)
        live_id = res.get("session_id")
        if not live_id:
            raise RuntimeError(f"no live session id in reply: {sorted(res)}")
        await _rpc(ws, 2, "prompt.submit", {"session_id": live_id, "text": text}, a.timeout)
        started = await _wait_started(ws, live_id, a.start_timeout)
        if not started:
            print(f"dashboard_dispatch: no agent activity within {a.start_timeout:.0f}s; detaching anyway "
                  "(the turn may still be building)", file=sys.stderr)
        return {"session_id": live_id, "stored_session_id": res.get("stored_session_id") or live_id,
                "started": started or None}


def main() -> None:
    ap = argparse.ArgumentParser(description="Start a chat turn inside the running dashboard, then detach.")
    ap.add_argument("--url", default=os.environ.get("HERMES_DASHBOARD_URL", "http://127.0.0.1:9119"))
    ap.add_argument("--key-file", default=None, help="default: the dashboard's own key path")
    ap.add_argument("--title")
    ap.add_argument("--cwd", help="workspace / project folder for a new session (must exist)")
    ap.add_argument("--resume", help="existing session id to continue instead of creating one")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--prompt")
    g.add_argument("--prompt-file")
    ap.add_argument("--timeout", type=float, default=60.0, help="per-RPC reply timeout")
    ap.add_argument("--start-timeout", type=float, default=240.0,
                    help="max wait for the turn's first agent event before detaching")
    a = ap.parse_args()
    if a.cwd:
        a.cwd = os.path.abspath(os.path.expanduser(a.cwd))
        if not os.path.isdir(a.cwd):
            ap.error(f"--cwd {a.cwd} is not a directory")
    try:
        print(json.dumps(asyncio.run(_main(a))))
    except (RuntimeError, TimeoutError, OSError) as exc:
        sys.exit(f"dashboard_dispatch: {exc}")


if __name__ == "__main__":
    main()
