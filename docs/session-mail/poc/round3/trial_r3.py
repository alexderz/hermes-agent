"""DER-701 Trial round 3 on v0.23 (FROZEN RECORD, NEVER PRODUCT CODE).

Questions (HLD O19, v023-delta.md D-1..D-4):
  Q1 which process hosts dashboard chats, owner-attached (Ink/Desktop-style) sessions, classic CLI
     sessions and messaging sessions;
  Q2 can a plugin INSIDE the owner drive steer / interrupt / queue / idle start / cold start for each
     kind, with the owner's existing verbs, and which calls are published (plugin_api.json);
  Q3 the reply route (post_llm_call) per kind, back to a sender of another kind.

Fidelity: one throwaway HERMES_HOME per run; a real `hermes gateway run` owner with the bundled ntfy
adapter against a fake ntfy server; a real `hermes dashboard` backend (gate on, agent key); a real
interactive classic CLI under a pty; a fake OpenAI-compatible model that records every request;
intercom copied UNEDITED, with intercom_overlay/ replacing only register() and _serve. All 127.0.0.1.

Reuses the round-2 fake model, fake ntfy server and agent-key WS client by loading that frozen file by
path (trial code only).

Run: PYTHONDONTWRITEBYTECODE=1 <venv023>/bin/python docs/session-mail/poc/round3/trial_r3.py \
       --run <run-dir> --intercom-clone <intercom-clone>
"""
import argparse
import asyncio
import base64
import importlib.util
import json
import os
import pty
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("trial_r2", REPO / "docs/session-mail/poc/round2/trial_r2.py")
r2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(r2)
STEER_OPEN = r2.STEER_OPEN
text_of = r2.text_of


