# Brief: session-mail (DER-701), session-to-session messaging

Step: Brief (gatherer), round 2, after Refine (`brief-refine.md`). Date: 2026-11-09.

Source dump: the request `requests/2026-11-09-session-mail-brief.md` in the Hermes Improvement vault (Alex's words, settled decisions 1–8), the research note `research/session-messaging.md`, and vault rule 19.

Where the code facts come from:
- this worktree (branch `integrate/session-mail`, v0.22.0 plus fork patches);
- tag `v0.23.0`;
- commit `1516a52669` (branch `alex/dispatch-steer-queue`);
- a clone of Hermes Mobile at upstream head `d426349` (2026-11-09).

Paths without a prefix are relative to the Hermes repository root. Hermes Mobile paths are relative to `app/src/main/java/com/m57/hermescontrol/` in that clone.

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

Still vague, and handled below:
- which text counts as "the target's final answer" when one turn holds Alex's prompt plus one or more mails;
- where a reply goes when the sender's session has finished for good;
- how `@<project-slug>` resolves for a project whose owner does not follow the title convention.

## Intent

1. Any session, cron job or script can send mail to one named session. It is delivered right away inside the dashboard, so Alex can watch and steer the result from the phone.
2. The receiving session can tell mail from Alex's own words, and treats mail as a message from a peer. This is best effort on every delivery path (see SM-Q7).
3. Replies come back automatically, so an orchestrator can delegate and act on the answer, and two sessions can argue a point until one has nothing new to add.
4. Every message is recorded: sender, target, body, delivery result and the reply.

## Out of scope

- Agent Tincan, relays, and agents on other machines or in other products (SM-Q6, "maybe later").
- Any limit, hold, cap, rate limit, duplicate filter, approval gate, retry or give-up timer (settled decisions 3 and 5; round 2).
- A background delivery worker, and redelivery of mail that was lost after a handover (round 2).
- Bot Mode, hosted rooms, and one profile per agent (rejected in the research).
- Messaging across profiles. The plugin serves the default profile's sessions.
- Changes to Hermes Mobile, including drafting an upstream issue for it in this chunk (that can be offered after the plugin runs).
- A core patch for the steer frame (SM-Q7 option C, dropped from this chunk).
- A "Mail" tab on the dashboard, and a plugin system-prompt section.
- Landing DER-686's `projects.owner_session_id`. This chunk only reads it once it exists.

## Constraints

- **Fork-bundled plugin, no core patch** (settled decision 1).
- **The steer/queue fix is not on this branch yet.** `git merge-base --is-ancestor 1516a52669 integrate/session-mail` fails. The plugin depends on that commit's delivery rule (`_deliver`), so the build branch must contain it.
- Hermes changes go only on fork branches. They are fast-forwarded into the deployed branch `alex/v0.22.0-mobile-fixes` and deployed with `git pull --ff-only` in the install. The plugin is enabled through house-infra `hosts/<dashboard-host>/hermes.py`. No live edits (vault rule 19).
- One announced dashboard restart at deploy. List the busy sessions before scheduling it. The restart also costs every resumed session one prompt-cache miss, because the new tool is added to its tool list (see "Tool list of a resumed session").
- Prompt caching is sacred (root `AGENTS.md`). Mail arrives as new user rows. It never rewrites past context or rebuilds a live session's system prompt.
- A new model tool reaches every API call of every session (root `AGENTS.md`, "The core is a narrow waist"). A plugin tool is the sanctioned way to add one (`tools/AGENTS.md:25-27`).
- Code-health ratchet: functions CC ≤ 20 and ≤ 300 lines; files ≤ 2,000 lines.
- Plugin data lives under `get_hermes_home()` (HX001). With no worker, the only work that runs outside a turn is the reply thread started by the hook. It must carry the turn's profile context (`tools/thread_context.py:36`, `propagate_context_to_thread`).
- **The `session_message` tool handler is synchronous.** The worst case for one send is resume (60 s) + steer (60 s) + submit (60 s) + start wait (240 s) = about 420 s. That is longer than the 300-second limit `model_tools._run_async` puts on an `is_async` handler that runs on a fresh thread (`model_tools.py:94-135`). A sync handler running its own short event loop avoids that limit. This is a timeout, not a cap on sending (planner note from the refiner, round 2).
- Behaviour goes in `config.yaml`, not in new `HERMES_*` environment variables.
- The Trial uses a temporary `HERMES_HOME`, its own dashboard on another port and a fake model.
- Question IDs continue the series. This brief uses SM-Q7 to SM-Q11.

## Decisions (settled by Alex; not reopened)

1. A fork-bundled plugin `plugins/session-mail`, shaped like the in-fork `plugins/model-routing/` (`plugin.yaml`, and `__init__.py` with `register(ctx)`).
2. Addressing: `@<project-slug>` resolves to the project owner; also an exact title, a session id, or `Home`. The result resolves to the compression tip. An ambiguous match is refused, and the candidates are listed.
3. Delivery right away inside the dashboard: steer, else queue (`prompt.submit` with `queued: true`), else start, resuming the session in the dashboard first if needed. Never cancel or redirect. No hold.
4. Replies: the target's final answer goes back to the sender by the same rule. A silence token or an empty answer sends nothing.
5. Debates are allowed. No caps.
6. No empty replies. The tool description and the footer of every message say so; `[SILENT]` ends an exchange.
7. A durable outbox records who sent what. The sender is named in the text.
8. A CLI, `hermes session-mail send …`, costs no turn.

Design choices taken from the research and the refiner, which the code supports:

- **Delivery at send time.** Three callers deliver mail themselves:
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
- **Verdict:** a queued mail survives the sender detaching while the running turn keeps working. It is lost in three cases, and the outbox then shows the handover with no reply:
  1. the turn goes quiet for 600 seconds with no client attached;
  2. a restart happens before the mail runs;
  3. the reaper fires in the gap between `running` clearing and the queue drain (`tui_gateway/prompt_turn.py:438-448`).

  Case 3 is a Trial observation only. It changes no design.

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

## Options map

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

---

❓ **SM-Q10** — **How should `@model-testing` resolve before DER-686 lands?** Five projects follow `<Project name> — Orchestrator`, but Model Testing's owner is titled "Model Master". Choices:
- refuse `@model-testing` until DER-686 ships;
- rename the session to "Model Testing — Orchestrator";
- add an alias map in the plugin's `config.yaml` entry.

➡️ Rename the session (a one-line `/title`, no code). DER-686 replaces the title rule later.

---

❓ **SM-Q11** — **Is "looks like you typed it" acceptable on the phone for v1?** Every mail is a bubble in your colour with a double tick, appearing 0–30 seconds after the turn ends, marked only by its 📨 first line.

➡️ Yes, accept it for v1. No Hermes Mobile issue in this chunk; it can be offered once the plugin runs.

## Open (cannot be settled by reading)

- **Real models and a 📨 header inside the out-of-band user frame.** The Trial's fake model cannot show this. Real use can, and it is the trigger for reopening SM-Q7 option C.
- **The reaper race at turn end** (finding 2, case 3). A Trial observation only.
- **Mail to a session that is running the caller's own turn** (self-mail, or a reply to a session whose turn is finishing) over the loopback socket. It looks safe in the code, but was not traced line by line.
- **How long a start holds the sender's tool call** for an idle target whose agent must be built. This is measured in the Trial.

## Verify later (how we would know the build matches this brief)

- **Steer:** mail into a running turn returns `steered` to the sending tool, and the target's transcript has a separate user row starting with the 📨 header.
- **Queue and start:**
  - mail into a busy session that cannot steer returns `queued` and runs after the turn without interrupting it;
  - mail into an idle session that is not loaded returns `started`, and the turn runs in the dashboard;
  - no delivery produces a redirect or an interrupt.
- **Send-time delivery from all three callers:** a tool call inside a dashboard-hosted turn delivers over the loopback socket without stalling that dashboard; the CLI delivers from its own process; the reply hook delivers from its thread without holding up the target's turn end.
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
