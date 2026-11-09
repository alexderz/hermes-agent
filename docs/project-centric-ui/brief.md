# Brief: project-centric Hermes UI (DER-686)

Gatherer's brief for the SDLC Brief step, 2026-11-08. Written headless from:
- Alex's dictated request, including his 21:00 addition;
- the research note;
- a read of the code;
- the refiner's review (`brief-refine.md`).

Round 2 narrowed the work to a small first slice; everything cut is listed under "Deferred after slice 1". Round 3 adds one requirement from Alex trying the system: owner sessions must be reachable and steerable from the phone while they work. Nothing here is decided beyond what Alex settled; the questions at the end are his to answer.

## Reflection (Alex's dump, tightened)

Alex groups his work into Hermes projects so each one carries its own context. The user interfaces do not reflect that:
- The Projects screen only edits project settings. It does not show a project's chats.
- History's "group by project" shows groups that do not match his projects, such as "hermes".

He wants the project to be the main thing. Tapping a project opens its main chat and shows the chats that belong to it. Each project has one owner chat: permanent, always there, long-lived, a session that "just compacts", like a Bot Chat but tied to a project. This must work in Hermes Mobile (his main surface) and in the web dashboard on laptop and phone, later as a home-screen progressive web app (PWA).

**Added 21:00.** Alex opened a project owner session in Hermes Mobile while its first turn was running as a command-line one-shot. Sending failed with `prompt.submit` error 4090, reason `SESSION_NOT_OWNED` ("This chat is open in another Hermes window/terminal"). An owner chat that works for hours is only useful if he can reach it and steer it from the phone while it works.

## Intent

### Slice 1 (unchanged from round 2)

1. **An owner chat per project, as data.** The `projects` table gets one nullable column, `owner_session_id`.
   - It is returned by the existing `projects.list` and `projects.get` calls and by the project nodes of `GET /api/profiles/projects/tree`.
   - It is set through the existing `projects.update` call.
   - There are no new remote procedure calls (RPCs).
2. **Owners seeded once.** The owner chats for Alex's six projects are set once with `projects.update`, as a reversible data fix that keeps an undo file, like the session re-homing already done.
3. **One dashboard Projects page.**
   - A project list, then a project page: the owner chat on top (it opens `/chat?resume=<id>`), then the project's other sessions by recency, and a "new chat here" button.
   - It reads only from `GET /api/profiles/projects/tree`, so it needs no new write endpoint.
   - It works in the laptop and phone browser.
4. **Two drafted Hermes Mobile issues** for Alex to review, never posted by agents:
   - **Issue 1:** a project page with the owner chat on top, read from `owner_session_id` in `projects.list`.
   - **Issue 2:** two bugs. The "hermes" History group (no home-directory rule), and new project chats starting in the first folder instead of the primary one.

A project with no owner (or whose owner session is gone) simply shows its session list and the "new chat here" button.

### New requirement (round 3)

5. **Owner sessions are reachable and steerable from the phone while they work.**
   - When the owner chat is running a turn, Alex can open it in Hermes Mobile.
   - He can queue a message, steer the running turn ("guide"), or stop it.
   - He does not get a refusal that only offers "start a new conversation".
   - How this is delivered is open (Q4, Q5).

## Out of scope

- Model routing (DER-675), the GPU host, Home Assistant (settled by Alex).
- The SDLC's shape and the branch/deploy flow (settled; `rules.md` rule 19).
- Per-project memory, instructions or model settings. Project context already comes from files in the project folder (Environment fact 3).
- The desktop Electron app, beyond keeping the shared backend contract compatible.
- Writing Hermes Mobile code ourselves in this slice.
- Letting two processes write one session at once. Hermes forbids this on purpose (Environment fact 18), and the requirement does not need it.

## Deferred after slice 1

These were in the round-1 brief. They are dropped from slice 1 and revisited after Alex has used it:
- **`/new` turns into a compaction in the owner chat.** Pending Q1, because it was in Alex's own scope list.
- **A server/TUI `/new` guard keyed on an owner flag.** It would change slash handling in the TUI, the CLI and the gateway.
- **A "get or create the owner chat" RPC.** The owner chats already exist.
- **Following the compression chain to its tip.** Compaction runs in place and keeps the id (Environment fact 7), so a missing session just means "no owner".
- **A "make owner" button in any UI.** Seeding covers the six projects; a later project needs one `projects.update` call.
- **A "Home" pseudo-project with its own owner chat.** Home is not a project, and the pinned "Home" chat already sits in the pinned section.
- **Rename protection for the owner chat.** A pointer survives renames.
- **The PWA** (manifest plus a network-first service worker). Already ordered after routing step 1 (`PROJECT.md` work item 2b).
- **Our own fork of Hermes Mobile, or pull requests to it.** Only if the drafted issues stall.

