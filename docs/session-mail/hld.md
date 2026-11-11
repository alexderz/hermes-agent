# HLD — session-mail: session-to-session messaging, built on intercom

- Slug: `session-mail` (chunk working name; the shipped plugin is `intercom`)
- Track / chunk ids: Hermes Improvement (no tracker id) / Epic `DER-701`
- Brief: `docs/session-mail/brief.md`, round 6, which passed Refine round 5
  (`docs/session-mail/brief-refine.md`). Alex's words and settled decisions are in the Hermes
  Improvement vault, `requests/2026-11-09-session-mail-brief.md`, including the sections
  "Scope addition", "Delivery modes" and "Build on intercom".
- Date: `2026-11-09` (HLD round 2; round 1 is in git at `f72a12780b`)

**Alex accepted the Plan and UX on 2026-11-10 with every recommended answer** (SM-Q7 to SM-Q11, SM-Q14 to SM-Q17; SM-Q17 is the Plan acceptance), recorded under [Open](#open). The detailed design is `docs/session-mail/lld.md`.

Paths without a prefix are relative to the Hermes repository root, on `integrate/session-mail`.
That branch carries v0.22.0, the fork patches, and the dispatch fix with the queue-aware
reapers (merge `3d4d482eb9`). Intercom paths are written `intercom:<path>`, against
`alexderz/hermes-intercom` at `ae90a2a`.

## Problem

Alex runs many long-lived Hermes sessions, and they cannot message each other:
- owner sessions per project, `Home` and helpers in the dashboard;
- terminal sessions (classic CLI, Ink TUI);
- messaging-gateway chats.

The community answer to upstream #81885, `majordave/hermes-intercom`, has several gaps:
- it reaches only a classic CLI;
- it parks mail for dashboard and TUI processes and drains it into **whichever** session runs
  next (`intercom:__init__.py:137-147`);
- it never interrupts and only steers;
- it has four caps;
- it frames mail with a process endpoint name that does not say "not Alex".

Hermes's own plugin seam, `ctx.inject_message`, breaks Alex's delivery rule on two hosts:
- a classic CLI turns every busy injection into a hard interrupt
  (`hermes_cli/plugins_injection.py:19-23`);
- the gateway only ever queues plugin events (`gateway/run_busy.py:843-849`);
- the TUI host only queues, with no accept-time row (`tui_gateway/plugin_inject.py:24-64`).

## Goals

1. Any session, cron job or script can mail one named session of **any** kind: a dashboard or
   desktop chat, an Ink TUI, a classic CLI, or a messaging-gateway chat (decision 9).
2. The **process that hosts the target** delivers it at once, in the requested mode:
   `interrupt`, `steer` or `queue`, with `steer` as the default. The host applies the strongest
   mode the target supports, at or below the request. An idle target starts a turn (decision 3).
3. A session that is live nowhere is woken in the dashboard, so Alex can watch and steer it from
   the phone.
4. The receiver can tell mail from Alex's words, and treats it as a peer's message (best effort,
   D2).
5. The final answer goes back on its own; a debate runs until `[SILENT]` (decisions 4–6).
6. A durable record keeps the sender, the target, the body, the requested and applied mode, and
   the reply (decision 7).
7. The work lands **in our intercom fork, in its style**, plus one small, upstreamable core seam,
   so both can be offered upstream (decisions 1, 11, 12).

## Non-goals

- Any hold, cap, rate limit, duplicate filter, hop limit, approval gate, retry or give-up timer.
  Intercom's four caps are removed.
- A background worker, a poller, or redelivery of mail that a host accepted and then lost.
- Cross-machine or cross-install delivery (Agent Tincan, SM-Q6); messaging across profiles,
  including bots in other profiles (SM-Q13).
- A core steer-frame patch (SM-Q7 C); Hermes Mobile changes; a plugin system-prompt section.
- miyu4u's v0.23 unified-gateway transport (prior art for the v0.23 rebase only).
- Posting anything upstream. Drafts go into intercom's `docs/` for Alex.
- Landing DER-686's `owner_session_id` (this chunk reads it once it exists).

## Users / operators

| Who | Uses |
|---|---|
| **Alex** | Watches and steers mailed turns from Hermes Mobile, the web app or Telegram; reads the record with `hermes intercom list` / `status`; answers the SM-Qs; approves the deploy restarts |
| **Agent sessions** (dashboard, desktop, Ink TUI, classic CLI, gateway chats) | The `intercom` tool. They receive mail as user rows and answer with their final answer |
| **Scripts and cron jobs** | `hermes intercom send --to … [--delivery …] [--from …] [--no-reply] (--message … \| --file …) [--json]`, plus `status` and `list` |
| **Upstream** (later, through Alex) | The #81885 update, an intercom pull request, the seam pull request |

## UX / stories

`docs/session-mail/ux.md` and `docs/session-mail/stories/` (designer). They must be redone for
the new base: intercom's `📡` frame instead of `📨`, the `intercom` tool instead of
`session_message`, `hermes intercom` instead of `hermes session-mail`, delivery modes, and
terminal and Telegram surfaces. Operator acceptance: pending. The HLD fixes the elements; the
wording belongs to the UX doc.

## Comparables

`docs/session-mail/comparables.md`. Intercom is now the **base**, not a comparable. The
comparables are Bot Mode, walkie-talkie, Claude Code, and upstream #106423 (peer messaging),
with miyu4u as prior art.

## Superseded decisions (HLD round 1 → round 2)

- P3, a new `plugins/session-mail` with a `session_message` tool → **our intercom fork**, plugin
  `intercom`, tool `intercom` (brief decision 1). The CLI `hermes session-mail` →
  `hermes intercom`.
- D4, every send goes over the dashboard WebSocket → **the hosting process delivers** through
  its intercom socket and the seam. The dashboard WebSocket is kept **only** for waking a session
  that is live nowhere (P5).
- "Never cancel or redirect" → **three delivery modes** with fallback, default `steer`
  (decision 3).
- "No core patch" → **one seam**, `inject_message(mode=…)` (decision 11).
- D2's `📨 Mail (not Alex)` header and `📨 End of mail` → **intercom's `📡 hermes@… says:` line
  in A′ form** (SM-Q7). The rules carry over: header first, an authority line, a footer, a
  closing line, and one relabel rule for every body line starting with the header emoji.
- The 4090 / `SESSION_NOT_OWNED` error for a CLI-held target → that target is now **delivered by
  its own CLI process**. 4090 remains only as a wake-path race (D4).
- D6, one dashboard restart only → dashboard **and gateway** restarts, plus vendoring by
  `git subtree` (SM-Q14).
- O11 and footer naming `session_message` → the footer names `intercom`.

**Shape changes from security review round 1 (LLD round 2, 2026-11-10).** Details are in
`lld.md`:
- **One chat rule in the gateway (F1).** A chat is `private` only when it is listed in
  `echo_chats`, or it is a DM with a user in `owner_user_ids`; everything else is `shared`.
  The rule governs the echo (private chats only), a model-only shared-chat line for bodies
  delivered into shared chats, and replies to shared-chat senders: there, only an explicit
  `[REPLY]` block is sent, never the whole-answer fallback. This is a data-class rule, not a
  delivery gate; SM-Q8 is unchanged between local sessions.
- **The seam gains two read-only `ctx` methods**, `injection_allowed()` and
  `session_chat_scope()`, plus `home_path` for a per-session profile check (F2, F1, F9).
- **Sender binding (F3).** On the socket, a claimed sender session is accepted only from the
  process that holds its lease, or from the verified gateway; otherwise the message is framed as
  a script and gets no reply.
- **Header (mockup review M-1).** Line 1 says `interrupt asked` (what was requested), not
  `interrupt`, because the frame is built before the host applies the mode.
- **Wake path.** Loopback only, with a port setting (F8), and the same `allow_gateway_injection`
  consent as live hosts (F2).

Still holds from round 1 and the Trial (`poc/poc.md`):
- the A′ reasoning (the outer frame is true; the content is a peer's);
- relabelling control-frame openers in bodies (Trial Q2);
- reply capture in `post_llm_call` with the record's target and "no reply yet" check (Trial Q3);
- stopped and failed turns fire no hook, so they send no reply (Trial Q9);
- Tool Search defers plugin tools (Trial Q8);
- the reaper's quiet-turn loss (Trial Q1);
- addressing (D5);
- the round-4 record fields, exit codes and the `status` transcript check.

## Shape

### Parts

| # | Part | Repo / where | Owns |
|---|---|---|---|
| P1 | **Core seam** | alexderz/hermes-agent: `hermes_cli/plugins.py` (`inject_message`), `hermes_cli/plugins_injection.py`, `tui_gateway/plugin_inject.py`, the CLI host (`hermes_cli/cli_tui_mixin.py` typed-input routine), `gateway/run_plugin_injection.py` + `gateway/run_busy.py` | `inject_message(…, mode="interrupt"\|"steer"\|"queue")` with the fallback chain on every host, returning what was applied (D1) |
| P2 | **Intercom transport changes** | alexderz/hermes-intercom: `inbox.py`, `__init__.py` | Socket kept; lookup by lease `pid`; many sessions per process; delivery through P1; GC lookup and private-field delivery dropped where P1 exists; caps removed; frame in A′ form (D2) |
| P3 | **Our additions inside intercom** | alexderz/hermes-intercom: new modules in its style (for example `address.py`, `record.py`, `replies.py`, `cli.py`) | Addressing (D5), `delivery` argument and receipt (D1), the record, automatic replies and `[SILENT]` (D3), `hermes intercom` CLI (D4) |
| P4 | **Gateway endpoint** | alexderz/hermes-intercom (gateway branch), plus P1's gateway path | The gateway's intercom endpoint marks itself; routing idle gateway sessions by `lookup_by_session_id`; SM-Q15 topic post (D6) |
| P5 | **Wake path** (fork only) | alexderz/hermes-agent: the dispatcher rule moved from `scripts/dashboard_dispatch.py` into an importable fork module (for example `hermes_cli/dashboard_dispatch.py`), with the script as a thin wrapper | Waking a session that is live nowhere: resume, then submit, then wait for the start, over the dashboard's loopback WebSocket with the agent key. Intercom feature-detects the module (D4) |
| P6 | **Vendored copy** | alexderz/hermes-agent: `plugins/intercom/`, by `git subtree` from alexderz/hermes-intercom (SM-Q14) | What the install runs; enabled through house-infra (D7) |
| P7 | **Upstream drafts** | alexderz/hermes-intercom `docs/` | The #81885 update, an intercom pull-request text, and the seam pull-request text. Nothing posted |

Intercom stays a plugin that touches no core file (`plugins/AGENTS.md`). P1 is the only core
change: generic, used through `ctx`, and it has a concrete consumer. P5 reshapes existing
fork-only code: the agent key and the dispatcher are not in `v0.23.0`.

### Sketch

```
 sender (tool in any host process, or `hermes intercom send`)
   │ P3: resolve address (state.db → compression tip)        ──refused──► receipt
   │ P3: record row (applied empty)
   │ route (D4):
   │   1. lease for the stored id in runtime/active_sessions.json → pid
   │        same pid as me → P1 in-process   other pid → that pid's intercom socket
   │   2. no lease, gateway source or route → the gateway's intercom endpoint
   │   3. live nowhere → P5 wake over the dashboard WebSocket (fork) / error
   ▼
 host process (dashboard/desktop, Ink TUI, classic CLI, gateway)
   P2 serve thread → P1 inject_message(session_key, text, mode=requested)
        → applied: interrupt (redirect | hard) / steer / queue / start
   receipt {mail, requested, applied, to} ──► sender ──► record updated
   … target turn ends … post_llm_call (P3 in that host): find mail ids in the turn's rows
        → reply stored / silent → reply thread → same route, delivery=steer
```

### Data

**Intercom registry (kept):** `$HERMES_HOME/intercom/sessions/<pid>-<time>.json`, one per
process (`name, pid, cwd, session_id, socket, started_at`). It gains `roles` (`gateway` when
that process hosts the messaging gateway; P4) and `seam: true|false`. The 0600 socket sits next
to it.

**Lease registry (Hermes, read-only to intercom):** `runtime/active_sessions.json`, one entry per
live session, with `session_id`, `surface` and `pid` (`hermes_cli/active_sessions.py:461-480`).
CLI and `tui_gateway` key it by the stored session id; the gateway keys it by the gateway
session key, and only while a turn runs.

**The record:** a SQLite file under `<hermes-home>/plugin-data/intercom/`, 0600, WAL, with short
write transactions. One row per mail; replies are mails with `in_reply_to`.

| Field | Meaning |
|---|---|
| `id`, `in_reply_to`, `reply_mail_id` | Short hex id (in the header); the mail answered; the reply's own row |
| `kind` | `send` or `ask`. Automatic replies apply only to `send` (SM-Q16 a) |
| `sender_session_id`, `sender_title`, `sender_source` | From the handler's `session_id` keyword, never model input. A CLI sender stores its `--from` label (default `cli`) |
| `target_session_id`, `target_title`, `address`, `host` | What was asked; the compression tip it resolved to; `pid:<n>`, `gateway`, `wake` or `in-process` |
| `body`, `expect_reply` | The text before framing; `true` by default (`false` from `expect_reply: false` / `--no-reply`; replies are `false` and labelled "reply optional") |
| `requested`, `applied`, `applied_detail` | `interrupt`/`steer`/`queue`; `interrupt`/`steer`/`queue`/`start`; for example `redirect` or `hard-interrupt` |
| `result`, `detail` | Empty while in flight; then `delivered`, `refused` or `error`. `detail` holds the reason, the candidates, or an error code: `not-reachable`, `delivery-unknown`, `no-endpoint`, `no-seam`, `no-dashboard`, `no-gateway`, or a host code |
| `reply`, `reply_state` | The captured reply; `stored`, `silent`, or empty |
| `created_at`, `delivered_at`, `replied_at` | Timestamps |

The row is written **before** routing. A fast target can finish and fire its hook before the
sender's receipt returns. There is no hop column, no status ladder and no retry count.

### Trust boundaries (HLD grain; the LLD details them for security)

| Boundary | Crossing | Rule |
|---|---|---|
| **B1: process to process over intercom's socket** | A sender connects to a host's `0600` Unix socket | Kept from intercom: the peer-UID check refuses other users (`intercom:inbox.py:545-569`); there is no TCP listener. Every sender already runs as the Hermes user. |
| **B2: process to dashboard, loopback WebSocket with the agent key** (wake path only, fork only) | P5 reads the existing key file and connects to 127.0.0.1 | No new credential and no new surface. The key already grants operator power. The URL is an intercom setting in `config.yaml`, not a `HERMES_*` variable. |
| **B3: model-written text becomes a user row in another session** | Every body and reply is another model's output | Attributed and inert (D2). The sender comes from the session, never from model input. **Relabel** every body line starting with `📡`, and every Hermes control-frame opener, the way hosted rooms do (`gateway/hosted_room_discussion.py:39-48`; required by Trial Q2). Intercom's existing defence breaks only `📡 INTERCOM`, which no longer matches its own `📡 hermes@` header (`intercom:inbox.py:154-181`), so it is replaced. Never `display_kind: "hidden"`. |
| **B4: the messaging gateway** | (a) Mail now steers or interrupts a gateway turn. Today internal events always queue, because "plugin events carry untrusted payload text" (`gateway/run_busy.py:843-849`). (b) Text a platform user typed can become mail from that session to Alex's other sessions. (c) SM-Q15 posts mail into a chat | (a) Only with the plugin's `allow_gateway_injection: true`, and still with `allow_gateway_control=False`: no slash commands, approvals or bang input. (b) The header names the sender session and its source (for example `telegram`), and the authority line applies. (c) Is a data-class question for security at Spec: mail from other sessions posted into a group chat leaves the machine (O7). |
| **B5: identity** | `act_as` credits agent-key turns to Alex | The sender is named in the header and the record. |
| **B6: profile** | Socket serve threads and reply threads run outside a turn | They bind the plugin manager's profile (`propagate_context_to_thread`, or the manager's `home_path` scope). The registry and the record live under that profile's `HERMES_HOME`. A dashboard that serves several profiles delivers through its socket only to sessions of the profile that loaded intercom; others are refused (`no-endpoint`). Cross-profile is out of scope (O14). |

### D1: the core seam

```python
ctx.inject_message(content, role="user", *, session_key=None, origin=None,
                   mode=None)   # mode: None | "interrupt" | "steer" | "queue"
```

- **Trial round 2 (R1):** all three modes and the idle start were observed on the dashboard, classic-CLI and gateway hosts. The stand-in reused each host's own typed-input or busy-submit logic. Every v0.22 agent reports `_supports_active_turn_redirect` (`agent/agent_init.py:544`), so `interrupt` normally applies as **redirect**; the hard-interrupt fallback is for media payloads and older agents (`poc/round2/poc.md`).
- `mode=None` keeps today's behaviour exactly, so existing plugins see no change (the plugin
  compatibility contract).
