# PoC — Does send-time delivery with the 1516a52669 rule, and reply capture in `post_llm_call`, work inside a real dashboard?

- Date: `2026-11-09`
- HLD: `docs/session-mail/hld.md` ("PoC questions" Q1–Q10)
- Ticket: n/a (Epic `DER-701`, Plan step, Trial)

## Required

### Question

The HLD's PoC questions Q1–Q10. In short: does queued mail survive the reaper (Q1)? What does the
model receive (Q2)? Does `post_llm_call` see steered mail in the right turn (Q3)? Idle start (Q4).
A session held by a CLI process (Q5). A second mail into a mail-started turn (Q6). A tool
delivering back into its own dashboard (Q7). Pre-plugin sessions after a restart (Q8).
Interrupted or failed turns (Q9). A debate (Q10).

### Setup

`trial_session_mail.py` and the throwaway plugin `sm_probe/`, both in this folder. Run from the
repo root with the isolated trial environment (built with `python -m pm.build_env`):

```
PYTHONDONTWRITEBYTECODE=1 <trial-venv>/bin/python docs/session-mail/poc/trial_session_mail.py --run <run-dir>
```

What it does:

- **Temporary `HERMES_HOME`** under `<run-dir>/home`, holding only throwaway values generated per
  run:
  - a `custom` provider pointing at the fake model;
  - the auth gate on (`dashboard.public_url: https://probe.invalid`, plus the bundled password
    provider with a random hash and secret);
  - a per-run `dashboard-agent.key` (0600, 64 chars);
  - `ws_orphan_reap_grace_s: 3` and `ws_orphan_activity_stale_s: 12`;
  - `display.busy_input_mode: interrupt` (as live);
  - a saved `platform_toolsets` list `[file]` for `cli` and `tui` (as live: an explicit list);
  - the default `tools.tool_search` settings.
  - No `.env`, no `auth.json`, no real credentials. The live install was never touched.
- **A real `hermes_cli.web_server.start_server` backend subprocess** on 127.0.0.1, started after
  `discover_plugins()`, on a free port.
- **A fake OpenAI-compatible model** on 127.0.0.1. It records every request. Directives in the
  turn's prompt drive it (`STEPS`, `DELAY`, `CALL`, `FAIL400`, …). Its final answer carries a
  `[REPLY <id>]` block for each probe mail in the turn, and `[SILENT]` once a debate reaches
  round 4.
- **Delivery rule under test:** `scripts/dashboard_dispatch.py` at `1516a52669`, written into the
  run directory with `git show`, not into git. The harness (standing in for the CLI) and the
  probe plugin's tool and reply thread both **load that file by path and call its `_main`
  coroutine**: resume, then steer → queue → start. That is the same RPC sequence the skills run
  today, not a re-implementation.
- **Probe plugin** (`sm_probe/`, copied into `<temp-home>/plugins/sm-probe/`):
  - a sync `sm_probe_send(to, message)` tool, which delivers on a fresh thread with
    `asyncio.run` inside `propagate_context_to_thread` (HLD D4);
  - a `post_llm_call` hook that records what it sees. For each probe mail found at a line start
    in the turn's user rows, it takes the `[REPLY]` block or the whole answer, skips `[SILENT]`,
    stores one reply per mail id, and delivers the reply from a daemon thread (HLD D3).
- **Clients** authenticate with the agent key on `/api/ws?token=…`, as the dispatcher does.

### Evidence

Final run: run 3 on fork commit `395f5fb668`, branch `integrate/session-mail`. **25 of 26 checks
pass** (`evidence-results.json`: 77 model requests, 29 hook records). There were no backend
tracebacks. Logs stayed outside git.

Earlier runs fixed the harness, not the product:
- Run 1 (20 of 26): the fake model called the plugin tool directly. A plugin tool is deferred
  behind Tool Search, so the call has to go through `tool_call`. That finding is Q8 below.
- Run 2 (24 of 25): added the bridge call.
- Run 3 added the "pre-plugin session calls through the bridge" check.