## Constraints

- **Branches only.** Every Hermes change goes on a feature branch of the fork, is fast-forwarded into the deployed branch, and is deployed with `git pull --ff-only`. No live edits and no side repos (`rules.md` 19).
- **Posting is Alex's call.** Hermes Mobile issues are drafted for Alex to review and never posted by agents. Its `CONTRIBUTING.md` ("AI Tool Usage") bans AI authorship trailers, which matters if we ever send it code.
- **Prompt caching** (`AGENTS.md` invariants). Nothing in slice 1 touches a system prompt: the column is read by clients, not by the agent. Steering a running turn injects text into the next tool result (Environment fact 20), which appends to the conversation rather than rewriting it.
- **Narrow core.** One column and one optional `projects.update` field; no model tool and no new RPC.
- **Profiles are islands.** The column lives in the per-profile `projects.db`. `projects.update` already takes `profile`.
- **Old app builds keep working.** The extra response field is harmless: the app decodes RPC replies with `ignoreUnknownKeys = true` (`data/remote/OkHttpProvider.kt:93-96`, used by `data/ws/HermesWsClient.kt:94-96`, app). The app's contract test pins hermes-agent v0.22.7 (`app/src/test/resources/gateway-contract/SOURCE`, app), so that file may need the new field listed when upstream adopts it.
- **Restarts cost Alex his phone session, and possibly a turn.** Each dashboard restart cuts Hermes Mobile off (`PROJECT.md` work item 2), so slice 1 is one announced deploy. A turn running inside the dashboard process would also die with a restart. This matters for option A below.
- **One writer per session.** This is a Hermes invariant (Environment fact 18). Any answer to the new requirement routes the phone's message to the process that owns the session; it never adds a second writer.

## Decisions

Settled by Alex:
- **Surfaces.** Hermes Mobile is the main surface; the web dashboard is second; the PWA comes after routing step 1 (`PROJECT.md` work items 2 and 2b).
- **Delivery.** Backend work is a fork patch, offered upstream. Hermes Mobile work goes through drafted upstream issues or our own fork of the app.
- **Fork timing.** The fork stays on v0.22.0 until routing step 3, then rebases once (`PROJECT.md` work item 3, HI-Q7). Q5 asks whether the new requirement changes this.
- **Already done.** The seven owner sessions were re-homed into their project folders (undo file under `<hermes-home>/backups/`). The CLI `cwd` bug is fixed on fork branch `alex/cli-session-cwd` (commit `4595840144`).

Taken in refinement (Alex can overturn):
- **Pointer column over a title convention.** `owner_session_id` was chosen over a Bot-Chat-style exact title because a pointer survives renames. It also lets existing titles such as "Model Master" stay, and it travels in `projects.list`, which both clients already load.
- **Existing calls over new RPCs.** Extending `projects.list` / `get` / `update` means old clients need no fallback.
- **The dashboard page now, the app via issues.** This puts the feature on Alex's phone browser in slice 1 while the app maintainer decides.

## Assumptions (now explicit)

- **A1.** "Project memories and context" means the context Hermes already loads from the session's working folder. Getting `cwd` right is what ties a chat to its project.
- **A2.** One owner chat per project per profile, because the column lives in the per-profile `projects.db`.
- **A3.** Alex runs the default in-place compaction, so the owner session id never changes.
- **A4.** The dashboard keeps embedding the real terminal user interface (TUI) for chat (`web/AGENTS.md` forbids re-implementing chat in React). So opening the owner chat in the dashboard means `/chat?resume=<session-id>`.
- **A5.** "The projects section in the web app" describes the phone app's Projects screen, or a mix of the two apps. The dashboard has none (Environment fact 10). The new dashboard page is its first projects section, with its own navigation entry.
- **A6.** Owner sessions are started by scripts: the SDLC kickoff runs as a transient user unit calling `hermes chat --in <project-folder> -c "<title>" --create-if-missing -q "<prompt>" --oneshot -Q` (live unit definition, read 2026-11-08). The kickoff script is Alex's tooling, outside the Hermes repo, so changing how it submits is not a Hermes change.
- **A7.** "Steerable" means what Hermes Mobile already offers for a busy chat: queue, guide (steer), correct (redirect) and interrupt (Environment fact 25). It does not mean a new kind of control.

