"""The processes and fakes behind ``test_e2e_owner.py``: one temporary home, every surface real.

- a scripted, recording fake model (``FakeLLMServer`` with a responder) that also names the process
  each request came from, by the TCP peer of the request;
- a fake ntfy server: one HTTP stream out (the bundled ntfy adapter's subscription), and every
  publish recorded;
- a real ``hermes gateway run`` owner, the bundled ntfy adapter inside it;
- a real classic CLI (``display.interface: cli``) under a pty, a client of that owner;
- owner-attached clients (``discover_gateway_endpoint`` + ``connect_gateway`` +
  ``session.create``), which is what the Ink TUI and the Desktop do;
- a real standalone ``hermes dashboard`` (the admin panel), whose chats the owner cannot reach;
- ``hook-probe``, a test plugin written into the temp home only: each turn it records its process's
  live hook table, so a hook registered after load (B12's legacy drain) is visible.

The model reads directives from the turn's prompt (the newest user row that is not a steer):

- ``TAG=<word>`` names the turn; ``STEPS=<n>`` makes it read a file ``n`` times before answering;
- ``CALL=<to>|<delivery>|<reply>|<message to end of line>`` makes it call the intercom tool once;
- ``ECHOWAIT`` anywhere in the turn's rows makes its final answer wait (bounded) until the fake ntfy
  server has a post naming every intercom message in those rows: the latency a real model has.

The final answer is ``DONE <tag>``, plus ``[REPLY <id>] answer from <tag> [/REPLY]`` for each intercom
message in the turn's rows whose label asks for an answer. A test can hold any request of a turn
(``Model.hold``) to keep that turn running while it delivers.
"""

from __future__ import annotations

import asyncio
import json
import os
import queue
import re
import secrets
import shutil
import signal
import sqlite3
import subprocess
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import psutil

from tests.e2e.core.chaos._helpers import chaos_config, hermetic_env, python_exe
from tests.fakes.fake_llm_provider import MODEL_ID, OFFER_VERSION, FakeLLMServer, Text, ToolCall, _handler_for
from tests.waiting import wait_until

USER_NAME = "Avery"
PRIVATE_TOPIC = "probe-in"      # listed in echo_chats: a private chat
GROUP_TOPIC = "probe-group"     # not listed: a shared chat
PUBLISH_TOPIC = "probe-out"
STEER_OPEN = "[OUT-OF-BAND USER MESSAGE"
HEADER_RE = re.compile(r"^📡 Not [^\n]*message ([0-9a-f]{8})\):$", re.MULTILINE)
ANSWER_LABELS = ("· reply requested ·", "· waiting on your reply ·")
_CALL_RE = re.compile(r"CALL=(\S+?)\|(\w+)\|(\w+)\|([^\n]*)")
HOLD_S = 120.0
ECHO_WAIT_S = 20.0
BOOT_S = 60.0
TURN_S = 90.0
COLS, ROWS = 160, 50


def text_of(content: Any) -> str:
    if isinstance(content, list):
        return "\n".join(str(p.get("text", "")) for p in content if isinstance(p, dict))
    return content if isinstance(content, str) else ""


def frame_ids(text: str) -> list[str]:
    return HEADER_RE.findall(text or "")


def _num(pattern: str, text: str, default: int) -> int:
    m = re.search(pattern, text)
    return int(m.group(1)) if m else default


# ── fake ntfy ────────────────────────────────────────────────────────────────