class T3:
    def __init__(self, run, clone):
        self.run, self.home, self.out = run, run / "home", run / "out"
        for d in (self.home, self.out):
            shutil.rmtree(d, ignore_errors=True)
            d.mkdir(parents=True)
        (self.home / "user").mkdir()
        (self.home / "notes.txt").write_text("probe\n")
        self.key = secrets.token_urlsafe(48)
        kf = self.home / "dashboard-agent.key"
        kf.write_text(self.key)
        os.chmod(kf, 0o600)
        self.mport, self.dport, self.nport = r2.free_port(), r2.free_port(), r2.free_port()
        self.model, self.ntfy = r2.Model(), r2.Ntfy()
        r2.start_model(self.model, self.mport, str(self.home / "notes.txt"))
        self.ntfy.start(self.nport)
        dst = self.home / "plugins" / "intercom"
        shutil.copytree(clone, dst, ignore=shutil.ignore_patterns(".git", "tests", "__pycache__"))
        for f in (HERE / "intercom_overlay").glob("*.py"):
            shutil.copy(f, dst / f.name)
        from plugins.dashboard_auth.basic import hash_password
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
    secret: "{base64.b64encode(secrets.token_bytes(32)).decode()}"
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
        (self.home / ".env").write_text(
            f"NTFY_TOPIC=probe-in\nNTFY_SERVER_URL=http://127.0.0.1:{self.nport}\nNTFY_ALLOW_ALL_USERS=true\n")
        os.chmod(self.home / ".env", 0o600)
        self.env = {"PATH": os.environ.get("PATH", ""), "HOME": str(self.home / "user"), "LANG": "C.UTF-8",
                    "HERMES_HOME": str(self.home), "PYTHONPATH": str(REPO), "OPENAI_API_KEY": "probe-key",
                    "PYTHONDONTWRITEBYTECODE": "1", "TERM": "xterm-256color", "COLUMNS": "160", "LINES": "50"}
        os.environ.update({k: v for k, v in self.env.items() if k not in ("TERM", "COLUMNS", "LINES")})
        self.procs, self.res = {}, {"checks": [], "obs": {}}
        self.res["sha"] = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, text=True).strip()
        self.res["intercom_sha"] = subprocess.check_output(["git", "-C", str(clone), "rev-parse", "--short", "HEAD"],
                                                           text=True).strip()

    # bookkeeping
    def check(self, q, name, ok, detail=None):
        self.res["checks"].append({"q": q, "name": name, "pass": bool(ok), "detail": detail})
        print(json.dumps(self.res["checks"][-1], default=str, ensure_ascii=False)[:900], flush=True)

    def obs(self, k, v):
        self.res["obs"][k] = v
        print("OBS", k, json.dumps(v, default=str, ensure_ascii=False)[:1000], flush=True)

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
        p = self.home / "r3-trial.jsonl"
        return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []

    def hooks(self, pred=lambda h: True):
        return [h for h in self.jsonl() if h["kind"] == "hook" and pred(h)]

    def spawn(self, name, args):
        log = (self.out / f"{name}.log").open("w")
        p = subprocess.Popen(args, cwd=REPO, env=self.env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        self.procs[name] = p
        return p

    def stop(self, name):
        p = self.procs.pop(name, None)
        if p and p.poll() is None:
            p.terminate()
            try:
                p.wait(20)
            except subprocess.TimeoutExpired:
                p.kill()

    # owner
    def start_owner(self):
        self.spawn("owner", [sys.executable, "-m", "hermes_cli.main", "gateway", "run"])
        from hermes_cli.gateway_runtime import discover_gateway_endpoint
        self.ep = None

        def ready():
            self.ep = discover_gateway_endpoint(self.home, timeout=1.0).endpoint
            return self.ep is not None
        if not self.wait(ready, 90, 0.5):
            raise RuntimeError("owner not discoverable")
        self.wait(lambda: self.endpoint(self.procs["owner"].pid), 30)
        return self.procs["owner"].pid

    async def _orpc(self, *calls):
        from hermes_cli.gateway_client import connect_gateway
        out = []
        async with connect_gateway(self.ep) as c:
            for method, params in calls:
                try:
                    out.append(await c.rpc(method, **params))
                except Exception as exc:
                    raise RuntimeError(f"{method}: {type(exc).__name__}: {exc}") from None
        return out

    def orpc(self, *calls):
        return asyncio.run(self._orpc(*calls))

    def owner_create(self):
        return self.orpc(("session.create", {"source": "tui"}))[0]["session_id"]

    def owner_submit(self, sid, text):
        return self.orpc(("session.resume", {"session_id": sid}),
                         ("prompt.submit", {"session_id": sid, "text": text, "submission_id": secrets.token_hex(8)}))[1]

    # dashboard
    def start_dashboard(self):
        self.spawn("dashboard", [sys.executable, "-m", "hermes_cli.main", "dashboard", "--host", "127.0.0.1",
                                 "--port", str(self.dport), "--no-open"])

        def up():
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{self.dport}/api/auth/providers", timeout=2)
            except urllib.error.HTTPError:
                pass
            return True
        if not self.wait(up, 90, 0.5):
            raise RuntimeError("dashboard not up")
        return self.procs["dashboard"].pid

    def dclient(self):
        return r2.Client(self.dport, self.key)

    # cli
    def start_cli(self):
        pid, fd = pty.fork()
        if pid == 0:
            os.chdir(REPO)
            os.execve(sys.executable, [sys.executable, "-m", "hermes_cli.main"], self.env)
        import fcntl, struct, termios
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", 50, 160, 0, 0))
        self.cli_pid, self.cli_fd = pid, fd
        out = (self.out / "cli.log").open("wb")

        def drain():
            while True:
                try:
                    b = os.read(fd, 65536)
                except OSError:
                    return
                if not b:
                    return
                out.write(b)
                out.flush()
        threading.Thread(target=drain, daemon=True).start()

    def cli_type(self, text):
        os.write(self.cli_fd, text.encode())
        time.sleep(0.4)
        os.write(self.cli_fd, b"\r")

    # plugin endpoints (intercom registry)
    def endpoint(self, pid):
        reg = self.home / "intercom" / "sessions"
        for p in reg.glob("*.json"):
            try:
                m = json.loads(p.read_text())
                if int(m.get("pid", -1)) == pid:
                    return m
            except Exception:
                pass
        return None

    def ask(self, pid, req, timeout=150):
        ep = self.endpoint(pid)
        if ep is None:
            return {"ok": False, "error": f"no intercom endpoint for pid {pid}"}
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect(ep["socket"])
            s.sendall((json.dumps(req) + "\n").encode())
            data = b""
            while b"\n" not in data:
                chunk = s.recv(65536)
                if not chunk:
                    break
                data += chunk
        return json.loads(data.decode() or "{}")

    # model observations
    def seen_as_prompt(self, token):
        return self.model.find(lambda r: token in r["prompt"])

    def steered(self, token, tag):
        return self.model.find(lambda r: r["tag"] == tag and any(
            m.get("role") == "user" and text_of(m.get("content")).lstrip().startswith(STEER_OPEN)
            and token in text_of(m.get("content")) for m in r["msgs"]))

    def quiet(self, secs=3, timeout=40):
        self.wait(lambda: not self.model.find(lambda r: time.time() - r["t"] < secs), timeout)


# ---------------------------------------------------------------- Q1

def q1(T):
    owner_pid = T.start_owner()
    try:
        early = T.owner_create()
        T.obs("owner_create_before_dashboard", early)
    except Exception as exc:
        T.obs("owner_create_before_dashboard", f"{exc}")
    dash_pid = T.start_dashboard()
    T.obs("pids", {"owner": owner_pid, "dashboard": dash_pid})
    T.obs("whoami", {"owner": T.ask(owner_pid, {"op": "whoami"}), "dashboard": T.ask(dash_pid, {"op": "whoami"})})
    kinds = {}
    # owner-attached (what Ink and Desktop do: attach + session.create)
    sid = T.owner_create()
    T.owner_submit(sid, "TAG=q1t STEPS=0")
    T.wait(lambda: T.hooks(lambda h: "TAG=q1t" in h["user_message"]), 40)
    h = T.hooks(lambda h: "TAG=q1t" in h["user_message"])
    kinds["owner_attached"] = {"session": sid, "turn_pid": h[-1]["pid"] if h else None}
    # dashboard chat (agent-key WS to the standalone dashboard, as dashboard_dispatch does)
    c = T.dclient()
    r = c.call("session.create", {"source": "tui"})
    live = (r.get("result") or {}).get("session_id")
    stored = (r.get("result") or {}).get("stored_session_id") or live
    sub = c.call("prompt.submit", {"session_id": live, "text": "TAG=q1d STEPS=0"}) if live else r
    T.wait(lambda: T.hooks(lambda h: "TAG=q1d" in h["user_message"]), 40)
    h = T.hooks(lambda h: "TAG=q1d" in h["user_message"])
    kinds["dashboard_chat"] = {"session": h[-1]["session_id"] if h else stored, "live_id": live,
                               "create": r.get("error") or "ok", "submit": sub.get("error") or (sub.get("result") or {}).get("status"),
                               "turn_pid": h[-1]["pid"] if h else None}
    T.dash_client, T.dash_live = c, live
    # classic CLI
    T.start_cli()
    T.wait(lambda: b"Type your message" in (T.out / "cli.log").read_bytes() or
           b"\xe2\x9d\xaf" in (T.out / "cli.log").read_bytes(), 90)
    time.sleep(3)
    got = False
    for _ in range(3):
        T.cli_type("TAG=q1c STEPS=0")
        got = T.wait(lambda: T.hooks(lambda h: "TAG=q1c" in h["user_message"]), 20)
        if got:
            break
    h = T.hooks(lambda h: "TAG=q1c" in h["user_message"])
    kinds["classic_cli"] = {"session": h[-1]["session_id"] if h else None, "cli_pid": T.cli_pid,
                            "turn_pid": h[-1]["pid"] if h else None}
    # messaging (ntfy)
    T.wait(lambda: "probe-in" in json.dumps(T.ntfy.__dict__.get("published", [])) or True, 1)
    time.sleep(3)
    T.ntfy.push("TAG=q1n STEPS=0")
    T.wait(lambda: T.hooks(lambda h: "TAG=q1n" in h["user_message"]), 60)
    h = T.hooks(lambda h: "TAG=q1n" in h["user_message"])
    kinds["messaging_ntfy"] = {"session": h[-1]["session_id"] if h else None, "platform": h[-1]["platform"] if h else None,
                               "turn_pid": h[-1]["pid"] if h else None}
    lp = T.home / "runtime" / "active_sessions.json"
    kinds["leases"] = json.loads(lp.read_text()).get("entries") if lp.exists() else None
    T.kinds = kinds
    T.obs("Q1_hosts", kinds)
    for k in ("owner_attached", "classic_cli", "messaging_ntfy"):
        T.check("Q1", f"{k} turns run in the owner process", kinds[k]["turn_pid"] == owner_pid, kinds[k])
    T.check("Q1", "dashboard chat turns: host recorded", kinds["dashboard_chat"]["turn_pid"] is not None, kinds["dashboard_chat"])


# ---------------------------------------------------------------- Q2

def _start_long(T, kind, tag):
    text = f"TAG={tag} STEPS=6 DELAY=1.0"
    k = T.kinds[kind]
    if kind == "owner_attached":
        T.owner_submit(k["session"], text)
    elif kind == "classic_cli":
        T.cli_type(text)
    elif kind == "messaging_ntfy":
        T.ntfy.push(text)
    elif kind == "dashboard_chat":
        T.dash_client.call("prompt.submit", {"session_id": T.dash_live, "text": text})
    return T.wait(lambda: len(T.model.find(lambda r: r["tag"] == tag)) >= 2, 40)


def q2(T):
    owner_pid = T.procs["owner"].pid
    table = {}
    for kind in ("owner_attached", "classic_cli", "messaging_ntfy", "dashboard_chat"):
        target = T.kinds[kind]["session"]
        if not target:
            table[kind] = "no session"
            continue
        cells = {}
        for mode in ("steer", "queue", "interrupt"):
            tag = f"q2{kind[:3]}{mode}"
            if not _start_long(T, kind, tag):
                cells[mode] = {"error": "long turn did not start"}
                continue
            token = f"MAIL{secrets.token_hex(4)}"
            r = T.ask(owner_pid, {"op": "deliver", "how": "client", "target": target, "mode": mode,
                                  "text": f"{token} TAG=m{tag} STEPS=0 (mode {mode})"})
            T.wait(lambda: T.seen_as_prompt(token) or T.steered(token, tag), 30)
            time.sleep(2)
            steps = max((x["steps"] for x in T.model.find(lambda x: x["tag"] == tag)), default=0)
            cells[mode] = {"result": r, "steered_into_turn": bool(T.steered(token, tag)),
                           "ran_as_own_turn": bool(T.seen_as_prompt(token)), "long_turn_steps": steps}
            T.quiet()
        token = f"MAIL{secrets.token_hex(4)}"
        r = T.ask(owner_pid, {"op": "deliver", "how": "client", "target": target, "mode": "steer",
                              "text": f"{token} TAG=q2idle STEPS=0"})
        T.wait(lambda: T.seen_as_prompt(token), 30)
        cells["idle"] = {"result": r, "ran_as_own_turn": bool(T.seen_as_prompt(token))}
        T.quiet()
        token = f"MAIL{secrets.token_hex(4)}"
        r = T.ask(owner_pid, {"op": "deliver", "how": "ctx", "key": target, "text": f"{token} TAG=q2ctx STEPS=0"})
        T.wait(lambda: T.seen_as_prompt(token), 25)
        cells["ctx_inject_idle"] = {"result": r, "ran_as_own_turn": bool(T.seen_as_prompt(token))}
        T.quiet()
        table[kind] = cells
        for mode, want in (("steer", "steered_into_turn"), ("queue", "ran_as_own_turn"), ("interrupt", "ran_as_own_turn")):
            c = cells.get(mode, {})
            T.check("Q2", f"{kind}: {mode} from inside the owner via canonical verbs",
                    (c.get("result") or {}).get("ok") and c.get(want), c)
        T.check("Q2", f"{kind}: idle start from inside the owner", cells["idle"]["ran_as_own_turn"], cells["idle"])
        T.obs(f"Q2_{kind}", cells)
    T.q2 = table


def q2_cold(T):
    target = T.kinds["owner_attached"]["session"]
    T.stop("owner")
    time.sleep(2)
    owner_pid = T.start_owner()
    time.sleep(2)
    token = f"MAIL{secrets.token_hex(4)}"
    r = T.ask(owner_pid, {"op": "deliver", "how": "client", "target": target, "mode": "steer",
                          "text": f"{token} TAG=q2cold STEPS=0"})
    T.wait(lambda: T.seen_as_prompt(token), 40)
    T.check("Q2", "cold session (owner restarted, session not loaded) started from inside the owner",
            T.seen_as_prompt(token), r)
    T.obs("Q2_cold", r)


# ---------------------------------------------------------------- Q3

def q3(T):
    owner_pid = T.procs["owner"].pid
    out = {}
    pairs = [("classic_cli", "owner_attached"), ("messaging_ntfy", "owner_attached"), ("owner_attached", "messaging_ntfy")]
    for to_kind, reply_kind in pairs:
        to, back = T.kinds[to_kind]["session"], T.kinds[reply_kind]["session"]
        if not (to and back):
            out[f"{to_kind}->{reply_kind}"] = "missing session"
            continue
        t0 = time.time()
        token = f"MAIL{secrets.token_hex(4)}"
        r = T.ask(owner_pid, {"op": "deliver", "how": "client", "target": to, "mode": "steer",
                              "text": f"{token} TAG=q3{to_kind[:3]} STEPS=0 REPLYTO={back}"})
        T.wait(lambda: any(e["kind"] == "reply" and e["t"] > t0 for e in T.jsonl()), 60)
        rep = [e for e in T.jsonl() if e["kind"] == "reply" and e["t"] > t0]
        landed = T.wait(lambda: T.model.find(lambda x: "ISREPLY" in x["flat"] and x["t"] > t0), 40)
        out[f"{to_kind}->{reply_kind}"] = {"send": r, "reply": rep[-1] if rep else None, "reply_reached_model": landed}
        T.check("Q3", f"reply from a {to_kind} turn's post_llm_call reached the {reply_kind} sender",
                bool(rep) and (rep[-1]["result"] or {}).get("ok") and landed, out[f"{to_kind}->{reply_kind}"])
        T.quiet()
    T.obs("Q3", out)


def q2_dash(T):
    """Dashboard-hosted chats: the owner refuses them (runtime_coordination_required). What reaches them?"""
    dash_pid = T.procs["dashboard"].pid
    stored, live = T.kinds["dashboard_chat"]["session"], T.dash_live
    out = {}
    token = f"MAIL{secrets.token_hex(4)}"
    out["dashboard_plugin_ctx_inject_idle"] = T.ask(dash_pid, {"op": "deliver", "how": "ctx", "key": stored,
                                                              "text": f"{token} TAG=q2dctx STEPS=0"})
    out["dashboard_plugin_ctx_inject_idle"]["ran"] = T.wait(lambda: T.seen_as_prompt(token), 25)
    T.quiet()
    # The dashboard's own socket with the agent key (the ported dashboard_dispatch route).
    c = T.dash_client
    for mode in ("steer", "queue"):
        tag = f"q2dws{mode}"
        if not _start_long(T, "dashboard_chat", tag):
            out[f"ws_{mode}"] = "long turn did not start"
            continue
        token = f"MAIL{secrets.token_hex(4)}"
        if mode == "steer":
            r = c.call("session.steer", {"session_id": live, "text": f"{token} steered"})
        else:
            r = c.call("prompt.submit", {"session_id": live, "text": f"{token} TAG=m{tag} STEPS=0", "queued": True})
        T.wait(lambda: T.seen_as_prompt(token) or T.steered(token, tag), 30)
        out[f"ws_{mode}"] = {"rpc": r.get("result") or r.get("error"), "steered": bool(T.steered(token, tag)),
                             "own_turn": bool(T.seen_as_prompt(token))}
        T.quiet()
    T.obs("Q2_dashboard_paths", out)
    T.check("Q2", "dashboard chat: its own process's ctx.inject_message (tui host) runs the message",
            out["dashboard_plugin_ctx_inject_idle"].get("ran"), out["dashboard_plugin_ctx_inject_idle"])
    T.check("Q2", "dashboard chat: steer and queue via the dashboard's own socket (agent key)",
            isinstance(out.get("ws_steer"), dict) and out["ws_steer"]["steered"]
            and isinstance(out.get("ws_queue"), dict) and out["ws_queue"]["own_turn"], out)


def main(run, clone, only):
    T = T3(run, clone)
    steps = [("q1", q1), ("q2", q2), ("q3", q3), ("q2_dash", q2_dash), ("q2_cold", q2_cold)]
    try:
        for name, fn in steps:
            if only and name not in only and name != "q1":
                continue
            t = time.time()
            try:
                fn(T)
            except Exception:
                import traceback
                T.check(name, f"scenario {name} raised", False, traceback.format_exc()[-1500:])
            print(f"== {name} {time.time() - t:.1f}s", flush=True)
    finally:
        for n in list(T.procs):
            T.stop(n)
        if getattr(T, "cli_pid", None):
            try:
                os.kill(T.cli_pid, 9)
                os.waitpid(T.cli_pid, 0)
            except Exception:
                pass
        T.res["hooks"] = [{k: h.get(k) for k in ("pid", "session_id", "platform", "gateway_injector", "tui_injector")}
                          for h in T.hooks()]
        T.res["passed"] = sum(c["pass"] for c in T.res["checks"])
        T.res["total"] = len(T.res["checks"])
        T.res["model_requests"] = len(T.model.requests)
        (T.out / "results.json").write_text(json.dumps(T.res, indent=2, default=str, ensure_ascii=False))
        print(json.dumps({"passed": T.res["passed"], "total": T.res["total"]}), flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--intercom-clone", type=Path, required=True)
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    sys.path.insert(0, str(REPO))
    main(a.run, a.intercom_clone.resolve(), {x for x in a.only.split(",") if x})
