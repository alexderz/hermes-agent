# HLD — session-mail: session-to-session messaging, built on intercom (gateway only)

- Slug: `session-mail` (chunk working name; the shipped plugin is `intercom`)
- Track / chunk ids: Hermes Improvement (no tracker id) / Epic `DER-701`
- Brief: `docs/session-mail/brief.md` (round 6, Refine pass round 5). Alex's words and decisions
  are in the Hermes Improvement vault, `requests/2026-11-09-session-mail-brief.md`.
- Base: `integrate/session-mail-023` (v0.23.1 canary, `alex/v0.23.1-canary-1110`)
- Date: `2026-11-11` (HLD round 3, gateway only, with security review round 5 folded in; round 2 is in git at `9aa6dbc600`, round 1 at
  `f72a12780b`)

Alex accepted the Plan and UX on 2026-11-10 with every recommended answer (SM-Q7 to SM-Q17).
On 2026-11-11 he settled **SM-Q20 (gateway only)** and **SM-Q22 (Hermes Mobile dropped)**. The
detailed design is `docs/session-mail/lld.md` (round 5).

## Problem

Alex runs many long-lived Hermes sessions, and they cannot message each other: project owner
sessions, `Home`, helpers, terminals and messaging chats. On the live v0.23 install, every chat
surface he uses runs in **one process per profile, the gateway owner**: the Webapp at the main
hostname (served by the gateway), desktop, Ink TUI, classic CLI and messaging.
- **Intercom**, the community answer to upstream #81885, reaches only a classic CLI process. Run
  unedited inside the owner, it parks every message and drains it into whichever session runs
  next (v0.23 delta).
- **Hermes's own `ctx.inject_message`** only queues, and called with a session id it is
  accepted but never runs (Trial round 3).

## Goals

1. Any session, cron job or script can message one named session hosted by the owner: Webapp,
   desktop, Ink TUI, classic CLI or messaging chat.
2. Delivery happens at once, in the requested mode (`interrupt`, `steer` or `queue`; default
   `steer`). The strongest mode the target can take, at or below the request, is applied. An idle
   or cold target starts a turn.
3. The receiver can tell a message from Alex's words, and treats it as a peer's (A′).
4. The final answer goes back on its own; a debate ends at `[SILENT]`.
5. A durable record keeps sender, target, body, requested and applied mode, and the reply.
6. The work lands in our intercom fork, plus **listing-only** core PRs, all upstreamable.

## Non-goals

- Any hold, cap, rate limit, duplicate filter, hop limit, approval gate, retry or give-up timer.
- **Chats in the old standalone dashboard** (`hermes dashboard`, kept as an admin panel): they
  are not addressable; intercom refuses them clearly.
- **Hermes Mobile** (SM-Q22).
- A core behaviour patch of any kind (this replaces settled decision 11).
- Cross-machine or cross-install delivery; messaging across profiles.
- A core steer-frame patch; a plugin system-prompt section.
- Posting anything upstream (drafts only, for Alex).

## Users / operators

| Who | Uses |
|---|---|
| **Alex** | Watches and steers mailed turns where they run (Webapp, desktop, terminal, Telegram); reads the record with `hermes intercom log` / `status`; approves the gateway restart |
| **Agent sessions in the owner** | The `intercom` tool; they receive messages as user rows and answer with their final answer |
| **Scripts and cron jobs** | `hermes intercom send …` (a client of the owner; always a script sender) |
| **The manager** | Edits the relay skills at deploy, renames "Model Master", schedules the restart |

## UX / stories

