# Refine: session-mail (DER-701), Brief step

Step: Brief (refiner). Date: 2026-11-09. Input: `brief.md` (gatherer, round 1). Method: the `yagni` skill, Alex's words in `requests/2026-11-09-session-mail-brief.md`, and the lessons "Too much process for a small feature" and "Do not invent gates". Code was read in this worktree, at `1516a52669`, at `v0.23.0`, and in the Hermes Mobile clone. Settled decisions 1–8 are not reopened.

## The main simplification

The brief and the research assume a **delivery worker**: a thread that runs only in the dashboard, polls the outbox every 5 seconds, retries lost mail and backs off on `SESSION_NOT_OWNED`. Alex did not ask for one. It brings three of the brief's four open points with it: where to start the thread (`dashboard/plugin_api.py`), how to bind its profile scope, and the 24-hour give-up.

**Deliver at send time instead.** The sender's process opens the dashboard WebSocket with the loopback agent key and runs the dispatcher's steer → queue → start rule. That is what `dashboard_dispatch` already does from cron, from any process on the box. It applies to:

- the tool handler, in whatever process runs the sender's turn;
- the CLI, in its own process;
- the reply hook (`post_llm_call`), in the process that runs the target's turn. It sends from a short-lived thread, so turn finalization is not blocked on a session resume.

The result goes into the outbox, and the tool or CLI returns it to the sender: `steered`, `queued`, `started`, or the error. A failed delivery is reported, not held and not capped. The sender (a model or a script) can send again. This keeps every settled decision:

- mail arrives right away by the same rule;
- replies go out by the same rule;
- debates have no caps;
- the outbox is still the durable record.

No "is this the dashboard?" detection is needed, because delivery always goes over the dashboard's own socket.

## Keep / simplify / kill

