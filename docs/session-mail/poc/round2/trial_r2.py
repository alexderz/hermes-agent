"""DER-701 Trial round 2 (FROZEN RECORD, NEVER PRODUCT CODE): HLD round-2 PoC questions R1-R11.

Fidelity:
- one throwaway HERMES_HOME per run, holding only values generated here;
- a real gated dashboard backend (`hermes_cli.web_server`) on a free 127.0.0.1 port;
- a real messaging gateway (`hermes gateway run`) with the bundled ntfy platform adapter, pointed at
  a fake ntfy server on 127.0.0.1 that records every publish;
- a real interactive classic CLI (`hermes`) under a pseudo-terminal;
- a fake OpenAI-compatible model that records every request;
- intercom copied UNEDITED from the clone into <home>/plugins/intercom/, with the trial overlay
  (intercom_overlay/) replacing only its register() and adding r2_trial.py.

The core seam is trial code in r2_trial.py (monkeypatched host calls); Hermes is not patched.

Run from the repo root:
  PYTHONDONTWRITEBYTECODE=1 <trial-venv>/bin/python docs/session-mail/poc/round2/trial_r2.py \
      --run <run-dir> --intercom-clone <intercom-clone>
"""
import argparse
import base64
import json
import os
import pty
import queue
import re
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
INTERCOM_CLONE = Path(".")  # set from --intercom-clone (a checkout of alexderz/hermes-intercom at ae90a2a)
STEER_OPEN = "[OUT-OF-BAND USER MESSAGE"
HDR = re.compile(r"^📡 hermes@.*· mail ([0-9a-f]{8})\s*$", re.M)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def text_of(c):
    if isinstance(c, list):
        return "\n".join(str(p.get("text", "")) for p in c if isinstance(p, dict))
    return str(c or "")


def _num(pat, s, d):
    m = re.search(pat, s)
    return type(d)(m.group(1)) if m else d


# ---------------------------------------------------------------- fake model

class Model:
    def __init__(self):
        self.requests, self.lock = [], threading.Lock()

    def find(self, pred):
        with self.lock:
            return [r for r in self.requests if pred(r)]


def plan(msgs):
    idx = 0
    for i, m in enumerate(msgs):
        if m.get("role") == "user" and not text_of(m.get("content")).lstrip().startswith(STEER_OPEN):
            idx = i
    prompt = text_of(msgs[idx].get("content")) if msgs else ""
    after = msgs[idx + 1:]
    steps = sum(1 for m in after if m.get("role") == "tool")
    called = any("intercom" in json.dumps(c) for m in after if m.get("role") == "assistant"
                 for c in (m.get("tool_calls") or []))
    return idx, prompt, steps, called


def final_answer(msgs, idx, prompt):
    if "SILENTONLY" in prompt:
        return "[SILENT]"
    tag = _num(r"TAG=(\w+)", prompt, "mail")
    blocks = []
    for m in msgs[idx:]:
        if m.get("role") != "user":
            continue
        t = text_of(m.get("content"))
        for part in re.split(r"(?=^📡 hermes@)", t, flags=re.M):
            h = HDR.search(part)
            if not h:
                continue
            rnd = _num(r"round=(\d+)", part, 0)
            body = "[SILENT]" if rnd >= 3 else f"answer from {tag} round={rnd + 1 if rnd else 0}"
            blocks.append(f"[REPLY {h.group(1)}] {body} [/REPLY]")
    return "\n".join([f"DONE {tag}"] + blocks)