- With a mode, every host applies the **strongest supported mode at or below the request**
  (interrupt > steer > queue), and an idle session starts a turn.
- It returns a result that is truthy when a host accepted. Its fields are `applied`
  (`interrupt`/`steer`/`queue`/`start`), `detail` (`redirect` / `hard-interrupt`) and `reason`
  when refused.

| Host | `interrupt` | `steer` | `queue` | Idle | Change |
|---|---|---|---|---|---|
| **`tui_gateway`** (dashboard, desktop, Ink TUI) | `_handle_busy_submit` in interrupt mode: redirect when `_supports_active_turn_redirect`, else queue then a hard interrupt | `agent.steer`; refused → queue | Queued submit, **with the accept-time row** | Starts a turn (drain) | `_handle_busy_submit` takes an explicit `mode` (today only config or `queued`, `tui_gateway/session_auto_continue.py:400-455`), and the injector calls it instead of the bare `_enqueue_prompt`. Compression keeps demoting to queue, reported as applied `queue`. A lazy or closing session returns "not hosted", so the sender falls through to the wake path. |
| **Classic CLI** | `agent.redirect` when supported, else `_interrupt_queue` (hard interrupt, message runs next) | `agent.steer`; refused → `_pending_input` | `_pending_input` | `_pending_input` starts a turn | `inject_message` goes through the typed-input routine (`hermes_cli/cli_tui_mixin.py:1505-1551`) with the mode passed in, instead of `busy_input_mode`, and returns the applied mode. Today's "busy → always `_interrupt_queue`" (`plugins_injection.py:19-23`) applies only to `mode=None`. |
| **Messaging gateway** | `_resolve_busy_steer_or_redirect`, then `_interrupt_running_agent_for_busy_event` | Same resolver | FIFO `_queue_or_replace_pending_event` | A new turn in the chat | An injected event carries `delivery_mode`. The internal-event branch (`run_busy.py:843-849`) honours it only for plugin injections that set it, still with `allow_gateway_control=False`. Without a mode, internal events keep queueing. |