`docs/session-mail/ux.md` (round 7) and `stories/`. The designer updates:
- Hermes Mobile surfaces are out of scope (SM-Q22);
- the cold-start receipt ("the gateway reopened it");
- the echo timing (posted as the target's turn runs, LLD B6);
- the `not-addressable` receipt for admin-dashboard chats.

Operator acceptance: pending for these deltas.

## Comparables

`docs/session-mail/comparables.md`: intercom (the base), Bot Mode, walkie-talkie, Claude Code
cross-session messaging, upstream #106423. miyu4u's fork is now the closest prior art: it is a
client of v0.23's owner, as this design is.

## Superseded decisions

- **Round 3 (2026-11-11, SM-Q20):**
  - "One small core seam on every host" (decision 11; HLD round 2 P1 and D1) → **no behaviour
    patch**. Intercom is a **client of the profile's owner** and uses its existing canonical
    verbs. Core changes are `plugin_api.json` listings only.
  - The dashboard route, the agent-key wake path and the fork-only wake module (P5, D4 step 3) →
    removed. The owner restores cold sessions on `session.resume`. Admin-dashboard chats are
    `not-addressable`.
  - Lease-pid routing, per-process sockets, envelope v2, the gateway endpoint role (P2, P4, D4,
    D6) → removed. One host: the owner.
  - F3's peer-pid binding and F11's gateway pid → replaced by the owner's authorisation (the
    same-UID ticket, actor, session reference and profile). See LLD § Removed security fixes.
  - `gateway/chat_scope.py` and the core echo → the chat rule and the echo move into the
    plugin (published `hermes_state`, `ctx.get_config`, `ctx.post_message`).
  - Deploy: the dashboard restart → **one announced gateway restart**.
- **Round 2 (2026-11-09):** a new `session-mail` plugin → our intercom fork; dashboard-only
  delivery → every host; "never cancel or redirect" → three delivery modes; "no core patch" → one
  seam (now superseded again, above).
- **Round 1:** the dashboard-only worker, outbox-as-bus, `📨` header and related details (in git).

## Shape

### Parts

| # | Part | Repo / where | Owns |
|---|---|---|---|
| L | **Listing PRs** | alexderz/hermes-agent `hermes_cli/data/plugin_api.json` (+ regenerated `public-api.md`, a behaviour test) | Publishing `connect_gateway`, the gateway client errors, `discover_gateway_endpoint`, `CONTROL_FRAME_OPENERS`, `sanitize_user_prompt_text`. No behaviour change |
| C | **Owner client** | `intercom:client.py` | Discovery and attach; the verb sequence per mode; error mapping |
| S | **Send path** | `intercom:route.py`, `address.py`, `scope.py`, `frame.py`, `record.py` | Addressing, the chat rule, consent for every delivery, framing and the hash, the record |
| R | **Replies and `ask`** | `intercom:replies.py` | `post_llm_call` in the owner, silence, SM-Q9 (b), the in-process `ask` waiter |
| E | **Echo** | `intercom:echo.py` | SM-Q15 (b) through `ctx.post_message` from the target's own turn, private chats only |
| U | **CLI and tool** | `intercom:cli.py`, `__init__.py` | `hermes intercom send\|list\|status\|log`; the tool schema |
| V | **Vendored copy** | alexderz/hermes-agent `plugins/intercom/` (`git subtree`) | What the install runs |
| D | **Upstream drafts** | `intercom:docs/upstream/` | #81885 update, majordave pull request, listing pull requests |

**What survives of intercom's transport:** the tool, its `send` / `ask` / `reply` / `list`
vocabulary, its frame style and echo stripping. **Not** its socket and registry: on an install
with an owner they are not used for delivery, the CLI, `ask` or cross-profile refusal. They stay
only as the legacy path on a Hermes **build** that cannot host an owner client (older Hermes,
upstream users). The choice is by capability (are the owner-client names importable?), never by
whether an owner is up right now; an owner that is down is `no-owner` / `owner-restarting`. On an
old build the legacy inbox starts only in a classic CLI process, never in a multi-session host.
This keeps intercom's 17 tests and its upstream behaviour (LLD B12).

### Sketch