class Ntfy:
    """A fake ntfy server: streams pushed events to each subscriber, records every publish."""

    def __init__(self) -> None:
        self.posts: list[dict[str, Any]] = []
        self.subscriptions: list[str] = []
        self._subscribers: list[queue.Queue] = []
        self._cond = threading.Condition()
        self._server: ThreadingHTTPServer | None = None

    @property
    def url(self) -> str:
        assert self._server is not None
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def push(self, topic: str, text: str) -> None:
        event = {"id": secrets.token_hex(6), "time": int(time.time()), "event": "message",
                 "topic": topic, "message": text}
        with self._cond:
            for q in self._subscribers:
                q.put(event)

    def bodies(self, since: float = 0.0) -> list[str]:
        with self._cond:
            return [p["body"] for p in self.posts if p["t"] >= since]

    def wait_for(self, predicate, timeout: float) -> bool:
        """Block (no polling sleep) until ``predicate(bodies)`` holds or ``timeout`` passes."""
        deadline = time.monotonic() + timeout
        with self._cond:
            while not predicate([p["body"] for p in self.posts]):
                left = deadline - time.monotonic()
                if left <= 0:
                    return False
                self._cond.wait(left)
        return True

    def start(self) -> None:
        me = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_a: object) -> None:
                pass

            def do_GET(self) -> None:
                q: queue.Queue = queue.Queue()
                with me._cond:
                    me._subscribers.append(q)
                    me.subscriptions.append(self.path)
                    me._cond.notify_all()
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson")
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                try:
                    self._chunk({"id": "open", "time": int(time.time()), "event": "open"})
                    while True:
                        try:
                            self._chunk(q.get(timeout=5))
                        except queue.Empty:
                            self._chunk({"id": "ka", "time": int(time.time()), "event": "keepalive"})
                except OSError:
                    return
                finally:
                    with me._cond:
                        me._subscribers.remove(q)

            def _chunk(self, obj: dict) -> None:
                data = (json.dumps(obj) + "\n").encode()
                self.wfile.write(f"{len(data):x}\r\n".encode() + data + b"\r\n")
                self.wfile.flush()

            def do_POST(self) -> None:
                body = self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode("utf-8", "replace")
                with me._cond:
                    me.posts.append({"t": time.time(), "path": self.path, "body": body})
                    me._cond.notify_all()
                out = json.dumps({"id": secrets.token_hex(6), "event": "message"}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        threading.Thread(target=self._server.serve_forever, name="fake-ntfy", daemon=True).start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()


# ── scripted model ───────────────────────────────────────────────────────────


@dataclass
class Hold:
    arrived: threading.Event = field(default_factory=threading.Event)
    release: threading.Event = field(default_factory=threading.Event)


@dataclass
class Request:
    t: float
    tag: str
    prompt: str
    rows: list[str]        # the prompt, then the steer rows after it
    steps: int             # tool results after the prompt
    steers: list[str]      # steer rows anywhere in the request
    host: str | None       # which known process sent it
    results: list[str]     # tool results after the prompt


class Model:
    """The responder: directives from the prompt, holds, and the host of every request."""

    def __init__(self, ntfy: Ntfy, readable: Path) -> None:
        self.ntfy, self.readable = ntfy, str(readable)
        self.requests: list[Request] = []
        self.processes: dict[str, int] = {}
        self._holds: dict[tuple[str, int], Hold] = {}
        self._lock = threading.Lock()
        self.peer = threading.local()

    def hold(self, tag: str, step: int = 0) -> Hold:
        h = Hold()
        with self._lock:
            self._holds[(tag, step)] = h
        return h

    def release_all(self) -> None:
        with self._lock:
            for h in self._holds.values():
                h.release.set()

    def find(self, pred) -> list[Request]:
        with self._lock:
            return [r for r in self.requests if pred(r)]

    def tagged(self, tag: str) -> list[Request]:
        return self.find(lambda r: r.tag == tag)

    def respond(self, record: dict[str, Any]):
        body = record["body"]
        msgs = body.get("messages") or []
        idx = _prompt_index(msgs)
        prompt = text_of(msgs[idx].get("content")) if msgs else ""
        after = msgs[idx + 1:]
        rows = [prompt] + [text_of(m.get("content")) for m in after
                           if m.get("role") == "user" and _is_steer(m)]
        steps = sum(1 for m in after if m.get("role") == "tool")
        called = any(_calls_intercom(m) for m in after if m.get("role") == "assistant")
        tag = (re.search(r"TAG=(\w+)", prompt) or [None, ""])[1]
        req = Request(time.time(), tag, prompt, rows, steps,
                      [text_of(m.get("content")) for m in msgs if m.get("role") == "user" and _is_steer(m)],
                      self._host(), [text_of(m.get("content")) for m in after if m.get("role") == "tool"])
        with self._lock:
            self.requests.append(req)
            hold = self._holds.get((tag, steps))
        if hold is not None:
            hold.arrived.set()
            hold.release.wait(HOLD_S)
        tools = {(t.get("function") or {}).get("name") for t in body.get("tools") or []}
        call = _CALL_RE.search(prompt)
        if call and not called:
            args = {"action": "send", "to": call.group(1), "delivery": call.group(2),
                    "reply": call.group(3), "message": call.group(4)}
            return _tool(tools, "intercom", args)
        if steps - (1 if called else 0) < _num(r"STEPS=(\d+)", prompt, 0):
            return _tool(tools, "read_file", {"path": self.readable})
        if any("ECHOWAIT" in row for row in rows):
            ids = [i for row in rows for i in frame_ids(row)]
            self.ntfy.wait_for(lambda bodies: all(any(f"message {i})" in b for b in bodies) for i in ids),
                               ECHO_WAIT_S)
        return Text(final_answer(tag, rows))

    def _host(self) -> str | None:
        addr = getattr(self.peer, "addr", None)
        if addr is None:
            return None
        for name, pid in list(self.processes.items()):
            try:
                root = psutil.Process(pid)
                family = [root, *root.children(recursive=True)]
            except psutil.Error:
                continue
            for proc in family:
                try:
                    if any(c.laddr and (c.laddr.ip, c.laddr.port) == tuple(addr[:2])
                           for c in proc.net_connections(kind="tcp")):
                        return name
                except psutil.Error:
                    continue
        return None


def _is_steer(message: dict) -> bool:
    return text_of(message.get("content")).lstrip().startswith(STEER_OPEN)


def _calls_intercom(message: dict) -> bool:
    """Whether an assistant row called the intercom tool, directly or through ``tool_call``."""
    for call in message.get("tool_calls") or []:
        fn = (call.get("function") if isinstance(call, dict) else None) or {}
        if fn.get("name") == "intercom":
            return True
        if fn.get("name") == "tool_call":
            try:
                inner = json.loads(fn.get("arguments") or "{}").get("calls") or []
            except (ValueError, AttributeError):
                continue
            if any(isinstance(c, dict) and c.get("name") == "intercom" for c in inner):
                return True
    return False


def _prompt_index(msgs: list[dict]) -> int:
    idx = 0
    for i, m in enumerate(msgs):
        if m.get("role") == "user" and not _is_steer(m):
            idx = i
    return idx


def _tool(tools: set, name: str, args: dict) -> ToolCall:
    if name in tools:
        return ToolCall(name, args)
    return ToolCall("tool_call", {"calls": [{"name": name, "arguments": args}]})


def find_receipt(value: Any) -> dict | None:
    """The intercom receipt inside a tool result (direct, or wrapped by ``tool_call``)."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return None
    if isinstance(value, dict):
        if "receipt" in value or ("error" in value and "message_id" in value):
            return value
        value = list(value.values())
    if isinstance(value, list):
        return next((found for item in value if (found := find_receipt(item))), None)
    return None


def final_answer(tag: str, rows: list[str]) -> str:
    lines = [f"DONE {tag}"]
    for row in rows:
        for header in HEADER_RE.finditer(row):
            if any(label in header.group(0) for label in ANSWER_LABELS):
                lines.append(f"[REPLY {header.group(1)}] answer from {tag} [/REPLY]")
    return "\n".join(lines)


class _ModelServer(FakeLLMServer):
    """``FakeLLMServer`` whose handler leaves the request's TCP peer for the responder."""

    def __init__(self, model: Model) -> None:
        super().__init__(model.respond)
        self._model = model

    def start(self) -> None:
        base, peer = _handler_for(self), self._model.peer

        class Handler(base):  # type: ignore[misc, valid-type]
            def do_POST(self) -> None:
                peer.addr = self.client_address
                super().do_POST()

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.daemon_threads = True
        self._server = server
        self._thread = threading.Thread(target=server.serve_forever, name="fake-llm", daemon=True)
        self._thread.start()


# ── dashboard websocket ──────────────────────────────────────────────────────


class WsClient:
    """JSON-RPC over the dashboard's ``/api/ws``, as the dashboard's own chat page speaks it."""

    def __init__(self, url: str) -> None:
        from websockets.sync.client import connect

        self.ws = connect(url, max_size=None, open_timeout=30)
        self._pending: dict[int, Any] = {}
        self._cond = threading.Condition()
        self._n = 0
        threading.Thread(target=self._read, daemon=True, name="dash-ws").start()

    def _read(self) -> None:
        try:
            while True:
                frame = json.loads(self.ws.recv())
                with self._cond:
                    if frame.get("id") in self._pending:
                        self._pending[frame["id"]] = frame
                        self._cond.notify_all()
        except Exception:  # the socket closed: pending calls time out
            return

    def call(self, method: str, params: dict, timeout: float = 60.0) -> dict:
        with self._cond:
            self._n += 1
            rid = self._n
            self._pending[rid] = None
        self.ws.send(json.dumps({"jsonrpc": "2.0", "id": rid, "method": method, "params": params}))
        deadline = time.monotonic() + timeout
        with self._cond:
            while self._pending[rid] is None:
                left = deadline - time.monotonic()
                if left <= 0:
                    raise TimeoutError(method)
                self._cond.wait(left)
            return self._pending.pop(rid)

    def close(self) -> None:
        try:
            self.ws.close()
        except Exception:
            pass


# ── the world ────────────────────────────────────────────────────────────────


HOOK_PROBE = "hook-probe"
HOOK_PROBE_YAML = f"""\
name: {HOOK_PROBE}
version: 0.1.0
description: "Test plugin: at each turn, write this process's live hook table to the home."
provides_tools: []
provides_hooks: [pre_llm_call]
"""
# The live table, not plugins.list's load-time count: a hook registered lazily (B12's legacy drain is
# registered at the first intercom call) shows here and nowhere else.
HOOK_PROBE_INIT = '''"""hook-probe: each pre_llm_call appends {pid, hook: [module:qualname]} to hook-probe.jsonl."""
import json
import os
import time

from hermes_cli.plugins import iter_hook_callbacks
from hermes_constants import get_hermes_home

HOOKS = ("pre_llm_call", "pre_api_request", "post_llm_call", "on_session_end")


def _snapshot(**_kw):
    record = {"pid": os.getpid(), "t": time.time()}
    for hook in HOOKS:
        record[hook] = [f"{getattr(cb, '__module__', '?')}:{getattr(cb, '__qualname__', '?')}"
                        for cb in iter_hook_callbacks(hook)]
    with open(get_hermes_home() / "hook-probe.jsonl", "a", encoding="utf-8") as out:
        out.write(json.dumps(record) + "\\n")


def register(ctx):
    ctx.register_hook("pre_llm_call", _snapshot)
'''


def home_config(model_url: str) -> str:
    """The temp home's config.yaml: the chaos knobs, plus what the ticket names for intercom."""
    return chaos_config(model_url, stale_timeout=600, request_timeout=600, max_turns=12, extra=(
        "auxiliary:\n  title_generation:\n    enabled: false\n"
        "models_dev:\n  url: http://127.0.0.1:9/api.json\n"
        f"telemetry:\n  shared_metrics:\n    enabled: false\n    send: false\n    offer_version: {OFFER_VERSION}\n"
        "display:\n  interface: cli\n"
        "plugins:\n"
        f"  enabled: [intercom, ntfy-platform, {HOOK_PROBE}]\n"
        "  entries:\n"
        "    intercom:\n"
        "      allow_gateway_injection: true\n"
        "      settings:\n"
        f"        user_name: {USER_NAME}\n"
        f"        echo_chats: [\"ntfy:{PRIVATE_TOPIC}\"]\n"))


def env_file(ntfy_url: str) -> str:
    """The temp home's .env: only the fake ntfy server's values (two topics: one private, one group)."""
    return (f"NTFY_SERVER_URL={ntfy_url}\n"
            f"NTFY_TOPIC={PRIVATE_TOPIC},{GROUP_TOPIC}\n"
            f"NTFY_PUBLISH_TOPIC={PUBLISH_TOPIC}\n"
            f"NTFY_ALLOWED_USERS={PRIVATE_TOPIC},{GROUP_TOPIC}\n")


class World:
    def __init__(self, root: Path, intercom_src: Path, tag: str) -> None:
        self.root, self.tag = root, tag
        self.home = root / "home"
        self.hermes_home = self.home / ".hermes"
        self.work = root / "work"
        self.logs = root / "logs"
        for d in (self.hermes_home, self.work, self.logs):
            d.mkdir(parents=True, exist_ok=True)
        (self.work / "notes.txt").write_text("probe\n", encoding="utf-8")
        self.ntfy = Ntfy()
        self.ntfy.start()
        self.model = Model(self.ntfy, self.work / "notes.txt")
        self.server = _ModelServer(self.model)
        self.server.start()
        (self.hermes_home / "config.yaml").write_text(home_config(self.server.base_url), encoding="utf-8")
        (self.hermes_home / ".env").write_text(env_file(self.ntfy.url), encoding="utf-8")
        self.plugin = self.hermes_home / "plugins" / "intercom"
        shutil.copytree(intercom_src, self.plugin,
                        ignore=shutil.ignore_patterns(".git", "tests", "docs", "__pycache__", "*.pyc"))
        probe = self.hermes_home / "plugins" / HOOK_PROBE
        probe.mkdir(parents=True)
        (probe / "plugin.yaml").write_text(HOOK_PROBE_YAML, encoding="utf-8")
        (probe / "__init__.py").write_text(HOOK_PROBE_INIT, encoding="utf-8")
        env = hermetic_env(self.home, self.hermes_home, tag)
        for key in ("NOTIFY_SOCKET", "INVOCATION_ID", "XDG_STATE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME",
                    "XDG_CACHE_HOME", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS", "TMUX", "TMUX_PANE"):
            env.pop(key, None)
        # Host rendezvous stays inside the tmp root: the developer's live gateway is never seen.
        env.update(HERMES_GATEWAY_LOCK_DIR=str(root / "locks"), HERMES_GATEWAY_MAX_STARTS="0",
                   HERMES_DISABLE_LAZY_INSTALLS="1", NO_PROXY="127.0.0.1,localhost", no_proxy="127.0.0.1,localhost",
                   LANG="C.UTF-8", LC_ALL="C.UTF-8")
        self.env = env
        self.procs: dict[str, subprocess.Popen] = {}
        self.endpoint: Any = None
        self.cli_fd: int | None = None
        self.cli_out = bytearray()
        self.dash_port: int | None = None
        self.dash_ws: WsClient | None = None
        self.dash_live = ""                 # the dashboard chat's live id (its own runtime's)
        self.sender = ""                    # the owner-attached session the Q2 and echo sends come from
        self.group = ""                     # the unlisted ntfy chat
        self.kinds: dict[str, str] = {}     # kind -> the stored session id of its target

    # owner
    def start_owner(self) -> None:
        from hermes_cli.gateway_runtime import discover_gateway_endpoint

        subscribed = len(self.ntfy.subscriptions)
        proc = self._spawn("owner", ["gateway", "run", "--quiet"])
        self.endpoint = self.poll(
            lambda: discover_gateway_endpoint(self.hermes_home, timeout=1.0).endpoint
            or (proc.poll() is not None and "exited"), BOOT_S, "the owner to be discoverable")
        assert self.endpoint != "exited", f"gateway exited rc={proc.returncode}\n{self.log_tail('owner')}"
        self.poll(lambda: len(self.ntfy.subscriptions) > subscribed, BOOT_S, "the ntfy adapter to subscribe")
        self.model.processes["owner"] = proc.pid

    def stop_owner(self) -> None:
        proc = self.procs.pop("owner")
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=90)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
        self.model.processes.pop("owner", None)

    def rpc(self, *calls: tuple[str, dict]) -> list[Any]:
        from hermes_cli.gateway_client import connect_gateway

        async def run() -> list[Any]:
            out = []
            async with connect_gateway(self.endpoint) as client:
                for method, params in calls:
                    out.append(await client.rpc(method, **params))
            return out
        return asyncio.run(run())

    def attached_session(self, text: str) -> str:
        """An owner-attached session (``session.create``, as Ink and Desktop do) with one turn."""
        made = self.rpc(("session.create", {"source": "tui"}))[0]
        self.rpc(("session.resume", {"session_id": made["session_id"], "omit_messages": True}),
                 ("prompt.submit", {"session_id": made["session_id"], "text": text,
                                    "submission_id": secrets.token_hex(8)}))
        return made["stored_session_id"]

    def attached_submit(self, sid: str, text: str) -> None:
        """Resume *sid* on one attached connection and submit *text* on the live id it returns."""
        from hermes_cli.gateway_client import connect_gateway

        async def run() -> None:
            async with connect_gateway(self.endpoint) as client:
                resumed = await client.rpc("session.resume", session_id=sid, omit_messages=True)
                await client.rpc("prompt.submit", session_id=resumed["session_id"], text=text,
                                 submission_id=secrets.token_hex(8))
        asyncio.run(run())

    # classic CLI under a pty
    def start_cli(self) -> None:
        import fcntl
        import struct
        import termios

        master, slave = os.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", ROWS, COLS, 0, 0))
        env = {**self.env, "TERM": "xterm-256color", "COLUMNS": str(COLS), "LINES": str(ROWS)}
        proc = subprocess.Popen([python_exe(), "-m", "hermes_cli.main"], cwd=str(self.work), env=env,
                                stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
        os.close(slave)
        self.procs["cli"] = proc
        self.cli_fd = master
        log = (self.logs / "cli.log").open("wb")

        def drain() -> None:
            while True:
                try:
                    chunk = os.read(master, 65536)
                except OSError:
                    return
                if not chunk:
                    return
                self.cli_out.extend(chunk)
                log.write(chunk)
                log.flush()
        threading.Thread(target=drain, daemon=True, name="cli-pty").start()
        self.model.processes["cli"] = proc.pid
        try:
            wait_until(lambda: f"\u2624 {MODEL_ID}" in self.cli_tail(), timeout=BOOT_S, interval=0.2,
                       what="the classic CLI's status bar")
        except AssertionError as exc:
            raise AssertionError(f"{exc}\n--- cli screen ---\n{self.cli_tail()}") from None

    def cli_tail(self, n: int = 3000) -> str:
        return re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", bytes(self.cli_out).decode("utf-8", "replace"))[-n:]

    def cli_type(self, text: str) -> None:
        assert self.cli_fd is not None
        os.write(self.cli_fd, text.encode())
        # health: allow HX013 -- the CLI takes an Enter within 50 ms of typing for a pasted newline
        time.sleep(1.2)
        os.write(self.cli_fd, b"\r")

    def stop_cli(self) -> None:
        proc = self.procs.pop("cli", None)
        self.model.processes.pop("cli", None)
        if proc is None or proc.poll() is not None:
            return
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)

    # admin dashboard
    def start_dashboard(self) -> None:
        dist = self.root / "web_dist"
        dist.mkdir(exist_ok=True)
        (dist / "index.html").write_text(
            "<!doctype html><html><head><title>hermes</title></head><body><div id=root></div></body></html>",
            encoding="utf-8")
        proc = self._spawn("dashboard", ["dashboard", "--no-open", "--skip-build", "--host", "127.0.0.1",
                                         "--port", "0"], extra={"HERMES_WEB_DIST": str(dist)}, group=True)
        ready = re.compile(r"HERMES_DASHBOARD_READY port=(\d+)")
        self.dash_port = int(self.poll(
            lambda: (m := ready.search(self.log_tail("dashboard", 200000))) and m.group(1)
            or (proc.poll() is not None and "0"), BOOT_S, "the dashboard to report its port"))
        assert self.dash_port, f"dashboard exited rc={proc.returncode}\n{self.log_tail('dashboard')}"
        import httpx

        index = httpx.get(f"http://127.0.0.1:{self.dash_port}/", timeout=60, trust_env=False).text
        token = re.search(r'__HERMES_SESSION_TOKEN__\s*=\s*"([^"]+)"', index)
        assert token, "the dashboard's index.html carried no session token"
        self.dash_ws = WsClient(f"ws://127.0.0.1:{self.dash_port}/api/ws?token={token.group(1)}")
        self.model.processes["dashboard"] = proc.pid

    def dashboard_session(self, text: str) -> tuple[str, str]:
        """A dashboard chat (the admin panel's own ``session.create``) with one turn: (live, stored)."""
        assert self.dash_ws is not None
        made = self.dash_ws.call("session.create", {"source": "tui"})
        assert "result" in made, made
        live = made["result"]["session_id"]
        stored = made["result"].get("stored_session_id") or live
        sub = self.dash_ws.call("prompt.submit", {"session_id": live, "text": text})
        assert "result" in sub, sub
        return live, stored

    # sends
    def tool_send(self, to: str, delivery: str, reply: str, body: str, *, sender: str | None = None) -> dict:
        """The sender session's model calls the intercom tool once; returns the tool's receipt."""
        tag = f"s{secrets.token_hex(4)}"
        self.attached_submit(sender or self.sender, f"TAG={tag} CALL={to}|{delivery}|{reply}|{body}")
        req = self.poll(lambda: next((r for r in self.model.tagged(tag) if r.results), None), TURN_S,
                        f"the intercom tool result of {tag}")
        receipt = next((found for text in req.results if (found := find_receipt(text))), None)
        assert receipt is not None, req.results
        return receipt

    def start_long(self, kind: str, tag: str, steps: int = 2) -> Hold:
        """A turn of *steps* file reads on the *kind* target, held at its first model request."""
        hold = self.model.hold(tag, 0)
        text = f"TAG={tag} STEPS={steps}"
        if kind == "owner_attached":
            self.attached_submit(self.kinds[kind], text)
        elif kind == "classic_cli":
            self.cli_type(text)
        elif kind == "messaging_ntfy":
            self.ntfy.push(PRIVATE_TOPIC, text)
        else:
            assert self.dash_ws is not None
            self.dash_ws.call("prompt.submit", {"session_id": self.dash_live, "text": text})
        assert hold.arrived.wait(TURN_S), f"the long turn {tag} on {kind} never reached the model"
        return hold

    def steered(self, needle: str, tag: str) -> list[Request]:
        return self.model.find(lambda r: r.tag == tag and any(needle in s for s in r.steers))

    # intercom's CLI (a script sender; an owner client of its own)
    def intercom(self, *args: str) -> tuple[int, dict]:
        ran = subprocess.run([python_exe(), "-m", "hermes_cli.main", "intercom", *args, "--json"],
                             cwd=str(self.work), env=self.env, stdin=subprocess.DEVNULL, capture_output=True,
                             text=True, timeout=TURN_S, check=False)
        line = next((ln for ln in reversed(ran.stdout.splitlines()) if ln.startswith("{")), None)
        return ran.returncode, (json.loads(line) if line else {"stdout": ran.stdout, "stderr": ran.stderr[-3000:]})

    # state
    def db(self, sql: str, *args: Any) -> list[tuple]:
        conn = sqlite3.connect(f"file:{self.hermes_home / 'state.db'}?mode=ro", uri=True, timeout=30)
        try:
            return conn.execute(sql, args).fetchall()
        finally:
            conn.close()

    def hook_tables(self, pid: int | None) -> list[dict]:
        """The hook-probe snapshots process *pid* wrote, oldest first."""
        path = self.hermes_home / "hook-probe.jsonl"
        if not path.exists():
            return []
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return [row for row in rows if pid is None or row["pid"] == pid]

    def record(self, message_id: str) -> dict | None:
        path = self.hermes_home / "plugin-data" / "intercom" / "record.db"
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
        finally:
            conn.close()
        return dict(row) if row else None

    def session_with(self, token: str) -> str:
        """The stored session whose transcript has a user row carrying *token*."""
        def find():
            try:
                rows = self.db("SELECT session_id FROM messages WHERE role = 'user' AND content LIKE ? "
                               "ORDER BY id", f"%{token}%")
            except sqlite3.Error:
                return None
            return rows[0][0] if rows else None
        return self.poll(find, TURN_S, f"a stored session with {token}")

    def answered(self, tag: str) -> Request:
        """The final request of turn *tag* (the one that got the answer), once it happened."""
        return self.poll(lambda: next((r for r in self.model.tagged(tag)
                                       if r.steps >= _num(r"STEPS=(\d+)", r.prompt, 0)
                                       + (1 if _CALL_RE.search(r.prompt) else 0)), None),
                         TURN_S, f"turn {tag} to reach its answer")

    def quiet(self, secs: float = 2.0) -> None:
        """Until neither the model nor ntfy has seen anything for *secs*: earlier turns are over."""
        def still() -> bool:
            now = time.time()
            return (not self.model.find(lambda r: now - r.t < secs)
                    and not any(now - p["t"] < secs for p in list(self.ntfy.posts)))
        self.poll(still, TURN_S, "the model and ntfy to go quiet")

    # helpers
    def poll(self, pred, timeout: float, what: str):
        try:
            return wait_until(pred, timeout=timeout, interval=0.1, what=what)
        except AssertionError as exc:
            raise AssertionError(f"{exc}\n--- owner log ---\n{self.log_tail('owner')}") from None

    def _spawn(self, name: str, args: list[str], extra: dict | None = None, group: bool = False) -> subprocess.Popen:
        log = (self.logs / f"{name}.log").open("ab")
        proc = subprocess.Popen([python_exe(), "-m", "hermes_cli.main", *args], cwd=str(self.work),
                                env={**self.env, **(extra or {})}, stdin=subprocess.DEVNULL, stdout=log,
                                stderr=subprocess.STDOUT, start_new_session=group)
        self.procs[name] = proc
        return proc

    def log_tail(self, name: str, n: int = 4000) -> str:
        try:
            return (self.logs / f"{name}.log").read_text(encoding="utf-8", errors="replace")[-n:]
        except OSError:
            return ""

    def close(self) -> None:
        self.model.release_all()
        if self.dash_ws is not None:
            self.dash_ws.close()
        self.stop_cli()
        for name, proc in list(self.procs.items()):
            if proc.poll() is None:
                if name == "dashboard":
                    os.killpg(proc.pid, signal.SIGTERM)
                else:
                    proc.send_signal(signal.SIGTERM)
                try:
                    proc.wait(timeout=60)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=10)
        self.server.stop()
        self.ntfy.stop()
