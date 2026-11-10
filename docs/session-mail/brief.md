# Brief: session-mail (DER-701), session-to-session messaging, built on intercom

Step: Brief (gatherer), round 6, after Refine round 4. Date: 2026-11-09. The chunk keeps its working name "session-mail"; the shipped plugin is `intercom`.

**Sources:**
- The request `requests/2026-11-09-session-mail-brief.md` in the Hermes Improvement vault: Alex's words, settled decisions 1–8, and three later sections, "Scope addition" (~19:45), "Delivery modes" (~19:50) and "Build on intercom, not a new plugin" (~20:00).
- The research note `research/session-messaging.md`, and vault rule 19.

**Code read:**
- this worktree (branch `integrate/session-mail`: v0.22.0, plus fork patches, plus `alex/v0.22.0-mobile-fixes` up to `c843eea710`);
- tag `v0.23.0`;
- the intercom clone (`alexderz/hermes-intercom` at `ae90a2a`; its `upstream` is `majordave/hermes-intercom`);
- the `miyu4u/hermes-intercom` clone at `1c1e677`;
- a Hermes Mobile clone at `d426349`.

Paths without a prefix are relative to the Hermes repository root. Intercom paths are given as `intercom:<path>`, Hermes Mobile paths are relative to its `app/src/main/java/com/m57/hermescontrol/`.

**History:** earlier rounds are in git (`d00e3f5a9e`, `2dce012608`, `8c6dd13539`) and in `brief-refine.md`. This round removes the superseded text; what was replaced is listed under "Superseded decisions".

## Intent

1. Any session, cron job or script can send a message to one named Hermes session of any kind:
   - a dashboard or desktop chat;
   - an Ink TUI or classic CLI session (each its own process);
   - a messaging-gateway chat (Telegram topics and other platforms).
2. The message is delivered right away by the process that hosts the target, in the requested delivery mode. A session that is live nowhere is woken in the dashboard, so Alex can watch and steer it from the phone.
3. The receiving session can tell the message from Alex's own words, and treats it as a message from a peer (best effort; see SM-Q7).
4. Replies come back automatically, so an orchestrator can delegate and act on the answer, and two sessions can debate until one has nothing new to add.
5. Every message is recorded: sender, target, body, requested and applied mode, reply.
6. The work extends the existing community implementation of upstream issue #81885 (intercom), so it can be offered upstream. Alex reviews any upstream text first.

## Out of scope

- Cross-machine and cross-install delivery: Agent Tincan, relays, other products (SM-Q6, "maybe later").
- Messaging across profiles, including bots in other profiles (SM-Q13).
- Any limit, hold, cap, rate limit, duplicate filter, approval gate, retry or give-up timer (settled decisions 3 and 5).
- Redelivery of a message that a host accepted and then lost (restart, interrupt). The record shows it as handed over, with no reply.
- A core patch for the steer frame (SM-Q7 option C). Changes to Hermes Mobile, including an issue draft for it.
- Posting anything to GitHub. Drafts for #81885, for a pull request to `majordave/hermes-intercom`, and for the seam's upstream pull request go into `docs/` on the intercom feature branch. Alex reviews the exact text; agents never post.
- The v0.23 unified-gateway transport from `miyu4u/hermes-intercom`; it is prior art for the v0.23 rebase only.
- Landing DER-686's `projects.owner_session_id`. This chunk reads it once it exists.

## Decisions (settled by Alex; not reopened)

1. **Base: our fork of intercom** (Alex, ~20:00: "I want us to make a fork of intercom, add to their code and post the update in the issue above").
   - Work lands in `alexderz/hermes-intercom` (a fork of `majordave/hermes-intercom`, MIT), on a feature branch, in its style.
   - The plugin name `intercom` and the `intercom` tool are kept.
   - Intercom's transport is kept where it fits: a `0600` Unix socket per process, the peer-UID check, and the registry under `$HERMES_HOME/intercom/`.
   - Its garbage-collector lookup of the CLI object and its private-field delivery are replaced by the core seam where that is available.
2. **Addressing:** `@<project-slug>` resolves to the project owner; also an exact title, a session id, or `Home`. The result resolves to the compression tip. An ambiguous match is refused, and the candidates are listed.
3. **Delivery modes** (Alex, ~19:50: "we need all 3 as tool options, and we apply the strongest the other session supports: interrupt - steer - queue, with admonition to only interrupt on intention, default to steer or queue"):
   - the `intercom` tool and the CLI take `delivery: interrupt | steer | queue`, **default `steer`**;
   - the host applies the requested mode if the target supports it, otherwise the strongest weaker one it does support (interrupt > steer > queue);
   - `interrupt`: the host's redirect where supported, otherwise a hard interrupt, then the message runs next;
   - `steer`: injected between tool calls, and the turn keeps going;
   - `queue`: runs after the current turn;
   - an idle target starts a turn, whatever the mode;
   - the tool description says: "only use interrupt when you intend to stop what the other session is doing right now (it is wrong, or the work is obsolete). Otherwise use steer (default) or queue.";
   - the record stores the requested and the applied mode, and the receipt names the applied mode;
   - `scripts/dashboard_dispatch.py` keeps its default (steer, else queue).

   No hold, even while Alex is active.