```
 sender: tool call in an owner session (session_id known)  |  `hermes intercom send` (script)
   │ resolve → chat scopes → consent (every delivery) → record row → frame + span hash
   ▼
 owner client (connect_gateway; ticket from the same-UID control socket)
   session.resume{omit_messages} ──► running?  no → prompt.submit                         = start (cold ok)
                       yes → steer:     session.steer, else prompt.submit{queued}
                             queue:     prompt.submit{queued}
                             interrupt: session.redirect, else session.interrupt + submit
   admin-dashboard chat → runtime_coordination_required → not-addressable
   ▼
 owner runs the turn (Webapp / desktop / Ink / CLI / messaging)
   pre_llm_call / post_tool_call (intercom) → echo via ctx.post_message (private chats only)
   post_llm_call (intercom) → reply / silent → owner client back to the sender (steer)
```

### Data

- **The record:** `plugin-data/intercom/record.db` (SQLite, `0600` with its sidecars). The round 4
  schema, with `delivery_path` and `admission_id` in place of the host columns. The sender writes
  `header_sha`.
- **Settings:** `plugins.entries.intercom.settings.{user_name, echo_chats, owner_user_ids}`, and
  the existing `allow_gateway_injection` key.
- **Nothing in** `runtime/active_sessions.json` is read, and no intercom registry is used, on an
  install with an owner.

### Trust boundaries (detail: LLD § Trust boundaries)

- **TB-1, plugin or CLI to the owner:** same-UID control socket, single-use ticket for this
  profile, and the owner authorises every verb. Admin-dashboard chats are refused.
- **TB-3, model text into another session:** the A′ frame, the relabel rule, field cleaning, the
  sender from the session (the CLI only as a script), never hidden.
- **TB-4, consent and operator power:** the existing `allow_gateway_injection` consent, required
  for every delivery; relayed text is labelled. The owner admits operator input without
  re-checking a chat's current platform authorisation, so intercom can start a turn in any stored
  chat of the profile, as Alex can from the Webapp (O23).
- **TB-5, content leaving the machine:** one chat rule in the plugin. Echo to private chats only;
  a shared chat gets a model-only line; a reply to a shared sender is the explicit block only.
- **TB-6, profiles:** the ticket is profile-bound and session references carry the profile.
- **TB-7, the record:** owner-only files.

Removed fixes and their replacements are listed in LLD § Removed security fixes, for security's
re-check.

### Decisions in force

- **A′ framing** (SM-Q7): `📡 Not Alex · [interrupt asked · ]<label> · hermes@<sender> says (…)`,
  then the authority line, the body (relabelled), the footer and the closing line.
- **Replies** (SM-Q8 option 2): the block, else the whole answer. The data-class exception is for
  shared-chat senders.
- **Senders whose run is over** (SM-Q9 b): replies to `cron`, `oneshot` and `subagent` senders
  are stored only.
- **Addressing** (decision 2): titles, `@slug`, ids, `Home`, compression tip. No endpoint names.
- **Modes** (decision 3): the owner verbs per LLD B1; `interrupt` normally applies as redirect.
- **No caps** (decision 5).
- **`ask` / `reply`** (SM-Q16 a): unchanged in meaning; the waiter is resolved in the owner.

## Persistence

| What | Where | Durable? |
|---|---|---|
| The record | `<hermes-home>/plugin-data/intercom/record.db` | Yes |
| Messages as delivered | The target's transcript (owner) | Yes |
| Queued messages | **The owner's durable FIFO** (admissions survive an owner restart; a started admission that was interrupted settles as such) | Yes, by the owner |
| A reply in flight | The reply thread | No; the reply row shows no result |
| Settings | `config.yaml` via house-infra | Yes |

## Worker rules

- Builders work on item branches in each repo (`chunk.md`):
  - **Claude Opus** for G-1 (listing), G-2 (client), G-3 (send path), G-5 (scope), G-6 (echo)
    and G-9 (replies);
  - **Grok 4.7** for the rest.

  Reviewers are fresh Claude Code sessions.
