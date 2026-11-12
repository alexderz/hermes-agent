"""Trial (frozen record, never product code): on v0.23, does a `hermes chat -q --oneshot` kickoff
turn run inside the combined gateway, so that a second interactive gateway connection (standing in
for the Webapp) can see it running and steer, queue and stop it? And does the turn survive the CLI
process exiting mid-turn?

Fidelity: a real `python -m gateway.run` daemon and a real `hermes chat` CLI subprocess against a
temporary HERMES_HOME holding only throwaway values, a deterministic fake OpenAI-compatible model on
127.0.0.1, and a second client built on the CLI's own `connect_gateway` (an `interactive` ticket,
the purpose a Webapp socket carries). No credentials, no live install, no public listener.
Patterned on evals/desktop_gateway_ticket_native/run.py and the v0.22 trial in ../.

Run from the repo root with HERMES_HOME pointing at an empty temporary folder:
  python docs/project-centric-ui/poc/v023/trial_gateway_oneshot.py --output <dir>
"""
import argparse
import asyncio
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
STEPS = 8
STEP_DELAY = 1.5
TITLE = "PRB - Owner"


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Model:
    def __init__(self):
        self.requests, self.lock = [], threading.Lock()

    def texts(self):
        with self.lock:
            return [r for r in self.requests]

    def seen(self, marker):
        return any(marker in r for r in self.texts())

    def count(self, marker=None):
        return sum(1 for r in self.texts() if marker is None or marker in r)


def start_model(model, port, readable):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            msgs = req.get("messages", [])
            with model.lock:
                model.requests.append(json.dumps(msgs))
            if not req.get("tools"):
                return self.reply(req, {"role": "assistant", "content": "Probe"}, "stop")
            last_user = max((i for i, m in enumerate(msgs) if m.get("role") == "user"), default=0)
            steps = sum(1 for m in msgs[last_user:] if m.get("role") == "tool")
            time.sleep(STEP_DELAY)
            if steps < STEPS:
                call = {"id": f"call_{steps}_{time.time_ns()}", "type": "function",
                        "function": {"name": "read_file", "arguments": json.dumps({"path": readable})}}
                return self.reply(req, {"role": "assistant", "content": None, "tool_calls": [call]}, "tool_calls")
            return self.reply(req, {"role": "assistant", "content": "TURN_DONE"}, "stop")

        def reply(self, req, message, finish):
            try:
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
            except BrokenPipeError:
                pass

    httpd = ThreadingHTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def write_home(home, project, model_port):
    (home / "config.yaml").write_text(f"""model:
  default: probe
  provider: custom
  base_url: http://127.0.0.1:{model_port}/v1
  api_key: probe-key
gateway:
  multiplex_profiles: false
auxiliary:
  title_generation:
    enabled: false
memory:
  memory_enabled: false
  user_profile_enabled: false
""")
    (project / "notes.txt").write_text("probe file\n")


async def wait_for(pred, timeout, step=0.25):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if await pred() if asyncio.iscoroutinefunction(pred) else pred():
            return True
        await asyncio.sleep(step)
    return False