| Q | Result | What was seen |
|---|---|---|
| **Q1** queued mail vs the reaper | **pass**, plus the expected loss case | Mail queued with `--no-steer` behind a **detached, producing** turn. The sender detached straight after the `queued` ack. The mail ran as the next turn after the turn ended, past the 3-second grace. **Quiet** detached turn (one 20-second model wait, over the 12-second stale limit): the queue ack came back, the reaper interrupted the turn, and the mail **never ran**. This is case 1 in the brief, as predicted. The turn-end drain race was not seen. |
| **Q2** what the model receives | **pass** (observed) | **Steered:** a user row `[OUT-OF-BAND USER MESSAGE — a direct message from the user …]`, then the 📨 header on the next line, the body and the footer, then `[/OUT-OF-BAND USER MESSAGE]`. **Queued / started:** a plain user row starting with the 📨 header. **Queued and merged:** `ALEX_QUEUED_TEXT …` + blank line + the 📨 mail, in **one** user row, so the header is not at the row start. **A body containing `[/OUT-OF-BAND USER MESSAGE]` passes verbatim.** It closes the steer frame early, so the following "fake trailing instruction" sits outside the frame. The system prompt carries "Mid-turn user steering" and "same authority". |
| **Q3** `post_llm_call` sees the right turn | **pass** (5 of 6 paths) | (a) An accepted steer appears as a `display_kind: "steer"` row in the joined turn's hook, and that turn's final answer carries the `[REPLY]` block. (c) A steer that arrives while the model writes the final answer is acked `steered`, misses that turn, and becomes the **next turn's plain user message** (no marker). It is answered exactly once. (d) Queued mail merged with Alex-style text: one turn, found at a line start. (e) Self-mail from a tool steers into its own turn and shows in the same hook. (f) A reply into a sender whose turn is still running steers (Q10 round 1). **Not run:** (b) a steer parked during compression. There is no cheap way to hold compression in flight. **Forged header:** a body line imitating the header was matched by the line-start regex alone, and the probe even tried to "reply" to the fake sender (`4007 session not found`). |
| **Q4** idle start, not loaded | **pass** | The session was torn down after the grace. Resume, steer refused, submit: `started` with `message.start`. The sender was held **0.14 s**. `message.start` comes before the model's first reply, so with a fake model the hold is the agent build only. |
| **Q5** a CLI process holds the session | **pass** | A `hermes chat -q … --resume <id>` turn was running. The mail got `prompt.submit failed: 4090 This chat is open in another Hermes window/terminal … opened by cli`. Resume succeeded. The steer was refused (the rule swallows a steer error), and the refusal came on submit. The CLI turn finished all 7 requests (rc 0), and the mail never reached the model. |
| **Q6** second mail into a mail-started turn | **pass** | The first mail started the turn and its sender detached. The second mail was `steered`. The first turn ran all 7 steps, and nothing about a takeover or interrupt was logged. |
| **Q7** a tool delivers back into its own dashboard | **pass** | The tool inside a dashboard turn delivered over loopback (`started`, 0.14 s). Another client's `session.list` stayed at 0.021 s at most over 30 calls. The tool thread had **no** running event loop. |
| **Q8** a pre-plugin session after the restart | **fail as worded; design changes** | Every plugin tool is **deferred behind Tool Search** (`tools.tool_search.enabled: auto`, which is on by default). The pre-plugin session's tool definitions were **byte-identical** before and after the restart: **no cache miss**. Its pinned bridge listing does **not** name the new tool. The session **can** call it through `tool_call` (the call steered and returned a result), but only if something tells it the name. A **new** session's `tool_search` description lists `sm_probe_send` with a truncated description. The stored system prompt was reused. |
| **Q9** interrupted or failed turn | **observed** | `post_llm_call` **did not fire** for an interrupted turn (`session.interrupt`), nor for a turn that failed on a provider 400 ("retrying won't help"). |
| **Q10** debate | **pass** | Three replies: A→B started, B→A **steered** into A's running turn, A→B started. Round 4 answered `[SILENT]`, and nothing more was sent. The hook took at most 0.6 ms; reply delivery ran on its own thread. |

### Conclusion

**Proceed**, with these HLD changes (made in the same commit):

- **Q8 → D6, Persistence, Open O11.** `session_message` will be a **deferred** tool wherever Tool
  Search is on. That is the default; the live setting was not read. The "one cache miss per
  resumed session" cost becomes **none**. But pre-plugin sessions are not told the tool exists,
  and the tool description (the "no empty replies" rule) is only visible through
  `tool_describe`. So:
  - the message footer is the load-bearing carrier of the reply rules (already so in D2);
  - senders must learn the name `session_message` somewhere else. The obvious place is the
    relay skills that run the dispatcher today. Those skills live in the live home, so this is
    a deploy step for Alex to agree.
- **Q2/Q3 → B2, D3.** Relabelling control frames and header lookalikes in the body is required,
  not optional. So is the outbox target and "no reply yet" check: the line-start anchor alone
  matched a forged header.
- **Q9 → O9 resolved.** No hook, no reply. The outbox shows "no reply". Nothing is mailed.
- **Q1 → O10 not triggered.** "Detach at once after `queued`" holds for a producing turn. The quiet
  turn loss stays a documented loss case.
- **Q5 → D4 table.** `SESSION_NOT_OWNED` arrives as **4090 on `prompt.submit`**, after resume and a
  refused steer.

**Still unknown:**
- Q3(b), a steer parked during compression.
- The turn-end drain race.
- Whether a mail steered into a turn that is then interrupted is lost or handed back.
- Real models' reading of the header inside the user frame (HLD O7).
- The live install's `tools.tool_search` setting.
- Hermes Mobile rendering. No phone was attached to the trial dashboard.

### What we will not treat as product

All of `poc/`. Build must rebuild:
- the delivery module (HLD P1) from `1516a52669`, with its own tests;
- the plugin's tool, CLI, outbox and reply hook (P3), including the outbox target check and
  body relabelling that the probe lacks.

`sm_probe/` deliberately skips the outbox, addressing, the sender-source rule and relabelling.
The fake model is not a reusable fixture.

## Optional

Output kept outside git: backend logs, the CLI log, the per-run home (`sm-probe-*.jsonl`) and the
raw `results.json`. They stay in the trial run directories. `evidence-results.json` is the run-3
results with local paths and ports replaced by placeholders.