- **Intercom work stays in intercom's style.** Its 17 tests keep passing, except the changed cap
  tests.
- **Hermes work:** `scripts/run_tests.sh`, a temporary `HERMES_HOME`, behaviour tests,
  `scripts/boundary_lint.py` clean for `plugins/intercom`.
- **Commits in `wt/v023` run with an isolated `HERMES_HOME`, or with hooks off.** The lefthook
  setup otherwise provisions into the account's real home (Trial round 3 incident).
- **HITL (Alex):** the mockup and UX deltas; the restart window; the upstream text.
- **Workers must not:**
  - add caps, holds, retries, timers, gates or a worker;
  - patch core behaviour;
  - use unpublished core names in `plugins/intercom` (only after G-1 lists them);
  - address admin-dashboard chats;
  - post upstream;
  - touch the live install or restart anything.

## Open

| # | Item | Status |
|---|---|---|
| O1–O8 | SM-Q7, SM-Q8, SM-Q9, SM-Q10, SM-Q11, SM-Q14, SM-Q15, SM-Q16 | **Answered** 2026-11-10 (as recommended). SM-Q11 is moot since SM-Q22 |
| O9, O10, O14, O16, O18 | Seam upstream shape; gateway endpoint role timing; multi-profile dashboard socket; re-applying the seam at the v0.23 rebase; a CLI without a lease | **Closed by SM-Q20:** there is no seam, no endpoint role, no lease routing, and every session is owner-hosted |
| O11 | Relay skills | **Settled:** the manager edits them at deploy to `hermes intercom send` (LLD G-11) |
| O12 | The live `tools.tool_search` setting (cache cost of the new tool) | Open; read at deploy planning |
| O13 | Real models and the header inside the steer frame (the reopen trigger for a frame patch) | Open; watch real use |
| O15 | One restart shared with DER-686 | Open (now a gateway restart) |
| O17 | The queued-row "duplicate" | **Retracted** (LLD round 4) |
| O19, O19a | The v0.23 shape change and the Trial round 3 answer | **Closed:** SM-Q20 answered "gateway only"; this HLD is the result |
| SM-Q20 | Keep the standalone dashboard as a host, or the gateway only | **Answered (Alex, 2026-11-11): gateway only.** The admin dashboard stays for administration; its chats are not addressable |
| SM-Q22 | Hermes Mobile | **Answered (Alex, 2026-11-11): dropped**, out of scope |
| O20 | Listing vs `ctx` wrapper upstream | Designed on listing (LLD G-1); a `ctx.owner_client()` wrapper is the fallback if upstream prefers it |
| O21 | Echo hooks: do `pre_llm_call` / `post_tool_call` run bound to the target messaging session in the owner, and does `ctx.post_message` post there? | Verify in G-6's E2E. If not, the echo is dropped for v1 (SM-Q15 falls back to (a)), with no core patch |
| O22 | The exact `sessions.source` strings for owner-local sessions (scope rule B4) | Verify in G-2's E2E |
| O23 | **Operator power (security R5-2):** intercom can start a turn in any stored chat of the profile, including one whose user has since been removed from an allowlist or unpaired; the answer goes to that person. v0.22's seam re-checked this; v0.23 publishes no predicate for it | **For Alex to accept with the LLD (SM-Q18).** Mitigated by the chat rule (such a chat is `shared`, no echo). If not accepted: a thin read-only core predicate plus its listing (a small core addition, not a host behaviour change) |

## Risks

- **`interrupt` misused** by a model: mitigated by Alex's sentence and the default `steer`. No
  gate.
- **Relayed messaging text** steering Alex's sessions: mitigated by the header, line 2 and the
  consent key.
- **The gateway restart** cuts every chat at once, the manager's included; it is scheduled and
  announced.
- **Upstream may decline the listings.** The fork carries them as one small fork patch, a
  listing with no behaviour.
- **Drift** between `plugins/intercom` and alexderz/hermes-intercom: intercom first, then the
  subtree pull.
