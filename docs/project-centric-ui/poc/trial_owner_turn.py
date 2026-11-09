"""Trial (frozen record, never product code): can an owner-session turn run inside a dashboard
process, driven by a small kickoff client over /api/ws, while a second client (the phone)
attaches, steers, queues and interrupts it? Does it survive the reapers, and what happens on a
backend restart mid-turn?

Fidelity: a real `hermes_cli.web_server` backend subprocess on 127.0.0.1 with the dashboard
auth gate ON (bundled password provider), a temporary HERMES_HOME holding only throwaway
values generated here, and a local deterministic OpenAI-compatible fake model. No credentials,
no live install, no public listener. Modelled on evals/desktop_bug_campaign/leases_live.py.

Run from the repo root:  python docs/project-centric-ui/poc/trial_owner_turn.py --output <dir>
"""
import argparse
import base64
import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
STEPS = 8          # tool-call steps per long turn
STEP_DELAY = 1.5   # seconds the fake model waits per reply -> ~12 s+ turns


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ---------------- fake model ----------------

class Model:
    def __init__(self):
        self.requests = []  # (time, flattened messages text)
        self.lock = threading.Lock()

    def seen(self, marker):
        with self.lock:
            return any(marker in r[1] for r in self.requests)

    def count(self):
        with self.lock:
            return len(self.requests)


def start_model(model, port, readable_file):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            msgs = req.get("messages", [])
            flat = json.dumps(msgs)
            with model.lock:
                model.requests.append((time.time(), flat))
            # Auxiliary calls (titles etc.) carry no tools: answer at once.
            if not req.get("tools"):
                return self.reply(req, {"role": "assistant", "content": "Probe title"}, "stop")
            # Count tool results since the last user message: one step per tool result.
            last_user = max((i for i, m in enumerate(msgs) if m.get("role") == "user"), default=0)
            steps = sum(1 for m in msgs[last_user:] if m.get("role") == "tool")
            time.sleep(STEP_DELAY)
            if steps < STEPS:
                call = {"id": f"call_{steps}_{int(time.time()*1000)}", "type": "function",
                        "function": {"name": "read_file", "arguments": json.dumps({"path": readable_file})}}
                return self.reply(req, {"role": "assistant", "content": None, "tool_calls": [call]}, "tool_calls")
            return self.reply(req, {"role": "assistant", "content": "TURN_DONE"}, "stop")

        def reply(self, req, message, finish):
            self.send_response(200)
            if req.get("stream"):
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                delta = dict(message)
                if delta.get("tool_calls"):
                    delta["tool_calls"] = [dict(c, index=i) for i, c in enumerate(delta["tool_calls"])]
                for d, f in [(delta, None), ({}, finish)]:
                    ev = {"id": "p", "object": "chat.completion.chunk", "model": "probe",
                          "choices": [{"index": 0, "delta": d, "finish_reason": f}]}
                    self.wfile.write(("data: " + json.dumps(ev) + "\n\n").encode())
                self.wfile.write(b"data: [DONE]\n\n")
            else:
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"id": "p", "object": "chat.completion", "model": "probe",
                    "choices": [{"index": 0, "message": message, "finish_reason": finish}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13}}).encode())

    httpd = ThreadingHTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


# ---------------- auth: the mechanism under test ----------------

def mint_access_token(home):
    """Mint a short-lived access token in memory with the bundled password provider's own code,
    from the signing secret in this profile's config (what a same-account local client can do).
    Runs in a child with HERMES_HOME set so config resolution matches the dashboard's."""
    code = ("from plugins.dashboard_auth.basic import BasicAuthProvider, _settings\n"
            "s=_settings(); s['ttl_seconds']=60\n"
            "print(BasicAuthProvider(**s)._mint_session(s['username']).access_token)\n")
    env = dict(os.environ, HERMES_HOME=str(home), PYTHONPATH=str(REPO))
    return subprocess.check_output([sys.executable, "-c", code], cwd=REPO, env=env, text=True).strip()


def ws_ticket(port, access_token):
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/auth/ws-ticket", data=b"", method="POST",
                                 headers={"Authorization": f"Bearer {access_token}"})
    return json.load(urllib.request.urlopen(req, timeout=30))["ticket"]


class Client:
    """Minimal JSON-RPC client over /api/ws; the ticket rides in the subprotocol header."""
    n = 0

    def __init__(self, port, ticket, name):
        from websockets.sync.client import connect
        self.name = name
        self.ws = connect(f"ws://127.0.0.1:{port}/api/ws",
                          subprotocols=["hermes-gateway-v1", f"hermes-gateway-ticket.{ticket}"])
        self.events = []
        self.pending = {}
        self.lock = threading.Lock()
        self.alive = True
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        try:
            while True:
                f = json.loads(self.ws.recv())
                with self.lock:
                    if "id" in f and f.get("id") in self.pending:
                        self.pending[f["id"]] = f
                    elif f.get("method") == "event":
                        self.events.append((time.time(), f["params"]))
        except Exception:
            self.alive = False

    def call(self, method, params, timeout=60):
        Client.n += 1
        rid = Client.n
        with self.lock:
            self.pending[rid] = None
        self.ws.send(json.dumps({"jsonrpc": "2.0", "id": rid, "method": method, "params": params}))
        end = time.time() + timeout
        while time.time() < end:
            with self.lock:
                if self.pending[rid] is not None:
                    return self.pending.pop(rid)
            time.sleep(0.05)
        raise TimeoutError(method)

    def saw(self, etype, since=0.0):
        with self.lock:
            return [p for t, p in self.events if p.get("type") == etype and t >= since]

    def close(self):
        self.ws.close()