def start_model(model, port, readable):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            msgs = req.get("messages", [])
            if not req.get("tools"):
                return self.reply(req, {"role": "assistant", "content": "Probe title"}, "stop")
            idx, prompt, steps, called = plan(msgs)
            tools = [t.get("function", {}).get("name") for t in req.get("tools", [])]
            with model.lock:
                model.requests.append({"t": time.time(), "tag": _num(r"TAG=(\w+)", prompt, ""), "steps": steps,
                                       "prompt": prompt, "msgs": msgs, "flat": json.dumps(msgs, ensure_ascii=False)})
            n = _num(r"STEPS=(\d+)", prompt, 0)
            delay = _num(r"DELAY=([\d.]+)", prompt, 1.0)
            call = re.search(r"CALL=(\S+?)\|(\w+)\|([^\n]*)", prompt)
            reads = steps - (1 if called else 0)
            if call and not called:
                time.sleep(0.3)
                args = {"action": "send", "to": call.group(1), "delivery": call.group(2), "message": call.group(3)}
                fn = ({"name": "intercom", "arguments": json.dumps(args)} if "intercom" in tools else
                      {"name": "tool_call", "arguments": json.dumps({"calls": [{"name": "intercom", "arguments": args}]})})
                return self.reply(req, {"role": "assistant", "content": None, "tool_calls": [
                    {"id": f"c{time.time_ns()}", "type": "function", "function": fn}]}, "tool_calls")
            if reads < n:
                time.sleep(delay)
                return self.reply(req, {"role": "assistant", "content": None, "tool_calls": [
                    {"id": f"r{time.time_ns()}", "type": "function",
                     "function": {"name": "read_file", "arguments": json.dumps({"path": readable})}}]}, "tool_calls")
            time.sleep(0.3)
            return self.reply(req, {"role": "assistant", "content": final_answer(msgs, idx, prompt)}, "stop")

        def reply(self, req, message, finish):
            try:
                self.send_response(200)
                if req.get("stream"):
                    self.send_header("Content-Type", "text/event-stream")
                    self.end_headers()
                    d = dict(message)
                    if d.get("tool_calls"):
                        d["tool_calls"] = [dict(c, index=i) for i, c in enumerate(d["tool_calls"])]
                    for delta, f in [(d, None), ({}, finish)]:
                        ev = {"id": "p", "object": "chat.completion.chunk", "model": "probe",
                              "choices": [{"index": 0, "delta": delta, "finish_reason": f}]}
                        self.wfile.write(("data: " + json.dumps(ev) + "\n\n").encode())
                    self.wfile.write(b"data: [DONE]\n\n")
                else:
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"id": "p", "object": "chat.completion", "model": "probe",
                        "choices": [{"index": 0, "message": message, "finish_reason": finish}],
                        "usage": {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13}}).encode())
            except (BrokenPipeError, ConnectionResetError):
                pass

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()


# ---------------------------------------------------------------- fake ntfy server

