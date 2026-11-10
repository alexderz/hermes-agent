# PoC — Round 2: does the intercom base with a mode seam deliver on every host?

- Date: `2026-11-09`
- HLD: `docs/session-mail/hld.md` (round 2, "PoC questions (Trial round 2)" R1–R11)
- Ticket: n/a (Epic `DER-701`, Plan step, Trial)

## Required

### Question

HLD round 2's R1–R11, in this priority:
- **R1:** the seam's three modes plus an idle start, on each host.
- **R3:** one dashboard process, several sessions, one socket.
- **R4:** gateway sessions.
- **R2, R5, R6, R7:** CLI by socket, exactly once, replies from each host, down hosts.
- **R8–R11:** if time allowed.

### Setup

Code in this folder:
- `trial_r2.py`, the harness;
- `intercom_overlay/`, the trial additions:
  - `__init__.py` replaces only intercom's `register()`;
  - `r2_trial.py` holds the stand-ins.

Run from the repo root with the isolated trial venv (built with `pm.build_env`):

```
PYTHONDONTWRITEBYTECODE=1 <trial-venv>/bin/python docs/session-mail/poc/round2/trial_r2.py --run <run-dir> --intercom-clone <intercom-clone> [--only r1_cli,r6,r5]
```

Per run, a throwaway `HERMES_HOME` holding only values generated for the run:
- a fake-model provider;
- the dashboard gate on (`public_url: https://probe.invalid`, password provider with random
  values);
- an agent key file (0600);
- `busy_input_mode: interrupt`, as live;
- saved `platform_toolsets` lists;
- `plugins.enabled: [intercom, ntfy-platform]`;
- `allow_gateway_injection: true` for intercom;
- a `.env` holding only `NTFY_TOPIC`, `NTFY_SERVER_URL` (the fake server) and
  `NTFY_ALLOW_ALL_USERS`.

Processes, all on 127.0.0.1:
1. **A fake OpenAI-compatible model** that records every request. It follows directives in the
   turn's prompt (`STEPS`, `DELAY`, `CALL=<to>|<delivery>|<message>`, `SILENTONLY`), and answers
   each mail with a `[REPLY <id>]` block (`[SILENT]` from round 3).
2. **A fake ntfy server:** a streaming `GET /<topic>/json` that carries messages the harness
   pushes, and a recording `POST /<topic>`.
3. **The dashboard:** a real `hermes_cli.web_server` backend, after `discover_plugins()`.
4. **The messaging gateway:** `hermes gateway run`, with the **bundled ntfy platform adapter**
   pointed at the fake server. No adapter code was written; the bundled adapter was enough.
5. **An interactive classic CLI** (`hermes`) under a pseudo-terminal.
6. **Senders:** `hermes intercom send …` subprocesses (the trial CLI command), and fake-model
   tool calls (`intercom` through `tool_call`, because Tool Search defers it).

**Intercom:** the clone (`ae90a2a`) is copied **unedited** into `<home>/plugins/intercom/`.
Its own `inbox.py` provides the socket, the registry, `_exchange` and the peer-UID check. The
overlay replaces `inbox._serve` so an envelope can name a target session and a mode.

**Trial stand-ins, not product code** (`r2_trial.py`):
- **The seam (HLD D1):** Hermes is not patched; the host internals are called from the plugin.
  - **tui_gateway (dashboard):** the real `prompt.submit` handler, with `_load_busy_input_mode`
    forced to the requested mode. This is exactly what D1 makes a parameter.
  - **classic CLI:** the typed-input routine's logic on `manager._cli_ref` (`agent.steer`,
    `agent.redirect`, `_pending_input`, `_interrupt_queue`).
  - **gateway:** the running agent's `steer`/`redirect` via the runner
    (`lookup_by_session_id`, `_peek_session_state`); `inject_gateway_message` for queue and idle.
- **Routing (D4):** the lease pid, then the gateway endpoint, then the wake path. The wake path
  uses this worktree's `scripts/dashboard_dispatch.py` `_main`, loaded by path.
- **Also stood in:** the A′ frame with relabelling, a SQLite record, reply capture in
  `post_llm_call` with the record check, the endpoint role refresh, and the CLI.

### Evidence

Fork commit `885b5ba120` (`integrate/session-mail`), intercom `ae90a2a`.
- **Run 3** (all scenarios): 23 of 24.
- **Run 4** (CLI-focused): 9 of 9.

The single run-3 miss was a harness readiness check: the CLI did run its turn, and the CLI
cells ran in run 4. Runs 1–2 fixed the harness (CLI typing, intercom's test discovery path, R5
classification). The results are in `evidence-results.json`; logs stayed outside git. Total trial
wall time was about 15 minutes of runs.