def raw_ws_close_code(port):
    from websockets.sync.client import connect
    from websockets.exceptions import ConnectionClosed, InvalidStatus
    try:
        ws = connect(f"ws://127.0.0.1:{port}/api/ws")
        try:
            ws.recv(timeout=5)
        except ConnectionClosed as e:
            return e.rcvd.code if e.rcvd else None
        return "open"
    except InvalidStatus as e:
        return f"http {e.response.status_code}"


# ---------------- harness ----------------

def write_home(home, model_port):
    from plugins.dashboard_auth.basic import hash_password
    secret = base64.b64encode(secrets.token_bytes(32)).decode()
    (home / "config.yaml").write_text(f"""model:
  default: probe
  provider: custom
  base_url: http://127.0.0.1:{model_port}/v1
  api_key: probe-key
dashboard:
  public_url: https://probe.invalid
  basic_auth:
    username: probe
    password_hash: "{hash_password(secrets.token_urlsafe(16))}"
    secret: "{secret}"
  ws_orphan_reap_grace_s: 3
  ws_orphan_activity_stale_s: 20
memory:
  memory_enabled: false
  user_profile_enabled: false
""")
    (home / "notes.txt").write_text("probe file\n")


def backend(port):
    # `hermes dashboard` discovers plugins before serving; the password provider is a backend plugin.
    from hermes_cli.plugins import discover_plugins
    discover_plugins()
    from hermes_cli.web_server import start_server
    start_server(host="127.0.0.1", port=port, open_browser=False, headless=True)


def rss_kb(pid):
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    except OSError:
        return None


