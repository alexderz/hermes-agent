# Brief: session-mail (DER-701), session-to-session messaging

Step: Brief (gatherer), round 5, after two more decisions from Alex. Date: 2026-11-09.

Source dump: the request `requests/2026-11-09-session-mail-brief.md` in the Hermes Improvement vault. It holds Alex's words, settled decisions 1–8, and three later sections:
- "Scope addition (Alex, 2026-11-09 ~19:45)";
- "Delivery modes (Alex, 2026-11-09 ~19:50)";
- "Build on intercom, not a new plugin (Alex, 2026-11-09 ~20:00)".

Also read: the research note `research/session-messaging.md`, and vault rule 19. The chunk keeps its working name "session-mail" (DER-701); the shipped plugin is `intercom`.

**Round 5 changes:**
- **Base = intercom (Alex; answers SM-Q12 with a fourth option, supersedes decision 1's "new plugin").** Our features land in the code of `alexderz/hermes-intercom`, a fork of `majordave/hermes-intercom`, on a feature branch, in its style. The plugin name `intercom` and the `intercom` tool stay; there is no `session-mail` plugin and no `session_message` tool. Intercom's transport is kept where it fits. Its garbage-collector lookup of the CLI object and its private-field delivery are replaced by the core seam where that is available.
- **Delivery modes (Alex; supersede "never cancel or redirect" in decision 3):**
  - `delivery: interrupt | steer | queue`, default `steer`;
  - each host applies the requested mode, or the strongest weaker one it supports (interrupt > steer > queue);
  - an idle target always starts a turn;
  - the outbox records the requested and the applied mode, and the receipt names the applied mode.

  The seam becomes `inject_message(..., mode="interrupt"|"steer"|"queue")` with that fallback on every host.
- **New facts:** intercom read in full (socket, registry, UID check, delivery, frame, ask and reply, spool, caps) and mapped onto our requirements; the `miyu4u/hermes-intercom` fork and the v0.23 APIs it needs; a per-host table of what interrupt, steer and queue mean today.
- **Questions:**
  - SM-Q12 is answered (intercom), and SM-Q14 is recorded as asked elsewhere (deploy method);
  - the round-4 Telegram question is renumbered **SM-Q15**;
  - new **SM-Q16**: what happens to intercom's blocking `ask` and its explicit `reply` next to automatic replies;
  - SM-Q7 to SM-Q11 are re-checked against the new base.

**Superseded in round 5** (kept below as the record, marked where they appear):
- the `plugins/session-mail` plugin and the `session_message` tool name;
- the outbox as the bus between processes, with a poller in each one: intercom's per-process sockets carry mail instead, and the outbox stays as the durable record;
- "never cancel or redirect";
- the seam shape `mode="steer_or_queue"`.

Where the code facts come from:
- this worktree (branch `integrate/session-mail`, v0.22.0 plus fork patches, now including `alex/v0.22.0-mobile-fixes` up to `c843eea710`: the dispatch fix `1516a52669` and the queue-aware reapers `8d4597bf8e` and `1ec78a0dcc`);
- tag `v0.23.0`, and `upstream/main` at `b3746e35dd` (2026-11-09);
- upstream pull requests #106423, #136861 and #123218 (read-only, with `gh pr diff` and `git show cff14a4c62`), the fork pull request linked from #136861's comments, and issues #81885 and #103748;
- a clone of Hermes Mobile at upstream head `d426349` (2026-11-09).

Paths without a prefix are relative to the Hermes repository root. Hermes Mobile paths are relative to `app/src/main/java/com/m57/hermescontrol/` in that clone. Paths inside upstream pull requests are given as `#<PR>: <path>:<line>`.

**Round 4 changes:**
- **Scope widened (Alex).** Mail must reach every kind of session: the dashboard and desktop, the terminal (classic CLI and Ink TUI, each its own process), and messaging-gateway sessions (Telegram topics and other platforms). The design becomes a full answer to upstream issue #81885, to be offered upstream later; Alex reviews the text first.
- **Superseded:**
  - **"Delivery inside the dashboard only."** Each host now delivers mail itself (decision 3 is widened below).
  - **"Delivery at send time over the dashboard socket"** (round 2). Replaced by an outbox read by a light poller in every process. The dashboard socket path stays only for sessions that are live nowhere.
  - **"No core patch."** The scope addition invokes decision 1's "real blocker" exception for one small seam.
- **New facts:**
  - how each host handles injected text today;
  - the session registry `runtime/active_sessions.json`;
  - gateway sessions;
  - finding 2 after the reaper fixes;
  - upstream peer messaging (#106423 and the work built on it).
- **Questions:** new SM-Q12 (build on our own protocol or on upstream's) and SM-Q14 (show mail in the Telegram topic; renumbered to SM-Q15 in round 5). SM-Q13 is recorded as answered. SM-Q7, SM-Q9 and SM-Q11 are updated for the wider scope.

Round 3 changes: SM-Q9 option (b) now tests the sender's session source instead of its end reason; the `agent_close` fact is corrected and `cron_incomplete_no_output` added; the `session_message` tool handler is synchronous (Constraints).

Round 2 changes:
- A dashboard-only delivery worker is replaced by **delivery at send time**.
- Redelivery is dropped.
- SM-Q7 now recommends the header-only option.
- SM-Q9 is narrowed, and its "ended" test is checked against the code.
- SM-Q11 drops the Mobile issue draft.
- The outbox fields are simplified.
- New facts: how the dispatcher is invoked today; the threading for send-time delivery; how a resumed session's tool list is built.

## Reflect (the dump, restated)

Alex wants Hermes sessions to message each other. A session or a script sends mail to another session, addressed by project, title, id or `Home`. The mail lands at once inside the dashboard: it steers into a running turn, queues behind it if steering is refused, and starts a turn if the session is idle. It never cancels or redirects work, and it is never held back while Alex is active.

The target's final answer goes back to the sender by the same rule, so two sessions can debate with no caps of any kind. A debate ends because every session is told never to send an empty reply, and to end with `[SILENT]` when it has nothing new.

A durable outbox records who sent what. The sender is named in the text, because agent-key turns are credited to the operator. A CLI sends mail from cron jobs and scripts. It all ships as a plugin bundled in Alex's fork.

Round 4: the same rules now apply to every kind of session Hermes runs, not only the dashboard's. That covers a terminal session in its own process, and a Telegram topic served by the messaging gateway. Each process delivers to the sessions it hosts. A session that is live nowhere is woken in the dashboard; an idle gateway session is woken by the gateway, so the reply shows in its chat. This needs one small, upstreamable change in the core: a delivery mode for the plugin injection call that every host honours.

Still vague, and handled below:
- which text counts as "the target's final answer" when one turn holds Alex's prompt plus one or more mails;
- where a reply goes when the sender's session has finished for good;
- how `@<project-slug>` resolves for a project whose owner does not follow the title convention.

## Intent

1. Any session, cron job or script can send mail to one named session, of any kind: dashboard or desktop, classic CLI, Ink TUI, or a messaging-gateway chat (Telegram topics and other platforms). It is delivered right away by whichever process hosts the target. A session that is live nowhere is woken in the dashboard, so Alex can watch and steer it from the phone. An idle gateway session is woken in its own chat. *(Round 4; round 1 said "inside the dashboard".)*
2. The receiving session can tell mail from Alex's own words, and treats mail as a message from a peer. This is best effort on every delivery path (see SM-Q7).
3. Replies come back automatically, so an orchestrator can delegate and act on the answer, and two sessions can argue a point until one has nothing new to add.
4. Every message is recorded: sender, target, body, delivery result and the reply.
5. *(Round 4.)* The result answers upstream issue #81885 for terminal and gateway sessions, so it can be offered upstream. Alex reviews any upstream text first.

## Out of scope

- Agent Tincan, relays, and agents on other machines or in other products (SM-Q6, "maybe later").
- Any limit, hold, cap, rate limit, duplicate filter, approval gate, retry or give-up timer (settled decisions 3 and 5; round 2).
- ~~A background delivery worker~~ *(superseded in round 4: a light poller per process is back; see "Why a per-process poller again")*. Redelivery of mail that was lost after a handover is still out (round 2).
- Bot Mode, hosted rooms, and one profile per agent (rejected in the research). *(Round 4, SM-Q13: the default profile's `Bot Chat` session is in scope as an ordinary target; bots in other profiles are not.)*
- Messaging across profiles, including bots in other profiles (SM-Q13). The plugin serves the default profile's sessions.
- Posting anything to GitHub. The upstream offer on #81885 is a later step, with Alex reviewing the text. *(Round 5)* That also covers a possible pull request to `majordave/hermes-intercom` and the seam's own upstream pull request. Agents draft them into `docs/` on the intercom feature branch, Alex reviews the exact text, and agents never post them.
- *(Round 5)* The v0.23 unified-gateway transport from `miyu4u/hermes-intercom` (`gateway_peers.py`). Its APIs do not exist on v0.22.0; it is prior art for the v0.23 rebase.
- Changes to Hermes Mobile, including drafting an upstream issue for it in this chunk (that can be offered after the plugin runs).
- A core patch for the steer frame (SM-Q7 option C, dropped from this chunk).
- A "Mail" tab on the dashboard, and a plugin system-prompt section.
- Landing DER-686's `projects.owner_session_id`. This chunk only reads it once it exists.

## Constraints

- **The intercom plugin (our fork), plus one small, upstreamable core seam** *(round 4, reshaped in round 5)*. Decision 1 allows a core patch when a real blocker is shown and Alex agrees. The scope addition shows one: no host can steer or wake through the plugin API (see "How each host handles injected text today").
  - The seam is `ctx.inject_message(..., mode="interrupt"|"steer"|"queue")`, honoured by the CLI, gateway and TUI/dashboard hosts, each falling back to the strongest weaker mode it supports. The round-4 shape `mode="steer_or_queue"` is superseded.
  - It is a small fork patch on Alex's Hermes fork, listed in PROJECT.md, kept upstreamable.
  - The plugin feature-detects the seam. Without it, the plugin falls back to intercom's current delivery, which is limited to the classic CLI.
  - Round 1 said "no core patch"; that is superseded.
- *(Round 5)* **Work lands in intercom's code and style.** That means intercom's tests (17 today, `tests/test_protocol.py`), its single multiplexed `intercom` tool, and its MIT licence. The fork is shared upstream as `alexderz/hermes-intercom`. How it reaches the Hermes install (vendored as `plugins/intercom` with `git subtree`, keeping rule 19) is **SM-Q14, asked elsewhere**.
- ~~**The steer/queue fix is not on this branch yet.**~~ *Resolved in round 4:* `1516a52669`, `8d4597bf8e`, `1ec78a0dcc` and `c843eea710` are now in this branch, through the merge `3d4d482eb9`.
- Hermes changes go only on fork branches. They are fast-forwarded into the deployed branch `alex/v0.22.0-mobile-fixes` and deployed with `git pull --ff-only` in the install. The plugin is enabled through house-infra `hosts/<dashboard-host>/hermes.py`. No live edits (vault rule 19).
- One announced dashboard restart at deploy. List the busy sessions before scheduling it. The restart also costs every resumed session one prompt-cache miss, because the new tool is added to its tool list (see "Tool list of a resumed session").
- Prompt caching is sacred (root `AGENTS.md`). Mail arrives as new user rows. It never rewrites past context or rebuilds a live session's system prompt.
- A new model tool reaches every API call of every session (root `AGENTS.md`, "The core is a narrow waist"). A plugin tool is the sanctioned way to add one (`tools/AGENTS.md:25-27`).
- Code-health ratchet: functions CC ≤ 20 and ≤ 300 lines; files ≤ 2,000 lines.
- Plugin data lives under `get_hermes_home()` (HX001). With no worker, the only work that runs outside a turn is the reply thread started by the hook. It must carry the turn's profile context (`tools/thread_context.py:36`, `propagate_context_to_thread`).
- **The `session_message` tool handler is synchronous** *(round 3; still true for any path where the tool itself waits on the dashboard socket, superseded for the poller path, where the tool only writes the outbox)*. The worst case for one send is resume (60 s) + steer (60 s) + submit (60 s) + start wait (240 s) = about 420 s. That is longer than the 300-second limit `model_tools._run_async` puts on an `is_async` handler that runs on a fresh thread (`model_tools.py:94-135`). A sync handler running its own short event loop avoids that limit. This is a timeout, not a cap on sending (planner note from the refiner, round 2).
- Behaviour goes in `config.yaml`, not in new `HERMES_*` environment variables.
- The Trial uses a temporary `HERMES_HOME`, its own dashboard on another port and a fake model. *(Round 4.)* It must also run a classic CLI process, an Ink TUI process and a gateway with a test adapter, because the live install has no gateway sessions to look at (see "Gateway sessions").
- *(Round 4.)* Every process that loads the plugin must stay cheap when there is no mail. The poller adds work to every CLI, TUI, gateway and dashboard process.
- Question IDs continue the series. This brief uses SM-Q7 to SM-Q16 (SM-Q14 is asked elsewhere: deploy method).

## Decisions (settled by Alex; not reopened)

1. ~~A fork-bundled plugin `plugins/session-mail`, shaped like the in-fork `plugins/model-routing/`.~~ *Superseded in round 5 (Alex: "I want us to make a fork of intercom, add to their code and post the update in the issue above").*
   - The base is `alexderz/hermes-intercom`; the plugin name `intercom` and the `intercom` tool are kept.
   - Our features extend it: hosting many sessions per process in the dashboard, TUI and desktop (one socket per process, one registry entry per live session); gateway sessions; the delivery modes; addressing by title or project owner; replies with no empty replies; a durable record.
   - The core seam stays a small fork patch on Alex's Hermes fork, feature-detected by the plugin.
2. Addressing: `@<project-slug>` resolves to the project owner; also an exact title, a session id, or `Home`. The result resolves to the compression tip. An ambiguous match is refused, and the candidates are listed.
3. Delivery right away. No hold.
   - *Round 5 wording (Alex: "we need all 3 as tool options, and we apply the strongest the other session supports: interrupt - steer - queue, with admonition to only interrupt on intention, default to steer or queue"):*
     - the `intercom` tool and the CLI take `delivery: interrupt | steer | queue`, default `steer`;
     - the host applies the requested mode if the target supports it, else the strongest weaker mode it does support (interrupt > steer > queue);
     - `interrupt` uses the host's redirect where supported, otherwise a hard interrupt, then the message runs next; `steer` injects between tool calls; `queue` runs after the turn;
     - an idle target starts a turn, whatever the mode;
     - the tool description says: "only use interrupt when you intend to stop what the other session is doing right now (it is wrong, or the work is obsolete). Otherwise use steer (default) or queue.";
     - the outbox records the requested and the applied mode, and the receipt to the sender says which was applied;
     - `scripts/dashboard_dispatch.py` keeps its default (steer, else queue); an interrupt option there is optional.
   - ~~"Steer, else queue, else start. Never cancel or redirect."~~ *(Rounds 1–4; superseded in round 5. "Never" now holds only for the default `steer` and for `queue`.)*
   - *Round 1 wording, superseded in round 4:* "inside the dashboard", with `prompt.submit` and `queued: true`, resuming the session in the dashboard first if needed.
   - *Round 4 wording (scope addition):* every host applies this rule to the sessions it hosts:
     - a live dashboard, desktop or TUI session is served by its process;
     - a classic CLI session by its own process;
     - a gateway session by the gateway;
     - a session that is live nowhere goes to the dashboard, which resumes it and starts a turn;
     - an idle gateway session goes to the gateway, which starts the turn in that chat.
4. Replies: the target's final answer goes back to the sender by the same rule. A silence token or an empty answer sends nothing.
5. Debates are allowed. No caps.
6. No empty replies. The tool description and the footer of every message say so; `[SILENT]` ends an exchange.
7. A durable outbox records who sent what. The sender is named in the text.
8. A CLI for cron jobs and scripts costs no turn. *(Round 5: it becomes an `intercom` command, for example `hermes intercom send …`, with the same `delivery` option; the exact name follows intercom's style. The name `hermes session-mail send` is superseded.)*
9. *(Round 4, scope addition.)* Every kind of session is a target: dashboard and desktop, classic CLI, Ink TUI, and messaging-gateway sessions. Cross-machine and cross-install delivery stays out (SM-Q6).
10. *(Round 4, SM-Q13, answered by the scope change.)* Bot sessions in scope:
    - the messaging-gateway sessions;
    - the default profile's `Bot Chat`.

    Bots in other profiles stay out, because that is cross-profile.
11. *(Round 4, reshaped in round 5.)* One small core seam is allowed under decision 1's exception: `ctx.inject_message(..., mode="interrupt"|"steer"|"queue")`, honoured by each host with the fallback chain. It goes in PROJECT.md as a fork patch.
12. *(Round 5, SM-Q12 answered: intercom.)* Build on our fork of `majordave/hermes-intercom` (option d below), not on our own protocol (a), not on upstream's peer messaging (b), and not by waiting (c).
13. *(Round 5.)* Upstream: when it works, draft an update for #81885, and possibly a pull request to `majordave/hermes-intercom`, into `docs/` on the branch. Alex reviews the exact text; agents never post.

Design choices taken from the research and the refiner, which the code supports:

- *(Round 5)* **Transport: intercom's per-process sockets, extended.** This supersedes the round-4 "outbox as the bus, plus a poller" for live targets.
  - Every Hermes process that loads the plugin binds one `0600` Unix socket, with the peer-UID check, under `$HERMES_HOME/intercom/`.
  - The registry gets one entry per live session it hosts, with the socket path, so the dashboard can list dozens.
  - A sender resolves the target to a session, finds the process that hosts it, and connects. The host delivers through the seam in the requested mode.
  - A target that is live nowhere is sent to the dashboard's socket, which resumes the session and starts a turn there.
  - An idle gateway session is served by the gateway's socket, which knows its sessions through its own session store.
  - The **outbox** remains the durable record. It also holds mail that no process can take right now (for example, when no dashboard runs); that is the A9 case, not a hold.
  - What still holds from the refined design: no retries beyond normal delivery, no caps, no holds, errors recorded and returned to the sender.
- ~~**Outbox plus a poller in every process**~~ *(round 4, superseded in round 5 by intercom's sockets, above)*:
  - **The outbox** (SQLite under `plugin-data/session-mail/`) is the bus between processes.
  - **The poller:** every Hermes process that loads the plugin (dashboard, gateway, each CLI or TUI) runs one. It claims mail only for sessions it hosts now, and delivers it through its own host with the new seam.
  - **Mail for a session that is live nowhere** goes to the dashboard, which resumes it and starts a turn.
  - **Mail for an idle gateway session** goes to the gateway, which starts the turn in that chat.
  - **Replies** come from `post_llm_call` in the process that ran the turn.
  - **Still holds from the refined design:**
    - no retries beyond normal delivery: mail waits in the outbox until a host claims it; once handed over it is not sent again;
    - no caps of any kind;
    - no holds;
    - errors are recorded and readable by the sender.
- ~~**Delivery at send time.**~~ *(Superseded in round 4 for the general case. The dashboard-socket rule below survives only as how the dashboard wakes a session that is live nowhere.)* Three callers deliver mail themselves:
  - the tool handler, in the process that runs the sender's turn;
  - the CLI, in its own process;
  - the reply hook (`post_llm_call`), from a short-lived thread in the process that runs the target's turn.

  Each caller opens the dashboard WebSocket with the loopback agent key and runs the steer → queue → start rule. It records the result in the outbox and returns it to the caller (`steered`, `queued`, `started`, or the error).

  A failed delivery is reported, not held and not retried. The sender (a model or a script) can send again. No "is this the dashboard?" check is needed, because delivery always goes over the dashboard's own socket. This works the same with `dashboard.turn_isolation` on, where turns run in a child process. That setting is off by default (`hermes_cli/config_defaults.py:1005`).
- **Reuse the dispatcher's rule instead of `ctx.inject_message`.** The plugin injection host only queues, never steers, and writes no accept-time row, so the phone does not see the mail until it runs (`tui_gateway/plugin_inject.py:53-64`).
- **One copy of the delivery logic** (see the options under A2). The architect picks how it is shared.
- **Header only on all three paths** (SM-Q7 recommendation A). The 📨 header and footer are the only separation from Alex's words. *(Round 5: the header becomes intercom's frame, made explicit about "not Alex"; see SM-Q7.)*
- **Outbox fields:**
  - id, in-reply-to id, sender, target, body, reply (or "silent"), timestamps;
  - *(round 5)* the delivery result is now two fields, **requested mode** and **applied mode**.

  There is no `hop` column (nothing reads it, and a counter invites a cap) and no status ladder.
- **Reply matching** finds the mail id anywhere in the turn's new rows: the `user_message`, or `display_kind: "steer"` rows in `conversation_history`. That covers every path:
  - an accepted steer;
  - a steer parked during compression;
  - a leftover steer that was requeued as plain text;
  - a queued prompt merged with other text.

## Environment facts

### Round 5: intercom, the new base (read in full)

Clone of `alexderz/hermes-intercom` at `ae90a2a` (merge of a protocol-hardening pull request, 2026-09-04). The `upstream` remote is `majordave/hermes-intercom`. It has 1,783 lines in total: `__init__.py` 178, `inbox.py` 751, `tests/test_protocol.py` 451 (17 tests), `README.md`, `docs/findings.md`, and `docs/AGENTS.md` (design notes, in Spanish). The manifest is `plugin.yaml`: name `intercom`, version 0.2.0, `kind: standalone`, `provides_tools: [intercom]`. Paths below are relative to that clone.

- **Tool:** one multiplexed tool `intercom(action=list|send|ask|reply, to, message, timeout, request_id)` in toolset `intercom`, with `check_fn` always true (`__init__.py:19-61,162-170`). Config is a single `inbound: always|never` setting (`:159-160`).
- **Registry and socket:**
  - `inbox.start()` runs once per process at plugin load (`__init__.py:172-176`). It writes `$HERMES_HOME/intercom/sessions/<id>.json` with `{name, pid, cwd, session_id, socket, started_at}`, binds `<id>.sock` with mode `0600`, and serves it on a daemon thread (`inbox.py:621-690`).
  - The `<id>` is **not** a Hermes session id. `start()` is called without one, so it is `<pid>-<time>`, an endpoint id per process (`:629`; a test checks it ignores an inherited session id, `tests/test_protocol.py:331`).
  - Names are `<profile>-<cwd folder>-<pid mod 1000>` (`inbox.py:114-127`).
  - There is **one entry per process**, so a dashboard with dozens of sessions appears as one peer.
  - Dead pids are swept on read (`:130-147,346-356`), and cleanup runs at exit (`:667-679`).
- **Peer-UID check:** every connection is refused unless the peer's effective UID equals the server's, via `getpeereid`, `LOCAL_PEERCRED` or `SO_PEERCRED` (`inbox.py:545-569`; test `:309`). The envelope is JSON lines (`:8-11,472-487`).
- **Delivery on the receiving side** (`_deliver_local`, `inbox.py:216-269`):
  - **Finding the agent:** the live `HermesCLI` is found by scanning garbage-collector objects for `type(o).__name__ == "HermesCLI"` (`:201-213`), and the agent through `cli._active_agent_ref` or `cli_obj.agent` (`:221-223`).
  - **Idle CLI:** `cli_obj._pending_input.put(text)` starts a turn ("submitted_as_turn", `:225-236`).
  - **Busy:** guessed from private flags (`_conversation_active`, `_processing`, `_current_tool_count`, …, `:272-291`) plus the registry's `turn_active` (`:230,259`). Delivery is `agent.steer(text)` ("steered"); a refused steer is "held_steer_rejected", and nothing is queued (`:257-262`).
  - **No reachable agent** (a TUI, dashboard or desktop process, where `cli` holds no CLI object): the text is parked in a per-process list and appended to an owner-only spool `intercom/pending/<id>.jsonl` (`:238-255,706-739`).
  - **Parked text is drained by `pre_llm_call`** into the next turn's user message, as `[Messages delivered from other sessions while you were idle]` (`__init__.py:137-147`). **In a process hosting many sessions (the dashboard), that is the next turn of *any* session, not the addressed one.**
  - **Interrupt:** never.
- **Frame:**
  - v3 is compact: `📡 hermes@<name> says:` then the body (`inbox.py:176-187`). The design notes record that v3 removed the earlier `[INTERCOM MESSAGE … NOT by the user …]` wrapper and its safety line (`docs/AGENTS.md`, "v3").
  - Body lines that copy the header are broken with a zero-width space (`inbox.py:154-167`), and brackets and newlines are stripped from names (`:170-173`).
  - On the sending side, `_strip_echo_headers` drops quoted `📡 hermes@… says:` lines (`__init__.py:64-76`).
  - A steered message still sits inside Hermes's `[OUT-OF-BAND USER MESSAGE …]` user marker; parked text rides inside the user message.
  - The README's claim that "the frame identifies the sending session so the model never mistakes it for user instructions" is not backed by any non-user frame. The human-view box `_human_view` / `_display_banner` is dead code (`inbox.py:48-98`; no callers).
- **Ask and reply:**
  - `ask` sends with a random `request_id` (`uuid4`) and **blocks the tool call** until a `reply` envelope comes back or the timeout ends (default 600 s, max 3,600 s; `__init__.py:102-116`, `inbox.py:370-422`). The receiver is told to call `intercom(action="reply", to=…, request_id=…)` (`:599-607`).
  - A reply is accepted only from the peer the ask was sent to (`:425-433`; tests `:209`, `:226`). Replies skip deduplication (`:436-451`).
  - Correlation is in-memory in the asking process, so a reply after a restart is lost.
- **Receipts:** `delivered` (submitted as a turn, or a reply resolved), `held` (steered or parked), `refused` (`inbox.py:527-538`).
- **Caps that conflict with decision 5 ("no caps"):**
  - 8,000-character body (`inbox.py:35,520`);
  - **6 messages per peer per minute** (`:37-38,503-505`);
  - **duplicate refusal within 120 s** (`:39,508-514`);
  - **10 parked messages**, then "rejected_pending_cap" (`:36,246-268`);
  - a 3,600-second ask maximum.

  The first four are caps to remove.
- **Tests:** 17 unit tests on the protocol (ask metadata, request ids, prefix resolution, reply binding, UID refusal, spool permissions, a same-UID socket round trip, error passing; `tests/test_protocol.py:52-451`). None cover dashboard, TUI or gateway hosting.
- **Its own roadmap** (README, "Still ahead") lists first-class TUI and desktop peers, a stable id per profile, durable mailbox identity, and "migrate delivery to the official host seam".

### Round 5: what intercom already does, what we change, what we add

| Our requirement | Intercom today | Change or add |
|---|---|---|
| Classic CLI target | Yes: idle starts a turn; busy steers | Replace the garbage-collector lookup and private flags with the seam; add `interrupt`; a refused steer queues instead of being "held" |
| Ink TUI, dashboard, desktop (many sessions per process) | No: one endpoint per process; text is parked and drained into whatever turn runs next | **Add** one registry entry per live session (from `tui_gateway`'s live `_sessions`), and route by session to the seam in that process. Remove the process-wide `pre_llm_call` drain for these hosts |
| Gateway sessions (Telegram topics) | No | **Add**: the gateway process binds a socket and registers the sessions its session store knows (`lookup_by_session_id`); delivers through the seam |
| A session that is live nowhere | No (the sender gets "no live peer") | **Add**: route to the dashboard's socket, which resumes the session (A2 rule) and starts a turn |
| Delivery modes interrupt / steer / queue, with fallback, default steer | Steer or park only | **Add** the `delivery` argument, the fallback chain, requested and applied mode in the receipt and the outbox, and the tool-description sentence on interrupt |
| Addressing by title, `@project`, `Home`, id, compression tip | Name or prefix of a live endpoint (`inbox.py:454-469`) | **Add** resolution through `state.db` (exact title, `@slug` owner rule, `Home`, id or prefix) to a session id, then to its compression tip, then to the hosting process. Keep intercom names as one more form |
| Automatic replies, no empty replies, `[SILENT]` | Explicit `reply` to an `ask` only; nothing automatic | **Add** `post_llm_call` reply capture (mail id in the turn's rows), the marked reply block (SM-Q8), `[SILENT]` and empty-answer suppression, and the footer rule. See SM-Q16 for `ask` and `reply` |
| Debates, no caps | Rate limit, dedupe, pending cap, size cap | **Remove** the caps |
| Durable record of who sent what | None (spool only for parked text; deleted after drain) | **Add** the outbox (SQLite, `0600`) with requested and applied mode and the reply. The spool can become the outbox's undelivered rows |
| Sender named in the text, not Alex's authority | `📡 hermes@<endpoint-name> says:` | **Change** the header to name the sender **session** (title and id) and say "not Alex" (SM-Q7). Keep the zero-width-space forgery defence and echo stripping |
| CLI for cron and scripts, no turn | None | **Add** a `register_cli_command` subcommand (`hermes intercom send|list|status`), as `plugins/model-routing/__init__.py` does |
| Same UID, same machine | Peer-UID check, `0600` sockets | Keep |
| Two sessions in the same process (two dashboard chats) | **Refused:** `send_to` rejects any target whose pid is the sender's own ("target is the current session", `inbox.py:498-499`) | **Change** to refuse only the same **session**. Same-process delivery goes straight to the seam, with no socket hop |

**What survives from rounds 1–4:**
- the outbox as the record (fields above), and reply matching by mail id in the turn's rows;
- header-first framing with relabelling of quoted control frames;
- SM-Q8's marked reply block, and SM-Q9's sender-source test;
- the addressing rules and data;
- the reaper facts (finding 2), the phone facts (finding 4) and the tool-list facts;
- the dashboard dispatcher for waking a session that is live nowhere;
- the per-host facts from round 4.

**What intercom replaces:**
- our socket and bus: the dashboard WebSocket from tools (round 2), and the outbox-plus-poller (round 4);
- the `session_message` name;
- the `session-mail` plugin name.

### Round 5: the `miyu4u/hermes-intercom` fork (prior art only)

- **Commits:** clone at `1c1e677`, four commits ahead of `ae90a2a`, all dated 2026-11-04 (messages in Korean): a same-workspace gateway transport with correlated replies; a frame redesign; a test matrix; docs. In total 18 files, +2,094/−233, including `gateway_peers.py` (233 lines) and tests.
- **Its "gateway" is v0.23's unified gateway (the backend that hosts CLI, TUI, desktop and ACP sessions), not the messaging gateway.** Its roster keeps only rows whose `created_source` is `cli`, `tui`, `desktop`, `acp`, `tool` or `oneshot`, in the same workspace (`gateway_peers.py:46-62,74-79`). **It does not reach Telegram.**
- **It relies on APIs this worktree lacks** (checked):

  | API | Used at | In this worktree | In `v0.23.0` |
  |---|---|---|---|
  | `hermes_cli.gateway_client.connect_gateway` | `gateway_peers.py:34` | no (file missing) | yes |
  | `hermes_cli.gateway_runtime.discover_gateway_endpoint` | `:35` | no (file missing) | yes (`hermes_cli/gateway_runtime.py:289`) |
  | `gateway.session_context.bound_session_key` | `:26` | no | yes (`gateway/session_context.py:117`) |
  | `session.steer` with `execution_generation` | `:224-233` | no | in the v0.23 contracts (`tui_gateway/contracts/canonical.py`) |

  `ctx.session_surface()` (`:29`) and the `created_source` column do exist here (`hermes_cli/plugins.py:602`; `hermes_state_common.py:385`).
- **Useful ideas:**
  - a cyclic-ask refusal (`:149-163`);
  - the sender label taken from the session **title** (`:192`);
  - routing metadata with a `message_id` per message (`:188-194`);
  - a frame `📡 INTERCOM from <sender> · <cwd>` plus a line `untrusted peer data (quoted; user policy)` (its `inbox.py:137-154`);
  - delivery through `ctx.inject_message(frame, session_key=…)` for idle peers (`gateway_peers.py:205-208`).

  It also keeps a 6-per-minute rate limit and a 10-message pending cap (`:173-183,199-202`).
- **Use:** read at the v0.23 rebase. Its unified-gateway transport could replace our per-process sockets for CLI, TUI and desktop sessions there.

### Round 5: delivery modes per host (what interrupt, steer and queue mean today, and what the seam adds)

| Host | `interrupt` today | `steer` today | `queue` today | What the seam must add |
|---|---|---|---|---|
| **Dashboard / desktop / Ink TUI** (`tui_gateway`) | `_handle_busy_submit` with mode `interrupt`: redirect the active turn when the agent supports it (`_supports_active_turn_redirect`), otherwise queue, then a hard interrupt (`tui_gateway/session_auto_continue.py:400-455`, `_interrupt_busy_session` at `:446-454`) | `AIAgent.steer` via `session.steer` (`tui_gateway/methods_session_interrupt.py:137-172`); during compression, steer and interrupt are demoted to queue (`session_auto_continue.py:410-411`) | Queued submit with an accept-time row (`:406`, `:438-443`) | Today the mode comes only from config (`_load_busy_input_mode`) or the `queued` flag. The seam passes the requested mode to that function, reports the applied mode, and lets `plugin_inject.py` (queue-only today, no accept-time row) use it |
| **Classic CLI** | `agent.redirect(text)` when supported, else `_interrupt_queue` (hard interrupt; the message becomes the next turn) (`hermes_cli/cli_tui_mixin.py:1535-1551`; `cli_chat_turn_mixin.py:418-441`) | `agent.steer(text)`, refusal → queue (`cli_tui_mixin.py:1515-1530`) | `_pending_input` (`:1531-1534`) | Today `inject_message` always uses `_interrupt_queue` when busy, which is a hard interrupt whatever is asked (`hermes_cli/plugins_injection.py:21-22`). The seam routes through the typed-input logic with the requested mode, instead of the configured `busy_input_mode` |
| **Messaging gateway** | `_resolve_busy_steer_or_redirect` plus `_interrupt_running_agent_for_busy_event` for typed messages (`gateway/run_busy.py:856-880`) | Same resolver, steer branch | FIFO `_queue_or_replace_pending_event` (`:862-864`) | Internal (plugin) events are forced to queue (`:843-849`, "plugin events carry untrusted payload text"). The seam lets an injected event carry a requested mode while keeping `allow_gateway_control=False`, so mail can steer or interrupt but never run gateway control commands |
| **All hosts, idle target** | starts a turn | starts a turn | starts a turn | Same on every host (decision 3) |

### Round 4: how each host handles injected text today (verifies the scope addition)

`ctx.inject_message` routes in `hermes_cli/plugins_injection.py:12-62`. Each claim in the scope addition, checked:

| Host | What happens today | Claim in the scope addition | Result |
|---|---|---|---|
| **Classic CLI** (also the prompt_toolkit TUI inside `cli.py`) | A CLI process ignores `session_key` and always targets its own REPL. Busy → `_interrupt_queue`; idle → `_pending_input` (`plugins_injection.py:19-23`). The turn loop reads `_interrupt_queue` while the agent runs and calls `self.agent.interrupt(msg)` (`hermes_cli/cli_chat_turn_mixin.py:418-441`). | "With `busy_input_mode: interrupt` that redirects the run." | **Worse than stated:** a **hard interrupt** of the running turn, whatever `busy_input_mode` is (that mode only routes *typed* input, `hermes_cli/cli_tui_mixin.py:1505-1551`). The CLI already has the parts a seam needs for typed input: `agent.steer(text)`, falling back to `_pending_input` as the next turn (`cli_tui_mixin.py:1515-1532`). Idle `_pending_input` starts a turn (`hermes_cli/cli_tui_runtime_mixin.py:36`). |
| **Ink TUI, dashboard, desktop** (`tui_gateway`, one per process) | `inject_tui_session_message` finds the live session by `session_key` in *this* process. It queues with `_enqueue_prompt` and drains if idle (`tui_gateway/plugin_inject.py:24-64`). It writes no accept-time row, and returns False when the session is not live here. | "Only queues; never steers." | **Verified.** The same process has `session.steer` / `AIAgent.steer` and the queued submit with an accept-time row (`tui_gateway/session_auto_continue.py:400-455`), so a seam can reuse them. |
| **Messaging gateway** | `_dispatch_plugin_message_injection` looks up the session by `session_key`, rechecks authorization, and calls `adapter.handle_message(MessageEvent(..., internal=True, allow_gateway_control=False, ...))` (`gateway/run_plugin_injection.py:126-157`). On a busy session, internal events are FIFO-queued and "must never interrupt or steer" (`gateway/run_busy.py:843-849`). An idle session starts a new turn through the normal path. | "The gateway's busy policy applies." | **Corrected:** the busy policy does **not** apply to injected events. They always queue, never interrupt, and never steer. The gateway can steer typed input (`_resolve_busy_steer_or_redirect`, `gateway/run_busy.py:856-858`), so a seam can reuse that. |
| All non-CLI hosts | Need `plugins.entries.<id>.allow_gateway_injection: true` (`plugins_injection.py:32-37`). | — | Config the house-infra enable must set. |

- **The gateway's bot-loop guard does not apply to injected mail.** It counts only bot-authored sources (`gateway/authz_mixin.py:600-612`, `if not getattr(source, "is_bot", False): return True`). Injection reuses the chat's stored source (`gateway/run_plugin_injection.py:136-138`). So it is not a hidden cap.
- **A bare `[SILENT]` answer to an injected gateway turn is not posted.** `gateway/response_filters.py:19-35` defines the silence markers. Only turns whose user row is the internal machinery kind (`internal_notification`) "may vanish on a bare silence marker". That injected mail rows get that kind is to **verify in Trial**.
- **The injected text is not shown in the Telegram chat.** It enters as an internal `MessageEvent`, not as a chat message; only the turn's answer is sent through the adapter. This is read from the dispatch path above; **verify in Trial**. See SM-Q15.

### Round 4: which process hosts a session (`runtime/active_sessions.json`)

- **Writer and format:** `hermes_cli/active_sessions.py`. The file is `<hermes-home>/runtime/active_sessions.json` (`:175-176`), written atomically as `{"entries": [...]}` (`:297-298`) under a file lock (`:183-189`). Each entry has (`:461-480`):
  - `lease_id`, `session_id`, `surface`, `pid`, `process_start_time`, `started_at`, `updated_at`;
  - optional `track_liveness` and `metadata`.

  Dead processes are pruned on read (`active_session_registry_snapshot`, `:711-744`). The lease is per-session exclusivity: "at most one live owner per stored session" (`:482-495`).
- **Who writes, and when:**

  | Writer | Surface value | Key | When |
  |---|---|---|---|
  | CLI (`cli.py:925-940`) | `"cli"` | the stored session id | while the CLI holds the session, idle or busy |
  | TUI / dashboard / desktop (`tui_gateway/session_lifecycle.py:62-85`) | `"tui"` or `"desktop"` (`track_liveness` only for desktop) | `session_key` (the stored session id) | while the session is live in that process. Metadata `bot_live_delivery_consumer: true` (`:62-65`) |
  | Gateway (`gateway/run_busy.py:236-262`) | `"gateway:<platform>"`, metadata with platform, chat_id, user_id | the gateway's **session key** (not the stored session id) | **only for a running turn** ("for a new gateway turn") |

- **Consequences for the poller:**
  - **CLI and TUI:** a poller can find "do I host this session?" from the registry by `pid`. Or more simply, from its own process state: the CLI's `self.session_id`, or the TUI's `_sessions`.
  - **Dashboard vs Ink TUI:** both write surface `tui`, so only the `pid` tells them apart.
  - **Gateway:** an **idle gateway session has no lease**, and a busy one is keyed by the gateway session key. So the registry cannot route gateway mail. The gateway's own session store can: `lookup_by_session_id(session_id)` (`gateway/session.py:1311-1317`) maps a stored session id to its routing entry, persisted in the `gateway_routing` table of `state.db` (`gateway/session_persistence.py:2`). Only the gateway process should claim mail whose target its store knows.
  - **Live nowhere** = no live lease and not known to a running gateway. Then the dashboard claims it. That needs a "this is the dashboard" signal again (round 1 found only the dashboard-only `dashboard/plugin_api.py` import, `hermes_cli/web_server_dashboard.py:869`, and the shared injector install, `hermes_cli/web_server.py:241`). Or the dashboard poller simply claims everything that is unclaimed after one poll.
- **Live metadata (read-only, 2026-11-09):** 5 entries (3 `desktop`, 2 `tui`); keys `lease_id, metadata, pid, process_start_time, session_id, started_at, surface, track_liveness, updated_at`.

### Round 4: gateway sessions

- **The live install has no messaging-gateway sessions yet.** The `gateway_routing` table in `state.db` has 0 rows. No session has a messaging-platform source; the sources are `cli` 9, `cron` 102, `desktop` 9, `oneshot` 6, `subagent` 6, `tui` 5 (read-only count). Telegram topics are a target for future use, and the Trial must create gateway sessions itself.
- **Addressing a gateway session** works through the same `state.db` rows (title, id, compression tip). Routing it needs the gateway store's entry (`origin`: platform, chat_id, thread_id), read by `_restored_source` before dispatch (`gateway/run_plugin_injection.py:136-138`).

### Round 4: why a per-process poller again

- **The refiner removed the dashboard-only worker (round 1)** because the dashboard socket reached every target that mattered then.
- **That is no longer true.**
  - A classic CLI session lives in its own process, has no WebSocket server, and holds its session's lease. The dashboard cannot resume it: `SESSION_NOT_OWNED` (round 1, research note).
  - A gateway session's turn runs in the gateway process, through the adapter.
  - Only code inside the hosting process can steer into its running turn, through `AIAgent.steer` on that process's agent object.
- **So delivery must happen in the hosting process.** With no shared socket for CLI or gateway processes, the outbox file is the only shared channel, and each process must look at it. Hence a poller (or an equivalent wake, such as a file watch) per process.
- **Still holds from the refined design:**
  - no retries beyond normal delivery: mail sits in the outbox until a host claims it, and a claimed mail is not sent again;
  - no caps;
  - no holds;
  - no give-up timer;
  - errors are recorded and readable by the sender.
- **No "redelivery of lost mail" either:** a mail that a host queued in memory and then lost (restart, interrupt) stays "handed over" in the outbox, with no reply (A3 stays dropped).

### Round 4: upstream peer messaging (missed by the research)

None of this is merged. `git ls-tree` finds no peer-messaging files in `v0.23.0` (`2bd378ed1b`) or `upstream/main` (`b3746e35dd`). All three pull requests below report `mergeable=false` / `dirty` (or unknown).

- **#106423 "peer session messaging"**, opened 2026-09-09 by an upstream maintainer; open, last update 2026-10-12. It is the single commit `cff14a4c62`, found only on `upstream/muse-code-inspired/peer-session-messaging`: 6 files, +470/−0, mainly `tools/peer_messaging_tool.py` (+363). Verified in `git show cff14a4c62`:
  - **Toolset and tools:** a core toolset `peer_messaging`, off by default, with `peer_sessions` and `peer_send` (`toolsets.py`, +127-133).
  - **Mailbox:** one JSON file per message in `$HERMES_HOME/runtime/peer_messages/<session>/` (directory mode 0700, temp file then `os.replace`; `tools/peer_messaging_tool.py:38,57-63,102,118-121`).
  - **Caps:** an inbox cap of 50 files (`:41,107`) and a body cap of 8,000 characters (`:39,88`).
  - **Delivery:** drained by the agent's activity hook, `inject_peer_messages(self)` inside `_touch_activity` (`agent/activity_tracking.py:81-85`), at most every 5 seconds per agent (`:44`). That works in **every host that runs an `AIAgent` turn** (CLI, TUI/dashboard, gateway) with no host-specific code.
  - **No wake:** `_touch_activity` runs only on turn and tool paths, so an idle or not-live target gets the mail at its next turn.
  - **Frame:** the message is steered in with the text "Message from another of your user's Hermes sessions (peer session {sender}) … It carries peer-agent authority, not user authority …" (`:239-242`). It goes through `agent.steer()`, so it still sits inside the `[OUT-OF-BAND USER MESSAGE …]` marker that the system prompt says carries user authority.
  - **Discovery:** reads `state.db` (`list_sessions_rich`, recently active, not ended; `:161-207`), not `active_sessions.json`.
  - **Sender:** taken from the dispatch context (`:361`).
  - **Replies and loss:** there are no replies and no acknowledgements. Files are deleted before `steer()`, so a crash loses mail (`:279-289`).
  - **Review:** one review (2026-09-09) raises two blockers: "Do not use the user-role steer lane for peer-agent authority" and "Keep the durable message until recipient delivery has settled". No response yet.
- **#136861**, opened 2026-10-12 by a community contributor; open, no reviews, last update 2026-10-19. It rebases #106423 onto main, keeping the original author: 7 files, +575/−1. It also:
  - pins the inbox to the recipient's own home (multi-profile fix);
  - rewords the frame;
  - documents the loss window as accepted ("does not provide acknowledgment, retry, or exactly-once execution").

  It does **not** fix the lost, user-looking or wrong-turn problems itself.
- **The fork pull request linked from #136861's comments** (on top of #136861; 19 files, +595/−153, 11 commits) is the one that fixes them. It was **closed unmerged by its author on 2026-11-05, with no comment**; the author keeps the branch merged in their own fork. Its fixes, as reported by the research subagent from the diff:
  1. **Lost mail:** delivery moves from the activity hook to right before each model request (`agent/turn_iteration_prep.py`). The row is persisted before the file is deleted: possible duplicates, never zero deliveries.
  2. **Looks like the user:** a new marker `[PEER SESSION MESSAGE — from another Hermes session of the same user, not from the user … It carries no user authority …]` with `display_kind="peer_message"` (`agent/prompt_builder.py`). The rows are excluded from user-row merging, added to the compressor's synthetic prefixes, and shown as a notice on desktop.
  3. **Spoofing:** quoted control frames are relabelled.
  4. **Wrong turn:** `_inject_steer_after_newest_tool_result` searches only after this turn's user row. The same bug exists for `/steer` on `main`.
  5. **Forks stealing mail:** review forks and `/btw` never read the mailbox.

  Still missing there: wake and replies.
- **#123218**, opened 2026-09-26 by another contributor; open, last update 2026-10-21, +1,184 lines. It adds:
  - `peer_receive` (non-destructive read, explicit acknowledgement);
  - replies (`in_reply_to`, `message_id`);
  - project-scoped discovery, using `active_session_registry_snapshot` for "owner present";
  - file locking;
  - a steer that carries only a hint, not the content.

  It **refuses non-local targets by design**: `_LOCAL_SOURCES = {"cli","tui","desktop"}`, "not managed messaging or workers". That excludes Telegram. It keeps the caps, and states "No automatic wake".
- **Issue #81885** ("Local cross-session messaging (intercom)", opened 2026-08-08, open, label `needs-decision`):
  - **Proposal:** a per-session registry plus a Unix socket, an `intercom` tool, a non-user frame, and **per-sender rate limits, dedupe and a pending cap**. Gateway inbound is out of scope for v1.
  - **The three-way split (comment, 2026-10-09; the same comment is on #103748):**
    1. addressing that survives compaction, restart and resume;
    2. live runtime ownership ("having a live owner does not necessarily mean a turn is active");
    3. a delivery policy of reject, queue or **wake** ("behave like Queue if a turn is already active; otherwise, proactively initiate one, including an authorized resume if needed").
  - **Telegram-topics use case (comment, 2026-10-26):** one profile, one bot, many topics; send and ask with replies to the origin; wake when idle without "a second competing runner"; attribute to the sending agent, not the human; **show the exchange in the topics**. It asks that gateway topic sessions be included.
  - **No maintainer position** has been stated on #81885.
- **Closed PR #83661** (the plugin seam `ctx.inject_message(..., mode="queue", target_session=...)` for CLI, TUI/desktop and gateway hosts): closed by its own author on 2026-08-13, two days after opening, with **no closing comment** and a force-push to zero commits. Why it was closed is not recorded.
- **Issue #103748** ("official way to deliver a message into an existing live session"): open, `needs-decision`. Triage kept it separate from #81885: "this request requires in-band delivery to an already attached owner".

### Steer framing (finding 1)

- **The frame is produced in one place.** `agent/prompt_builder.py:561-565` defines `STEER_MARKER_OPEN` (`[OUT-OF-BAND USER MESSAGE — a direct message from the user, delivered once at this position; …]`) and `STEER_MARKER_CLOSE`. `format_steer_marker` (`:577-579`) wraps the text. `steer_user_row` (`:585-591`) builds a standalone `role: "user"` row with `display_kind: "steer"`.
- **The system prompt gives that frame Alex's authority.** `STEER_CHANNEL_NOTE` (`agent/prompt_builder.py:594-611`) says the marker "is a genuine user message with the same authority as their original request". It is added to every session with tools (`agent/system_prompt.py:567`).
- **The caller cannot choose the frame.** `AIAgent.steer(text)` takes only text (`agent/interrupt_control.py:267-278`), and `session.steer` passes only `params.text` (`tui_gateway/methods_session_interrupt.py:137-172`). Pending steers are joined into one buffer under one marker (`agent/interrupt_control.py:274-276`).
- **Queued and started mail carry no marker at all.** They go through `prompt.submit` and become ordinary user turns, with the user's full authority (`tui_gateway/methods_prompt.py:735-887`; the queued path is `tui_gateway/session_auto_continue.py:400-455`). On those two paths, the 📨 header is already the only separation. A steer-frame patch would separate steered mail only.
- **The existing "turn author" changes no model-visible text.** `prompt.submit` accepts `_turn_author` only as an in-process `DeliveryAuthor` object (`tui_gateway/methods_prompt.py:759-765`; `tools/bot_relay.py:525-539`). The author only reaches memory providers (`agent/turn_context.py:903-918`).
- **Plugin system-prompt sections reach new sessions only** (`hermes_cli/plugins.py:957-981`).
- **Upstream v0.23.0** keeps the same marker and the same "same authority" note. It stores steers as per-part `(ticket, text)` entries (`git show v0.23.0:agent/interrupt_control.py`, `steer` at line 310).

### Delivery primitives and the dispatcher

- **`session.steer` returns `queued` both for an accepted steer** (`tui_gateway/methods_session_interrupt.py:171`) **and while compression is in flight**, when the text goes to the prompt queue and no accept-time row is written (`:156-159`). An idle session returns `rejected` (`:164-165`).
- **A steer that comes too late becomes a new turn.** It is handed back (`agent/turn_finalizer.py:745-749`) and queued as plain text with no marker (`tui_gateway/prompt_turn.py:444-447`).
- **`prompt.submit` with `queued: true` always queues** (`tui_gateway/session_auto_continue.py:406`). It writes the row at accept time (`:438-443`). Text-only prompts without an author merge into one envelope (`:162-168`).
- **The dispatcher on the fix branch** resumes the session, then steers, queues or starts. It detaches at once after a steer or a queue, and waits for the first agent event, up to `--start-timeout` (default 240 seconds), only when it started a turn (`git show 1516a52669:scripts/dashboard_dispatch.py`, `_deliver` and `_main`). That wait exists because the reaper interrupts a detached turn whose agent is still being built. The one RPC timeout default is 60 seconds.

### How the dispatcher is invoked today (for A2)

- `scripts/` has no `__init__.py`, so `scripts/dashboard_dispatch.py` cannot be imported as part of a package. Its only in-tree importer of Hermes code is a `sys.path.insert` of the repository root inside `_key_path` (`scripts/dashboard_dispatch.py:42-53`).
- **Nothing in the repository calls it.** A `git grep` outside `tests/` finds only these documents.
- **Callers are skills that run it as a subprocess:** `<venv>/bin/python -I scripts/dashboard_dispatch.py --resume <id> --prompt-file <file>` (or `--title … --cwd … --prompt-file …`), from the install checkout. Three skills under `<hermes-home>/skills/` do this:
  - `autonomous-ai-agents/session-relay/SKILL.md:16`;
  - `software-development/toolbox-sdlc-manager/SKILL.md:29`;
  - `devops/house-host-operations/references/` (the dashboard-host reference, lines 20-23).
- Cron agent runs follow those skills, so cron output mentions it. No cron job definition in `<hermes-home>/cron/jobs.json` calls it directly.
- The tests for the delivery rule live at `tests/scripts/test_dashboard_dispatch_delivery.py` (in `1516a52669`).

### Threading for delivery at send time

*(Round 4: these facts now apply to the dashboard waking a session that is live nowhere, and to any send that still goes over the dashboard socket. In-process delivery through the seam does not open a socket.)*

- **The dashboard runs every WebSocket RPC on a worker thread, not on its event loop:** `await asyncio.to_thread(server.dispatch, req, transport)` (`tui_gateway/ws.py:319-333`). A turn also runs on its own thread (`tui_gateway/methods_prompt.py:879-886`, `run_thread`). So a tool handler that opens a loopback WebSocket back into the same dashboard is a client on another thread. It does not block the server loop that must answer it.
- **Tool handlers:** an `is_async=True` plugin handler is run by `registry.dispatch` through `model_tools._run_async` (`tools/registry.py:895-907`). That uses a persistent loop per worker thread, or a fresh thread with a 300-second timeout when a loop is already running (`model_tools.py:65-135`). A sync handler can run its own short event loop on the turn's tool thread. The handler gets the calling `session_id` as a keyword (the refiner cites `model_tools.py:875`, `:901`).
- **A start blocks the sender's tool call.** When the target is idle, the rule waits for the target's first agent event, so the sender's turn is held for the target's agent build (normally seconds; the 240-second ceiling is the dispatcher default). This is the one place where send time is not instant.
- **The reply hook** fires on the target's turn thread, inside turn finalization and before `running` clears (`agent/turn_finalizer.py:453-479`). Delivering from a short-lived thread keeps finalization from waiting on a resume. That thread needs `propagate_context_to_thread` for the profile (`tools/thread_context.py:36`). As a daemon thread, it dies with the process. A reply that is in flight during a restart is lost, and the outbox shows no reply.
- **Mail to the sender's own session** (a session mailing itself, or a reply to a session whose own turn is finishing) resumes a session that is running the caller's turn. The code paths look safe: resume reuses a live session; an accepted steer lands after the current tool batch, or becomes the next turn. This was not traced line by line. **Verify in Trial.**

### WebSocket orphan reaper (finding 2)

- The last client leaving parks the session and arms a reap timer (`tui_gateway/session_lifecycle.py:1000-1060`). A second attached client prevents this (`:1030-1032`).
- After the grace period (20 seconds, `tui_gateway/server.py:138-146`):
  - idle sessions are torn down (`session_lifecycle.py:944-945`);
  - running turns with fresh activity (under 600 seconds) are left alone (`:946-951`);
  - stale ones are interrupted, which clears the prompt queue (`:952-967`, `:709-713`).
- Queued rows that never ran are retired on the next resume after a restart (`hermes_state_sessions.py:546-559`; `tui_gateway/methods_session.py:688-692`).
- ~~**Verdict (rounds 1–3)**~~ *(superseded in round 4 by the re-check below)*: a queued mail is lost (1) when the turn goes quiet for 600 seconds with no client attached, (2) on a restart before the mail runs, (3) when the reaper fires between `running` clearing and the queue drain.
- **Round 4 re-check against the merged reaper fixes** (`8d4597bf8e`, `1ec78a0dcc`, `c843eea710`, all in this branch):
  - **Case 3 is fixed.**
    - A detached idle session that still holds a queued prompt is not reaped. The reaper re-arms for up to `_WS_ORPHAN_QUEUED_MAX_POLLS = 30` grace periods, about 10 minutes, and resets the budget whenever a turn runs or the queue drains (`tui_gateway/session_lifecycle.py:938-955`; `tui_gateway/server.py:165`).
    - A leftover steer is queued before `running` is released (`_requeue_leftover_steer`, `tui_gateway/prompt_turn.py:438-447`, called from the release and again, as a no-op, in the follow-ups).
    - The drain sets `running` before clearing the queue head (commit message of `1ec78a0dcc`).
    - The idle-TTL and LRU reapers spare a session holding a queued prompt (`tui_gateway/session_reaper.py`, same commit).
  - **Case 1 stands:** a stale running turn is still interrupted, and the interrupt still clears the queue (`tui_gateway/session_lifecycle.py:709-713`).
  - **Case 2 stands:** queued rows are retired on the next resume after a restart.
  - **New, bounded case:** a queue that never drains for 30 grace periods is reaped, with a warning logged ("queued prompt never drained after %d grace periods — reaping", `session_lifecycle.py:957-960`). That bound is a reaper safety net, not a mail cap.
  - **Dispatcher changes in the same commits:**
    - only `status: "streaming"` counts as a started turn; any other submit result is an error (`scripts/dashboard_dispatch.py:124-130`);
    - a steer timeout is an error that says the text "may or may not have been steered", with no fallback to a second send (`:114-117`).
  - **Other hosts (round 4):** a CLI's `_pending_input` and the gateway's FIFO of pending events are in-memory too. A process exit loses mail queued there, and the outbox shows it as handed over with no reply. No redelivery (A3 stays dropped).

### Reply capture (finding 3)

- `post_llm_call` receives `session_id`, `task_id`, `turn_id`, `user_message` (the turn's original prompt), `assistant_response`, `conversation_history`, `model` and `platform`. It does not fire for detached forks (`agent/turn_finalizer.py:453-479`).
- A steered mail appears only in `conversation_history`, as a `display_kind: "steer"` user row (`agent/prompt_builder.py:585-591`).

### Who counts as an "ended" sender (for SM-Q9)

- **"Ended" is a column pair**, `ended_at` and `end_reason` (`hermes_state_common.py:400-401`). `end_session` sets both; the first reason wins (`hermes_state_sessions.py:520-525`).
- **Ended does not mean finished for good.**
  - Every process close stamps it: a CLI exit writes `cli_close` (`hermes_cli/cli_shutdown.py:276`, `hermes_cli/cli_tui_runtime_mixin.py:469`), and there are also `tui_shutdown` and `ws_orphan_reap`.
  - The next real turn clears it again: `_reopen_if_finalized` (`tui_gateway/methods_prompt.py:593-609`) calls `reopen_session` (`hermes_state_sessions.py:562`).
- **No end reason reliably means "this run is over by design".**
  - `agent_close` is the generic close backstop: `AIAgent.close()` writes it for any session whose owner did not end the row first (`run_agent.py:1013-1017`). The code lists it among the recoverable, accidental reasons (`hermes_state_common.py:185-189`, `_RECOVERABLE_END_REASONS`). That today's `agent_close` rows are subagents is a fact about the live data, not a rule.
  - A cron run ends as `cron_complete` (`cron/scheduler.py:2167`) or as `cron_incomplete_no_output` (`:2172`).
  - Oneshots record `cli_close`, the same reason an interactive CLI session gets when its terminal exits.
- **The session source says who the sender is.** `agent/agent_init.py:1266-1267` uses the `cron` and `subagent` platforms. Live counts (read-only `select source, count(*) from sessions group by source`, 2026-11-09):

  | Source | Sessions |
  |---|---|
  | `cron` | 96 |
  | `cli` | 9 |
  | `desktop` | 9 |
  | `oneshot` | 6 |
  | `subagent` | 6 |
  | `tui` | 4 |

  The owner sessions and `Home` are `cli`. 8 of the 9 `desktop` sessions are subagent windows opened from the desktop app (titles start with "Subagent:"). The source does not mark them as subagents.
- **Live end state (read-only, 2026-11-09):**
  - 3 of the 6 project owner sessions are "ended" right now: Minecrafting and Budgeting Orchestrators and "Model Master", all `cli_close`. So is every oneshot.
- So a plain `ended_at` test would stop replies from waking half of the owner sessions, and no end-reason list is reliable. A test on the sender's source avoids both problems.

### Tool list of a resumed session (new open point, settled by code)

- **A fresh agent builds its tools from current config.** The dashboard builds a new agent on resume after a restart (`tui_gateway/agent_callbacks.py:414`, `_load_enabled_toolsets("tui")`; `tui_gateway/server.py:2048-2090`).
- **A plugin toolset is on by default.** It is enabled unless it is default-off or already "known" for the platform and missing from the saved list (`hermes_cli/tools_config.py:510-517`). The live config saves an explicit `platform_toolsets.cli` list (`<hermes-home>/config.yaml`), and plugin toolsets are added on top of a saved list (`hermes_cli/tools_config.py:595-610`).
- **The session's pinned tool list keeps its order, and new tools are appended.** Each session row stores its tool list (`tool_names`; `agent/conversation_loop.py:696-714`). `restore_agent_tool_prefix` folds the fresh build onto that pin: "deregistered tools drop, new tools append". It then persists the merged list (`tools/mcp_tool_agent.py:204-248`).
- The stored system prompt is reused when model, provider, session id and working directory match (`agent/conversation_loop.py:883-910`).
- **So existing owner sessions get `session_message` after the deploy restart.** The tool list heads every request, so each resumed session pays **one prompt-cache miss**, then is stable. The deploy also changes the code identity that the pin records (`tools/mcp_tool_agent.py:161-167`). So the restart already re-derives tool definitions, and the new tool adds to a miss the deploy causes anyway.
- The stored system prompt is not rebuilt, so it does not mention the tool. Only the tool's own description explains it. **Verify in Trial** that a session created before the plugin was enabled lists and calls the tool after a restart.

### What the phone shows (finding 4)

- Hermes Mobile shows user rows only from REST history (`data/remote/HermesApiService.kt:221-234`). It fetches on open, on return to the foreground, and every 30 seconds, but skips the fetch while a turn runs (`ChatViewModel.kt:7146-7157`, `ChatScreen.kt:315-325`). So mail appears 0–30 seconds after the turn it joined ends.
- Queued mail from another client is never shown as queued. It is an ordinary user bubble with a double tick (`fullbleed/FullBleedTurns.kt:131-134`; `UserBubble.kt:106-114`).
- The app reads `display_kind` (`data/model/SessionMessagesResponse.kt:59`) and treats `steer` as a user turn (`ui/chat/ChatListEntries.kt:40`). It strips a leading `[OUT-OF-BAND USER MESSAGE …]` (`ui/chat/ChatTranscriptMerge.kt:17-39`) and draws no badge.
- No sender field is read. Bubbles are plain text, so `📨` shows literally (`UserBubble.kt:118-137`).
- **Net:** every mail looks like a message Alex typed. Only the header line marks it.

### Plugin API

- `register_tool(..., check_fn=…, is_async=…)` (`hermes_cli/plugins.py:456`) and `register_cli_command` (`:633-645`, used by `plugins/model-routing/__init__.py`).
- The hooks `post_llm_call` and `transform_llm_output` are in `VALID_HOOKS` (`hermes_cli/plugins.py:109-205`).
- `inject_message` only queues, in-process only (`tui_gateway/plugin_inject.py:24-64`). Not used.

### Addressing data

- Titles are unique (`hermes_state_schema.py:135`). `resolve_session_by_title` prefers a `"<title> #N"` continuation (`hermes_state_titles.py:194-210`); the exact lookup is `get_session_by_title` (`:186-192`).
- The compression tip is `get_compression_tip` (`hermes_state_compression.py:779-783`). Id prefixes resolve with `resolve_session_id` (`hermes_state_sessions.py:942`).
- Projects live in `projects.db` (`hermes_cli/projects_db.py:23-36`). There is no owner column. DER-686's `owner_session_id` exists only as documents on `origin/integrate/project-centric-ui`.
- **Live:** five projects have a `<Project name> — Orchestrator` owner, named after the project name, not its slug. Model Testing's owner is titled "Model Master". `Home` exists as an exact title.

## Assumptions (now explicit)

A1 and A3 were dropped in round 2. They covered the dashboard-only worker and redelivery.

- **A2.** There is one shared copy of the steer → queue → start rule (`_rpc`, `_deliver` and the resume step). Two ways to share it are listed in the options map. The architect picks one.
- **A4.** The plugin resolves the sender from the calling session, never from model input. A CLI send names itself with `--from`, or defaults to `cli`. A CLI sender has no session, so its reply is stored in the outbox and read with the CLI's `status` command (round 5: `hermes intercom status <id>`, not `hermes session-mail status`).
  - *(Round 5)* Intercom today names the sender by its endpoint name, `self_meta()` (`__init__.py:94-100`). That must become the calling **session**: the `session_id` keyword the tool handler receives (`model_tools.py:875`), and its title.
- **A5.** The header goes at the very start of the text, so on the phone it is the first visible line. *(Round 5: this is intercom's header line, reworded per SM-Q7.)*
- **A6.** Mail never uses `display_kind: "hidden"` (`tui_gateway/methods_prompt.py:743`).
- **A7.** No mail is dropped for repetition (settled decision 5).
- **A8** *(round 4)*. A process delivers only to sessions it hosts now:
  - the CLI to its own `session_id`;
  - a `tui_gateway` process (dashboard or Ink TUI) to its live `_sessions`;
  - the gateway to sessions its session store knows (`lookup_by_session_id`).

  Two processes never deliver the same mail: claiming is one atomic update of the outbox row.

  *(Round 5: still true, but the hosting process is reached through its intercom socket, which the registry names per session. "Claiming" an outbox row is superseded: the sender connects to the host's socket and gets the receipt back.)*
- **A9** *(round 4)*. Mail for a session that no process claims goes to the dashboard. The dashboard resumes the session and starts a turn there, using the dispatcher's rule (A2) or the seam after an in-process resume. If no dashboard runs, the mail waits in the outbox; that is not a hold, since nothing could deliver it. *(Round 5: kept. The dashboard's intercom socket takes mail for a session with no live registry entry. Mail waiting with no dashboard is delivered when the dashboard's socket comes up and reads the outbox.)*
- ~~**A10** *(round 4)*. The poller's interval is short enough to count as "right away"…~~ *(Superseded in round 5: there is no poller.)* Sends are synchronous over the socket: the tool and the CLI get the receipt (requested and applied mode, or the error) at once, as intercom's `send` does today (`inbox.py:490-538`).

## Options map

### SM-Q12 (round 4; answered in round 5: option d): what to build on

| Option | What it would be now | Fork cost | Rebase picture | Fit with Alex's rules |
|---|---|---|---|---|
| **(d) Our fork of `majordave/hermes-intercom` — chosen by Alex (round 5)** | Intercom's tool, sockets, registry, UID check, receipts, forgery defence and ask/reply, extended:<br>• one registry entry per live session in the dashboard, TUI and desktop processes;<br>• gateway hosting;<br>• delivery through the seam with interrupt, steer and queue;<br>• addressing through `state.db`;<br>• the outbox;<br>• automatic replies, with the caps removed;<br>• a CLI command.<br>The garbage-collector lookup and private-field delivery stay only as the fallback when the seam is missing | The plugin lives in its own repo (shared upstream), vendored into the Hermes fork (SM-Q14, asked elsewhere). The core seam is a small fork patch, the same as in (a). Intercom's ~1,800 lines grow by our features | The seam is the only core patch, the same as (a). At the v0.23 rebase, the miyu4u fork's unified-gateway transport is the prior art for CLI, TUI and desktop sessions | Plugin first, one small upstreamable seam, credit and history with the existing #81885 implementation. Its caps and its endpoint-per-process model must change. The ask/reply protocol is kept (SM-Q16) |
| **(a) Our own protocol** | Plugin (outbox, poller per process, addressing, replies, CLI) plus one core seam: `inject_message(mode="steer_or_queue")` in the three hosts (`hermes_cli/plugins_injection.py`, `tui_gateway/plugin_inject.py`, `gateway/run_plugin_injection.py` / `gateway/run_busy.py`). Each host reuses its own steer and queue code (CLI `cli_tui_mixin.py:1515-1532`, TUI `session_auto_continue.py:400-455`, gateway `run_busy.py:856-858`). Header-only framing (SM-Q7 A) | The seam only, in 3 host files plus tests (an estimate: low hundreds of lines). The rest is a plugin | The seam touches small host files on v0.22. Upstream has nothing in these spots yet. It is the same idea as closed #83661, so it is offerable upstream on #81885 / #103748 | Plugin first, one small upstreamable patch. No caps. Reaches gateway sessions. Steered mail still sits inside the user marker (SM-Q7) |
| **(b) #106423 + #136861 (+ the fixes from the closed fork pull request) as the base, ours on top** | Their mailbox and per-request drain as the bus and the running-session delivery in every host, with their peer frame (`[PEER SESSION MESSAGE — … not from the user …]`). Our seam only for **waking** idle sessions in each host. Our outbox (record, replies, `status`), addressing, CLI and footer. Caps removed (50-file inbox, 8,000-character body). Discovery widened beyond "recent and not ended" | Carry roughly +1,100/−150 lines of unmerged core code (+470 base, the rebase changes, about +595/−153 fixes) across `tools/`, `agent/prompt_builder.py`, `agent/turn_iteration_prep.py`, `agent/context_compressor.py` and desktop TypeScript. Ported **back** from `main` to our v0.22 base. Plus our cap removal as a patch on their patch, plus the seam | Large conflicts are likely at the v0.23 rebase, and again whenever upstream merges a different version (none of the three is mergeable now; no maintainer position). If upstream merges it as is, most of the carried code disappears, but its caps come back | A new core toolset, against "plugin first" and the "new core tool" rubric. Brings the peer frame Alex wanted for steered mail. No wake, no replies, capped: the parts we need most are still ours |
| **(c) Wait for upstream** | Nothing now; adopt what lands | None | None until something merges | Nothing upstream wakes idle sessions, gives replies, or drops caps, and #123218 excludes gateway sessions by design. Waiting delivers less than Alex asked for, at an unknown date |

### Round 4: delivery through each host (inside option a or b; round 5: now inside option d, and each "seam →" cell takes the requested mode; see "Round 5: delivery modes per host")

| Path | Running target | Busy, cannot steer | Idle, live in this process | Live nowhere |
|---|---|---|---|---|
| Dashboard / desktop / Ink TUI | seam → `AIAgent.steer` (as `session.steer` does) | seam → queued submit with an accept-time row | seam → drain, start a turn | dashboard poller resumes (A2 rule) and starts |
| Classic CLI | seam → `agent.steer` | seam → `_pending_input` (next turn) | seam → `_pending_input` starts a turn | — (it is then "live nowhere": dashboard) |
| Gateway | seam → the gateway's steer path for the running agent | seam → FIFO queue (today's internal-event path) | seam → `handle_message`, new turn in the chat | idle gateway sessions are "live" in the gateway store; the gateway starts the turn |

### A2: one shared copy of the delivery logic

| Option | What | Ugly part |
|---|---|---|
| **Move into an importable module** | Move `_rpc`, `_deliver` and the resume/start steps into a module the plugin imports (inside the plugin package, or a small fork module). `scripts/dashboard_dispatch.py` becomes a thin command-line wrapper over it, so existing skill commands keep working unchanged | Touches the script from `1516a52669` again. The module must not depend on the script's `sys.path` trick |
| **Run the script as a subprocess** | The tool, the CLI and the reply thread run `<venv>/bin/python -I scripts/dashboard_dispatch.py --resume <id> --prompt-file <tmp>` and parse its JSON, the way the skills do | A process start per mail (Python plus the `websockets` import). A temporary prompt file. The plugin must find the install checkout and venv. Errors come back as exit codes and stderr text |

### Finding 1: how a mail is framed (kept as the record)

| Option | What | Ugly part | Status |
|---|---|---|---|
| **A. Header only** | The 📨 header and footer inside the text, on all three paths | A steered mail still sits inside the "direct message from the user" marker | **Recommended** (SM-Q7) |
| **B. A plus a plugin system-prompt section** | Adds "📨 text is from another session" | New sessions only; contradicts the core note | Not taken |
| **C. Fork patch: a frame chosen by the caller** | `session.steer` takes a frame kind; a separate peer marker | About 100 lines in core; a v0.23 rebase conflict; Mobile shows the new marker literally; separates steered mail only, since queued and started mail have no marker anyway | Dropped from this chunk. Reopen only if real models treat mail as Alex's words |
| **D. Upstream's peer frame** *(round 4)* | The `[PEER SESSION MESSAGE …]` marker and `display_kind="peer_message"` from the fixes on top of #136861 | Comes only with SM-Q12 (b). Separates steered mail only, like C | Recorded; depends on SM-Q12 |

### Finding 3: which text is the reply when a turn holds more than one message

| Option | What | Ugly part |
|---|---|---|
| **1. Whole final answer to every sender in the turn** | Literal decision 4 | Alex's own long answers get mailed to agents and wake them |
| **2. Marked reply block, with the whole answer as a fallback** | The footer asks for `[REPLY <id>] … [/REPLY]` or `[SILENT]` | Relies on the model following the footer |
| **3. The target replies with the tool** | The footer says "reply with `session_message`" | Extra tool turns; contradicts the sketch |

## Questions for Alex

❓ **SM-Q7** — **How should mail be framed?** Hermes wraps a steer as `[OUT-OF-BAND USER MESSAGE — a direct message from the user …]`, with "the same authority" as you, and the caller cannot change that. Queued and started mail arrive as ordinary user turns with no marker at all. So on every path, the 📨 header (`Message from session "X" (not Alex)`) is what tells the model and you that it is not you. Choices:
- A, header only, on all three paths;
- C, a fork patch giving steered mail its own frame.

➡️ A on all three paths. Drop C from this chunk, and reopen it only if real models act on mail as if you had said it.

*Round 4 re-check:* the wider scope does not change this.
- A CLI steer and a gateway steer go through the same `AIAgent.steer` and the same user marker.
- Queued mail on the CLI (`_pending_input`) and on the gateway (an internal event) becomes an ordinary user turn.

The one change: if you pick SM-Q12 (b), steered mail gets upstream's peer frame (option D) for free. That would not cover queued or started mail.

*Round 5 re-check (intercom base; SM-Q12 went to intercom, so D is out):* intercom has its own frame, `📡 hermes@<endpoint-name> says:` and the body. Its v3 dropped the earlier "NOT by the user" wrapper (`docs/AGENTS.md`, v3). It names a process endpoint, not a session, and it does not say the mail is not from you. Choices:
- A′, header only, in intercom's style: keep the `📡` header line, but make it name the sender session and say it is not you, for example `📡 hermes@<session title> (session <id>, not Alex) says:` or `📡 INTERCOM from <session title> · not Alex`. Add our footer. Keep intercom's zero-width-space forgery defence and echo stripping, and update the echo regex to match;
- keep intercom's v3 frame unchanged.

➡️ A′. It is the same decision as A, in intercom's form. Intercom's current header carries neither the sender session nor "not you", and the footer carries the no-empty-replies rule. Interrupt and queued deliveries become ordinary user turns, like the rest, so the header stays the only separation on every path.

---

❓ **SM-Q8** — **Which text is the reply when a mail shares a turn?** A steered mail often joins one of your turns, and queued mails can merge with other queued text. Choices:
- 1, send the whole final answer to every sender in that turn;
- 2, the footer asks for a `[REPLY <id>] … [/REPLY]` block per mail (or `[SILENT]`); the plugin sends only that block, falling back to the whole answer;
- 3, the target replies with the tool.

➡️ 2. The reply stays automatic and comes from the final answer, and your own long answers are not mailed to agents.

*Round 5 re-check (intercom base):*
- Intercom already has option 3 in its own form: `ask` plus an explicit `reply` with the `request_id` (`inbox.py:599-607`).
- Option 2 still holds for automatic replies. The `[REPLY <id>]` block takes intercom's `request_id`, or our mail id, as its id.
- An `interrupt` delivery makes the mail its own turn, so its final answer is the reply, with no block needed. The block still works there.
- How `ask` and `reply` live next to automatic replies is SM-Q16.

---

❓ **SM-Q9** — **Should a reply wake an agent sender whose run is over?** A cron run, a oneshot or a subagent that sent mail has usually finished by the time the reply arrives. Waking it resumes that transcript in the dashboard and starts a turn nobody reads. "Ended" is not a usable test:
- `ended_at` is stamped on every process close and cleared on the next turn, and 3 of your 6 owner sessions are "ended" right now (`cli_close`);
- `agent_close` is a generic backstop that the code treats as recoverable;
- cron runs can end two ways (`cron_complete`, `cron_incomplete_no_output`).

The sender's session source answers it directly. Choices:
- (a) always wake the sender (decision 4 as written);
- (b) store the reply in the outbox only when the sender's source is `cron`, `subagent` or `oneshot`, and wake every other sender per decision 4. Owner sessions are `cli`, so a closed terminal never stops their reply. Subagent windows opened from the desktop app have source `desktop`, so they would still be woken;
- (c) use `ended_at` alone. Not recommended: it would stop replies from waking half the owners.

➡️ (b). It is a test on who the sender is, not a hold or a limit. A cron job or a oneshot that needs the answer to act on can address its owner session instead.

*Round 4 re-check (gateway senders):* a messaging-gateway session stores the platform name as its source (for example `telegram`; `gateway/session_recovery.py:173`, `gateway/slash_commands_session.py:792`). It is not in the list, so it is woken, in the same Telegram topic: the gateway starts the turn in that chat and the answer is posted there. That is what the Telegram-topics use case on #81885 asks for. A classic CLI sender in its own terminal is source `cli` and is woken by its own process if it is still open. If not, the dashboard wakes it.

*Round 5 re-check (intercom base):* unchanged. Two notes:
- A reply is mail like any other, so it is delivered with the default `steer` mode. A reply never interrupts the sender unless the replying session asks for `interrupt` explicitly.
- Intercom's blocking `ask` has one more sender case: a sender still waiting inside its tool call gets the reply as the tool result, not as a wake. See SM-Q16.

---

❓ **SM-Q10** — **How should `@model-testing` resolve before DER-686 lands?** Five projects follow `<Project name> — Orchestrator`, but Model Testing's owner is titled "Model Master". Choices:
- refuse `@model-testing` until DER-686 ships;
- rename the session to "Model Testing — Orchestrator";
- add an alias map in the plugin's `config.yaml` entry.

➡️ Rename the session (a one-line `/title`, no code). DER-686 replaces the title rule later.

*Round 5 re-check (intercom base):* unchanged. Intercom's own names (`<profile>-<cwd folder>-<pid>`) cannot name an owner session that is not live, so the `@project` rule goes through `state.db` either way.

---

❓ **SM-Q11** — **Is "looks like you typed it" acceptable on the phone for v1?** Every mail is a bubble in your colour with a double tick, appearing 0–30 seconds after the turn ends, marked only by its 📨 first line.

➡️ Yes, accept it for v1. No Hermes Mobile issue in this chunk; it can be offered once the plugin runs.

*Round 4 re-check:*
- **Terminal sessions** would show mail like typed input that was queued or steered, if the seam reuses the CLI's typed-input routine: that routine prints a "steered" or "queued for next turn" line with a preview (`hermes_cli/cli_tui_mixin.py:1527-1534`).
- **Telegram** is different: the mail is **not shown in the topic at all**. Only the target's answer is posted, including any `[REPLY …]` block markers from SM-Q8; a bare `[SILENT]` answer is suppressed. That is a separate decision: see SM-Q15. For the phone app, the answer above stands.

*Round 5 re-check (intercom base):*
- **Phone:** the bubble's first line becomes intercom's header (SM-Q7 A′) instead of the 📨 one. Everything else stands.
- **Interrupt:** an `interrupt` delivery on the dashboard redirects or stops the turn Alex may be watching. The phone shows that like any redirect, with nothing marking that a mail caused it beyond the header in the next user bubble. That is accepted by Alex's delivery-modes decision; the tool description limits interrupt to intent.

---

❓ **SM-Q12** — **Build on our own protocol, on upstream's peer messaging, or wait?** ✅ **Answered by Alex (2026-11-09 ~20:00), with a fourth option: (d) build on our fork of `majordave/hermes-intercom`** ("I want us to make a fork of intercom, add to their code and post the update in the issue above"). Recorded as decision 12; the options table above keeps (a) to (c) as the record. The round-4 text below is kept as asked.

*Round 4 text:* Upstream has three open, unmerged pull requests: #106423 by a maintainer, #136861 rebasing it, and #123218 adding replies and acknowledgements. They steer mail into a **running** session in every host (CLI, TUI, dashboard, gateway) from a file mailbox. They do **not** wake idle sessions, have no automatic replies, and cap the inbox at 50 and the body at 8,000 characters. #123218 also refuses Telegram and other gateway sessions. The fixes that stop mail being lost, looking like you, or landing in the wrong turn sit in a fork pull request that was closed unmerged. Choices:
- (a) **Our own protocol:**
  - our outbox, a light poller in each process, addressing, replies, CLI, header framing;
  - one small seam (`inject_message(mode="steer_or_queue")`) in the CLI, gateway and TUI/dashboard hosts, which also does the wake.

  Fork cost: the plugin plus the seam (a few hundred lines in three host files).
- (b) **Upstream's mailbox as the base:**
  - carry #106423 + #136861 + those fixes (about 1,100 lines of core code, ported back from `main` to our v0.22) as the bus and the delivery into running sessions, with its peer frame;
  - add our seam for waking idle sessions, our outbox and replies, addressing and CLI, and remove its caps.

  Bigger fork, a new core toolset, likely conflicts at the v0.23 rebase and whenever upstream merges something different.
- (c) **Wait for upstream:** nothing merged, no maintainer position, and nothing there wakes, replies or reaches Telegram.

➡️ **(a)**, built so it can sit on top of upstream later:
- keep our seam's shape close to #83661 and the "Wake" policy in #81885;
- keep the outbox format separate from the delivery path, so that if upstream merges peer messaging, its mailbox can replace our poller for running sessions without changing the tool, the replies or the CLI.

(b) would carry about 1,100 lines of someone else's unmerged code, and the parts you asked for most (wake, replies, no caps, Telegram) would still be ours. Revisit at the v0.23 rebase.

---

❓ **SM-Q13** — **Which bot sessions are in?** *Answered by the scope change (2026-11-09):* messaging-gateway sessions and the default profile's `Bot Chat` are in. Bots in other profiles stay out, because that is cross-profile. Recorded under Decisions (10).

---

❓ **SM-Q14 (asked elsewhere): deploy method.** Asked of Alex by the "Session Messaging" session, not by this brief. The recommendation there: vendor `alexderz/hermes-intercom` into Alex's Hermes fork as `plugins/intercom` with `git subtree`, so rule 19 holds (no side repos or symlinks into the plugins folder). Recorded here only so the ID is not reused.

---

❓ **SM-Q15** *(was SM-Q14 in round 4; renumbered in round 5)* — **Should mail to a Telegram session also show in its topic?** Injected mail enters the gateway as an internal event, so the topic shows only the target's answer, out of nowhere, and you do not see what the agent was asked or by whom. The Telegram-topics comment on #81885 asks to "show the exchange in the topics". Choices:
- (a) answer only (today's behaviour, no extra code);
- (b) before the turn starts, post the 📨 header and the body into the topic as a bot message, through the same adapter (one send per mail).

➡️ (b). Telegram is one of your phone surfaces, and without it a gateway session's chat reads as the bot talking to itself. It is one adapter send, and it needs no change to how the turn runs.

*Round 5 re-check:* unchanged by the intercom base. The posted text is intercom's header (SM-Q7 A′) and the body.

---

❓ **SM-Q16** — **What happens to intercom's blocking `ask` and explicit `reply`, now that replies are automatic?**
- **Today:** intercom's `ask` holds the sender's tool call for up to 600 s by default (3,600 s max) until the target calls `intercom(action="reply", request_id=…)`. The correlation lives only in the asking process's memory, so it is lost on restart. Our design makes every reply automatic: the target's final answer (its `[REPLY]` block) goes back as new mail and wakes the sender.
- **The conflict:** keeping both as they are gives two reply paths. A target could answer twice, once with the `reply` action and once through the automatic reply, or a waiting `ask` could miss an automatic reply.

Choices:
- (a) keep `send`, `ask` and `reply` as they are, and add automatic replies only for `send`;
- (b) keep all three actions for upstream compatibility, but route everything through one reply path:
  - an automatic reply resolves a waiting `ask` as its tool result;
  - if the sender is no longer waiting, the reply is delivered as mail;
  - `reply` becomes an explicit way to send the same reply early;
  - the outbox records each reply once;
- (c) drop `ask` and `reply`; every message is `send`, and replies are automatic only.

➡️ (b). It keeps intercom's existing protocol and tests, which the upstream offer relies on. It gives each mail exactly one reply, and an orchestrator that wants a synchronous answer can still `ask`. The ask timeout is a wait on one tool call, not a cap on messages.

## Open (cannot be settled by reading)

- **Real models and a 📨 header inside the out-of-band user frame.** The Trial's fake model cannot show this. Real use can, and it is the trigger for reopening SM-Q7 option C.
- ~~**The reaper race at turn end**~~ *(closed in round 4 by `8d4597bf8e` and `1ec78a0dcc`; see finding 2).*
- *(Round 4, reshaped in round 5)* **The seam's exact shape:**
  - `inject_message(..., mode="interrupt"|"steer"|"queue")` with fallback, returning the applied mode (Alex: the host falls back instead of returning False).
  - How the gateway steers or interrupts for an internal event. `run_busy.py:843-849` deliberately queues internal events because "plugin events carry untrusted payload text", so the seam must keep that security split: mail is never treated as a gateway control command (`allow_gateway_control=False`).
  - How the dashboard picks redirect versus a hard interrupt for a compute-host turn.
- ~~*(Round 4)* **Poller wake-up**~~ *(superseded in round 5: no poller; intercom's sockets push).* What replaces it: the cost of one listening socket thread per process, which is intercom's existing design.
- *(Round 5)* **One registry entry per live session in a `tui_gateway` process:** written when a session goes live and removed when it is reaped or closed. It must stay right across compression, which rotates the session id, and across the reaper's park and unpark. Intercom today writes one entry per process at plugin load. **Verify in Trial.**
- *(Round 5)* **The fallback without the seam:** what the plugin does on a Hermes build without the seam (feature detection). It should be intercom's current CLI-only behaviour, plus refusal (not silent parking) for dashboard, TUI and gateway targets, so mail never lands in the wrong session through the process-wide `pre_llm_call` drain.
- *(Round 4)* **The dashboard as the "live nowhere" host** needs a dashboard-only start point again: the `dashboard/plugin_api.py` import, or a check for the dashboard's injector install. Round 1 left this open, and the refiner removed it with the worker. *(Round 5: it is still needed, to know which intercom socket takes mail for sessions that are live nowhere.)* **Verify in Trial.**
- *(Round 4)* **Gateway routing for an idle session:** whether `lookup_by_session_id` finds every gateway session a title or id can name, including after compression rotates the session id. The live install has no gateway sessions, so **verify in Trial**.
- *(Round 4)* **Whether injected gateway turns are stored with the `internal_notification` kind**, so a bare `[SILENT]` reply is suppressed rather than posted. **Verify in Trial.**
- **Mail to a session that is running the caller's own turn** (self-mail, or a reply to a session whose turn is finishing) over the loopback socket. It looks safe in the code, but was not traced line by line. *(Round 5: intercom refuses a target in the same process today; the change to refuse only the same session makes this case reachable, so the Trial must cover it.)*
- **How long a start holds the sender's tool call** for an idle target whose agent must be built. This is measured in the Trial.

## Verify later (how we would know the build matches this brief)

- **Steer:** mail into a running turn returns `steered` to the sending tool, and the target's transcript has a separate user row starting with the 📨 header.
- **Queue and start:**
  - mail into a busy session that cannot steer returns `queued` and runs after the turn without interrupting it;
  - mail into an idle session that is not loaded returns `started`, and the turn runs in the dashboard;
  - ~~no delivery produces a redirect or an interrupt~~ *(round 5: true for `steer` and `queue`; see the delivery-mode checks below).*
- ~~**Send-time delivery from all three callers**~~ *(superseded in round 4 by the poller checks below; the loopback-socket part remains for the dashboard waking a session that is live nowhere).*
- *(Round 4)* **Every host delivers by the same rule:**
  - mail into a running classic CLI turn is steered, and the turn is **not** interrupted (today's `inject_message` would hard-interrupt it);
  - mail into an idle CLI starts a turn there;
  - the same steer, queue and start checks pass for an Ink TUI process and for a gateway session with a test adapter;
  - mail into an idle gateway session starts the turn in that chat, and the answer is posted there.
- *(Round 4)* **One claimant:** with the dashboard, a CLI and a gateway all running, each mail is delivered exactly once, by the process that hosts the target. A mail for a session that is live nowhere is woken by the dashboard.
- *(Round 4)* **Gateway sender:** a reply to a mail sent from a Telegram session wakes that session in its topic (SM-Q9).
- *(Round 4, SM-Q15 option b)* **Telegram shows the exchange:** the 📨 header and body appear in the target's topic before its answer.
- *(Round 4)* **Idle cost:** with no mail, a CLI or TUI process shows no measurable extra CPU ~~from the poller~~ *(round 5: from intercom's socket thread)*.
- **Errors are returned, not held:** a `SESSION_NOT_OWNED` target returns the error to the sender, and the outbox records it.
- **Replies:**
  - a reply returns to the sender by the same rule;
  - `[SILENT]` or an empty answer sends nothing, and the outbox records "silent";
  - a two-session debate runs several rounds and stops only at `[SILENT]`;
  - a mail steered into a long unrelated turn returns only its `[REPLY <id>]` block (SM-Q8 option 2).
- **Unwakeable senders (SM-Q9 option b):** a reply to a sender whose source is `cron`, `subagent` or `oneshot` is stored and wakes nothing, whatever its end reason (`cron_complete`, `cron_incomplete_no_output`, `agent_close`, `cli_close`, or none). A reply to an owner session (source `cli`) whose terminal was closed (`cli_close`) wakes it.
- **Existing sessions get the tool:** a session created before the plugin was enabled lists and calls `intercom` *(round 5; was `session_message`)* after a dashboard restart, and pays one cache miss on its first turn, not one on every turn.
- **Addressing:** `@hermes-improvement`, an exact title, an id prefix and `Home` each resolve to the compression tip after `/compress`. An ambiguous title is refused with the candidates.
- **Outbox and CLI:**
  - every send records sender, target, body, requested and applied mode *(round 5)*, reply and timestamps, with no hop column;
  - `send`, `list` and `status` run without starting a turn;
  - a CLI sender reads its reply with `status`.
- **Phone:** after the turn ends, the mail shows on Hermes Mobile as a bubble whose first line is the header (round 5: intercom's header, SM-Q7 A′).
- **No caps, no retries:** the plugin has no hop, rate, duplicate or daily cap, and no retry loop or give-up timer. *(Round 5: intercom's 6-per-minute rate limit, 120-second duplicate refusal, 10-message pending cap and 8,000-character body cap are gone. A test sends 20 identical messages in a minute and all 20 arrive.)*
- *(Round 5)* **Delivery modes on every host** (dashboard or TUI, classic CLI, gateway with a test adapter):
  - `delivery` omitted → `steer` is requested and applied into a running turn;
  - `steer` into a target that cannot steer → `queue` is applied, and the receipt says so;
  - `interrupt` → redirect where the host supports it, else a hard interrupt with the mail as the next turn; on a host where interrupt is unsupported → `steer`, else `queue`;
  - an idle target starts a turn for every mode;
  - the outbox shows requested and applied mode for each case;
  - the tool description contains Alex's sentence on interrupt.
- *(Round 5)* **Many sessions in one process:**
  - two dashboard chats can mail each other;
  - mail addressed to dashboard chat A never lands in chat B: no process-wide `pre_llm_call` drain;
  - after `/compress`, the registry entry follows the new session id.
- *(Round 5)* **Intercom compatibility:** intercom's existing 17 protocol tests still pass, except where a test asserts a removed cap (those change with the cap). `ask` gets an automatic reply as its tool result, and an explicit `reply` and an automatic reply never both deliver for one mail (SM-Q16 option b).
- *(Round 5)* **Seam detection:** on a Hermes build without the seam, the plugin keeps intercom's CLI-only delivery, and refuses dashboard, TUI and gateway targets with a clear error instead of parking them.
- *(Round 5)* **Upstream drafts exist and were not posted:** an update for #81885 (and, if chosen, a pull request text for `majordave/hermes-intercom` and for the seam) sits in `docs/` on the intercom branch, marked for Alex's review. Nothing was posted by an agent.
