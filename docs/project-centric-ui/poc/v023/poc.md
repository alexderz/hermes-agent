# PoC — On v0.23, can a second gateway client steer, queue and stop a `hermes chat -q --oneshot` turn, also after the CLI exits?

- Date: `2026-11-11`
- HLD: `docs/project-centric-ui/hld.md` (Goal 5, PoC questions)
- Ticket: n/a (Epic `DER-686`, Plan step, v0.23 round)

## Required

### Question

Alex's 21:00 requirement: an owner chat must be reachable and steerable from the phone while it
works. The brief (round 4, facts 17–19) and the refiner say the v0.23 base already meets it,
verified in code only. Owner kickoffs keep using `hermes chat --in <folder> -c "<title>"
--create-if-missing -q "<prompt>" --oneshot -Q` (assumption A5). Questions:

1. Does that one-shot turn run inside the combined gateway, so that another interactive client of
   the gateway (what a Webapp socket is) sees it running?
2. Can that client steer it, queue a follow-up and stop it, with no `SESSION_NOT_OWNED`?
3. The brief's open point: if the CLI process exits mid-turn (unit time limit, crash), does the
   gateway turn keep running and stay steerable?

### Setup

`trial_gateway_oneshot.py`, run from the repo root with an isolated environment built by
`python -m pm.build_env --source . --out <trial-venv> --cache <trial-cache>` (temporary
`HERMES_HOME` and cache folders), then:

```
HERMES_HOME=<empty tmp> PYTHONDONTWRITEBYTECODE=1 <trial-venv>/bin/python \
  docs/project-centric-ui/poc/v023/trial_gateway_oneshot.py --output <out-dir>
```

What it does:

- Writes a temporary `HERMES_HOME` with only throwaway values: a `custom` model provider pointing
  at a fake local model on 127.0.0.1, `gateway.multiplex_profiles: false`, title generation off,
  memory off. No `auth.json`, no `.env`, no credentials.
- Starts a real gateway daemon (`python -m gateway.run`) on that home and waits for
  `query_identify(home)` to report `ready` (pattern: `evals/desktop_gateway_ticket_native/run.py`).
- Fake model: each tool-carrying request waits 1.5 s, then asks for a `read_file` tool call until
  8 tool results follow the last user message, then answers `TURN_DONE`. It records every
  request, so the harness sees what reached the model.
- Kickoff: a real `python -m hermes_cli.main chat --in <project> -c "PRB - Owner"
  --create-if-missing -q "<prompt>" --oneshot -Q` subprocess on the same home.
- "Webapp" stand-in: a second connection opened with the CLI's own `connect_gateway()`, which
  mints an `interactive` socket ticket (the purpose a Webapp socket carries). It sends
  `session.resume` (by title, then by id), `session.steer` (with the resume reply's
  `execution_generation`), `prompt.submit {queued: true, submission_id}` and `session.interrupt`.

### Evidence

Run on commit `5e45a249b537b48fc63b8ca706625f2c0a997ea9` (branch
`integrate/project-centric-ui-023`: v0.23.1 plus the fork's carried commits). Result:
**14 of 14 checks pass** on the first run (`evidence-results.json`). Logs stayed outside git; the
gateway log had no tracebacks.

| # | Check | Result |
|---|---|---|
| 1 | Gateway daemon ready on the temporary home | pass |
| 2 | The one-shot CLI's turn reached the fake model | pass |
| 3 | Second client resumes the CLI's session by title and sees `running: true` | pass (`execution_generation: 1`) |
| 4 | `session.steer` during the CLI's turn | pass (`status: queued`) |
| 5 | Queued `prompt.submit`, no `SESSION_NOT_OWNED` | pass (`status: queued`, admission id returned) |
| 6 | The steer text reached the model inside the CLI's running turn | pass |
| 7 | The CLI finished its turn and exited 0 | pass |
| 8 | The queued prompt ran as the next turn, in the gateway, after the CLI had exited | pass |
| 9 | SIGKILL of a second kickoff's CLI mid-turn: the gateway turn keeps calling the model | pass (2 → 7 requests in 8 s) |
| 10 | That turn is still `running` for the second client | pass |
| 11 | `session.steer` still accepted after the CLI died | pass |
| 12 | That steer reached the model | pass |
| 13 | `session.interrupt` from the second client accepted | pass |
| 14 | The interrupted turn stops calling the model | pass (no request in the 6 s after) |

Also seen: a session the v0.23 CLI creates gets a `local-…` id. Alex's six owners are older rows
(source `cli`, historical ids). On first gateway use the gateway adopts such a row and keeps its
historical id as the stable logical id; compaction may later move the physical row, never the
logical identity (`gateway/session_local_migration.py`, module docstring and
`resolve_local_target`). So the owner pointer stores the durable stored id, and the Webapp matches
it on either identity a row carries (`id` or `_lineage_root_id`), the same way pins are matched.

### Conclusion

**Proceed: slice 1 builds nothing for steering.** On v0.23 the one-shot kickoff's turn runs in the
gateway; another interactive gateway client sees it running and can steer, queue and stop it; and
the turn keeps running, still steerable, after the CLI process is killed. The round-3 kickoff
command stays dropped.

**Still unknown** (not cheap to prove here; checked live after deploy, as the brief's Verify
later says):

- **The real Webapp in a phone browser.** The stand-in used the same verbs and ticket purpose,
  not the browser's sign-in path (`hermes_cli/web_routers/webapp.py`). The Webapp's own code joins
  a running turn on open (brief fact 16).
- **Hours, not seconds,** and a real model.
- **A gateway restart mid-turn.** Not tried; the HLD's deploy section uses the drain-first restart
  instead.

### What we will not treat as product

All of `poc/v023/`. Build rebuilds nothing from it for steering (nothing is built). Build's own
tests for the owner field, the sidebar and the `/new` rule are separate (HLD Worker rules). If a
regression test for "a one-shot turn is steerable from a second client" is wanted, rebuild it as a
proper test against a temporary `HERMES_HOME`, never by importing this file.

## Optional

Output kept outside git: the gateway and CLI logs and the raw results file stayed in the trial's
temporary output folder (logs are not committed; the results file is committed with temporary
paths replaced). The isolated trial environment also stayed outside the checkout.