def main(out):
    out.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(REPO))
    home = Path(tempfile.mkdtemp(prefix="owner-turn-trial-"))
    (home / "user").mkdir()
    model_port, port = free_port(), free_port()
    write_home(home, model_port)
    model = Model()
    start_model(model, model_port, str(home / "notes.txt"))
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(home / "user"), "LANG": "C.UTF-8",
           "HERMES_HOME": str(home), "PYTHONPATH": str(REPO), "OPENAI_API_KEY": "probe-key"}
    results = {"sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
               "fidelity": "real dashboard backend subprocess, auth gate on (password provider), "
                           "temporary HERMES_HOME, 127.0.0.1 only, fake local model",
               "checks": [], "rss_kb": []}

    def check(name, ok, detail=None):
        results["checks"].append({"name": name, "pass": bool(ok), "detail": detail})
        print(json.dumps(results["checks"][-1], default=str)[:600], flush=True)

    procs = []

    def start_backend(tag):
        log = (out / f"backend-{tag}.log").open("w")
        p = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--backend", str(port)],
                             cwd=REPO, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        procs.append(p)
        end = time.time() + 90
        while time.time() < end:
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/auth/providers", timeout=2)
                return p
            except urllib.error.HTTPError:
                return p
            except Exception:
                if p.poll() is not None:
                    raise RuntimeError(f"backend exited {p.returncode}")
                time.sleep(0.3)
        raise TimeoutError("backend readiness")

    def client(name):
        return Client(port, ws_ticket(port, mint_access_token(home)), name)

    def wait(pred, timeout):
        end = time.time() + timeout
        while time.time() < end:
            if pred():
                return True
            time.sleep(0.2)
        return False

    try:
        p = start_backend("1")
        # 1. Auth gate: no credential is refused; the minted-token -> ticket -> subprotocol path is accepted.
        check("gate on: bare /api/ws refused", raw_ws_close_code(port) in (4401, "http 403"), raw_ws_close_code(port))
        kick = client("kickoff")
        check("kickoff authenticated via minted token + ws-ticket subprotocol", kick.alive)

        created = kick.call("session.create", {"source": "tui"})
        sid = created["result"]["session_id"]
        stored = created["result"].get("stored_session_id") or created["result"].get("session_key")
        check("kickoff session.create", "result" in created, created.get("result", created))

        # 2. Long turn driven by the kickoff; phone attaches mid-turn.
        t0 = time.time()
        sub = kick.call("prompt.submit", {"session_id": sid, "text": "OWNER_TURN_1 do the long task"})
        check("kickoff prompt.submit accepted", "result" in sub, sub)
        wait(lambda: model.count() >= 3, 30)
        results["rss_kb"].append({"t": "turn1-early", "kb": rss_kb(p.pid)})

        phone = client("phone")
        res = phone.call("session.resume", {"session_id": stored, "source": "tui", "lazy": True, "omit_messages": True})
        r = res.get("result", {})
        check("phone session.resume reuses the live session and sees it running",
              r.get("session_id") == sid and r.get("running") is True,
              {k: r.get(k) for k in ("session_id", "running", "status")} if r else res)
        psid = r.get("session_id", sid)

        st = phone.call("session.steer", {"session_id": psid, "text": "STEER_MARKER_7"})
        check("phone session.steer accepted while kickoff turn runs", st.get("result", {}).get("status") == "queued", st)
        q = phone.call("prompt.submit", {"session_id": psid, "text": "QUEUE_MARKER_9 follow-up", "queued": True})
        check("phone queued prompt.submit accepted (no 4090)", "result" in q, q)

        check("steer text reached the model inside the running turn", wait(lambda: model.seen("STEER_MARKER_7"), 40))
        done1 = wait(lambda: len(kick.saw("message.complete", t0)) >= 1, 90)
        check("turn 1 completed; kickoff saw message.complete", done1, time.time() - t0)
        check("phone also saw turn 1 stream (same live session)", len(phone.saw("message.complete", t0)) >= 1)
        check("queued prompt ran as the next turn", wait(lambda: model.seen("QUEUE_MARKER_9"), 30))
        wait(lambda: len(kick.saw("message.complete", t0)) >= 2, 90)
        results["rss_kb"].append({"t": "after-turn2", "kb": rss_kb(p.pid)})

        # 3. Interrupt from the phone.
        t1 = time.time()
        kick.call("prompt.submit", {"session_id": sid, "text": "OWNER_TURN_3 long again"})
        wait(lambda: model.count() >= 2 and any("OWNER_TURN_3" in x[1] for x in model.requests), 30)
        it = phone.call("session.interrupt", {"session_id": psid})
        check("phone session.interrupt accepted", it.get("result", {}).get("status") == "interrupted", it)
        check("interrupted turn ended (message.complete) well before its natural length",
              wait(lambda: len(kick.saw("message.complete", t1)) >= 1, 20), time.time() - t1)

        # 4. Both clients gone mid-turn: does the detached turn keep running past the orphan grace?
        t2 = time.time()
        kick.call("prompt.submit", {"session_id": sid, "text": "OWNER_TURN_4 detached run"})
        wait(lambda: any("OWNER_TURN_4" in x[1] for x in model.requests), 30)
        n_before = model.count()
        kick.close(); phone.close()
        time.sleep(8)  # > ws_orphan_reap_grace_s (3 s)
        check("detached running turn keeps calling the model past the orphan grace", model.count() > n_before + 2,
              {"before": n_before, "after": model.count()})
        check("detached turn finished its steps (final step reached)",
              wait(lambda: sum(1 for x in model.requests if "OWNER_TURN_4" in x[1]) >= STEPS + 1, 60))
        results["rss_kb"].append({"t": "after-detached", "kb": rss_kb(p.pid)})

        # 5. Restart mid-turn: SIGKILL the backend, start it again, resume -> auto-continue?
        kick = client("kickoff-2")
        res = kick.call("session.resume", {"session_id": stored, "source": "tui", "lazy": True, "omit_messages": True})
        sid = res["result"]["session_id"]
        kick.call("prompt.submit", {"session_id": sid, "text": "OWNER_TURN_5 killed by restart"})
        wait(lambda: sum(1 for x in model.requests if "OWNER_TURN_5" in x[1]) >= 2, 30)
        p.send_signal(signal.SIGKILL); p.wait(10)
        check("kickoff socket dropped when the backend died", wait(lambda: not kick.alive, 10))
        n_kill = model.count()
        p = start_backend("2")
        kick = client("kickoff-3")
        # Non-lazy (cold) resume: auto-continue runs on the cold/eager resume paths only, not on lazy.
        res = kick.call("session.resume", {"session_id": stored, "source": "tui", "omit_messages": True})
        r = res.get("result", {})
        check("after restart, session.resume schedules auto-continue for a fresh killed turn",
              bool(r.get("auto_continue")), {k: r.get(k) for k in ("auto_continue", "running", "status")})
        check("continuation turn reached the model with the recovery note and the original prompt",
              wait(lambda: any("OWNER_TURN_5" in x[1] for x in model.requests[n_kill:]), 40))
        results["rss_kb"].append({"t": "after-restart", "kb": rss_kb(p.pid)})
        kick.close()
    finally:
        for pr in procs:
            if pr.poll() is None:
                pr.terminate()
                try:
                    pr.wait(10)
                except subprocess.TimeoutExpired:
                    pr.kill()
        results["model_requests"] = model.count()
        results["passed"] = sum(c["pass"] for c in results["checks"])
        results["total"] = len(results["checks"])
        (out / "results.json").write_text(json.dumps(results, indent=2, default=str))
        print(json.dumps({"passed": results["passed"], "total": results["total"]}), flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", type=int)
    ap.add_argument("--output", type=Path)
    a = ap.parse_args()
    if a.backend:
        backend(a.backend)
    else:
        main(a.output)
