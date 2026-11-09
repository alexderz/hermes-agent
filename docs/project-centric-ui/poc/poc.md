# PoC — Can an owner turn run in the dashboard process, kicked off by a script, and be steered from a second client?

- Date: `2026-11-08`
- HLD: `docs/project-centric-ui/hld.md` (Shape part 6, PoC questions)
- Ticket: n/a (Epic `DER-686`, Plan step)

## Required

### Question

For option A (owner-session turns submitted through the dashboard's `/api/ws` by a small kickoff
client, instead of `hermes chat -q --oneshot`):

1. Can a non-browser client on the same host authenticate to a **gated** dashboard (auth
   required, password provider) with existing mechanisms only, with no credential in a file,
   argv or URL?
2. Does a long turn run in the dashboard process survive the dashboard's reapers (WebSocket
   orphan reaping, idle/LRU eviction) while the kickoff client is connected, and after both
   clients drop?
3. Can a second client (standing in for the phone) attach to the running turn and steer,
   queue and interrupt it, without `SESSION_NOT_OWNED` (4090)?
4. What happens to a running owner turn when the dashboard process dies (restart)?
5. Memory: what does the process use? (Informational only; see limits.)

### Setup

`trial_owner_turn.py`, run from the repo root with an isolated environment built by
`python -m pm.build_env --source . --out <trial-venv> --cache <trial-cache>` (temporary
`HERMES_HOME` and cache directories), then:

```
PYTHONDONTWRITEBYTECODE=1 HERMES_HOME=<tmp> <trial-venv>/bin/python \
  docs/project-centric-ui/poc/trial_owner_turn.py --output <out-dir>
```

What it does:

- Writes a temporary `HERMES_HOME` with only throwaway values generated per run: a `custom`
  model provider pointing at a fake local model, `dashboard.public_url: https://probe.invalid`
  (engages the auth gate on a 127.0.0.1 bind), `dashboard.basic_auth` with a random password
  hash and random signing secret, `ws_orphan_reap_grace_s: 3`, `ws_orphan_activity_stale_s: 20`.
  No `auth.json`, no `.env`, no real credentials.
- Starts a real `hermes_cli.web_server.start_server` backend subprocess on 127.0.0.1 (after
  `discover_plugins()`, as `hermes dashboard` does). The live install, its services and the
  live home are never touched.
- Fake model (127.0.0.1): every tool-carrying request waits 1.5 s, then answers with a
  `read_file` tool call until 8 tool results follow the last user message, then `TURN_DONE`.
  It records every request so the harness can see what reached the model.
- Auth for each client: mint a 60 s access token in memory with the bundled password
  provider's own code (`plugins.dashboard_auth.basic`), from the signing secret in the
  profile config; `POST /api/auth/ws-ticket` with `Authorization: Bearer`; open `/api/ws` with
  the single-use ticket in the `Sec-WebSocket-Protocol` header
  (`hermes-gateway-v1, hermes-gateway-ticket.<ticket>`).
- Clients: "kickoff" (`session.create`, `prompt.submit`) and "phone" (`session.resume` on the
  stored id, then `session.steer`, `prompt.submit {queued: true}`, `session.interrupt`).

### Evidence

Run on fork commit `3f8137dd347e0b9e8b1afddf5e43535b7dad1f4c` (v0.22.0 plus fork patches).
Result: **18 of 18 checks pass** (`evidence-results.json`). Backend logs stayed outside git.

| # | Check (rows group the 18 checks) | Result |
|---|---|---|
| 1 | Bare `/api/ws` without credential refused (gate on) | pass (HTTP 403) |
| 2 | Kickoff authenticated: minted token → ws-ticket → subprotocol | pass |
| 3 | Kickoff `session.create` + `prompt.submit` | pass (`status: streaming`) |
| 4 | Phone `session.resume` reuses the **same live session** and reports it running | pass (`running: true`, `status: working`) |
| 5 | Phone `session.steer` while the kickoff's turn runs | pass (`status: queued`) |
| 6 | Steer text reached the model inside the running turn | pass |
| 7 | Phone `prompt.submit {queued: true}` accepted, no 4090 | pass |
| 8 | Queued prompt ran as the next turn | pass |
| 9 | Both clients saw the turn's `message.complete` (shared stream) | pass |
| 10 | Phone `session.interrupt` stops the turn | pass (ended 0.5 s later) |
| 11 | Both clients closed mid-turn: the detached turn keeps calling the model past the 3 s orphan grace | pass (27 → 32 requests in 8 s) |
| 12 | The detached turn finishes all its steps | pass |
| 13 | SIGKILL of the backend mid-turn drops the kickoff socket | pass |
| 14 | After restart, a **cold** `session.resume` schedules auto-continue for the killed turn | pass (`auto_continue: {attempt: 1}`) |
| 15 | The continuation turn reached the model with the original prompt | pass |