| Seam option | For | Against | Chosen |
|---|---|---|---|
| **`mode=` on `inject_message`, fallback in the host, applied mode returned** | One small, additive change; each host already has the three behaviours for typed input; feature-detectable; the same shape as closed #83661, but narrower | The return type grows from `bool` to a truthy result object | **Yes** |
| #83661's full shape (`mode` + `target_session` + `on_session_open` + slash-command context) | Upstream already saw it | Several surfaces nobody here needs; its author closed it | No |
| A new `ctx.deliver_message()` method | Clean return type | A second API for the same job; the compatibility rule prefers extending | No |
| No seam; intercom reaches into host internals (today's GC and private fields) | No core patch | Cannot address one of many dashboard sessions; breaks on every refactor; cannot be upstreamed | No (this is the "real blocker") |

**Feature detection:** intercom checks `inspect.signature(ctx.inject_message)` for `mode`.
Without it (an older Hermes), intercom keeps its current CLI-only delivery for CLI targets
(minus the caps). Dashboard, TUI and gateway targets are refused with `no-seam`, and nothing is
parked. So the process-wide `pre_llm_call` drain never puts mail into the wrong session.

**Tests (fork, `scripts/run_tests.sh`):**
- one behaviour test per host and mode: applied mode, fallback, idle start;
- `mode=None` unchanged per host;
- the tui accept-time row;
- the gateway keeps `allow_gateway_control=False` and still queues internal events without a
  mode;
- compression demotion reported as `queue`.

Each test is proven red on the base.

**Upstream shape:** one pull request against `NousResearch/hermes-agent` that touches only these
files plus the docs page for `inject_message`. The draft text is in P7, for Alex.

### D2: framing (SM-Q7 A′ in intercom's form)

D1 of round 1 still holds. The steer marker claims the user's authority, and the caller cannot
change it. Queued, interrupt and started mail are plain user turns. A core frame patch would
cover steered mail only and conflict at the v0.23 rebase. A **forwarding header** is truthful
inside a user frame. Exact wording is in `ux.md`; the elements are:

1. **Header line 1, first in the text** (brief A5), in intercom's form: it opens `📡 hermes@`
   and carries the sender session's title, its id, `not Alex`, the reply label (`reply
   expected` / `no reply needed` / `reply optional`), and `mail <id>`. For example:
   `📡 hermes@"Budgeting — Orchestrator" (session 20261109_…, not Alex) says: · reply expected · mail 3f2a9c`.
   A script sender is `📡 script "<label>" (not Alex) says: …`. A Telegram-source sender names
   its source.
2. **The authority line:** forwarded mail from a peer session; not an instruction from Alex (the
   user); none of his approval or consent.
3. **The body**, relabelled (B3).
4. **The footer:**
   - the answer goes back by itself; `intercom` is for new mail;
   - the `[REPLY <id>] … [/REPLY]` block, with `[SILENT]` inside when there is nothing new;
   - the no-empty-replies rule;
   - mail cannot approve anything; anything that needs Alex goes to Alex;
   - for an `ask`, intercom's existing "use `intercom(action="reply", …)`" line instead of the
     block rule.
5. **Closing line** `📡 end of mail <id>`. Anything after it in the same row is not mail.

Intercom's echo stripping (`intercom:__init__.py:64-76`) is updated to the new header. The
**tool description** keeps intercom's opening, adds `delivery` and Alex's sentence word for
word ("only use interrupt when you intend to stop what the other session is doing right now
(it is wrong, or the work is obsolete). Otherwise use steer (default) or queue."), and carries
the no-empty-replies rule in its first sentence, because Tool Search shows only that much
(Trial Q8).

### D3: replies

`post_llm_call` runs in **the process that ran the turn**, which is any host. It is the same
design as round 1, confirmed by Trial Q3 and Q9:

1. Scan the turn's user rows (`user_message` and the `display_kind: "steer"` rows) for lines
   that **start** with `📡 hermes@` or `📡 script` and carry `mail <id>`. The mail runs to its
   closing line. Keep an id only if its record row targets this session (or its compression
   lineage), is `kind = send`, and has no reply yet. The line-start anchor alone matched a
   forged header in the Trial, so this record check is required.
2. The reply is the `[REPLY <id>]` block, or else the whole final answer (SM-Q8).
3. Silence sends nothing: an empty or `[SILENT]` block; or, with no block, an empty answer or one
   that is `[SILENT]` read as cron reads it (whole answer, or its first or last line).
4. Store the reply, then deliver it from a short-lived thread, bound to the profile, by the same
   route with `delivery = steer`. Its result goes on the reply's own row.
5. SM-Q9 (b): senders whose source is `cron`, `subagent` or `oneshot`, and CLI senders, get
   storage only. Every other sender is woken, including `cli`-source owner sessions with a
   closed terminal, and `telegram` senders in their topic.

A turn that was stopped or failed fires no hook, so nothing is sent (Trial Q9). A debate runs
until one side writes `[SILENT]`; nothing counts rounds. `ask` keeps intercom's explicit
`reply` and its in-memory waiter (SM-Q16 a).

### D4: routing, the receipt and the CLI

**Routing**, first match wins:

| Step | Test | Delivered by |
|---|---|---|
| 0 | Target is the sender's own session | Refused (`self`). Intercom refused the whole **process**; now only the session is refused, so two dashboard chats can mail each other |
| 1 | A live lease for the stored id in `runtime/active_sessions.json` | Its `pid`. If that is the sender's own pid, P1 is called in-process. Otherwise intercom connects to the socket registered for that pid. A pid with no intercom entry (a process started before the deploy) → `error no-endpoint`: "it receives mail after its next start". **Trial R2/R3:** a lease exists only after the session's **first turn** in that process (dashboard and CLI alike). A lazy-resumed or never-run session has none and goes to step 3, as does a host that answers "not hosted" (lazy or closing) |
| 2 | No lease, and the session's source is a messaging platform or it has a `gateway_routing` row | The registry entry with role `gateway`, which calls `lookup_by_session_id` and then P1 with that session key. No running gateway → `error no-gateway`. It never falls through to the dashboard, which would answer outside the chat |
| 3 | Live nowhere | P5 wake (fork): resume, then submit, then wait for the start. Requested `interrupt`/`steer` on an idle session applies `start`. No dashboard → `error no-dashboard`. Upstream intercom without P5 returns intercom's "no live peer" |

A gateway turn's lease is keyed by the gateway session key, so step 1 never matches it; step 2
handles it.

| Routing option | For | Against | Chosen |
|---|---|---|---|
| **Lease `pid` → per-process socket** | Hermes already keeps "at most one live owner" per session; intercom keeps one entry per process; nothing to sync on compression or reaping | Gateway idle sessions need step 2 | **Yes** (Refine round 4) |
| One intercom entry per live session | Direct lookup | Must track every park, unpark and compression | No |
| Outbox as a bus with a poller per process | No sockets | A worker and polling; superseded by Alex's base | No |

**Exactly once:** only the process named by the lease (or the gateway) delivers (brief A8).

**Timeouts, not caps:**
- Intercom's 5-second exchange timeout becomes long enough for a host to accept (Spec sets it;
  acceptance does not wait for a turn).
- A timeout after the request was sent is `delivery-unknown`.
- The wake path keeps P5's limits: 60 seconds per RPC and a 240-second start wait. So the tool
  handler stays synchronous with its own short loop on a fresh thread (round-1 D4; Trial Q7).

**Receipt** (tool JSON, intercom style): `ok`, `receipt` (intercom's `delivered` / `held` /
`refused`; `held` now means queued), `mail`, `to` (title and id), `requested`, `applied`,
`applied_detail`, and a `message` sentence (wording in `ux.md`). Every result is final.

**CLI** (`register_cli_command`, as `plugins/model-routing/__init__.py` does):
`hermes intercom send|status|list`, with the round-4 output and exit codes.

| Exit code | Meaning |
|---|---|
| 0 | Delivered |
| 1 | `status`: no such id |
| 2 | Usage error |
| 3 | Refused (address, empty body, self) |
| 4 | The host refused, or `no-seam` |
| 5 | `not-reachable`, `no-endpoint`, `no-gateway` or `no-dashboard` |
| 6 | `delivery-unknown` |

`status` keeps its **read-only** transcript check (it opens `state.db` read-only and matches the
header anchor). `list` joins reply rows.

### D5: addressing (unchanged from round 1)

- An exact title or `Home`.
- A session id or id prefix.
- `@<project-slug>`: DER-686's `owner_session_id` when that column exists and is set, else the
  exact title `<name> — Orchestrator`.
- An **intercom endpoint name** (kept for compatibility; it maps to that process's single CLI
  session, or is refused as ambiguous for a multi-session process).

The result always resolves to the compression tip. An ambiguous match is refused, with the
candidates. The switch-over to DER-686 is by column presence, with no flag.

### D6: the gateway host (build step 2)

| Item | Decision |
|---|---|
| **Endpoint role** | The gateway publishes its message host after its adapters start (`gateway/run_startup.py:1654`), later than `inbox.start()`. So intercom checks `manager.has_gateway_message_injector` (`hermes_cli/plugins.py:1242`) when it refreshes its registry entry, and sets `roles: [gateway]`. One pid can be both a dashboard and a gateway. |
| **Routing** | `lookup_by_session_id` (`gateway/session.py:1311-1317`), then P1 with `session_key` and the mode |
| **Silence** | **Settled by Trial R4.** Injected gateway turns are stored as `internal_notification`, so a bare `[SILENT]` answer is not posted to the chat (`gateway/response_filters.py:19-34`), while normal answers are |
| **SM-Q15 (b)** | Before the turn starts, one adapter send posts the header and body into the target's chat or topic. It needs security's view first (B4c, O7) |
| **Bot-loop guard** | It counts bot-authored sources only; injection reuses the chat's human source (`gateway/authz_mixin.py:600-612`). It is not a cap |

### D7: deploy (SM-Q14, answered: subtree vendoring)

1. **Code:**
   - The seam (P1) and the wake module (P5) land on alexderz/hermes-agent's
     `integrate/session-mail`.
   - Intercom changes land on alexderz/hermes-intercom's `integrate/session-mail` and are
     vendored into hermes-agent as `plugins/intercom` with `git subtree add/pull --prefix
     plugins/intercom` (no `--squash`, so authorship survives).
   - hermes-agent's project-main is fast-forwarded into `alex/v0.22.0-mobile-fixes`, then
     `git pull --ff-only` in the install (rule 19). There are no side repos and no symlinks
     into `<hermes-home>/plugins`.
2. **Enable through house-infra** (`hosts/<dashboard-host>/hermes.py`): `plugins.enabled` gains
   `intercom`, plus `plugins.entries.intercom.allow_gateway_injection: true` and the dashboard
   URL setting if the port is not the default.
3. **Restarts:**

| Process | Restart | Why |
|---|---|---|
| Dashboard | **Yes, once, announced**; list busy sessions first. It cuts the phone off and kills running owner turns | It hosts most targets and must load intercom and the seam |
| Messaging gateway | **Yes** (it does not cut the phone off) | It hosts gateway targets (build step 2); without it, step 2 returns `no-gateway` |
| CLI / TUI processes | At their next start | Until then their sessions return `no-endpoint` (D4 step 1) |

4. **Cost:** with Tool Search on (the default), `intercom` is deferred, so there is no
   cache miss but pre-deploy sessions are not told it exists (Trial Q8). With it off, there is
   one miss per resumed session (O12).
5. **Relay skills:** the manager replaces the dispatcher command with an `intercom` line at
   deploy. This is a skill-text change, not product code.
6. **Share the restart with DER-686** when both are ready.
7. **Rollback:** remove the enable and restart, or revert the fast-forward. The record file
   stays.

### Host build order

1. **`tui_gateway` (dashboard, desktop, Ink TUI) and classic CLI:**
   - P1 for those two hosts;
   - P2 (lease routing, many sessions per process, seam delivery, caps out, A′ frame);
   - P3 (addressing, modes, record, replies, CLI);
   - P5 (wake).

   This covers the owner sessions, `Home`, dashboard chats, desktop and terminals.
2. **Messaging gateway:**
   - P1's gateway path;
   - P4 (endpoint role, `lookup_by_session_id` routing, silence, SM-Q15).

   It comes second because the live install has no gateway sessions, and because it carries
   the B4 security question.
3. **Upstream drafts (P7)** for Alex: the #81885 update, an intercom pull request, the seam pull
   request.

| Order option | For | Against | Chosen |
|---|---|---|---|
| **tui_gateway + CLI → gateway → drafts** | The most-used targets first; the gateway's security question is reviewed with a working base | Telegram later | **Yes** (brief, Refine round 4) |
| All hosts at once | One deploy | The largest diff before any proof; the gateway has no live sessions to try | No |

## Persistence

| What | Where | Durable? |
|---|---|---|
| The record | `<hermes-home>/plugin-data/intercom/` SQLite, 0600, WAL | Yes; never pruned in v1 |
| Intercom registry and sockets | `<hermes-home>/intercom/sessions/` | Per process; dead pids swept on read |
| Session leases | `runtime/active_sessions.json` (Hermes) | Per live session; read only |
| Mail as the target saw it | The target's transcript in `state.db` (tui accept-time row; steer row) | Yes |
| Queued mail not yet run | The host's queue: tui prompt queue, CLI `_pending_input`, gateway FIFO | **No.** It is lost on a restart, on a process exit, or when a quiet detached dashboard turn is reaped (Trial Q1). The record shows "delivered, no reply" |
| Intercom's spool | Only on the no-seam CLI fallback | As today |
| A reply in flight | The reply thread's memory | No; the reply row shows no result |
| Settings | `config.yaml` `plugins.entries.intercom` (house-infra) | Yes |
| Design | git `docs/session-mail/`; upstream drafts in intercom `docs/` | Yes |

## Worker rules

- **Who:** builders on item branches in each repo (`chunk.md`). Grok 4.7 through SuperGrok, or
  Claude Opus for P1 and P2. Reviewers are fresh Claude Code sessions.
- **Intercom work is in intercom's style:** module layout, docstrings, `tests/test_protocol.py`
  conventions. Its 17 tests keep passing, except those asserting a removed cap, which change
  with the cap.
- **Hermes work:** `scripts/run_tests.sh`, a temporary `HERMES_HOME`, behaviour-contract tests
  proven red on the base, the code-health ratchet, and no `HERMES_*` variables for behaviour.
- **HITL (Alex):** SM-Q7 to SM-Q11, SM-Q14, SM-Q15, SM-Q16; the restart window; the exact
  upstream text. The manager makes the relay-skill edit.
- **Workers must not:**
  - add caps, holds, retries, timers, gates or a worker;
  - use the GC lookup or private fields where the seam exists;
  - park mail for a session other than the addressed one;
  - set `display_kind: "hidden"`;
  - take the sender from model input;
  - put plugin-specific logic in core (P1 stays generic);
  - post to GitHub;
  - touch the live install or restart anything;
  - write to Linear.

## Open

SM-Q17 (Plan acceptance) answered by Alex on 2026-11-10: accepted. The LLD follows `ux.md` where it differs from this HLD (see the LLD's opening note).

| # | Item | If the answer differs |
|---|---|---|
| O1 | **SM-Q7 answered (Alex, 2026-11-10): A′.** The intercom header names the sender session, says "not Alex", and carries one authority line. No core frame patch | — |
| O2 | **SM-Q8 answered (2026-11-10): option 2.** A `[REPLY <id>]` block, with the whole answer as fallback | — |
| O3 | **SM-Q9 answered (2026-11-10): (b).** Replies to `cron`, `oneshot` and `subagent` senders are stored only | — |
| O4 | **SM-Q10 answered (2026-11-10):** rename "Model Master" to "Model Testing — Orchestrator" at deploy (a step, not code) | — |
| O5 | **SM-Q11 answered (2026-11-10):** the phone look is accepted for v1 | — |
| O6 | **SM-Q14 answered (Alex, 2026-11-10):** vendor with `git subtree` as `plugins/intercom`; `alexderz/hermes-intercom` stays the repo shared upstream. Alternatives kept for the record: | A **git submodule**: the install checkout needs `--recurse-submodules`, and the pull and deploy steps change. **Installing from the intercom repo** as a user plugin breaks rule 19 (a side repo). Either way P1 and P5 stay in hermes-agent |
| O7 | **SM-Q15 answered (2026-11-10): (b),** with security's data-class rule (LLD TB-5, F1). Echo only to `private` chats (listed in `echo_chats`, or a DM with an owner user id); shared chats get a model-only shared-chat line, and replies to shared-chat senders send only an explicit `[REPLY]` block | — |
| O8 | **SM-Q16 answered (2026-11-10): (a).** `ask`/`reply` unchanged; automatic replies for `send` only | — |
| O9 | **Seam upstream shape:** the truthy result object, and whether upstream wants steering of plugin events in the gateway behind a separate consent key | A separate key adds one config line, set by house-infra |
| O10 | **Gateway endpoint role timing:** `has_gateway_message_injector` checked at refresh | If the signal is unreliable, the gateway runner would need to announce itself, which is a core hook |
| O11 | **Relay skills:** settled; the manager edits them at deploy | — |
| O12 | **The live `tools.tool_search` setting** decides the cache cost | — |
| O13 | **Real models and the header inside the steer frame** (reopen trigger for C) | — |
| O14 | **Multi-profile dashboard:** the socket serves the profile that loaded intercom; other profiles' sessions get `no-endpoint` | Serving every profile from one socket is cross-profile scope, so it would need a decision |
| O15 | **One restart shared with DER-686** | — |
| O16 | **v0.23 rebase:** miyu4u's unified-gateway transport may replace the socket lookup for tui sessions; P1 must be re-applied on v0.23's injection code | — |
| O17 | **Retracted (LLD, 2026-11-10).** The "queued prompt written twice" finding was wrong. The drain deactivates the accept-time row (`tui_gateway/session_auto_continue.py:350-375`): in round 2, run 3, the early row is `active=0` and the replacement `active=1`. Transcript readers use `active = 1 OR compacted = 1` (`hermes_state_common.py:640-682`), so a queued message shows once. No fix item | — |
| O18 | **A CLI with a session open but no turn yet has no lease** (Trial R2: the lease appears at the first turn). Mail to it goes to step 3, so the dashboard would resume that session while the CLI has it open, and the CLI's next turn could then be refused 4090 | Proposed: accept for v1 (rare: the session must already exist and be idle in a fresh CLI); Spec checks whether the CLI writes its lease at resume |

## PoC questions (Trial round 2)

**Ran 2026-11-09:** `poc/round2/poc.md`. Run 3 passed 23 of 24 (one harness miss, rerun); run 4 (CLI) passed 9 of 9. R1, R2, R3, R4 (apart from the `/compress` lookup and the SM-Q15 post), R5, R6 (CLI and gateway), R7 and R9 pass. R8, R10, R11 and the Ink TUI host were not run. The design changes are in D1, D4, D6 and O17–O18.

The first Trial (`poc/poc.md`) covered the dashboard WebSocket path, framing, the reply hook,
the reaper, a CLI-held session's 4090, Tool Search and debates. The new shape needs these
answered. They are not run in this pass.

Setup: the same as the first Trial (a temporary `HERMES_HOME`, a gated dashboard on a free
loopback port, a fake model), plus the seam branch, the intercom branch copied into the temp
home, a classic CLI process, an Ink TUI backend process, and a messaging gateway with a
throwaway platform-adapter plugin in the temp home, modelled on `plugins/platforms/irc` and
recording what it sends. The built-in webhook adapter is the fallback.

| # | Question | Pass looks like |
|---|---|---|
| R1 | **The seam's three modes on each host** (tui_gateway, classic CLI, gateway): `interrupt` (redirect vs a hard interrupt), `steer`, `queue`, and an idle start; the applied mode returned; `mode=None` unchanged | Each cell of D1's table is observed, and the tui path writes the accept-time row |
| R2 | **A classic CLI session receives mail through intercom's socket and the seam**, with no GC lookup: `steer` lands without interrupting; `interrupt` redirects; `queue` waits | Yes, with the applied mode in the receipt |
| R3 | **One dashboard process, several sessions, one socket:** routing by lease `pid`; mail to chat A never lands in B; two chats in one process mail each other in-process; a lazy session falls through to the wake path | No cross-delivery; in-process delivery works |
| R4 | **Gateway sessions in the trial home**, with the fake adapter: idle → a new turn in the chat; busy → steer with `allow_gateway_control=False`; a bare `[SILENT]` is not posted; `lookup_by_session_id` after `/compress`; the endpoint role set after the gateway's host is published; the SM-Q15 post | Each one observed. The answer and the posted header appear in the adapter's recorded sends |
| R5 | **Exactly once across hosts:** with a CLI, a dashboard and a gateway running, each mail is delivered once, by the right process; a process without intercom returns `no-endpoint` | One delivery per mail, with the right error |
| R6 | **Replies from each host's `post_llm_call`** (CLI, Ink TUI, gateway) back to a sender on another host, including a steered mail | One reply per mail, to the right sender |
| R7 | **Wake path from a non-dashboard sender** (a CLI process) through P5; with the dashboard stopped, `no-dashboard`; a gateway-source target with no gateway, `no-gateway` | As stated, with no fall-through to the dashboard for gateway targets |
| R8 | **No-seam behaviour:** intercom on a build without `mode` keeps CLI delivery and refuses other hosts with `no-seam`, parking nothing | Nothing parked; clear errors |
| R9 | **Intercom's own tests** on our branch | 17 pass, apart from the changed cap tests |
| R10 | **A dashboard serving two profiles:** mail for the second profile's session is refused, and nothing leaks across homes | `no-endpoint`; files only under the first profile's home |
| R11 | **Interrupt on a dashboard compute-host turn** (`dashboard.turn_isolation` on), optional | Redirect or a hard interrupt reported correctly |

## Risks

- **`interrupt` misused** by a model: it would stop Alex's or an orchestrator's work. Mitigated
  by Alex's sentence in the description and the default `steer`. No gate (decision 3).
- **Untrusted gateway text** becoming mail that steers Alex's sessions (B4b). Mitigated by the
  sender's source in the header and the authority line; security review at Spec.
- **Pre-deploy processes** cannot receive mail until restarted (`no-endpoint`).
- **Queued mail lost** on restart, process exit or reaper (Persistence). It is visible in the
  record.
- **Two repos and a subtree:** drift between `plugins/intercom` and alexderz/hermes-intercom if
  a fix lands in only one. Rule: intercom changes land in alexderz/hermes-intercom first, then
  `git subtree pull`.
