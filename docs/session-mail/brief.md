# Brief: session-mail (DER-701), session-to-session messaging

Step: Brief (gatherer), round 4, after a scope change from Alex. Date: 2026-11-09.

Source dump: the request `requests/2026-11-09-session-mail-brief.md` in the Hermes Improvement vault (Alex's words, settled decisions 1–8, and the section "Scope addition (Alex, 2026-11-09 ~19:45)"), the research note `research/session-messaging.md`, and vault rule 19.

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
- **Questions:** new SM-Q12 (build on our own protocol or on upstream's) and SM-Q14 (show mail in the Telegram topic). SM-Q13 is recorded as answered. SM-Q7, SM-Q9 and SM-Q11 are updated for the wider scope.

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
- Posting anything to GitHub. The upstream offer on #81885 is a later step, with Alex reviewing the text.
- Changes to Hermes Mobile, including drafting an upstream issue for it in this chunk (that can be offered after the plugin runs).
- A core patch for the steer frame (SM-Q7 option C, dropped from this chunk).
- A "Mail" tab on the dashboard, and a plugin system-prompt section.
- Landing DER-686's `projects.owner_session_id`. This chunk only reads it once it exists.

## Constraints

- **Fork-bundled plugin, plus one small, upstreamable core seam** *(round 4)*. Decision 1 allows a core patch when a real blocker is shown and Alex agrees. The scope addition shows one: no host can steer or wake through the plugin API (see "How each host handles injected text today"). The seam is a delivery mode on `ctx.inject_message`, for example `mode="steer_or_queue"`, honoured by the CLI, gateway and TUI/dashboard hosts. It is listed in PROJECT.md as a fork patch, kept small and upstreamable (vault rules). Round 1 said "no core patch"; that is superseded.
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
- Question IDs continue the series. This brief uses SM-Q7 to SM-Q14.

## Decisions (settled by Alex; not reopened)

1. A fork-bundled plugin `plugins/session-mail`, shaped like the in-fork `plugins/model-routing/` (`plugin.yaml`, and `__init__.py` with `register(ctx)`).
2. Addressing: `@<project-slug>` resolves to the project owner; also an exact title, a session id, or `Home`. The result resolves to the compression tip. An ambiguous match is refused, and the candidates are listed.
3. Delivery right away: steer, else queue, else start. Never cancel or redirect. No hold.
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
8. A CLI, `hermes session-mail send …`, costs no turn.
9. *(Round 4, scope addition.)* Every kind of session is a target: dashboard and desktop, classic CLI, Ink TUI, and messaging-gateway sessions. Cross-machine and cross-install delivery stays out (SM-Q6).
10. *(Round 4, SM-Q13, answered by the scope change.)* Bot sessions in scope:
    - the messaging-gateway sessions;
    - the default profile's `Bot Chat`.

    Bots in other profiles stay out, because that is cross-profile.
11. *(Round 4, scope addition.)* One small core seam is allowed under decision 1's exception: a steer-or-queue delivery mode on `ctx.inject_message`, honoured by each host. It goes in PROJECT.md as a fork patch.

Design choices taken from the research and the refiner, which the code supports:

- **Outbox plus a poller in every process** *(round 4, scope addition; supersedes "delivery at send time" below for every target that is live somewhere)*:
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
- **Header only on all three paths** (SM-Q7 recommendation A). The 📨 header and footer are the only separation from Alex's words.
- **Outbox fields:** id, in-reply-to id, sender, target, body, delivery result, reply (or "silent"), timestamps. There is no `hop` column (nothing reads it, and a counter invites a cap) and no status ladder.
- **Reply matching** finds the mail id anywhere in the turn's new rows: the `user_message`, or `display_kind: "steer"` rows in `conversation_history`. That covers every path:
  - an accepted steer;
  - a steer parked during compression;
  - a leftover steer that was requeued as plain text;
  - a queued prompt merged with other text.

## Environment facts

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
- **The injected text is not shown in the Telegram chat.** It enters as an internal `MessageEvent`, not as a chat message; only the turn's answer is sent through the adapter. This is read from the dispatch path above; **verify in Trial**. See SM-Q14.

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
- **A4.** The plugin resolves the sender from the calling session, never from model input. A CLI send names itself with `--from`, or defaults to `cli`. A CLI sender has no session, so its reply is stored in the outbox and read with `hermes session-mail status <id>`.
- **A5.** The 📨 header goes at the very start of the text, so on the phone it is the first visible line.
- **A6.** Mail never uses `display_kind: "hidden"` (`tui_gateway/methods_prompt.py:743`).
- **A7.** No mail is dropped for repetition (settled decision 5).
- **A8** *(round 4)*. A process delivers only to sessions it hosts now:
  - the CLI to its own `session_id`;
  - a `tui_gateway` process (dashboard or Ink TUI) to its live `_sessions`;
  - the gateway to sessions its session store knows (`lookup_by_session_id`).

  Two processes never deliver the same mail: claiming is one atomic update of the outbox row.
- **A9** *(round 4)*. Mail for a session that no process claims goes to the dashboard. The dashboard resumes the session and starts a turn there, using the dispatcher's rule (A2) or the seam after an in-process resume. If no dashboard runs, the mail waits in the outbox; that is not a hold, since nothing could deliver it.
- **A10** *(round 4)*. The poller's interval is short enough to count as "right away" (seconds, not minutes). The tool returns once the mail is in the outbox. The delivery result (`steered`, `queued`, `started`, error) is filled in by the host and readable with `status`. The architect may let the tool wait briefly for the claim.

## Options map

### SM-Q12 (round 4): what to build on

| Option | What it would be now | Fork cost | Rebase picture | Fit with Alex's rules |
|---|---|---|---|---|
| **(a) Our own protocol** | Plugin (outbox, poller per process, addressing, replies, CLI) plus one core seam: `inject_message(mode="steer_or_queue")` in the three hosts (`hermes_cli/plugins_injection.py`, `tui_gateway/plugin_inject.py`, `gateway/run_plugin_injection.py` / `gateway/run_busy.py`). Each host reuses its own steer and queue code (CLI `cli_tui_mixin.py:1515-1532`, TUI `session_auto_continue.py:400-455`, gateway `run_busy.py:856-858`). Header-only framing (SM-Q7 A) | The seam only, in 3 host files plus tests (an estimate: low hundreds of lines). The rest is a plugin | The seam touches small host files on v0.22. Upstream has nothing in these spots yet. It is the same idea as closed #83661, so it is offerable upstream on #81885 / #103748 | Plugin first, one small upstreamable patch. No caps. Reaches gateway sessions. Steered mail still sits inside the user marker (SM-Q7) |
| **(b) #106423 + #136861 (+ the fixes from the closed fork pull request) as the base, ours on top** | Their mailbox and per-request drain as the bus and the running-session delivery in every host, with their peer frame (`[PEER SESSION MESSAGE — … not from the user …]`). Our seam only for **waking** idle sessions in each host. Our outbox (record, replies, `status`), addressing, CLI and footer. Caps removed (50-file inbox, 8,000-character body). Discovery widened beyond "recent and not ended" | Carry roughly +1,100/−150 lines of unmerged core code (+470 base, the rebase changes, about +595/−153 fixes) across `tools/`, `agent/prompt_builder.py`, `agent/turn_iteration_prep.py`, `agent/context_compressor.py` and desktop TypeScript. Ported **back** from `main` to our v0.22 base. Plus our cap removal as a patch on their patch, plus the seam | Large conflicts are likely at the v0.23 rebase, and again whenever upstream merges a different version (none of the three is mergeable now; no maintainer position). If upstream merges it as is, most of the carried code disappears, but its caps come back | A new core toolset, against "plugin first" and the "new core tool" rubric. Brings the peer frame Alex wanted for steered mail. No wake, no replies, capped: the parts we need most are still ours |
| **(c) Wait for upstream** | Nothing now; adopt what lands | None | None until something merges | Nothing upstream wakes idle sessions, gives replies, or drops caps, and #123218 excludes gateway sessions by design. Waiting delivers less than Alex asked for, at an unknown date |

### Round 4: delivery through each host (inside option a or b)

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

---

❓ **SM-Q8** — **Which text is the reply when a mail shares a turn?** A steered mail often joins one of your turns, and queued mails can merge with other queued text. Choices:
- 1, send the whole final answer to every sender in that turn;
- 2, the footer asks for a `[REPLY <id>] … [/REPLY]` block per mail (or `[SILENT]`); the plugin sends only that block, falling back to the whole answer;
- 3, the target replies with the tool.

➡️ 2. The reply stays automatic and comes from the final answer, and your own long answers are not mailed to agents.

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

---

❓ **SM-Q10** — **How should `@model-testing` resolve before DER-686 lands?** Five projects follow `<Project name> — Orchestrator`, but Model Testing's owner is titled "Model Master". Choices:
- refuse `@model-testing` until DER-686 ships;
- rename the session to "Model Testing — Orchestrator";
- add an alias map in the plugin's `config.yaml` entry.

➡️ Rename the session (a one-line `/title`, no code). DER-686 replaces the title rule later.

---

❓ **SM-Q11** — **Is "looks like you typed it" acceptable on the phone for v1?** Every mail is a bubble in your colour with a double tick, appearing 0–30 seconds after the turn ends, marked only by its 📨 first line.

➡️ Yes, accept it for v1. No Hermes Mobile issue in this chunk; it can be offered once the plugin runs.

*Round 4 re-check:*
- **Terminal sessions** would show mail like typed input that was queued or steered, if the seam reuses the CLI's typed-input routine: that routine prints a "steered" or "queued for next turn" line with a preview (`hermes_cli/cli_tui_mixin.py:1527-1534`).
- **Telegram** is different: the mail is **not shown in the topic at all**. Only the target's answer is posted, including any `[REPLY …]` block markers from SM-Q8; a bare `[SILENT]` answer is suppressed. That is a separate decision: see SM-Q14. For the phone app, the answer above stands.

---

❓ **SM-Q12** — **Build on our own protocol, on upstream's peer messaging, or wait?** *(Already asked, not answered yet; restated for the wider scope.)* Upstream has three open, unmerged pull requests: #106423 by a maintainer, #136861 rebasing it, and #123218 adding replies and acknowledgements. They steer mail into a **running** session in every host (CLI, TUI, dashboard, gateway) from a file mailbox. They do **not** wake idle sessions, have no automatic replies, and cap the inbox at 50 and the body at 8,000 characters. #123218 also refuses Telegram and other gateway sessions. The fixes that stop mail being lost, looking like you, or landing in the wrong turn sit in a fork pull request that was closed unmerged. Choices:
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

❓ **SM-Q14** — **Should mail to a Telegram session also show in its topic?** Injected mail enters the gateway as an internal event, so the topic shows only the target's answer, out of nowhere, and you do not see what the agent was asked or by whom. The Telegram-topics comment on #81885 asks to "show the exchange in the topics". Choices:
- (a) answer only (today's behaviour, no extra code);
- (b) before the turn starts, post the 📨 header and the body into the topic as a bot message, through the same adapter (one send per mail).

➡️ (b). Telegram is one of your phone surfaces, and without it a gateway session's chat reads as the bot talking to itself. It is one adapter send, and it needs no change to how the turn runs.

## Open (cannot be settled by reading)

- **Real models and a 📨 header inside the out-of-band user frame.** The Trial's fake model cannot show this. Real use can, and it is the trigger for reopening SM-Q7 option C.
- ~~**The reaper race at turn end**~~ *(closed in round 4 by `8d4597bf8e` and `1ec78a0dcc`; see finding 2).*
- *(Round 4)* **The seam's exact shape:** one `mode` argument on `inject_message`, or a new method. How the gateway steers for an internal event, given that `run_busy.py:843-849` deliberately queues internal events because "plugin events carry untrusted payload text". The seam must keep that security split: mail is never treated as a gateway control command (`allow_gateway_control=False`).
- *(Round 4)* **Poller wake-up:** a short poll interval, or a file watch on the outbox. The cost in every CLI and TUI process when there is no mail, to be measured.
- *(Round 4)* **The dashboard as the "live nowhere" host** needs a dashboard-only start point again: the `dashboard/plugin_api.py` import, or a check for the dashboard's injector install. Round 1 left this open, and the refiner removed it with the worker. It comes back with the poller. **Verify in Trial.**
- *(Round 4)* **Gateway routing for an idle session:** whether `lookup_by_session_id` finds every gateway session a title or id can name, including after compression rotates the session id. The live install has no gateway sessions, so **verify in Trial**.
- *(Round 4)* **Whether injected gateway turns are stored with the `internal_notification` kind**, so a bare `[SILENT]` reply is suppressed rather than posted. **Verify in Trial.**
- **Mail to a session that is running the caller's own turn** (self-mail, or a reply to a session whose turn is finishing) over the loopback socket. It looks safe in the code, but was not traced line by line.
- **How long a start holds the sender's tool call** for an idle target whose agent must be built. This is measured in the Trial.

## Verify later (how we would know the build matches this brief)

- **Steer:** mail into a running turn returns `steered` to the sending tool, and the target's transcript has a separate user row starting with the 📨 header.
- **Queue and start:**
  - mail into a busy session that cannot steer returns `queued` and runs after the turn without interrupting it;
  - mail into an idle session that is not loaded returns `started`, and the turn runs in the dashboard;
  - no delivery produces a redirect or an interrupt.
- ~~**Send-time delivery from all three callers**~~ *(superseded in round 4 by the poller checks below; the loopback-socket part remains for the dashboard waking a session that is live nowhere).*
- *(Round 4)* **Every host delivers by the same rule:**
  - mail into a running classic CLI turn is steered, and the turn is **not** interrupted (today's `inject_message` would hard-interrupt it);
  - mail into an idle CLI starts a turn there;
  - the same steer, queue and start checks pass for an Ink TUI process and for a gateway session with a test adapter;
  - mail into an idle gateway session starts the turn in that chat, and the answer is posted there.
- *(Round 4)* **One claimant:** with the dashboard, a CLI and a gateway all running, each mail is delivered exactly once, by the process that hosts the target. A mail for a session that is live nowhere is woken by the dashboard.
- *(Round 4)* **Gateway sender:** a reply to a mail sent from a Telegram session wakes that session in its topic (SM-Q9).
- *(Round 4, SM-Q14 option b)* **Telegram shows the exchange:** the 📨 header and body appear in the target's topic before its answer.
- *(Round 4)* **Idle cost:** with no mail, a CLI or TUI process shows no measurable extra CPU from the poller.
- **Errors are returned, not held:** a `SESSION_NOT_OWNED` target returns the error to the sender, and the outbox records it.
- **Replies:**
  - a reply returns to the sender by the same rule;
  - `[SILENT]` or an empty answer sends nothing, and the outbox records "silent";
  - a two-session debate runs several rounds and stops only at `[SILENT]`;
  - a mail steered into a long unrelated turn returns only its `[REPLY <id>]` block (SM-Q8 option 2).
- **Unwakeable senders (SM-Q9 option b):** a reply to a sender whose source is `cron`, `subagent` or `oneshot` is stored and wakes nothing, whatever its end reason (`cron_complete`, `cron_incomplete_no_output`, `agent_close`, `cli_close`, or none). A reply to an owner session (source `cli`) whose terminal was closed (`cli_close`) wakes it.
- **Existing sessions get the tool:** a session created before the plugin was enabled lists and calls `session_message` after a dashboard restart, and pays one cache miss on its first turn, not one on every turn.
- **Addressing:** `@hermes-improvement`, an exact title, an id prefix and `Home` each resolve to the compression tip after `/compress`. An ambiguous title is refused with the candidates.
- **Outbox and CLI:**
  - every send records sender, target, body, delivery result, reply and timestamps, with no hop column;
  - `send`, `list` and `status` run without starting a turn;
  - a CLI sender reads its reply with `status`.
- **Phone:** after the turn ends, the mail shows on Hermes Mobile as a bubble whose first line is the 📨 header.
- **No caps, no retries:** the plugin has no hop, rate, duplicate or daily cap, and no retry loop or give-up timer.