## Environment facts

Paths are relative to the Hermes repo unless marked "(app)", which means relative to the Hermes Mobile clone under `app/src/main/java/com/m57/hermescontrol/` (or under `app/src/main/` / the clone root where the path starts with `res/` or `app/src/test/`). Facts marked "@v0.23.0" are read with `git show v0.23.0:<path>`.

### Backend: projects

1. **Project storage.** Projects live per profile in `<hermes-home>/projects.db`, with tables `projects`, `project_folders`, `project_meta` and `discovered_repos` (`hermes_cli/projects_db.py:28-67`).
   - There is no owner, main or pinned session, and no memory, instructions or model field.
   - Edits go through `update_project` (`projects_db.py:273`; display fields and `board_slug` only), exposed as the `projects.update` RPC (`tui_gateway/methods_projects.py:72`).
   - `Project.to_dict` is at `projects_db.py:173`.
2. **How a session finds its project.** A session has no project id. Its project is the deepest project folder that contains its `cwd` or git repo root (`projects_db.py:462` `project_for_path`; `tui_gateway/project_tree.py:336`).
   - Sessions with no workspace go to a synthetic "Home" bucket with id `__no_project__` (`project_tree.py:29-30`).
   - The user's home directory and `<hermes-home>` never become auto projects (`methods_projects.py:133-160`).
3. **Project context comes from folder files.** Hermes loads `.hermes.md` / `HERMES.md` and the `AGENTS.md` chain from the session's working folder (`agent/prompt_builder.py:140`, `:1718`).
4. **One project's sessions are already served.**
   - Over REST: `GET /api/profiles/projects/tree` (`hermes_cli/web_routers/profiles.py:718`) returns the project tree with per-project session counts, preview sessions and `sessionIds`.
   - Its project nodes are built in `tui_gateway/project_tree.py:348` `_project_node`.
   - Over RPC: `projects.tree` and `projects.project_sessions` (`tui_gateway/methods_config.py:138`, `:153`).
   - Only the desktop app calls these today.
5. **Bot Chat for comparison.** Its identity is its exact title, `"Bot Chat"`, with no session-id pointer (`hermes_state.py:1604-1609`). A unique index on `sessions.title` allows one row per title per profile (`hermes_state_schema.py:134-135`).
6. **Where `/new` turns into `/compact` today.** Only in clients, and only for Bot Chat:
   - the desktop composer (`apps/desktop/src/plugins/hermes-bots/plugin.tsx:762-797`);
   - Hermes Mobile, by title check (`ui/chat/ChatViewModel.kt:4669-4677`, app).
   - The TUI, and so the dashboard chat, has no such guard.
7. **Compaction keeps the session id by default** (`compression.in_place: True`, `hermes_cli/config_defaults.py:686`). Alex's config does not override it.
8. **Session flags already exist.** `pinned`, `hidden` and `archived` are session columns, editable with `PATCH /api/sessions/{id}` (`hermes_cli/web_routers/sessions.py:887`).
9. **The project code is unchanged in v0.23.0.** `projects_db.py` and `project_tree.py` are byte-identical at v0.23.0 (`git diff HEAD v0.23.0`), so the patch should carry over.

### Web dashboard

10. **The dashboard has no projects section, at HEAD or v0.23.0.**
    - **Core tabs:** Chat, Sessions, Files, Analytics, Models, Logs, Cron, Skills, Plugins, MCP, Channels, Webhooks, Pairing, Profiles, Config, Keys, System, Docs (`web/src/App.tsx:142-222`).
    - **Plugin tabs:** Achievements, Kanban and Usage (`plugins/hermes-achievements/dashboard/manifest.json`, `plugins/kanban/dashboard/manifest.json`, `plugins/model-routing/dashboard/manifest.json`).
    - **Kanban:** its only project UI is the "Board settings" dialog, which binds a board to a project and sets the board's default project directory (`plugins/kanban/dashboard/plugin_api.py:1301-1330`, `:1398`). Live, there is only the default board and no project has a `board_slug`, so Alex has not used it.
    - **Workspace picker:** it chooses a folder for a new chat (`web/src/components/ChatWorkspacePicker.tsx`).
    - **The phone app:** the screen that matches "I can only edit project settings" is Hermes Mobile's Projects screen (fact 13).
