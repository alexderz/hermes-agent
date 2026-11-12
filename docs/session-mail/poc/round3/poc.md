# PoC — Round 3 (v0.23): who hosts which session, and can intercom drive them from inside the owner?

- Date: `2026-11-11`
- HLD: `docs/session-mail/hld.md` (O19), `docs/session-mail/v023-delta.md` (D-1 to D-4)
- Ticket: n/a (Epic `DER-701`, Plan step, Trial)

## Required

### Question

1. On v0.23, which process hosts each of these:
   - dashboard chats;
   - Ink TUI / Desktop sessions (sessions attached to the owner);
   - classic CLI sessions;
   - messaging-gateway sessions?

   And how is the live canary laid out (read only)?
2. **D-1 option (b):** can a plugin running **inside the owner** drive steer, redirect or
   interrupt, queue, idle start and cold start for each kind, with only the owner's existing
   verbs and **published** plugin API names?
3. **The reply route:** does `post_llm_call` fire for each kind, and can a reply be delivered
   back to a sender of another kind?
4. Is a core patch needed at all? If so, the smallest one, and is it a behaviour change or only
   a `plugin_api.json` listing?

### Setup

`trial_r3.py` and `intercom_overlay/` (`__init__.py` replaces only intercom's `register()`;
`r3_trial.py` holds the stand-ins), in this folder. The round-2 fake model, fake ntfy server and
agent-key WebSocket client are reused by loading `../round2/trial_r2.py` by path.

```
PYTHONDONTWRITEBYTECODE=1 <venv023>/bin/python docs/session-mail/poc/round3/trial_r3.py \
    --run <run-dir> --intercom-clone <intercom-clone> [--only q2_dash]
```

**Per run**, a throwaway `HERMES_HOME` with:
- a fake-model provider;
- the dashboard gate on, as live;
- an agent key (`0600`);
- `busy_input_mode: interrupt`;
- `plugins.enabled: [intercom, ntfy-platform]`, with `allow_gateway_injection: true`;
- a `.env` holding only the fake ntfy server values.

**Processes**, all on 127.0.0.1, each run memory-capped:
- a real `hermes gateway run` owner, with the bundled ntfy adapter against a fake ntfy server;
- a real standalone `hermes dashboard`;
- a real interactive classic CLI (`hermes`) under a pty;
- the harness, attaching to the owner the way Ink and Desktop do
  (`discover_gateway_endpoint` + `connect_gateway`, then `session.create`).

**Intercom:** the clone (`ae90a2a`) is copied **unedited**. The overlay:
- replaces `inbox._serve`, so the harness can ask a given process to deliver;
- records `post_llm_call` with the pid;
- delivers two ways:
  - **"client":** the owner's canonical verbs, opened from inside the process;
  - **"ctx":** the published `ctx.inject_message`.

**Live layout:** read with `ps` and `systemctl --user list-units` only, with no connections.

### Evidence

Fork commit `9aa6dbc600` (`integrate/session-mail-023`, v0.23.1 canary base), intercom `ae90a2a`.
- **Run 6** (full): 20 of 24. The 4 misses are one finding: the owner refuses dashboard-hosted
  chats.
- **Run 7** (Q1 plus the dashboard paths): 6 of 6.

Runs 0–5 fixed the harness: `connect_gateway` is an async context manager; canonical
`prompt.submit` needs a `submission_id`; a connection must `session.resume` a session before it
may submit to it; and the agent key is only accepted when the dashboard gate is on. Results are
in `evidence-results.json`; logs stayed outside git.

**Q1, hosts** (the process whose `post_llm_call` ran the turn):

| Session kind | Host | Lease in `runtime/active_sessions.json` |
|---|---|---|
| Attached to the owner (what Ink and Desktop do) | **owner** (`gateway run`) | none |
| Classic CLI | **owner**. The CLI process is only a client, though it also writes a lease for a v0.22-style row it keeps | CLI pid (not the host) |
| Messaging (ntfy) | **owner** | none |
| Standalone `hermes dashboard` chat | **the dashboard process** (legacy in-process `tui_gateway`; v0.22-style id) | dashboard pid |