4. **Replies:** the target's final answer goes back to the sender automatically, by the same rule. A silence token or an empty answer sends nothing.
5. **Debates are allowed. No caps** of any kind.
6. **No empty replies:** the tool description and the footer of every delivered message tell the session to reply only with something new, and to end with `[SILENT]` otherwise. That is how a debate ends.
7. **A durable record** of who sent what. The sender is named in the message text, because agent-key turns are credited to the operator.
8. **A CLI** for cron jobs and scripts that costs no turn (for example `hermes intercom send|list|status`, named in intercom's style).
9. **Every kind of session is a target** (scope addition, ~19:45): dashboard and desktop, classic CLI, Ink TUI, messaging gateway.
10. **Bot sessions** (SM-Q13, answered by the scope addition): messaging-gateway sessions and the default profile's `Bot Chat` are in; bots in other profiles are out.
11. **One small, upstreamable core seam** (decision 1's "real blocker" exception):
    - `ctx.inject_message(..., mode="interrupt"|"steer"|"queue")`, honoured by the CLI, `tui_gateway` and gateway hosts with the fallback chain;
    - a fork patch on Alex's Hermes fork, listed in PROJECT.md;
    - intercom feature-detects it.
12. **Upstream:** when it works, draft an update for #81885, and possibly a pull request to `majordave/hermes-intercom`, into `docs/` on the branch. Alex reviews the text first.

## Superseded decisions

- 2026-11-09, round 1 → round 5: a new plugin `plugins/session-mail` with a `session_message` tool → our fork of intercom, with the `intercom` tool (decision 1).
- 2026-11-09, round 1 → ~19:45: delivery only inside the dashboard → every host delivers to the sessions it hosts (decision 9).
- 2026-11-09, round 1 → ~19:50: "steer, else queue, else start; never cancel or redirect" → three delivery modes with fallback, default steer (decision 3).
- 2026-11-09, round 1 → ~19:45: no core patch → one small seam (decision 11). The round-4 seam shape `mode="steer_or_queue"` → `mode="interrupt"|"steer"|"queue"`.
- 2026-11-09, round 1 → round 2 (Refine): a dashboard-only delivery worker → delivery by the sender.
- 2026-11-09, round 2 → round 4: delivery from the sender over the dashboard WebSocket for every target → delivery by the hosting process. The dashboard WebSocket is now used only to wake a session that is live nowhere.
- 2026-11-09, round 4 → round 5: an outbox as the bus between processes, with a poller in each one → intercom's per-process sockets. The outbox is the record only.
- 2026-11-09, round 5 → round 6 (Refine): one intercom registry entry per live session → the existing `runtime/active_sessions.json` lease `pid`, with intercom's one entry per process.
- 2026-11-09, round 5 → round 6 (Refine): a session that is live nowhere is taken by the dashboard's intercom socket, and mail waits in the outbox when no dashboard runs → the sender wakes it with the dispatcher rule; with no dashboard, the error is returned.
- 2026-11-09, round 1 → round 2: framing options B (plugin system-prompt section) and C (a core steer-frame patch) → A (header only), now A′ in intercom's form (SM-Q7).

## Constraints

- Hermes changes go only on fork branches. They are fast-forwarded into `alex/v0.22.0-mobile-fixes` and deployed with `git pull --ff-only` in the install. The plugin enable goes through house-infra `hosts/<dashboard-host>/hermes.py`. No live edits (vault rule 19). How intercom reaches the install is SM-Q14, asked elsewhere.
- The dispatch steer/queue fix and the queue-aware reapers (`1516a52669`, `8d4597bf8e`, `1ec78a0dcc`, `c843eea710`) are on this branch, through merge `3d4d482eb9`.
- One announced dashboard restart at deploy; list busy sessions first. Every resumed session pays one prompt-cache miss when the `intercom` tool is added to its tool list (see "Tool list of a resumed session").
- Prompt caching is sacred (root `AGENTS.md`). Messages arrive as new user rows; past context and live system prompts are never rewritten.
- A plugin tool is the sanctioned way to add a model tool (`tools/AGENTS.md:25-27`). Behaviour goes in `config.yaml`, not new `HERMES_*` environment variables. Plugin data lives under `get_hermes_home()` (HX001).
- Code-health ratchet on the Hermes fork: functions CC ≤ 20 and ≤ 300 lines, files ≤ 2,000 lines.
- Work outside a turn carries the profile context: the reply thread started by `post_llm_call`, and intercom's socket threads (`tools/thread_context.py:36`, `propagate_context_to_thread`).
- **The waking path is synchronous.** Waking a session that is live nowhere runs the dispatcher rule from the sender. Its worst case is about 420 s: resume, steer and submit at 60 s each, plus a 240 s start wait. That exceeds the 300 s limit `model_tools._run_async` puts on an `is_async` handler (`model_tools.py:94-135`). So the tool handler is synchronous and runs its own short event loop. This is a timeout, not a cap on sending.
- The Trial uses a temporary `HERMES_HOME`, its own dashboard on another port, and a fake model. It also runs a classic CLI, an Ink TUI and a gateway with a test adapter, because the live install has no gateway sessions.
- Question IDs: SM-Q7 to SM-Q16 (SM-Q14 is asked elsewhere). New questions start at SM-Q17.

## Design (what the plan builds on)

- **Transport:** each Hermes process that loads intercom binds one socket and writes one registry entry, as intercom does today. The send path:
  1. The sender resolves the address through `state.db` (decision 2) to a session id, then to its compression tip.
  2. **Find the host.** It reads that session's lease in `runtime/active_sessions.json`, takes the lease's `pid`, and connects to the intercom socket registered for that pid.
  3. **Deliver.** The host delivers through the seam in the requested mode and returns the receipt (requested and applied mode, or the error).
  4. **Same process.** Two sessions in one process (two dashboard chats) are delivered directly. Only a message to the sender's own session is refused.
- **A gateway session** has no lease while idle, so it is found through the gateway: its intercom endpoint marks itself in the registry (see Open), and its session store maps the session id (`gateway/session.py:1311`, `lookup_by_session_id`).
- **A session that is live nowhere** (no lease, not known to a running gateway) is idle by definition. The sender wakes it with the dispatcher rule over the dashboard's loopback WebSocket, using the agent key: resume, then submit, then wait for the turn to start. If no dashboard answers, the send returns the error, and the record stores it. The sender can send again.
- **The record:** a SQLite file under `<hermes-home>/plugin-data/intercom/`, mode `0600`. It stores id, in-reply-to id, sender session, target session, body, requested mode, applied mode, reply (or "silent"), and timestamps. It has no hop counter and no status ladder.
- **Replies (SM-Q16 a):** `post_llm_call`, in the process that ran the turn, finds message ids in the turn's new rows (the `user_message`, or `display_kind: "steer"` rows in `conversation_history`). For each **`send`** message, it takes the `[REPLY <id>] … [/REPLY]` block, or the whole final answer (SM-Q8). It skips empty and `[SILENT]` answers, stores the reply, and delivers it to the sender with the default `steer` mode, from a short-lived thread. Messages sent with `ask` are skipped; intercom's explicit `reply` answers those.
- **Framing (SM-Q7 A′):**
  - intercom's header line, made to name the sender **session** (title and id) and to say it is not Alex, then the body, then the footer (no empty replies, the reply block, `[SILENT]`);
  - the header goes first, so it is the first visible line on the phone;
  - intercom's zero-width-space forgery defence and echo stripping stay, with the echo pattern updated;
  - never `display_kind: "hidden"`.
- **Sender identity:** the calling session, from the `session_id` keyword the tool handler receives (`model_tools.py:875`), and its title. Never from model input. A CLI send uses `--from`, or defaults to `cli`; its reply goes to the record and is read with `status`.
- **Without the seam** (an older Hermes build), intercom keeps its CLI-only delivery and refuses dashboard, TUI and gateway targets with a clear error. It never parks them, so the process-wide `pre_llm_call` drain cannot put a message into the wrong session.

### Build order (hosts)

1. **The core seam on the `tui_gateway` (dashboard, desktop, Ink TUI) and classic CLI hosts, plus the intercom changes they need:**
   - addressing through `state.db`, then the lease `pid`, then the socket;
   - the `delivery` argument with fallback, and the receipt;
   - same-session refusal, and the four caps removed;
   - the A′ header and footer;
   - the record, and automatic replies for `send`;
   - the CLI command;
   - waking a session that is live nowhere with the dispatcher rule.

   This covers the owner sessions, `Home`, dashboard chats, desktop, Ink TUI and classic CLI.
2. **The messaging-gateway host:**
   - the seam's gateway path, with a mode for an internal event and still `allow_gateway_control=False`;
   - the gateway endpoint marking itself;
   - routing by `lookup_by_session_id`;
   - the SM-Q15 topic post.

   It comes second because the live install has no gateway sessions, and because it carries the one security question (untrusted text that may now steer).
3. **The upstream drafts** in `docs/` for Alex: the #81885 update, an intercom pull request, and the seam pull request. Nothing posted.

## Environment facts

### Intercom (the base)

Clone at `ae90a2a` (2026-09-04). The code is 1,380 lines with its tests (`__init__.py` 178, `inbox.py` 751, `tests/test_protocol.py` 451 with 17 tests). Docs: `README.md`, `docs/findings.md`, `docs/AGENTS.md` (in Spanish). The manifest declares `kind: standalone` and `provides_tools: [intercom]`.

- **Tool:** `intercom(action=list|send|ask|reply, to, message, timeout, request_id)`; one setting, `inbound: always|never` (`intercom:__init__.py:19-61,158-178`).
- **Registry and socket:**
  - `inbox.start()` runs once per process. It writes `$HERMES_HOME/intercom/sessions/<pid>-<time>.json` (`name, pid, cwd, session_id, socket, started_at`) and binds a `0600` socket served by a daemon thread (`intercom:inbox.py:621-690`).
  - That id is a process endpoint, not a Hermes session id (test `intercom:tests/test_protocol.py:331`). Names are `<profile>-<cwd folder>-<pid mod 1000>` (`intercom:inbox.py:114-127`).
  - Dead pids are swept on read (`:130-147,346-356`).
- **Peer-UID check:** a connection from another UID is refused (`intercom:inbox.py:545-569`). Envelopes are JSON lines (`:472-487`).
- **Delivery today** (`intercom:inbox.py:201-291`):
  - the live `HermesCLI` is found by a garbage-collector scan;
  - an idle CLI gets `_pending_input.put` (a turn starts);
  - a busy one, judged from private flags plus the registry's `turn_active`, gets `agent.steer`. A refused steer is "held_steer_rejected", with nothing queued;
  - with no reachable agent (any `tui_gateway` process), or an idle agent without `_pending_input`, the text is parked and spooled (`:238-269,706-739`). `pre_llm_call` drains it into the next turn of **any** session in that process (`intercom:__init__.py:137-147`);
  - never an interrupt.
- **Self-send:** `send_to` refuses any target in the sender's own **process** ("target is the current session", `intercom:inbox.py:498-499`).
- **Frame:** `📡 hermes@<endpoint-name> says:` then the body (`intercom:inbox.py:176-187`). Version 3 removed the earlier "NOT by the user" wrapper (`intercom:docs/AGENTS.md`). Copies of the header inside the body are broken with a zero-width space (`:154-167`), and senders' echoed headers are stripped (`intercom:__init__.py:64-76`). A steer still lands inside Hermes's `[OUT-OF-BAND USER MESSAGE …]` user marker.
- **Ask and reply:**
  - `ask` holds the sender's tool call until a `reply` arrives (default 600 s, maximum 3,600 s); the receiver is told to call `intercom(action="reply", request_id=…)` (`intercom:inbox.py:370-451,599-607`);
  - a reply is accepted only from the asked peer (`:425-433`);
  - the correlation is in-memory in the asker.
- **Receipts:** `delivered`, `held`, `refused` (`intercom:inbox.py:527-538`).
- **Caps to remove** (decision 5):
  - an 8,000-character body;
  - 6 messages per peer per minute;
  - duplicate refusal within 120 s;
  - 10 parked messages (`intercom:inbox.py:35-39,246-268,500-514`).

### What intercom does, what we change, what we add

| Requirement | Intercom today | Change or add |
|---|---|---|
| Classic CLI target | Idle → turn; busy → steer | Deliver through the seam; add `interrupt`; a refused steer queues |
| Dashboard, desktop, Ink TUI (many sessions per process) | Parked, then drained into whatever turn runs next | Route by the target's lease `pid`; that process delivers to the addressed session through the seam. No process-wide drain where the seam exists |
| Two sessions in one process | Refused | Refuse only the same session |
| Gateway sessions | None | Gateway endpoint marks itself; routing by `lookup_by_session_id`; seam's gateway path (build step 2) |
| Live nowhere | "no live peer" | Sender wakes it with the dispatcher rule; error if no dashboard |
| Delivery modes | Steer or park | `delivery` argument, fallback chain, requested and applied mode in receipt and record, tool-description sentence |
| Addressing | Live endpoint name or prefix (`intercom:inbox.py:454-469`) | Title, `@project`, `Home`, id or prefix through `state.db`, compression tip; endpoint names still accepted |
| Automatic replies, `[SILENT]` | Explicit `reply` to an `ask` only | `post_llm_call` capture for `send` messages, reply block, empty and `[SILENT]` suppression, footer |
| No caps | Four caps | Removed |
| Durable record | Spool for parked text only | The record (SQLite, `0600`) |
| Sender named, not Alex's authority | Endpoint name in the header | Session title and id, and "not Alex" (A′) |
| CLI for cron | None | `register_cli_command` subcommand, as `plugins/model-routing/__init__.py` does |

### How each host handles injected text today, and what the seam adds

`ctx.inject_message` routes in `hermes_cli/plugins_injection.py:12-62`. Non-CLI hosts need `plugins.entries.<id>.allow_gateway_injection: true` (`:32-37`).

| Host | `interrupt` today | `steer` today | `queue` today | Injection today | Seam adds |
|---|---|---|---|---|---|
| **`tui_gateway`** (dashboard, desktop, Ink TUI) | `_handle_busy_submit` in mode `interrupt`: redirect when `_supports_active_turn_redirect`, else queue, then a hard interrupt (`tui_gateway/session_auto_continue.py:400-455`) | `AIAgent.steer` via `session.steer` (`tui_gateway/methods_session_interrupt.py:137-172`). Compression demotes steer and interrupt to queue (`session_auto_continue.py:410-411`) | Queued submit with an accept-time row (`:406,438-443`) | Queue only, no accept-time row; False when the session is not live in this process (`tui_gateway/plugin_inject.py:24-64`) | Pass the requested mode to `_handle_busy_submit` (today it comes only from config or the `queued` flag), and return the applied mode |
| **Classic CLI** | `agent.redirect` when supported, else `_interrupt_queue`: a hard interrupt, then the text runs next (`hermes_cli/cli_tui_mixin.py:1535-1551`; `hermes_cli/cli_chat_turn_mixin.py:418-441`) | `agent.steer`, refusal → queue (`cli_tui_mixin.py:1515-1530`) | `_pending_input` (`:1531-1534`); idle `_pending_input` starts a turn (`hermes_cli/cli_tui_runtime_mixin.py:36`) | Busy → `_interrupt_queue`, i.e. **always a hard interrupt**; idle → `_pending_input`; ignores `session_key` (`plugins_injection.py:19-23`) | Route through the typed-input logic with the requested mode instead of the configured `busy_input_mode` |
| **Messaging gateway** | `_resolve_busy_steer_or_redirect` plus `_interrupt_running_agent_for_busy_event` for typed messages (`gateway/run_busy.py:856-880`) | Same resolver | FIFO `_queue_or_replace_pending_event` (`:862-864`) | `adapter.handle_message(MessageEvent(internal=True, allow_gateway_control=False, …))` (`gateway/run_plugin_injection.py:126-157`). Internal events are always queued: "plugin events carry untrusted payload text" (`run_busy.py:843-849`). Idle → a new turn in the chat | Let an injected event carry the requested mode, keeping `allow_gateway_control=False` |
| **Any idle target** | starts a turn | starts a turn | starts a turn | — | Same on every host |

- The gateway's bot-loop guard counts only bot-authored sources (`gateway/authz_mixin.py:600-612`), and injection reuses the chat's stored human source (`gateway/run_plugin_injection.py:136-138`). It is not a hidden cap.
- A bare `[SILENT]` answer is suppressed only for turns whose user row has the internal kind `internal_notification` (`gateway/response_filters.py:19-34`).
- Injected text is not posted to the Telegram chat; only the turn's answer is (see SM-Q15).

### Which process hosts a session

- **`runtime/active_sessions.json`** (`hermes_cli/active_sessions.py`):
  - written atomically under a file lock as `{"entries": [...]}` (`:175-189,297-298`);
  - each entry has `lease_id, session_id, surface, pid, process_start_time, started_at, updated_at`, plus optional `track_liveness` and `metadata` (`:461-480`);
  - dead pids are pruned on read (`active_session_registry_snapshot`, `:711-744`);
  - at most one live owner per stored session (`:482-495`).
- **Writers:**

  | Writer | Surface | Key | When |
  |---|---|---|---|
  | CLI (`cli.py:925-940`) | `cli` | stored session id | while it holds the session |
  | `tui_gateway` (`tui_gateway/session_lifecycle.py:62-85`) | `tui` or `desktop` | `session_key` (stored session id) | while live in that process |
  | Gateway (`gateway/run_busy.py:236-262`) | `gateway:<platform>` | gateway session key | only while a turn runs |

  The dashboard and an Ink TUI both write `tui`; the `pid` tells them apart.
- **Gateway sessions:**
  - an idle one has no lease;
  - the gateway's session store maps a stored session id to its routing entry (`gateway/session.py:1311-1317`), persisted in the `gateway_routing` table of `state.db`;
  - gateway sessions store the platform name as their source, for example `telegram` (`gateway/session_recovery.py:173`).
- **No API says "this process is the gateway".** `ctx.session_surface()` does not exist anywhere in this worktree (a round-5 claim was wrong). One in-process signal does exist: the gateway runner publishes its plugin message host at start (`gateway/run_startup.py:1654`, `hermes_cli/plugins.py:1640`), visible as `manager.has_gateway_message_injector` (`hermes_cli/plugins.py:1242`). See Open.
- **Live metadata (read-only, 2026-11-09):**
  - 5 leases (3 `desktop`, 2 `tui`);
  - 0 rows in `gateway_routing`;
  - session sources: `cli` 9, `cron` 102, `desktop` 9, `oneshot` 6, `subagent` 6, `tui` 5.

### Waking a session that is live nowhere (the dispatcher rule)

- **`scripts/dashboard_dispatch.py`** (fix `1516a52669` and review fixes `8d4597bf8e`, `1ec78a0dcc`):
  - `session.resume`, then `session.steer`, then `prompt.submit` with `queued: true`;
  - only `status: "streaming"` counts as a started turn;
  - a steer timeout is an error with no second send;
  - after a start, it waits for the first agent event, up to 240 s by default; the per-RPC timeout is 60 s (`scripts/dashboard_dispatch.py:106-130`, argparse defaults).
  - It authenticates with the loopback agent key (`hermes_cli/dashboard_auth/agent_key.py`).
- **Sharing the code (A2, the architect picks):**
  - `scripts/` has no `__init__.py`, and nothing in the repository imports the script. Skills run it as a subprocess: `<venv>/bin/python -I scripts/dashboard_dispatch.py …` (`<hermes-home>/skills/autonomous-ai-agents/session-relay/SKILL.md:16`, and two more skills).
  - Options: (1) move `_rpc` and `_deliver` into an importable module that the script also uses; (2) run the script as a subprocess.
- **Threading:**
  - the dashboard serves each WebSocket RPC on a worker thread (`tui_gateway/ws.py:319-333`), and a turn runs on its own thread (`tui_gateway/methods_prompt.py:879-886`), so a loopback client in a tool thread does not block the server;
  - `post_llm_call` fires on the target's turn thread before `running` clears (`agent/turn_finalizer.py:453-479`), so replies are sent from a short-lived thread.

### Reaper and queued messages (finding 2)

- In the dashboard, a detached idle session that still holds a queued prompt is kept for up to 30 grace periods, about 10 minutes, with the budget reset whenever a turn runs or the queue drains. After that it is reaped, with a warning (`tui_gateway/session_lifecycle.py:938-960`; `tui_gateway/server.py:165`).
- A leftover steer is queued before `running` is released (`tui_gateway/prompt_turn.py:438-447`).
- **Still lost, recorded as handed over with no reply:**
  - a queued message when a running turn with no client attached goes quiet for 600 s and is interrupted (the interrupt clears the queue, `session_lifecycle.py:709-713`);
  - queued rows on a restart (retired on the next resume, `hermes_state_sessions.py:546-559`);
  - a CLI's `_pending_input` and the gateway's FIFO on a process exit.

### Steer framing (finding 1)

- **The steer marker claims the user's authority.** Every steer is wrapped as `[OUT-OF-BAND USER MESSAGE — a direct message from the user, …]` (`agent/prompt_builder.py:561-591`). The system prompt says that marker has "the same authority as their original request" (`:594-611`, added at `agent/system_prompt.py:567`).
- **The caller cannot change the frame.** `AIAgent.steer(text)` takes text only, and pending steers are joined under one marker (`agent/interrupt_control.py:267-278`).
- **Queued, interrupt and started messages are ordinary user turns.** On every path, the header is the only separation from Alex's words.

### Reply capture (finding 3)

- `post_llm_call` receives `session_id`, `turn_id`, `user_message`, `assistant_response` and `conversation_history`, and is skipped for detached forks (`agent/turn_finalizer.py:453-479`).
- A steered message appears only in `conversation_history`, as a `display_kind: "steer"` row (`agent/prompt_builder.py:585-591`).
- A steer that arrives too late is requeued as plain text (`agent/turn_finalizer.py:745-749`).
- Text-only queued prompts can merge (`tui_gateway/session_auto_continue.py:162-168`).
- So reply matching looks for the message id in all of the turn's new rows.

### What the phone shows (finding 4)

- Hermes Mobile shows user rows only from REST history. It refreshes every 30 s, skipping the refresh while a turn runs (`ChatViewModel.kt:7146-7157`), so a message appears 0–30 s after the turn it joined ends.
- Every delivered message is an ordinary user bubble in Alex's colour with a double tick (`fullbleed/FullBleedTurns.kt:115,131-134`; `UserBubble.kt:106-137`).
- The app strips a leading `[OUT-OF-BAND USER MESSAGE …]` (`ui/chat/ChatTranscriptMerge.kt:17-39`), reads no sender field, and draws plain text.

### Tool list of a resumed session

- A fresh agent builds its tools from current config, where a plugin toolset is on by default (`hermes_cli/tools_config.py:510-517`).
- The fresh build is folded onto the session's pinned list, with new tools appended (`tools/mcp_tool_agent.py:204-248`).
- So existing owner sessions get `intercom` after the deploy restart, with one prompt-cache miss each.

### Addressing data

- Titles are unique (`hermes_state_schema.py:135`); lookups are `get_session_by_title` (`hermes_state_titles.py:186-192`) and `resolve_session_id` for id prefixes (`hermes_state_sessions.py:942`). The compression tip is `get_compression_tip` (`hermes_state_compression.py:779-783`).
- Projects live in `projects.db`, with no owner column yet (`hermes_cli/projects_db.py:23-36`).
- Live:
  - five projects have a `<Project name> — Orchestrator` owner;
  - Model Testing's owner is titled "Model Master";
  - `Home` is an exact title.

### "Ended" senders (for SM-Q9)

- `ended_at` is stamped on every process close and cleared on the next turn (`hermes_state_sessions.py:520-525,562`; `tui_gateway/methods_prompt.py:593-609`). Three of the six owner sessions are "ended" right now (`cli_close`).
- `agent_close` is the generic backstop, listed as recoverable (`run_agent.py:1013-1017`; `hermes_state_common.py:185-189`).
- Cron runs end as `cron_complete` or `cron_incomplete_no_output` (`cron/scheduler.py:2167,2172`).
- So the session **source** is the usable test.

### Upstream (for the #81885 offer)

- **#106423** (open, by a maintainer), its rebase **#136861**, and **#123218**: a core `peer_messaging` toolset that steers mail from a file mailbox into **running** sessions in every host.
  - None is merged, none wakes an idle session, and none has automatic replies.
  - They cap the inbox at 50 and the body at 8,000 characters, and #123218 refuses gateway sessions.
  - Fixes for lost and user-looking messages were in a fork pull request that was closed unmerged.
- **Issue #81885:** open, `needs-decision`, no maintainer position.
  - A comment splits the problem into addressing, live ownership, and a reject / queue / wake policy.
  - Another asks for Telegram topics: wake when idle, reply to the origin, show the exchange in the topic.
  - Intercom is the implementation linked there.
- **Closed #83661** proposed the same seam shape (`mode=queue|steer|interrupt`). It was closed by its author with no stated reason.
- **`miyu4u/hermes-intercom`** (4 commits ahead, 2026-11-04):
  - its `gateway_peers.py` is a transport over v0.23's **unified** gateway (CLI, TUI, desktop and ACP sessions), not the messaging gateway, so it does not reach Telegram;
  - it needs `hermes_cli.gateway_client`, `hermes_cli.gateway_runtime.discover_gateway_endpoint` and `gateway.session_context.bound_session_key`. All exist in `v0.23.0` and none in this worktree;
  - it is prior art for the v0.23 rebase.

## Assumptions

- **A2.** One shared copy of the dispatcher rule, for the waking path (options under "Waking a session that is live nowhere").
- **A4.** The sender is resolved from the calling session, never from model input.
- **A5.** The header comes first in the text.
- **A6.** Never `display_kind: "hidden"` (`tui_gateway/methods_prompt.py:743`).
- **A7.** No message is dropped for repetition.
- **A8.** The process named by a session's lease `pid` is the only one that delivers to it, so no message is delivered twice.
- **A11.** A send is synchronous: the tool and the CLI get the receipt at once, as intercom's `send` does today (`intercom:inbox.py:490-538`).

## Questions for Alex

❓ **SM-Q7** — **How should a message be framed?** A steer lands inside Hermes's "direct message from the user" marker, and the caller cannot change it. Queued, interrupt and started messages are plain user turns. Intercom's own header, `📡 hermes@<endpoint-name> says:`, names a process endpoint and does not say it is not you. Choices:
- A′: keep intercom's `📡` header line, but name the sender session and say "not Alex" (for example `📡 hermes@<session title> (session <id>, not Alex) says:`), plus our footer;
- keep intercom's frame unchanged;
- C: a core patch for a separate peer frame (it would cover steered messages only).

➡️ A′. Reopen C only if real models act on messages as if you had said them.

---

❓ **SM-Q8** — **Which text is the reply when a message shares a turn?** A steered message often joins one of your turns, and queued messages can merge. Choices:
- 1, the whole final answer to every sender in the turn;
- 2, the footer asks for a `[REPLY <id>] … [/REPLY]` block or `[SILENT]`, and only the block is sent, with the whole answer as a fallback;
- 3, the target replies with the tool.

➡️ 2. An `interrupt` delivery makes the message its own turn, where the block still works. Intercom's `ask` keeps its explicit `reply` (SM-Q16).

---

❓ **SM-Q9** — **Should a reply wake a sender whose run is over?** "Ended" is not a usable test (see "Ended senders"). Choices:
- (a) always wake;
- (b) store the reply only when the sender's source is `cron`, `subagent` or `oneshot`, and wake every other sender;
- (c) use `ended_at`, which would stop replies to half the owner sessions.

➡️ (b). Owner sessions are `cli`, so a closed terminal never stops their reply. A Telegram sender (source `telegram`) is woken in its own topic. Subagent windows opened from the desktop (`desktop`) are woken.

---

❓ **SM-Q10** — **How should `@model-testing` resolve before DER-686 lands?** Model Testing's owner is titled "Model Master". Choices: refuse until DER-686; rename the session to "Model Testing — Orchestrator"; or an alias map in config.

➡️ Rename the session (one `/title`, no code).

---

❓ **SM-Q11** — **Is "looks like you typed it" acceptable on the phone for v1?** Every message is a bubble in your colour, 0–30 s after the turn ends, marked only by its header line. An `interrupt` delivery on a dashboard chat redirects or stops the turn you may be watching, which looks like any redirect.

➡️ Yes for v1. No Hermes Mobile issue in this chunk. Telegram is SM-Q15.

---

**SM-Q12** — *Answered (Alex, ~20:00):* build on our fork of intercom (decision 1).

**SM-Q13** — *Answered (scope addition):* gateway sessions and the default profile's `Bot Chat` are in; bots in other profiles are out (decision 10).

**SM-Q14** — *Asked elsewhere* (the "Session Messaging" session): the deploy method, recommended as vendoring `alexderz/hermes-intercom` into Alex's Hermes fork as `plugins/intercom` with `git subtree`.

---

❓ **SM-Q15** — **Should a message to a Telegram session also show in its topic?** Injected text never reaches the chat, so the topic shows only the target's answer, out of nowhere. Choices:
- (a) answer only;
- (b) post the header and body into the topic as a bot message before the turn starts (one adapter send).

➡️ (b). Telegram is one of your phone surfaces; without it, you never see the message there.

---

❓ **SM-Q16** — **Intercom's blocking `ask` and explicit `reply`, next to automatic replies.** Choices:
- (a) keep `send`, `ask` and `reply` as they are; automatic replies apply to `send` messages and skip `ask` messages, which intercom's `reply` answers;
- (b) one shared reply path in which an automatic reply resolves a waiting `ask` across processes;
- (c) drop `ask` and `reply`.

➡️ (a). Each message gets exactly one reply with no new correlation code, and intercom's protocol and its 17 tests stay as they are, which the upstream offer needs. (b) adds cross-process plumbing nobody asked for.

## Open (cannot be settled by reading)

- **The seam's exact shape:**
  - one `mode` argument with fallback, returning the applied mode;
  - how the gateway steers or interrupts for an internal event while keeping `allow_gateway_control=False`;
  - how the dashboard picks redirect versus a hard interrupt for a compute-host turn.
- **How the gateway's intercom endpoint marks itself** in intercom's registry, so a sender can route gateway sessions to it. There is no `ctx.session_surface()`. A candidate signal is `manager.has_gateway_message_injector`, true in the process where the gateway runner has published its host (`hermes_cli/plugins.py:1242`; `gateway/run_startup.py:1654`). The planner picks; **verify in Trial**.
- **Gateway routing for an idle session:** whether `lookup_by_session_id` finds every gateway session a title or id can name, including after compression rotates the id. **Verify in Trial** (no live gateway sessions).
- **Whether injected gateway turns get the `internal_notification` kind**, so a bare `[SILENT]` is suppressed. **Verify in Trial.**
- **A message to a session running the caller's own turn** (self-mail is refused, but a reply to a session whose turn is finishing is the normal debate path). **Verify in Trial.**
- **How long a wake holds the sender's tool call** for a target whose agent must be built. Measured in the Trial.
- **Real models and the header inside the user frame.** The fake model cannot show this; real use can. It is the trigger for reopening SM-Q7 C.

## Verify later (how we would know the build matches this brief)

- **Delivery modes on each host** (`tui_gateway`, classic CLI; then gateway with a test adapter):
  - `delivery` omitted → `steer` is applied into a running turn;
  - `steer` where steering is refused → `queue` is applied, and the receipt says so;
  - `interrupt` → redirect where supported, else a hard interrupt with the message as the next turn; where interrupt is unsupported → steer, else queue;
  - an idle target starts a turn in every mode;
  - the record shows requested and applied mode;
  - the tool description contains Alex's sentence on interrupt.
- **Classic CLI:** a `steer` into a running CLI turn does not interrupt it (today's `inject_message` would).
- **Many sessions in one process:** two dashboard chats message each other; a message to chat A never appears in chat B; after `/compress`, addressing reaches the new tip.
- **Routing:** a CLI, a dashboard and a gateway all running, and each message is delivered once, by the process named in the target's lease (or by the gateway for an idle gateway session).
- **Live nowhere:** an idle owner session with no lease is woken in the dashboard and runs a turn there. With the dashboard stopped, the send returns an error and the record stores it.
- **Replies:**
  - a `send` message's reply returns to the sender with `steer`;
  - `[SILENT]` or an empty answer sends nothing, and the record says "silent";
  - a two-session debate runs several rounds and ends only at `[SILENT]`;
  - a message steered into a long unrelated turn returns only its `[REPLY <id>]` block;
  - an `ask` message is answered once, by intercom's `reply`, and gets no automatic reply.
- **Senders whose run is over (SM-Q9 b):**
  - a reply to a `cron`, `subagent` or `oneshot` sender is stored and wakes nothing;
  - a reply to an owner session whose terminal closed (`cli_close`) wakes it;
  - a Telegram sender is woken in its topic.
- **Telegram (SM-Q15 b):** the header and body appear in the target's topic before its answer.
- **Addressing:**
  - `@hermes-improvement`, an exact title, an id prefix, `Home` and an intercom endpoint name each resolve;
  - an ambiguous title is refused with the candidates.
- **Record and CLI:**
  - every send records sender, target, body, requested and applied mode, reply and timestamps;
  - `send`, `list` and `status` start no turn;
  - a CLI sender reads its reply with `status`.
- **No caps, no retries:** 20 identical messages in one minute all arrive; there is no retry loop or give-up timer.
- **Without the seam:** dashboard, TUI and gateway targets are refused with a clear error, and nothing is parked.
- **Intercom compatibility:** its 17 tests pass, except those asserting a removed cap, which change with the cap.
- **Tool list:** a session created before the plugin was enabled lists and calls `intercom` after a restart, with one cache miss.
- **Phone:** after the turn ends, the message shows on Hermes Mobile with the header as its first line.
- **Upstream drafts:** the #81885 update (and, if chosen, the intercom and seam pull-request texts) sit in `docs/` on the intercom branch for Alex's review; nothing was posted.