async def scenario(model, env, project, out, check):
    from hermes_cli.gateway_client import connect_gateway

    def kickoff(prompt):
        log = (out / f"cli-{prompt.split()[0]}.log").open("w")
        return subprocess.Popen(
            [sys.executable, "-m", "hermes_cli.main", "chat", "--in", str(project), "-c", TITLE,
             "--create-if-missing", "-q", prompt, "--oneshot", "-Q"],
            cwd=REPO, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)

    # 1. Kickoff turn 1 from a real one-shot CLI.
    cli = kickoff("OWNER_TURN_1 long task")
    started = await wait_for(lambda: model.count("OWNER_TURN_1") >= 2, 120)
    check("one-shot CLI turn reached the fake model", started, {"cli_exit": cli.poll()})

    async with connect_gateway() as webapp:
        res = await webapp.rpc("session.resume", title=TITLE, omit_messages=True)
        sid, gen = res.get("session_id"), res.get("execution_generation")
        check("second gateway client resumes the CLI's session by title and sees it running",
              res.get("running") is True, {k: res.get(k) for k in ("running", "execution_generation")})

        st = await webapp.rpc("session.steer", session_id=sid, text="STEER_MARKER_7", execution_generation=gen)
        check("second client session.steer accepted during the CLI's turn", st.get("status") in ("queued", "steered", "accepted"), st)
        q = await webapp.rpc("prompt.submit", session_id=sid, text="QUEUE_MARKER_9 follow-up",
                             submission_id=str(uuid.uuid4()), queued=True)
        check("second client queued prompt.submit accepted (no SESSION_NOT_OWNED)", isinstance(q, dict), q)
        check("steer text reached the model inside the CLI's running turn",
              await wait_for(lambda: model.seen("STEER_MARKER_7"), 40))
        rc = await asyncio.to_thread(cli.wait, 120)
        check("CLI one-shot finished its turn and exited", rc == 0, {"exit": rc})
        check("queued prompt ran as the next turn in the gateway",
              await wait_for(lambda: model.seen("QUEUE_MARKER_9"), 60))
        await wait_for(lambda: model.count("QUEUE_MARKER_9") >= STEPS + 1, 90)

        # 2. CLI killed mid-turn: does the gateway turn keep running, still steerable?
        cli = kickoff("OWNER_TURN_2 cli dies")
        await wait_for(lambda: model.count("OWNER_TURN_2") >= 2, 90)
        cli.send_signal(signal.SIGKILL)
        cli.wait(10)
        before = model.count("OWNER_TURN_2")
        await asyncio.sleep(8)
        after = model.count("OWNER_TURN_2")
        check("after SIGKILL of the CLI, the gateway turn keeps calling the model", after > before + 2,
              {"before": before, "after": after})
        res = await webapp.rpc("session.resume", session_id=sid, omit_messages=True)
        check("the turn is still running and visible to the second client", res.get("running") is True,
              {k: res.get(k) for k in ("running", "execution_generation")})
        st = await webapp.rpc("session.steer", session_id=sid, text="STEER_AFTER_KILL",
                              execution_generation=res.get("execution_generation"))
        check("steer still accepted after the CLI died", st.get("status") in ("queued", "steered", "accepted"), st)
        check("that steer reached the model", await wait_for(lambda: model.seen("STEER_AFTER_KILL"), 40))

        # 3. Stop from the second client.
        res = await webapp.rpc("session.resume", session_id=sid, omit_messages=True)
        if res.get("running"):
            it = await webapp.rpc("session.interrupt", session_id=sid,
                                  execution_generation=res.get("execution_generation"))
            check("second client session.interrupt accepted", isinstance(it, dict), it)
            stopped = await wait_for(lambda: True, 0)
            n = model.count("OWNER_TURN_2")
            await asyncio.sleep(6)
            check("interrupted turn stops calling the model", model.count("OWNER_TURN_2") <= n + 1,
                  {"at_interrupt": n, "after": model.count("OWNER_TURN_2")})
        else:
            check("turn 2 was still running at the stop step", False, res)


def main(out):
    out.mkdir(parents=True, exist_ok=True)
    base = Path(tempfile.mkdtemp(prefix="owner-023-trial-"))
    home, user, project = base / "home", base / "user", base / "project"
    for d in (home, user, project):
        d.mkdir(parents=True)
    model_port = free_port()
    write_home(home, project, model_port)
    model = Model()
    start_model(model, model_port, str(project / "notes.txt"))
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(user), "LANG": "C.UTF-8", "TMPDIR": str(base),
           "HERMES_HOME": str(home), "PYTHONPATH": str(REPO), "PYTHONUNBUFFERED": "1",
           "PYTHONDONTWRITEBYTECODE": "1", "OPENAI_API_KEY": "probe-key", "HERMES_NONINTERACTIVE": "1"}
    os.environ.update(env)
    sys.path.insert(0, str(REPO))
    results = {"sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
               "fidelity": "real gateway daemon + real `hermes chat -q --oneshot` CLI, temporary HERMES_HOME, "
                           "127.0.0.1 only, fake local model, second client via connect_gateway (interactive ticket)",
               "checks": []}

    def check(name, ok, detail=None):
        results["checks"].append({"name": name, "pass": bool(ok), "detail": detail})
        print(json.dumps(results["checks"][-1], default=str)[:500], flush=True)

    log = (out / "gateway.log").open("w")
    gw = subprocess.Popen([sys.executable, "-m", "gateway.run"], cwd=REPO, env=env,
                          stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
    try:
        from hermes_cli.gateway_runtime_discovery import query_identify
        end = time.monotonic() + 120
        ready = False
        while time.monotonic() < end and gw.poll() is None:
            try:
                if query_identify(home, timeout=2).get("state") == "ready":
                    ready = True
                    break
            except (OSError, ValueError):
                pass
            time.sleep(0.3)
        check("gateway daemon ready on the temporary home", ready, {"exit": gw.poll()})
        if ready:
            asyncio.run(scenario(model, env, project, out, check))
    except Exception as exc:  # trial harness: record and stop
        check("harness error", False, repr(exc))
    finally:
        if gw.poll() is None:
            gw.terminate()
            try:
                gw.wait(20)
            except subprocess.TimeoutExpired:
                gw.kill()
        results["passed"] = sum(c["pass"] for c in results["checks"])
        results["total"] = len(results["checks"])
        results["model_requests"] = model.count()
        (out / "results.json").write_text(json.dumps(results, indent=2, default=str))
        print(json.dumps({"passed": results["passed"], "total": results["total"]}), flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    main(ap.parse_args().output)