**Live (read only):** `hermes-dashboard.service` ("dashboard (PWA) on 127.0.0.1:9119, behind
caddy-edge") and `hermes-gateway.service` are separate processes. The dashboard's main process has
the embedded `/chat` Ink client and agent terminal shells as children, so live dashboard and phone
chats run in the **dashboard** process, as in the Trial. **Live has two hosts.**

**Q2, from inside the owner** (one call sequence per cell):

| Target | steer | queue | interrupt | idle start | cold (owner restarted) |
|---|---|---|---|---|---|
| Owner-attached | ✅ `session.resume` → `session.steer` (steer row in the running turn; turn kept 4 of 6 steps) | ✅ `session.resume` → `prompt.submit{queued:true}` (ran after the turn's 6 steps) | ✅ `session.resume` → `session.redirect` (`redirected`; turn stopped at step 1; the message ran) | ✅ `prompt.submit` | ✅ `session.resume` restores the session, then `prompt.submit` (0.7 s) |
| Classic CLI | ✅ same | ✅ same | ✅ same (redirect) | ✅ | — |
| Messaging (ntfy) | ✅ same | ✅ same | ✅ same (redirect) | ✅ | — |
| Dashboard chat | ❌ `runtime_coordination_required` | ❌ same | ❌ same | ❌ same | — |

- **Dashboard chats are reached only through the dashboard process** (run 7):
  - the dashboard plugin's own `ctx.inject_message` (tui host) ran the message (queue or start
    only, as in v0.22);
  - the dashboard's own `/api/ws` with the agent key (the ported dispatcher route) steered
    (`session.steer` → steer row) and queued (`prompt.submit{queued}` → own turn).
- **The published `ctx.inject_message(text, session_key=<session id>)` inside the owner**
  returned `True` for every kind, **but no message ran.** The call needs the route key, which a
  plugin has no published way to read, and it would be queue-only anyway (a producer admission).
  An accepted-then-dropped `True` is worth reporting upstream.
- **Published status of every call used from inside the owner:**

| Call | In `plugin_api.json`? |
|---|---|
| `hermes_constants.get_hermes_home` | yes |
| `ctx.register_hook`, `ctx.inject_message` | yes (`ctx`) |
| `hermes_cli.gateway_client.connect_gateway` | **no** |
| `hermes_cli.gateway_runtime.discover_gateway_endpoint` | **no** |
| `tools.thread_context.propagate_context_to_thread` | **no** (stdlib `contextvars.copy_context().run` can replace it) |
| The verbs `session.resume`, `session.steer`, `session.redirect`, `session.interrupt`, `prompt.submit` | wire verbs, not Python names; declared in `tui_gateway/contracts/canonical_sessions.py` |

**Q3, reply route:**
- `post_llm_call` fired in the owner for owner-attached (`tui`), CLI (`cli`) and ntfy (`ntfy`)
  turns, and in the dashboard process for dashboard chats (`tui`, the dashboard pid).
- **Replies from the owner's hook reached senders of another kind:**
  - CLI → owner-attached: `started`;
  - ntfy → owner-attached: `started`;
  - owner-attached → ntfy: `started`.

  Each reply reached the model (the `ISREPLY` text was seen).
- **Not run:** a reply from an owner-hosted session to a **dashboard** sender. The owner verbs
  refuse dashboard chats (Q2), so that leg must use the dashboard route (agent-key socket or the
  dashboard's own tui host), which Q2 proved.

### Conclusion

**Proceed with D-1 (b), plus a dashboard leg while the dashboard is a standalone process.**

**Owner-hosted sessions** (Ink, Desktop, classic CLI, messaging) need **no behaviour patch**.
The owner's existing verbs give every mode, idle and cold start, and the reply route, from inside
the owner.
- The only core change is publishing two names in `plugin_api.json`
  (`hermes_cli.gateway_client:connect_gateway`,
  `hermes_cli.gateway_runtime:discover_gateway_endpoint`), each in its own listing PR with docs
  and a behaviour test. Or a `ctx` method that wraps them.
- The framing helpers the LLD uses (`CONTROL_FRAME_OPENERS`, `sanitize_title`,
  `sanitize_user_prompt_text`) need the same treatment, or an in-plugin copy.

**Dashboard-hosted chats** on the live layout are refused by the owner. Two options:
- **(i)** keep the fork's dashboard socket route with the agent key (already deployed, steer and
  queue proven; redirect is the same `correct` verb family on v0.22); or
- **(ii)** move Alex's dashboard under the gateway owner (the gateway-mounted dashboard), so every
  chat has one host. That is a deploy and config question for Alex, not code.

**Still unknown:**
- whether the gateway-mounted dashboard serves the phone app the same way (option ii);
- the Ink TUI client itself (emulated by an attach that does what Ink does);
- the Desktop's own `hermes serve` backend (likely like the standalone dashboard);
- the hard-interrupt fallback, because redirect always succeeded;
- multiplexed profiles.

### What we will not treat as product

All of `poc/round3/`. Build rebuilds the client delivery (D-1 b), the dashboard leg, and the
listings. The trial's use of unpublished names is exactly what the listing PRs must replace.

## Optional

Output kept outside git: per-run homes (`r3-trial.jsonl`, `state.db`), owner, dashboard and CLI
logs, and the raw `results.json` files in the trial run directories. `evidence-results.json` is
runs 6 and 7 with paths and ports replaced.