First run: 16 of 18. The two misses were checks 14–15, because the harness resumed with
`lazy: true`; auto-continue runs only on the cold and eager resume paths
(`tui_gateway/methods_session.py` `_resume_cold` / `_resume_eager`, not the lazy path). The
second run used a cold resume for that step. Also from the first run: the backend needs plugin
discovery before `start_server`, or the password provider is not registered and the gated
backend refuses to start (fail-closed, as designed).

Backend RSS (fake model, so a floor, not a forecast): 251 MB after start of turn 1, 259 MB
after two turns, 260 MB after the detached turn, 251 MB after a restart.

Read from code, consistent with the run:

- Running sessions are never evicted by the idle/LRU reaper (`tui_gateway/session_reaper.py`
  `_session_is_lru_evictable`: `running` exempts); the idle TTL is 6 h of inactivity, and only
  for sessions that are not running.
- A detached running turn is interrupted only once its activity clock is idle for
  `dashboard.ws_orphan_activity_stale_s` (default 600 s, the turn-liveness watchdog)
  (`tui_gateway/session_lifecycle.py` `_schedule_ws_orphan_reap`). So a turn waiting more than
  10 minutes on one silent step with no client attached would be interrupted; with the kickoff
  connected it is not detached at all.
- Auto-continue freshness is measured from the **turn's start** (`turn_marker.py` records
  `started_at` once per turn) against `desktop.auto_continue.freshness_minutes` (default 15),
  with at most 2 attempts. So a turn killed after running longer than 15 minutes is **not**
  auto-continued: the marker is cleared and the partial transcript stays.

### Conclusion

**Proceed with option A.** On v0.22.0, with no Hermes core change:

- a same-account client can authenticate to the gated dashboard using only existing
  mechanisms, with nothing stored and no credential in argv or a URL;
- the phone attaches to the kickoff's live turn and can steer, queue and interrupt it;
- the turn survives the reapers while connected, and keeps running if clients drop as long as
  it shows activity;
- a dashboard restart kills the turn; a short one (under 15 minutes) is auto-continued on the
  next cold resume; a long one is not and must be re-kicked.

**Still unknown** (not cheap to prove here; Build/after-deploy must check):

- **Hours, not seconds.** The run used ~20 s turns with timers shortened. Nothing in the code
  times out a running, active turn, but a multi-hour real run was not observed.
- **Memory under a real model** over hours (context growth, tool output). The fake model's
  RSS is a floor only.
- **The real Hermes Mobile app** against this flow. The check used a Python client sending the
  same RPCs the app sends (`session.resume`, `session.steer`, `prompt.submit {queued}`,
  `session.interrupt`, per brief fact 25); the resume reply's `running: true` is what the app
  reads to treat the chat as busy (brief fact 27).

### What we will not treat as product

All of `poc/`. Build must rebuild:

- the kickoff client (HLD Shape part 6) with its own behaviour tests against a temporary
  `HERMES_HOME` (auth chain, resume of an existing session, turn completion, exit codes,
  refusal on 4090, no reconnect);
- a reusable fake-model fixture if the tests need one (the in-tree precedent is
  `evals/desktop_bug_campaign/leases_live.py`).

Build and after-deploy must test instead of trusting this note: one real owner run of an hour
or more from the kickoff client, with Alex steering it from the phone; RSS of the dashboard
process sampled during that run; and one deliberate restart during a short owner turn to see
the auto-continue on the live install (only with Alex's go).

## Optional

Output kept outside git: backend logs and the raw results file stayed in the trial's temporary
output folder (logs are not committed; the results file is committed with local paths
replaced). The isolated trial environment also stayed outside the checkout.