| Item in brief.md | Verdict | Reason |
|---|---|---|
| Intent 1–4 | Keep | Restates Alex's ask. Intent 2 ("treats mail as a peer, not Alex") is best effort on every path (see SM-Q7). |
| Out of scope list | Keep | All correct. Add: the Hermes Mobile issue draft (see SM-Q11). |
| Constraints (fork branch, ff deploy, one restart, caching, ratchet, HX001, `config.yaml`, Trial on a temporary home with a fake model) | Keep | Settled or repo rules. Add one fact: `1516a52669` is **not** on `integrate/session-mail` yet. The plugin depends on it (or on its `_deliver`), so the build branch must contain it. |
| Constraint: "work outside a turn binds the profile scope" | Simplify | With no worker, this applies only to the reply thread started by the hook. Bind the scope there; default profile only. |
| Reuse the dispatcher's delivery logic, not `ctx.inject_message` | Keep | Verified: injection only queues and writes no accept-time row. |
| **A1** worker only in the dashboard; tool and CLI only write to the outbox | **Kill** | Replaced by delivery at send time (above). Removes the Open point on `dashboard/plugin_api.py` and the thread's lifecycle. |
| **A2** import the dispatcher's code | Simplify | `scripts/` has no `__init__.py`, so `scripts/dashboard_dispatch.py` is not importable as a package. Either move `_deliver`/`_rpc` into an importable module the script also uses (one copy), or run the script as a subprocess the way cron does. The plan picks one; no second copy of the logic. |
| **A3** delivered only when `post_llm_call` sees the turn; redeliver the same mail id when a queue is cleared or retired | **Kill for v1** | Retrying needs a worker and a "was it lost?" test. The three loss cases are rare: a turn quiet for 600 s with no client attached, an announced restart, or a sub-millisecond race at turn end. The outbox records `handed over` and the reply when it comes. A mail with no reply stays visible in `status`. Add retries only if the Trial or real use shows losses ("build a small working slice, show it, then harden"). |
| **A4** sender resolved from the calling session; CLI uses `--from`, default `cli` | Keep | Verified: plugin tool handlers get `session_id` as a keyword (`model_tools.py:875`, `:901`). |
| **A5** header first in the text | Keep | Verified: Mobile strips only a leading `[OUT-OF-BAND USER MESSAGE …]`. The header is then the first visible line. |
| **A6** never `display_kind: "hidden"` | Keep | One line, prevents an invisible mail. |
| **A7** no drop on repetition; one mail at a time per target | Simplify | The "no drop" half is settled decision 5. The "one at a time per target" half goes with the worker: concurrent steers already join in arrival order (`interrupt_control.py:274-276`), and queued prompts drain in order. |
| Outbox fields | Simplify | Keep id, in-reply-to id, sender, target, body, delivery result, reply, timestamps (Intent 4). Drop the research's `hop` column. Nothing reads it, and a counter there invites a cap. Drop the status ladder `queued → delivering → delivered → replied/failed/expired`; use the delivery result plus "reply stored / silent". |
| CLI `send`, `list`, `status` | Keep | `send` is settled. `status` is how a CLI sender reads its reply. `list` is the "who sent what" view, about 10 lines. |
| Finding 1 options table | Keep as record | See SM-Q7 for the change in recommendation. |
| **SM-Q7** recommends C (core patch for a steer frame), ship A until then | **Simplify: A only; drop C from this chunk** | C fixes only one of three delivery paths. A queued or started mail goes through `prompt.submit` and becomes an ordinary user turn, with the user's full authority and no marker at all. On those paths the 📨 header is already the only separator. C would give steered mail a separation that queued and started mail never get. It would also cost about 100 lines in core files, a v0.23 rebase conflict, and a marker Hermes Mobile shows literally. That does not meet decision 1's "real blocker" bar. Ship A on all three paths, and reopen C only if real models obey mail as if Alex had said it (the brief's own Open point). |
| **SM-Q8** recommends option 2 (marked reply block, whole answer as fallback) | Keep | Small: a footer line and one regex. It stops Alex's own long answers being mailed to agents when a mail is steered into his turn. Steering is the default for busy owner sessions, so this case is common. It still follows decision 4: the reply is automatic and comes from the final answer. |
| Reply matching | Simplify | Find the mail id anywhere in the turn's new rows (the `user_message` or `display_kind: "steer"` rows in `conversation_history`). Then it does not matter that the RPC answers `queued` both for an accepted steer and during compression, or that a leftover steer is requeued as plain text: the mail id is in the text either way. |
| **SM-Q9** recommends outbox only for CLI, cron, oneshot and subagent senders | Simplify | A CLI sender has no session, so its reply goes to the outbox. That is a fact, not a question. Keep the question only for **agent senders that are ended sessions** (cron runs, oneshots, subagents): wake them by decision 4, or store the reply only. Base the test on whether the sender session is ended, not on a list of sources. |
| **SM-Q10** rename "Model Master" to "Model Testing — Orchestrator" | Keep | No code. Renaming Alex's live session is his call, so it stays a question. |
| **SM-Q11** accept the phone look for v1, and draft a Mobile issue | Simplify | Accept for v1. Drop the issue draft from this chunk: Alex did not ask for it, and Mobile changes are out of scope. Offer it after the plugin runs. |
| Open: reaper race at turn end | Simplify | Keep as a Trial observation only. Without A3, the result changes no design. |
| Open: `dashboard/plugin_api.py` as the worker host | **Kill** | No worker. |
| Open: real models and a 📨 header inside the user frame | Keep | It is the trigger for reopening SM-Q7 C. |
| Open: `SESSION_NOT_OWNED` retry for 24 h | **Kill** | The send returns the error to the sender, who can send again later. No give-up timer to argue about. |
| Verify later: "after a forced restart the outbox delivers the same mail id again" | **Kill** | Follows A3. |
| Verify later: steer row with the session-mail marker (option C) | **Kill** | Follows SM-Q7 → A. |
| Verify later: the other items (steer, queue, start, no interrupt, replies, `[SILENT]`, debate, addressing after `/compress`, outbox, phone, no caps) | Keep | |

## Smallest first slice

One fork branch with the plugin and the dispatch fix, about 300–400 lines plus tests:

1. **Address:** `@slug` → `<Project name> — Orchestrator`, an exact title, an id or id prefix, or `Home` → the compression tip. Refuse an ambiguous match and list the candidates.
2. **Deliver now:** `session.resume`, then `session.steer`; if that is refused, `prompt.submit` with `queued: true`. A queued submit into an idle session starts a turn. Prefix `📨 Message from session "X" (not Alex) [mail <id>]`, then the body, then the footer: no empty replies; put your answer in `[REPLY <id>] … [/REPLY]` or end with `[SILENT]`. Record the result in the outbox and return it to the caller.
3. **Tool:** `session_message(to, message)`. The sender comes from the calling session.
4. **CLI:** `hermes session-mail send --to … [--from …] (--message|--file)`, plus `status <id>` and `list`.
5. **Reply hook:** `post_llm_call` finds mail ids in the turn's new rows. For each one, it takes the marked block (or the whole answer), skips empty and `[SILENT]` answers, stores the reply, and delivers it to the sender session by step 2. A reply is itself mail, so it can be answered, and a debate runs until one side writes `[SILENT]`.

No worker, no retries, no system-prompt section, no core patch, no dashboard page.

## Fact checks

| Claim | Result |
|---|---|
| **Finding 1:** steer frame says "a direct message from the user"; `STEER_CHANNEL_NOTE` gives it "the same authority"; added to every session with tools; `steer(text)` takes only text; several steers join into one buffer | **Verified** (`agent/prompt_builder.py:560-611`, `agent/system_prompt.py:566-567`, `agent/interrupt_control.py:267-278`). Unchanged at `v0.23.0` (lines 563 and 608). **Missing from the brief:** queued and started mail carry user authority too, as plain user turns (see SM-Q7). |
| **Finding 2:** reaper grace 20 s; idle sessions torn down; fresh running turns (< 600 s) deferred; stale ones interrupted, which clears the queue; a second attached client prevents parking; queued rows retired after restart | **Verified** (`tui_gateway/session_lifecycle.py:700-716`, `:937-967`, `:1000-1060`; `tui_gateway/server.py:136-156`). Case 3 (the race at turn end) is real but narrow. `_run_post_turn_followups` drains right after `running` is released (`tui_gateway/prompt_turn.py:438-448`), so the reap timer would have to fire inside that window. Only the restart line numbers in `hermes_state_*` were not re-read. |
| **Finding 3:** `post_llm_call` carries `user_message`, `assistant_response`, `conversation_history`; skipped for detached forks; a leftover steer becomes the next turn's plain text | **Verified** (`agent/turn_finalizer.py:452-479`, `:745-749`; `tui_gateway/prompt_turn.py:444-447`). Note: with `dashboard.turn_isolation` on, the turn and the hook run in a compute-host child, not the dashboard process. The default is `False` (`hermes_cli/config_defaults.py:1005`). Delivery at send time works from either process, which is one more reason to drop the dashboard-only worker. |
| **Finding 4:** Mobile strips only a leading wrapper; a steer row is a normal user bubble; no sender field; plain-text bubble; history sync every 30 s, skipped while the agent types or streams | **Verified in substance** (`ui/chat/ChatTranscriptMerge.kt:17-39`; `fullbleed/FullBleedTurns.kt:110-133`; `ChatScreen.kt:159`, `:315-325`; `ChatViewModel.kt:7146-7157`; `UserBubble.kt:116-136` uses `AnnotatedString` and `clampForDisplay`). Small correction: Mobile **does** read `display_kind` (`data/model/SessionMessagesResponse.kt:59`) and treats `steer` as a real user turn (`ui/chat/ChatListEntries.kt:40`). It just draws no badge for it. The "20,000 characters" limit was not checked. |
| Dispatcher at `1516a52669`: steer → queue → start; reports any `queued` from `session.steer` as `steered`; waits only after a start | **Verified** (`scripts/dashboard_dispatch.py:106-150` at that commit). **Not on this branch** (`git merge-base --is-ancestor` fails). |
| `session.steer` answers `queued` both when accepted and during compression; `rejected` when idle | **Verified** (`tui_gateway/methods_session_interrupt.py:137-172`). |
| `prompt.submit` with `queued: true` never interrupts and stores the row at accept time | **Verified** (`tui_gateway/session_auto_continue.py:400-457`: mode is forced to `queue`, and the interrupt only runs for mode `interrupt`). |
| `register_system_prompt_section` reaches new sessions only; `register_cli_command`; `inject_message` needs `allow_gateway_injection` | **Verified** (`hermes_cli/plugins.py:603-650`, `:957-981`). |
| `dashboard/plugin_api.py` is imported only by the dashboard | Verified (`hermes_cli/web_server_dashboard.py:1015-1030`). Moot without the worker. |
| Addressing helpers; `projects.db` has no owner column | **Verified** (`hermes_state_titles.py:186-210`, `hermes_state_compression.py:779`, `hermes_cli/projects_db.py:23-40`). Live metadata (six projects, "Model Master") was not re-read; the live home was not touched. |

## New open point

- **Do long-lived owner sessions get a new plugin tool after the restart?** If a session keeps its toolset from when it was created, existing owners cannot call `session_message`. They could still send through the CLI from their terminal, but then A4 needs a way for the CLI to learn the calling session. If the tool does appear, adding it to the tool list costs each resumed session one prompt-cache miss. That cost is unavoidable and should be stated at deploy. Check this in the Trial with a session created before the plugin was enabled.

## Verdict

Requirements die: A1 (dashboard-only worker), A3 (redelivery of lost mail), SM-Q7 option C (core steer-frame patch), the 24-hour `SESSION_NOT_OWNED` retry, the `hop` column, and the Mobile issue draft. The gatherer's recommendations on SM-Q7, SM-Q9 and SM-Q11 change, and one new open point appears.

Refine: back to Gather — drop the worker (A1, A3, A7's ordering half, the `plugin_api.py` and 24 h Open points, and the restart-redelivery check) for delivery at send time from the tool, CLI and reply hook; SM-Q7 recommends A on all three paths, with C dropped from this chunk (queued and started mail are plain user turns anyway); SM-Q9 narrowed to ended agent-session senders (a CLI reply goes to the outbox by fact); SM-Q11 without the Mobile issue draft; A2 must pick one shared copy of `_deliver` (`scripts/` is not a package); note `1516a52669` is not on the branch; add the open point on whether existing owner sessions see the new tool after restart.