11. **What the Sessions page lacks.** It has no project grouping. The web `SessionInfo` type lacks `cwd`, `git_repo_root` and `pinned` (`web/src/lib/api.ts:2118-2136`).
12. **What the dashboard can already do.** It can open any session with `/chat?resume=<id>` (`web/src/pages/ChatPage.tsx:372`) and start a fresh chat in a chosen folder (`ChatPage.tsx:1228-1230`). It has no PWA manifest or service worker (`web/public/` holds only the favicon and fonts).

### Hermes Mobile: projects

13. **The Projects screen only edits.** Tapping a project card opens the edit sheet (`ui/projects/ProjectsScreen.kt:281`, app), and the screen never lists sessions.
    - History groups by project with its own rules (`ui/sessions/SessionProject.kt:27-55`, app), which have no home-directory rule.
    - Dashboard and phone chats record the service user's home directory as `cwd`, whose last segment is `hermes`. That is the "hermes" group.
    - New project chats use the first folder, not the primary one (`data/model/ProjectLaunch.kt:5`, app).
14. **There is a pattern to copy.** The app has a pinned section in History (`ui/sessions/components/PinnedSectionHeader.kt`, app) and opens a bot's canonical chat from its roster (`ui/bots/BotsScreen.kt:403-433`, app). So "open the owner chat on tap" has a precedent.
15. **The app is active and takes requests.** Its project features shipped through issues (#1526, #1527, #1581, #1669 in github.com/Hy4ri/hermes-mobile, read on 2026-11-08). Feature requests use `.github/ISSUE_TEMPLATE/feature_request.yml`. An official Nous mobile app is in beta (hermes-agent.nousresearch.com/mobile; the community app's issue #1752 discusses it).

### Live data (metadata only, read 2026-11-08)

16. **Projects and pinned sessions.** There are six projects and nine pinned sessions, including:
    - five "<Project> — Orchestrator" sessions (Hermes Improvement, SDLC, Budgeting, Home Eng, Minecrafting);
    - "Model Master" (Model Testing folder);
    - "Llama-bored" (Home Eng folder);
    - "Home" (no `cwd`);
    - the default profile's "Bot Chat".
17. **The session from Alex's report** ("Hermes Improvement — Project UI") has source `cli`, `cwd` in the Hermes Improvement project folder, and no end time yet. It was started by the transient unit described in A6.

### Session ownership (v0.22.0, deployed)

18. **One live writer per session, recorded in a lease file.**
    - Each open chat surface records a lease in `<hermes-home>/runtime/active_sessions.json`, guarded by a file lock (`hermes_cli/active_sessions.py:175-189`).
    - Lease fields: `lease_id`, `session_id`, `surface`, `pid`, process start time, timestamps and metadata (`:461-479`).
    - `try_acquire_active_session` (`:482-574`) refuses a second process with `SESSION_NOT_OWNED` (`:557-561`; message `:159-168`). An unreadable registry fails closed with `SESSION_COORDINATION_UNAVAILABLE` (`:525-531`).
    - The same writer means the same pid plus the same `live_session_id` (`:137-148`).
    - Liveness is "the pid exists and its start time matches"; there is no heartbeat or time limit (`:335-394`). Leases of dead processes are dropped on the next read.
19. **A command-line one-shot holds the lease for its whole turn.**
    - `hermes chat -q` claims the lease at `hermes_cli/cli_single_query.py:522`. It runs the turn and any follow-on loops, then releases in `_finalize_single_query` (`hermes_cli/cli_shutdown.py:309-362`).
    - The interactive CLI holds its lease for the whole session (`cli.py:1401`, released at `hermes_cli/cli_tui_runtime_mixin.py:493`).
    - So for a multi-hour kickoff, the phone is locked out for hours.
20. **The dashboard's chat backend refuses before queueing.**
    - In the dashboard's chat backend (`tui_gateway`, behind `/api/ws`, which Hermes Mobile uses), the first `prompt.submit` claims the lease (`tui_gateway/session_lifecycle.py:121-137`). `session.create` and `session.resume` do not claim one (`tui_gateway/methods_session.py:418, 639-648`).
    - The ownership check runs before the busy/queue logic (`tui_gateway/methods_prompt.py:774-778`), so even `prompt.submit {queued: true}` gets 4090.
21. **Viewing a held session works, but steering it does not.**
    - `session.resume` works; the transcript is re-read from the database.
    - `session.steer`, `session.redirect` and `session.interrupt` act only on a turn running in this same process (`tui_gateway/methods_session_interrupt.py:70-175`). For a turn in another process they do nothing useful.
22. **Hazard: compaction ignores ownership.** `session.compress` has no ownership check (`tui_gateway/methods_session.py:2136-2160`). So a phone `/compact` can compact a session another process is still writing to. This bears on Q1.
23. **Busy chats in the same process can already be steered.**
    - `display.busy_input_mode` is `queue`, `steer` or `interrupt`, default `interrupt` (`tui_gateway/server.py:382-384`; handled in `tui_gateway/session_auto_continue.py:400-461`).
    - Steering injects the text into the next tool result. Queued prompts run after the turn.
    - Every client attached to the same process sees the same live stream (`website/docs/developer-guide/programmatic-integration.md:60`).
24. **The only cross-process delivery today is the Bot Chat mailbox.**
    - It lives in `tools/bot_live_delivery.py` (files in `<hermes-home>/runtime/bot_live_delivery/`). It delivers only to sessions titled "Bot Chat", owned by a dashboard or desktop chat backend that advertises itself as a consumer (`:32-61`).
    - Delivery happens at an idle boundary, as a queued message, never a steer (`tui_gateway/session_notifications.py:647-701`). CLI owners never consume it.
    - Two other paths do not help here. A "shared session attach" path exists on the client side (`hermes_cli/shared_session_attach.py`), but no shipped runtime serves it (`tests/e2e/core/security/test_attach_handshake.py:28-29`). There is no `-q` mode that drives a turn through a running dashboard.
    - What a script can do today is open the dashboard's `/api/ws` socket and send `session.resume` (or `session.create`) plus `prompt.submit`. The turn then runs in the dashboard process, where the phone can attach and steer (`hermes_cli/web_routers/chat_ws.py:701-720`). A client that disconnects leaves an orphan, which is reaped after a grace period.

### Hermes Mobile: busy chats

25. **The app has a busy-send setting.** It is `BusySendMode` with options correct, queue, guide and interrupt (`data/model/BusySendMode.kt:6-11`, app), set in Settings → Appearance.
    - These map to `session.redirect`, `prompt.submit {queued}`, `session.steer` and `session.interrupt` plus a submit (`ui/chat/ChatViewModel.kt:3780-3806`, app).
    - `/queue` and `/btw` exist as slash commands (`ui/chat/SlashCommandDispatcher.kt:59-78`, app).
26. **On 4090 the app only offers a new conversation.**
    - The message moves to a recovery card: "This chat is open in another window. Start a new conversation with this message?", with Discard and New conversation (`res/values/strings.xml:2143`; `ui/chat/components/PendingSendRecovery.kt:198-328`, app). This came from the app's PR #1730 (merged 2026-10-30).
    - There is no retry, take-over, read-only state or live view.
27. **The app cannot see a turn running elsewhere.**
    - In the chat screen, "busy" comes only from this connection's stream events and the `running` flag from `session.resume` (`ui/chat/ChatViewModel.kt:665, 1490-1544, 2461`, app). So a CLI-run turn looks idle, and the app sends a plain `prompt.submit`, which gets 4090.
    - Only the History list shows "working" for other processes, from `last_activity_at` under 180 seconds (`data/session/SessionSharedStatus.kt:23-39`, app).
    - No app issue covers this (searched 2026-11-08).

### Session ownership in v0.23.0

28. **v0.23.0 moves CLI turns into the gateway.**
    - The command line builds no agent of its own; turns run through `GatewayAgent` in the gateway (`hermes_cli/cli_agent_setup_mixin.py:650` @v0.23.0).
    - It attaches to, or starts, the home's one owner process (`hermes_cli/gateway_client.py:319-350` @v0.23.0).
    - A durable admission ledger (`session_admissions`, intents queue/steer/redirect) records work per session (`hermes_state_common.py:586-638` @v0.23.0).
29. **v0.23.0 forwards a refused prompt to the owner.**
    - When the ledger owner holds the session, a dashboard-side `prompt.submit` goes to the owner instead of failing (`tui_gateway/methods_prompt.py:724-729` @v0.23.0, `tui_gateway/owner_forward.py` @v0.23.0). It runs after the current turn, exactly once, and the owner's frames are relayed back.
    - This forward is text only and queue only: no steer and no images. New refusal reasons are `SESSION_OWNER_BUSY` and `SESSION_OWNER_UNCONFIRMED`.
    - The dashboard's `/api/ws` can also be served by the owner's session authority, so the phone attaches as a co-viewer that can steer (`hermes_cli/web_routers/chat_ws.py:651-708` @v0.23.0).
    - Not tested live: whether our phone-to-dashboard setup takes the co-viewer path (steer works) or the forward path (queue only).

## Options map

### Where the dashboard Projects page lives

| Option | Ugly part | Fit |
|---|---|---|
| **A core dashboard page** (`web/src/pages/`, a "Projects" nav entry next to Sessions) | Touches core `web/` files, so more rebase work until upstream takes it | Can be offered upstream as a general feature; links straight into Chat and Sessions |
| **A dashboard plugin tab** (`plugins/<name>/dashboard/`, like Kanban and Usage) | A tab among plugins, not core navigation; upstream is less likely to want it as a plugin | No core `web/` edits; the fork already ships the model-routing plugin this way |

Prior art from round 1 (Claude Projects, ChatGPT Projects: a project page that lists its chats) still holds. Neither has an owner chat.

### Making a working owner session steerable from the phone

**A. Run owner-session turns inside the dashboard process**

- **How:** change the kickoff script so that, instead of `hermes chat -q --oneshot`, it opens the dashboard's `/api/ws` socket and sends `session.resume` plus `prompt.submit`. It then stays connected until the turn completes (a small client script). Fact 24.
- **Ugly part:**
  - A dashboard restart (every deploy) kills a running turn. Long runs then share the dashboard's memory instead of the unit's own cap.
  - The script must handle the dashboard token and reconnects.
  - It retires once the fork reaches v0.23.0.
- **Fit:**
  - No Hermes code change.
  - Phone queue, guide, correct and interrupt all work today, because the phone attaches to the same process (fact 23).
  - The fix sits in the kickoff tooling, where the problem starts.

**B. A cross-process queue into a held session (fork patch)**

- **How:** when `prompt.submit` meets `SESSION_NOT_OWNED`, write the message to a mailbox like Bot Chat's (fact 24). The owner, or whoever next holds the session, picks it up when the current turn ends.
- **Ugly part:**
  - A core change in the turn path that duplicates v0.23.0's ledger and forward (fact 29), so it conflicts at the rebase.
  - A CLI one-shot has no idle point to consume it. "Steer" would need the CLI turn loop to poll, which is more core change.
  - Queue only, in practice.
- **Fit:** works with the CLI kickoff unchanged. Weak fit, because upstream already built the real thing.

**C. Rebase onto v0.23.0 sooner**

- **How:** move fork upkeep (work item 3) ahead of routing step 3. CLI turns then run in the gateway owner, and phone prompts reach it (facts 28-29).
- **Ugly part:**
  - Large diff (the routing plugin and fork patches must be carried).
  - Whether steering works from our phone setup is unverified (fact 29).
  - It reorders a decision Alex made (HI-Q7).
- **Fit:** the upstream design for exactly this problem. No workaround to retire later.

**D. Only change the app**

- **How:** ask Hermes Mobile to show "working elsewhere" in the chat (from `last_activity_at`, fact 27), and to offer "retry when it finishes" instead of only "new conversation".
- **Ugly part:** no steering at all on v0.22.0, because the server refuses even queued sends (fact 20).
- **Fit:** cheap; a sentence in the issue 1 draft. It helps under any option, but solves nothing alone.

**E. Run owner chats interactively in the dashboard and stop CLI one-shots for them**

- **How:** start owner-session work by hand from the phone or browser chat.
- **Ugly part:** loses the scripted, scheduled kickoff the SDLC uses.
- **Fit:** works today for ad-hoc work only.

## Questions for Alex

❓ **Q1** — **Is `/new` turning into a compaction needed in slice 1?** Your scope list said "`/new` compacts instead of forking, like a Bot Chat".

The refiner proposes dropping it. With a pointer, `/new` in the owner chat just starts a separate new chat in the same folder. The owner chat stays pinned and untouched, and automatic compaction already makes it "just compact". Bot Chat needs the guard only because its identity is its title.

The alternative is to keep a guard. Cheapest: ask Hermes Mobile, in the issue 1 draft, to treat the chat whose id is the project's `owner_session_id` like Bot Chat. The app already has that code path (`ChatViewModel.kt:4669`). Costliest: a server/TUI guard that also covers the dashboard.

New in round 3: `session.compress` ignores ownership (fact 22). So a phone `/compact` sent while a CLI run holds the owner chat would compact under a live writer.

➡️ No server or TUI guard in slice 1. Add one sentence to the issue 1 draft asking the app to reuse its Bot Chat `/new` → `/compact` path for owner chats, but only when the chat is not busy elsewhere. Note the missing ownership check on `session.compress` as a fork bug fix (one guard line, offered upstream), since it endangers any session, not just owner chats.

---

❓ **Q2** — **Which session owns each project at seeding?**

➡️ The five "<Project> — Orchestrator" sessions, plus "Model Master" for Model Testing. "Llama-bored" stays pinned but does not own Home Eng; "Home Eng — Orchestrator" does.

---

❓ **Q3** — **Is the dashboard Projects page a core page or a plugin tab?** (See the options map.)

➡️ A core page, with a "Projects" entry next to Sessions. It is a general feature worth offering upstream, it sits beside the pages it links to, and the code it reads (`project_tree.py`) has not changed in v0.23.0. A plugin tab is the fallback if upstream declines.

---

❓ **Q4** — **How do owner sessions become steerable from the phone on today's v0.22.0?** (Options A, B, D, E above.)

➡️ Option A plus D:
- Change the kickoff tooling to submit through the dashboard's `/api/ws` instead of `hermes chat -q --oneshot`. This makes no Hermes change, and queue, guide and interrupt from the phone then work on the existing app.
- Add the "working elsewhere" sentence to the issue 1 draft.

Accept the cost that a dashboard deploy kills a running owner turn, and keep announcing restarts. Skip option B: it is a core patch that v0.23.0 already replaces.

---

❓ **Q5** — **Should the v0.23.0 rebase move ahead of routing step 3?** v0.23.0 runs command-line turns inside the gateway and forwards phone prompts to it (option C).

➡️ Not yet. First run a short check of v0.23.0 against a temporary Hermes home: start a turn with `hermes chat -q`, then submit, queue and steer from a client on the dashboard's `/api/ws`. If steering works, reorder the rebase and retire option A's script. If only queueing works, keep the order and option A.

## Open (not answerable by talking)

- **The phone layout** of the project page (how many sessions, where the "new chat" button goes). This needs a mock-up at the Plan/UX gate.
- **Upstream interest** in `owner_session_id`. This needs the upstream proposal sent with the fork patch.
- **The Hermes Mobile maintainer** adopting a field that only our fork serves until upstream takes it. This needs the drafted issue and the answer.
- **Steering under v0.23.0.** Whether the dashboard's `/api/ws` acts as a co-viewer of the gateway owner (steer works) or only forwards (queue only) in our setup. This needs the live check in Q5.
- **Long turns in the dashboard process** (option A). Whether a multi-hour turn there survives the dashboard's orphan reaping when the kickoff client stays connected, and what memory it uses. This needs a trial run.

## Verify later

- **Projects page.** Opening a project on the dashboard (laptop and phone browser) opens its owner chat, and the page lists the same sessions `/api/profiles/projects/tree` returns for that project.
- **Owner field.** `projects.list` and `projects.get` return `owner_session_id`, and `projects.update` sets and clears it. A test against a temporary Hermes home covers the migration on an existing `projects.db`.
- **No owner.** A project with no owner, or whose owner session was deleted, shows its list and "new chat here" with no error.
- **Seeding.** The seeding fix sets six owners, and its undo file restores them.
- **Old app builds.** The current Hermes Mobile build works unchanged against the patched backend.
- **Drafts only.** The issue drafts exist for Alex to review, and nothing is posted.
- **Rebase.** The backend patch rebases onto v0.23.0 without conflicts in `projects_db.py` or `project_tree.py`.
- **Steering from the phone.** While an owner session's scripted turn runs, Alex opens it in Hermes Mobile and sees it as busy. A message sent with busy mode "queue" runs after the turn, "guide" reaches the running turn, and Stop ends it. No 4090 refusal and no "new conversation" prompt.
- **One writer.** At every point exactly one process holds the owner session's lease (check `<hermes-home>/runtime/active_sessions.json`).
- **Compaction guard.** A `/compact` against a session another process holds is refused, not run (if the Q1 fix is taken).