| Q | Result | What was seen |
|---|---|---|
| **R1** seam: three modes plus idle, per host | **pass on all three hosts** (12 of 12 cells) | **Dashboard (tui_gateway):** `steer` became a steer row inside the running turn; `queue` ran after the turn; `interrupt` was applied as **redirect**, the long turn stopped after 3 of 6 steps and the mail ran; an idle session started a turn. **Classic CLI:** the same four results (redirect for `interrupt`). **Gateway (ntfy chat):** the same four results (redirect for `interrupt`). The hard-interrupt fallback was never needed: every agent reports `_supports_active_turn_redirect` (`agent/agent_init.py:544`). |
| **R1 extra** queued mail row | **pass, plus a Hermes bug found** | Dashboard-queued mail **is** in the transcript at accept time, but is written **twice**: the accept-time row, then again when the queued turn runs. The first Trial's plain queued text (`ALEX_QUEUED_TEXT`, `q1am`) shows the same, so it is not caused by mail: the drained turn does not adopt the accept-time row (`tui_gateway/session_workdir.py:727`, `_adopt_submit_user_row`). Gateway and CLI queues write one row. |
| **R3** one dashboard process, several sessions | **pass** | Chat A's tool mailed chat B in the same process (`host: in-process`, 0.013 s, applied `start`). B's automatic reply steered back into A's running turn, and the debate stopped at `[SILENT]`. Every mail landed only in its addressed session. A torn-down session and a **lazy**-resumed session had **no lease**, so they went to the wake path (`started`, 0.18 s). |
| **R4** gateway sessions, bundled ntfy adapter | **pass** (`/compress` lookup and the SM-Q15 post not run) | The endpoint set `roles: [gateway]` after the gateway published its host (refresh loop). An ntfy chat created a gateway session (source `ntfy`). Mail reached it through the gateway endpoint in all modes. **Injected turns are stored as `internal_notification`**, so a bare `[SILENT]` answer was **not posted** to the chat, while normal answers were. |
| **R2** a CLI receives mail through intercom's socket | **pass** | All four cells delivered by the CLI's own pid through its socket, with no GC lookup. `steer` did not interrupt (the turn kept all its steps). **The CLI's lease appears only at its first turn**, not at process start (`started_at` about 95 s after the process started). |
| **R5** exactly once | **pass** | 17 + 7 delivered mails, none in a wrong session. The only extra rows are the dashboard queued-row duplicate above. A lease pid whose process has no intercom endpoint returned `no-endpoint` (registry entry removed to simulate a pre-deploy process). |
| **R6** replies from each host's `post_llm_call` | **pass** (CLI and gateway; Ink TUI not run) | The CLI host's hook and the gateway host's hook each sent the reply back to the dashboard sender through the dashboard's socket (`steer`, under 0.01 s). In one gateway turn, the hook's turn-boundary guess picked up three older mails, and the record's "no reply yet" check stopped any repeat reply. |
| **R7** wake path and down hosts | **pass** | A CLI-process sender woke a session that was live nowhere through the dashboard (`started`). Gateway-source target with the gateway stopped: `no-gateway` (exit 5), with no dashboard fall-through. Live-nowhere target with the dashboard stopped: an error (connection refused, exit 5). |
| **R9** intercom's own tests | **pass** | 17 tests, OK, on the unedited clone (`unittest discover -p 'test_*.py'`). |
| **R8** no-seam behaviour | **not run** | The seam here is trial code inside the plugin, so "no seam" would only be a flag. It is meaningful only against a real Hermes build without P1, so Build tests it. |
| **R10** two profiles in one dashboard | **not run** | Time. Out-of-scope behaviour (refusal); Build tests it. |
| **R11** interrupt with `turn_isolation` | **not run** | Optional, and time. |
| **Ink TUI host** (part of R1/R6) | **not run** | It is the same `tui_gateway` code as the dashboard, run as a separate process over stdio; driving its JSON-RPC was out of time. Expected to behave as the dashboard. |

Timings (fake model): a `hermes intercom send` subprocess takes about 2.1–2.4 s, almost all of it
Python and plugin start-up. Socket and in-process delivery take 0.002–0.03 s. A wake takes
about 0.18 s.

### Conclusion

**Proceed.** The seam shape (D1) works on all three hosts by reusing each host's own
typed-input or busy-submit logic with an explicit mode. Lease-pid routing, one socket per
process with many sessions, the gateway endpoint role and the wake path all behave as the HLD
says.

HLD changes (same commit):
- **D4 routing:** a lease exists only after a session's **first turn** in that process. A lazy
  or never-run session falls through to the wake path. That is correct for dashboard sessions.
  For a CLI that has a session open but has not run a turn yet, the wake path would resume it
  in the dashboard; see O18.
- **D6 silence: settled.** Injected gateway turns are `internal_notification`, so a bare
  `[SILENT]` is not posted.
- **D1 `interrupt`:** every v0.22 agent supports redirect, so "redirect" is the normal applied
  detail and the hard-interrupt fallback is for older agents or media payloads.
- **New O17:** the dashboard writes queued prompts twice (an existing Hermes bug; queued mail
  would show twice on the phone). A small fork fix or an upstream report, outside this
  chunk's plugin.

**Still unknown:**
- the Ink TUI host;
- R8, R10, R11;
- `lookup_by_session_id` after `/compress`;
- the SM-Q15 topic post (pending Alex and security);
- real models.

### What we will not treat as product

All of `poc/round2/`. Build rebuilds:
- the seam as a real, generic `inject_message(mode=…)` in each host (D1), not monkeypatching
  from a plugin;
- intercom's changes in its own modules and style (P2, P3);
- the record, replies and CLI with tests.

The trial's forced `_load_busy_input_mode` swap is not thread-safe and is not a design.

## Optional

Output kept outside git: per-run homes (`r2-trial.jsonl`, `record.db`, `state.db`), backend,
gateway and CLI logs, and the raw `results.json` files, in the trial run directories.
`evidence-results.json` is runs 3 and 4 with paths and ports replaced.