class Ntfy:
    def __init__(self):
        self.inbox, self.published, self.lock = queue.Queue(), [], threading.Lock()

    def push(self, text):
        self.inbox.put({"id": secrets.token_hex(6), "time": int(time.time()), "event": "message",
                        "topic": "probe-in", "message": text})

    def start(self, port):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        me = self

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson")
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()

                def chunk(obj):
                    b = (json.dumps(obj) + "\n").encode()
                    self.wfile.write(f"{len(b):x}\r\n".encode() + b + b"\r\n")
                    self.wfile.flush()
                try:
                    chunk({"id": "o", "time": int(time.time()), "event": "open", "topic": "probe-in"})
                    while True:
                        try:
                            chunk(me.inbox.get(timeout=5))
                        except queue.Empty:
                            chunk({"id": "k", "time": int(time.time()), "event": "keepalive", "topic": "probe-in"})
                except Exception:
                    return

            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode(errors="replace")
                with me.lock:
                    me.published.append({"t": time.time(), "path": self.path, "body": body})
                out = json.dumps({"id": secrets.token_hex(6), "event": "message"}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)

        srv = ThreadingHTTPServer(("127.0.0.1", port), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()


# ---------------------------------------------------------------- WS client (agent key)

class Client:
    n = 0

    def __init__(self, port, key):
        from websockets.sync.client import connect
        self.ws = connect(f"ws://127.0.0.1:{port}/api/ws?token={key}", max_size=None)
        self.events, self.pending, self.lock = [], {}, threading.Lock()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        try:
            while True:
                f = json.loads(self.ws.recv())
                with self.lock:
                    if f.get("id") in self.pending:
                        self.pending[f["id"]] = f
                    elif f.get("method") == "event":
                        self.events.append((time.time(), f["params"]))
        except Exception:
            pass

    def call(self, method, params, timeout=60):
        Client.n += 1
        rid = 50_000 + Client.n
        with self.lock:
            self.pending[rid] = None
        self.ws.send(json.dumps({"jsonrpc": "2.0", "id": rid, "method": method, "params": params}))
        end = time.time() + timeout
        while time.time() < end:
            with self.lock:
                if self.pending[rid] is not None:
                    return self.pending.pop(rid)
            time.sleep(0.02)
        raise TimeoutError(method)

    def saw(self, etype, sid, since):
        with self.lock:
            return [p for t, p in self.events if p.get("type") == etype and p.get("session_id") == sid and t >= since]

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def backend(port):
    from hermes_cli.plugins import discover_plugins
    discover_plugins()
    from hermes_cli.web_server import start_server
    start_server(host="127.0.0.1", port=port, open_browser=False, headless=True)


# ---------------------------------------------------------------- trial

class Trial:
    def __init__(self, run):
        self.run, self.home, self.out = run, run / "home", run / "out"
        for d in (self.home, self.out):
            if d.exists():
                shutil.rmtree(d)
            d.mkdir(parents=True)
        (self.home / "user").mkdir()
        (self.home / "notes.txt").write_text("probe\n")
        self.key = secrets.token_urlsafe(48)
        kf = self.home / "dashboard-agent.key"
        kf.write_text(self.key)
        os.chmod(kf, 0o600)
        self.mport, self.port, self.nport = free_port(), free_port(), free_port()
        self.model, self.ntfy = Model(), Ntfy()
        start_model(self.model, self.mport, str(self.home / "notes.txt"))
        self.ntfy.start(self.nport)
        dst = self.home / "plugins" / "intercom"
        shutil.copytree(INTERCOM_CLONE, dst, ignore=shutil.ignore_patterns(".git", "tests", "__pycache__"))
        for f in (HERE / "intercom_overlay").glob("*.py"):
            shutil.copy(f, dst / f.name)
        self.intercom_sha = subprocess.check_output(["git", "-C", str(INTERCOM_CLONE), "rev-parse", "--short", "HEAD"],
                                                    text=True).strip()
        (self.home / "r2-trial.json").write_text(json.dumps({
            "dispatch_path": str(REPO / "scripts" / "dashboard_dispatch.py"), "url": f"http://127.0.0.1:{self.port}",
            "key_file": str(kf)}))
        self.write_config()
        (self.home / ".env").write_text(
            f"NTFY_TOPIC=probe-in\nNTFY_SERVER_URL=http://127.0.0.1:{self.nport}\nNTFY_ALLOW_ALL_USERS=true\n")
        os.chmod(self.home / ".env", 0o600)
        self.env = {"PATH": os.environ.get("PATH", ""), "HOME": str(self.home / "user"), "LANG": "C.UTF-8",
                    "HERMES_HOME": str(self.home), "PYTHONPATH": str(REPO), "OPENAI_API_KEY": "probe-key",
                    "PYTHONDONTWRITEBYTECODE": "1", "TERM": "xterm-256color", "COLUMNS": "160", "LINES": "50"}
        self.procs, self.results = {}, {"checks": [], "obs": {}}
        self.results["sha"] = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, text=True).strip()
        self.results["intercom_sha"] = self.intercom_sha

    def write_config(self):
        from plugins.dashboard_auth.basic import hash_password
        secret = base64.b64encode(secrets.token_bytes(32)).decode()
        (self.home / "config.yaml").write_text(f"""model:
  default: probe
  provider: custom
  base_url: http://127.0.0.1:{self.mport}/v1
  api_key: probe-key
dashboard:
  public_url: https://probe.invalid
  basic_auth:
    username: probe
    password_hash: "{hash_password(secrets.token_urlsafe(16))}"
    secret: "{secret}"
  ws_orphan_reap_grace_s: 3
  ws_orphan_activity_stale_s: 60
display:
  busy_input_mode: interrupt
platform_toolsets:
  cli: [file]
  tui: [file]
  ntfy: [file]
plugins:
  enabled: [intercom, ntfy-platform]
  entries:
    intercom:
      allow_gateway_injection: true
memory:
  memory_enabled: false
  user_profile_enabled: false
""")

    # bookkeeping
    def check(self, q, name, ok, detail=None):
        self.results["checks"].append({"q": q, "name": name, "pass": bool(ok), "detail": detail})
        print(json.dumps(self.results["checks"][-1], default=str, ensure_ascii=False)[:900], flush=True)

    def obs(self, k, v):
        self.results["obs"][k] = v
        print("OBS", k, json.dumps(v, default=str, ensure_ascii=False)[:900], flush=True)

    def wait(self, pred, timeout, step=0.25):
        end = time.time() + timeout
        while time.time() < end:
            try:
                if pred():
                    return True
            except Exception:
                pass
            time.sleep(step)
        return False

    def jsonl(self):
        p = self.home / "r2-trial.jsonl"
        return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []

    def db(self, sql, *a):
        c = sqlite3.connect(self.home / "state.db", timeout=10)
        try:
            return c.execute(sql, a).fetchall()
        finally:
            c.close()

    def rows_with(self, mid):
        return self.db("select session_id, role from messages where content like ?", f"%· mail {mid}%")

    # processes
    def spawn(self, name, args, **kw):
        log = (self.out / f"{name}.log").open("w")
        p = subprocess.Popen(args, cwd=REPO, env=self.env, stdin=subprocess.DEVNULL, stdout=log,
                             stderr=subprocess.STDOUT, **kw)
        self.procs[name] = p
        return p

    def start_dashboard(self):
        p = self.spawn("dashboard", [sys.executable, str(Path(__file__).resolve()), "--backend", str(self.port)])
        ok = self.wait(lambda: urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/auth/providers", timeout=2), 90)
        if not ok and p.poll() is not None:
            raise RuntimeError("dashboard exited")
        return p

    def start_gateway(self):
        return self.spawn("gateway", [sys.executable, "-m", "hermes_cli.main", "gateway", "run"])

    def start_cli(self):
        pid, fd = pty.fork()
        if pid == 0:
            os.chdir(REPO)
            os.execve(sys.executable, [sys.executable, "-m", "hermes_cli.main"], self.env)
        import fcntl, struct, termios
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", 50, 160, 0, 0))
        self.cli_pid, self.cli_fd = pid, fd
        self.cli_out = (self.out / "cli.log").open("wb")

        def drain():
            while True:
                try:
                    b = os.read(fd, 65536)
                except OSError:
                    return
                if not b:
                    return
                self.cli_out.write(b)
                self.cli_out.flush()
        threading.Thread(target=drain, daemon=True).start()

    def cli_type(self, text):
        os.write(self.cli_fd, text.encode())
        time.sleep(0.4)
        os.write(self.cli_fd, b"\r")

    def stop(self, name):
        p = self.procs.get(name)
        if p and p.poll() is None:
            p.terminate()
            try:
                p.wait(15)
            except subprocess.TimeoutExpired:
                p.kill()

    def client(self):
        return Client(self.port, self.key)

    def send_cli(self, to, message, delivery="steer"):
        t0 = time.time()
        r = subprocess.run([sys.executable, "-m", "hermes_cli.main", "intercom", "send", "--to", to, "--message",
                            message, "--delivery", delivery], cwd=REPO, env=self.env, capture_output=True, text=True,
                           timeout=120)
        line = next((ln for ln in r.stdout.splitlines()[::-1] if ln.startswith("{")), None)
        res = json.loads(line) if line else {"ok": False, "error": (r.stdout + r.stderr)[-600:]}
        res["cli_seconds"] = round(time.time() - t0, 2)
        res["rc"] = r.returncode
        return res

    def new_dash_session(self, label, keep=True):
        c = self.client()
        r = c.call("session.create", {"source": "tui"})["result"]
        sid = r["session_id"]
        stored = r.get("stored_session_id") or sid
        t0 = time.time()
        c.call("prompt.submit", {"session_id": sid, "text": f"TAG=init{label} STEPS=0"})
        self.wait(lambda: c.saw("message.complete", sid, t0), 30)
        if not keep:
            c.close()
            c = None
        return c, sid, stored

    def leases(self):
        p = self.home / "runtime" / "active_sessions.json"
        try:
            return json.loads(p.read_text()).get("entries", [])
        except Exception:
            return []

    def mail_ran_as_prompt(self, mid):
        return self.model.find(lambda r: f"· mail {mid}" in r["prompt"])

    def mail_steered(self, mid, tag):
        return self.model.find(lambda r: r["tag"] == tag and any(
            m.get("role") == "user" and text_of(m.get("content")).lstrip().startswith(STEER_OPEN)
            and f"· mail {mid}" in text_of(m.get("content")) for m in r["msgs"]))


# ---------------------------------------------------------------- R1 per host

def mode_cells(T, host, target, start_turn, tag_prefix, settle=25):
    """For each mode: start a long turn on the target, mail it, record applied mode and what the model saw."""
    cells = {}
    for mode in ("steer", "queue", "interrupt"):
        tag = f"{tag_prefix}{mode}"
        start_turn(f"TAG={tag} STEPS=6 DELAY=1.0")
        if not T.wait(lambda: len(T.model.find(lambda r: r["tag"] == tag)) >= 2, 40):
            cells[mode] = {"error": "long turn never started"}
            continue
        res = T.send_cli(target, f"mail for {tag} (mode {mode})", mode)
        mid = res.get("mail")
        T.wait(lambda: T.mail_ran_as_prompt(mid) or T.mail_steered(mid, tag), settle)
        time.sleep(2)
        steps_done = max((r["steps"] for r in T.model.find(lambda r: r["tag"] == tag)), default=0)
        cells[mode] = {"requested": mode, "applied": res.get("applied"), "detail": res.get("applied_detail"),
                       "host": res.get("host"), "error": res.get("error"), "steered_into_turn": bool(T.mail_steered(mid, tag)),
                       "ran_as_own_turn": bool(T.mail_ran_as_prompt(mid)), "long_turn_steps": steps_done,
                       "rows": T.rows_with(mid) if mid else None, "cli_seconds": res.get("cli_seconds")}
        T.wait(lambda: not T.model.find(lambda r: time.time() - r["t"] < 2.5), 30)  # let the host go quiet
    # idle start
    res = T.send_cli(target, f"TAG={tag_prefix}idle STEPS=0 idle mail", "steer")
    mid = res.get("mail")
    T.wait(lambda: T.mail_ran_as_prompt(mid), 30)
    cells["idle"] = {"applied": res.get("applied"), "host": res.get("host"), "error": res.get("error"),
                     "ran_as_own_turn": bool(T.mail_ran_as_prompt(mid))}
    T.obs(f"R1_{host}", cells)
    exp = {"steer": "steer", "queue": "queue", "interrupt": "interrupt"}
    for mode, want in exp.items():
        c = cells.get(mode, {})
        seen = c.get("steered_into_turn") if want == "steer" else c.get("ran_as_own_turn")
        T.check("R1", f"{host}: {mode} applied as {want} and observed", c.get("applied") == want and seen, c)
    T.check("R1", f"{host}: idle target starts a turn", cells["idle"].get("applied") == "start"
            and cells["idle"].get("ran_as_own_turn"), cells["idle"])
    return cells


def r1_dashboard(T):
    c, sid, stored = T.new_dash_session("r1d")
    T.r1d = stored

    def start(text):
        c.call("prompt.submit", {"session_id": sid, "text": text})
    T.obs("leases_after_dash_init", T.leases())
    cells = mode_cells(T, "dashboard", stored, start, "d")
    q = cells.get("queue", {})
    T.check("R1", "dashboard: queued mail has a transcript row (accept-time row)", bool(q.get("rows")), q.get("rows"))
    c.close()


def r1_cli(T):
    T.start_cli()
    ok = T.wait(lambda: b"Type your message" in (T.out / "cli.log").read_bytes(), 90)
    time.sleep(3)
    got = False
    for attempt in range(3):
        T.cli_type("TAG=cinit STEPS=0")
        got = T.wait(lambda: T.model.find(lambda r: r["tag"] == "cinit"), 15)
        if got:
            break
    T.obs("R2_cli_type_attempts", attempt + 1)
    T.wait(lambda: any(e.get("surface") == "cli" for e in T.leases()), 20)
    cli_lease = next((e for e in T.leases() if e.get("surface") == "cli"), None)
    T.obs("R2_cli_lease", cli_lease)
    if not (got and cli_lease):
        T.check("R2", "interactive CLI started and holds a lease", False, {"started": ok, "turn": bool(got)})
        return
    T.cli_sid = cli_lease["session_id"]
    time.sleep(2)
    cells = mode_cells(T, "cli", T.cli_sid, T.cli_type, "c")
    T.check("R2", "CLI receives mail through intercom's socket (host pid = CLI pid)",
            all(str(v.get("host")) == f"pid:{T.cli_pid}" for k, v in cells.items() if k != "idle"),
            {k: v.get("host") for k, v in cells.items()})


def r4_gateway(T):
    T.start_gateway()
    up = T.wait(lambda: any("gateway" in (json.loads(p.read_text()).get("roles") or [])
                            for p in (T.home / "intercom" / "sessions").glob("*.json")), 90)
    T.obs("R4_endpoint_role_seconds_bound", up)
    T.check("R4", "gateway endpoint marks itself (roles: gateway) after the host is published", up)
    T.ntfy.push("TAG=ginit STEPS=0")
    got = T.wait(lambda: T.db("select id from sessions where source='ntfy'"), 60)
    if not got:
        T.check("R4", "ntfy chat produced a gateway session", False, (T.out / "gateway.log").read_text()[-1500:])
        return
    T.wait(lambda: T.ntfy.published, 30)
    T.gw_sid = T.db("select id from sessions where source='ntfy' order by started_at")[0][0]
    T.obs("R4_gateway_session", {"sid": T.gw_sid, "published_answers": len(T.ntfy.published)})
    time.sleep(2)
    cells = mode_cells(T, "gateway", T.gw_sid, T.ntfy.push, "g", settle=30)
    T.check("R4", "gateway: mail routed to the gateway endpoint",
            all("gateway" in str(v.get("host")) for v in cells.values()), {k: v.get("host") for k, v in cells.items()})
    n0 = len(T.ntfy.published)
    res = T.send_cli(T.gw_sid, "SILENTONLY bare silence test", "steer")
    T.wait(lambda: T.mail_ran_as_prompt(res.get("mail")), 30)
    time.sleep(5)
    posted = [p["body"] for p in T.ntfy.published[n0:]]
    T.obs("R4_silent_posts", posted)
    T.check("R4", "a bare [SILENT] answer to mail is not posted to the chat", not any("[SILENT]" in b for b in posted),
            posted)


def r3_many_sessions(T):
    ca, sa, A = T.new_dash_session("r3a")
    cb, sb, B = T.new_dash_session("r3b")
    if cb:
        cb.close()
    t0 = time.time()
    ca.call("prompt.submit", {"session_id": sa, "text": f"TAG=r3a STEPS=4 DELAY=1.0 CALL={B}|steer|TAG=r3b round=1"})
    T.wait(lambda: any(e.get("kind") == "hook" and "silent" in json.dumps(e) for e in T.jsonl()) or
           T.wait(lambda: False, 0), 5)
    T.wait(lambda: len([e for e in T.jsonl() if e.get("kind") == "send" and e["t"] > t0]) >= 3, 60)
    time.sleep(4)
    sends = [e for e in T.jsonl() if e.get("kind") == "send" and e["t"] > t0]
    T.obs("R3_sends", [{k: e.get(k) for k in ("mail", "sender", "to", "requested", "applied", "host", "error")} for e in sends])
    first = next((e for e in sends if e.get("to") == B and not e.get("reply_to")), None)
    T.check("R3", "dashboard chat A mails chat B in the same process (in-process seam)",
            first and first.get("host") == "in-process" and first.get("ok"), first)
    leak = []
    for e in sends:
        rows = T.rows_with(e["mail"])
        if any(r[0] != e["to"] for r in rows) or len(rows) != 1:
            leak.append({"mail": e["mail"], "to": e["to"], "rows": rows})
    T.check("R3", "every mail landed once, only in its addressed session", not leak and sends, leak)
    T.check("R3", "B's automatic reply came back to A", any(e.get("to") == A and e.get("reply_to") for e in sends))
    # A torn-down (not loaded) session and a lazy-loaded one fall through to the wake path.
    _, _, C = T.new_dash_session("r3c", keep=False)
    time.sleep(6)
    res = T.send_cli(C, "TAG=r3cm STEPS=0 to a torn-down session", "steer")
    T.check("R3/R7", "a session live nowhere is woken by the sender (dispatcher rule)",
            res.get("applied") == "start" and "wake" in str(res.get("host")), res)
    _, _, D = T.new_dash_session("r3d", keep=False)
    time.sleep(6)
    cl = T.client()
    cl.call("session.resume", {"session_id": D, "source": "tui", "lazy": True, "omit_messages": True})
    T.obs("R3_leases_with_lazy", [e for e in T.leases() if e.get("session_id") == D])
    res = T.send_cli(D, "TAG=r3dm STEPS=0 to a lazy session", "steer")
    T.obs("R3_lazy_send", res)
    T.check("R3", "a lazy-loaded session still receives (seam or wake fall-through)", res.get("ok"), res)
    cl.close()
    ca.close()


def r6_replies(T):
    ca, sa, A = T.new_dash_session("r6a")
    out = {}
    for name, target in (("cli", getattr(T, "cli_sid", None)), ("gateway", getattr(T, "gw_sid", None))):
        if not target:
            out[name] = "host not running"
            continue
        t0 = time.time()
        ca.call("prompt.submit", {"session_id": sa, "text": f"TAG=r6{name} STEPS=3 DELAY=1.0 CALL={target}|steer|reply test round=1"})
        T.wait(lambda: any(e.get("kind") == "send" and e.get("to") == A and e.get("reply_to") and e["t"] > t0
                           for e in T.jsonl()), 60)
        rep = [e for e in T.jsonl() if e.get("kind") == "send" and e.get("to") == A and e.get("reply_to") and e["t"] > t0]
        out[name] = rep[0] if rep else None
        T.check("R6", f"reply from the {name} host's post_llm_call reached the dashboard sender",
                bool(rep) and rep[0].get("ok"), rep[0] if rep else None)
        T.wait(lambda: not T.model.find(lambda r: time.time() - r["t"] < 3), 30)
    T.obs("R6_replies", out)
    ca.close()


def r5_exactly_once(T):
    sends = [e for e in T.jsonl() if e.get("kind") == "send" and e.get("ok")]
    bad, dup = [], []
    for e in sends:
        rows = [r for r in T.rows_with(e["mail"]) if r[1] == "user"]
        if not rows or any(r[0] != e["to"] for r in rows):
            bad.append({"mail": e["mail"], "to": e["to"], "host": e.get("host"), "rows": rows})
        elif len(rows) > 1:
            dup.append({"mail": e["mail"], "applied": e.get("applied"), "host": e.get("host"), "rows": len(rows)})
    seen_turns = {e["mail"]: len(T.model.find(lambda r, m=e["mail"]: f"· mail {m}" in r["prompt"])) for e in sends}
    T.obs("R5_counts", {"delivered": len(sends), "wrong_session": bad[:10], "duplicate_rows": dup,
                        "ran_as_prompt_requests": seen_turns})
    T.check("R5", "every delivered mail is in its target session only (no cross-delivery)", sends and not bad, bad[:5])
    T.check("R5", "duplicate rows occur only for tui queued mail (the accept-time row is not adopted)",
            all(d["applied"] == "queue" and "pid:" in str(d["host"]) for d in dup), dup)
    cli_sid = getattr(T, "cli_sid", None)
    if cli_sid:
        reg = next((p for p in (T.home / "intercom" / "sessions").glob("*.json")
                    if json.loads(p.read_text()).get("pid") == T.cli_pid), None)
        if reg:
            saved = reg.read_text()
            reg.unlink()
            res = T.send_cli(cli_sid, "to a process without an intercom endpoint", "steer")
            reg.write_text(saved)
            T.check("R5", "a lease pid with no intercom endpoint returns no-endpoint", res.get("error") == "no-endpoint", res)


def r7_down_hosts(T):
    gw = getattr(T, "gw_sid", None)
    if gw:
        T.stop("gateway")
        T.wait(lambda: not any("gateway" in (json.loads(p.read_text()).get("roles") or [])
                               for p in (T.home / "intercom" / "sessions").glob("*.json") if p.exists()), 20)
        res = T.send_cli(gw, "gateway target while the gateway is down", "steer")
        T.check("R7", "gateway-source target with no gateway: no-gateway, no dashboard fall-through",
                res.get("error") == "no-gateway", res)
    _, _, W = T.new_dash_session("r7w", keep=False)
    time.sleep(6)
    T.stop("dashboard")
    res = T.send_cli(W, "while the dashboard is down", "steer")
    T.check("R7", "live-nowhere target with no dashboard returns an error", not res.get("ok"), res)


def r9_intercom_tests(T):
    r = subprocess.run([sys.executable, "-I", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"],
                       cwd=INTERCOM_CLONE, capture_output=True, text=True, timeout=120,
                       env={"PATH": os.environ.get("PATH", ""), "HOME": str(T.home / "user"),
                            "PYTHONDONTWRITEBYTECODE": "1"})
    tail = (r.stdout + r.stderr).strip().splitlines()[-4:]
    T.obs("R9_intercom_tests", {"rc": r.returncode, "tail": tail})
    T.check("R9", "intercom's own tests pass on the unedited clone", r.returncode == 0, tail)


def main(run, only):
    T = Trial(run)
    scen = [("r1_dashboard", r1_dashboard), ("r3", r3_many_sessions), ("r4_gateway", r4_gateway),
            ("r1_cli", r1_cli), ("r6", r6_replies), ("r5", r5_exactly_once), ("r7", r7_down_hosts),
            ("r9", r9_intercom_tests)]
    try:
        T.start_dashboard()
        for name, fn in scen:
            if only and name not in only:
                continue
            t = time.time()
            try:
                fn(T)
            except Exception as exc:
                import traceback
                T.check(name, f"scenario {name} raised", False, traceback.format_exc()[-1200:])
            print(f"== {name} {time.time() - t:.1f}s", flush=True)
    finally:
        for name in list(T.procs):
            T.stop(name)
        if getattr(T, "cli_pid", None):
            try:
                os.kill(T.cli_pid, 9)
                os.waitpid(T.cli_pid, 0)
            except Exception:
                pass
        T.results["passed"] = sum(c["pass"] for c in T.results["checks"])
        T.results["total"] = len(T.results["checks"])
        T.results["model_requests"] = len(T.model.requests)
        T.results["ntfy_published"] = len(T.ntfy.published)
        (T.out / "results.json").write_text(json.dumps(T.results, indent=2, default=str, ensure_ascii=False))
        print(json.dumps({"passed": T.results["passed"], "total": T.results["total"]}), flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", type=int)
    ap.add_argument("--run", type=Path)
    ap.add_argument("--only", default="")
    ap.add_argument("--intercom-clone", type=Path)
    a = ap.parse_args()
    if a.intercom_clone:
        INTERCOM_CLONE = a.intercom_clone.resolve()
    sys.path.insert(0, str(REPO))
    if a.backend:
        backend(a.backend)
    else:
        main(a.run, {x for x in a.only.split(",") if x})
