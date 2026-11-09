# Brief: project-centric Hermes UI (DER-686)

Gatherer's brief for the SDLC Brief step, round 2, 2026-11-08. Written headless from:
- Alex's dictated request;
- the research note;
- a read of the code;
- the refiner's review (`brief-refine.md`).

This round narrows the work to a small first slice. Everything cut is listed under "Deferred after slice 1". Nothing here is decided beyond what Alex settled; the questions at the end are his to answer.

## Reflection (Alex's dump, tightened)

Alex groups his work into Hermes projects so each one carries its own context. The user interfaces do not reflect that:
- The Projects screen only edits project settings. It does not show a project's chats.
- History's "group by project" shows groups that do not match his projects, such as "hermes".

He wants the project to be the main thing. Tapping a project opens its main chat and shows the chats that belong to it. Each project has one owner chat: permanent, always there, long-lived, a session that "just compacts", like a Bot Chat but tied to a project. This must work in Hermes Mobile (his main surface) and in the web dashboard on laptop and phone, later as a home-screen progressive web app (PWA).

## Intent (slice 1)

1. **An owner chat per project, as data.** The `projects` table gets one nullable column, `owner_session_id`.
   - It is returned by the existing `projects.list` and `projects.get` calls and by the project nodes of `GET /api/profiles/projects/tree`.
   - It is set through the existing `projects.update` call.
   - There are no new remote procedure calls (RPCs).
2. **Owners seeded once.** The owner chats for Alex's six projects are set once with `projects.update`, as a reversible data fix, like the session re-homing already done. The fix keeps an undo file.
3. **One dashboard Projects page.**
   - A project list, then a project page: the owner chat on top (it opens `/chat?resume=<id>`), then the project's other sessions by recency, and a "new chat here" button.
   - It reads only from `GET /api/profiles/projects/tree` and needs no new write endpoint.
   - It works in the laptop and phone browser, so Alex gets the feature on his phone without waiting for the app.
4. **Two drafted Hermes Mobile issues** for Alex to review, never posted by agents:
   - **Issue 1:** a project page with the owner chat on top, read from `owner_session_id` in `projects.list`.
   - **Issue 2:** two bugs. The "hermes" History group (no home-directory rule), and new project chats starting in the first folder instead of the primary one.

A project with no owner (or whose owner session is gone) simply shows its session list and the "new chat here" button.

## Out of scope

- Model routing (DER-675), the GPU host, Home Assistant (settled by Alex).
- The SDLC's shape and the branch/deploy flow (settled; `rules.md` rule 19).
- Per-project memory, instructions or model settings. Project context already comes from files in the project folder (Environment fact 3).
- The desktop Electron app, beyond keeping the shared backend contract compatible.
- Upgrading the fork to v0.23.0 (work item 3).
- Writing Hermes Mobile code ourselves in this slice.

## Deferred after slice 1

These were in the round-1 brief. They are dropped from slice 1 and revisited after Alex has used it:
- **`/new` turns into a compaction in the owner chat.** This is pending Q1 below, because it was in Alex's own scope list.
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
- **Prompt caching** (`AGENTS.md` invariants). Nothing in slice 1 touches a system prompt: the column is read by clients, not by the agent.
- **Narrow core.** One column and one optional `projects.update` field; no model tool and no new RPC.
- **Profiles are islands.** The column lives in the per-profile `projects.db`. `projects.update` already takes `profile`.
- **Old app builds keep working.** The extra response field is harmless: the app decodes RPC replies with `ignoreUnknownKeys = true` (`data/remote/OkHttpProvider.kt:93-96`, used by `data/ws/HermesWsClient.kt:94-96`, app). The app's contract test pins hermes-agent v0.22.7 (`app/src/test/resources/gateway-contract/SOURCE`, app), so that file may need the new field listed when upstream adopts it.
- **One restart.** Slice 1 is one deploy and one dashboard restart. Each restart cuts Hermes Mobile off, so it is announced (`PROJECT.md` work item 2).

## Decisions

Settled by Alex:
- Hermes Mobile is the main surface; the web dashboard is second; the PWA comes after routing step 1 (`PROJECT.md` work items 2 and 2b).
- Backend work is a fork patch, offered upstream. Hermes Mobile work goes through drafted upstream issues or our own fork of the app.
- The seven owner sessions were already re-homed into their project folders (undo file under `<hermes-home>/backups/`), and the CLI `cwd` bug is fixed on fork branch `alex/cli-session-cwd` (commit `4595840144`).

Taken in refinement (Alex can overturn):
- **Pointer column over a title convention.** `owner_session_id` was chosen over a Bot-Chat-style exact title because a pointer survives renames. It also lets existing titles such as "Model Master" stay, and travels in `projects.list`, which both clients already load.
- **Existing calls over new RPCs.** Extending `projects.list` / `get` / `update` was chosen over new RPCs, so old clients need no fallback.
- **The dashboard page now, the app via issues.** This puts the feature on Alex's phone browser in slice 1 while the app maintainer decides.

## Assumptions (now explicit)

- **A1.** "Project memories and context" means the context Hermes already loads from the session's working folder. Getting `cwd` right is what ties a chat to its project.
- **A2.** One owner chat per project per profile, because the column lives in the per-profile `projects.db`.
- **A3.** Alex runs the default in-place compaction, so the owner session id never changes.
- **A4.** The dashboard keeps embedding the real terminal UI for chat (`web/AGENTS.md` forbids re-implementing chat in React). So opening the owner chat in the dashboard means `/chat?resume=<session-id>`.
- **A5.** "The projects section in the web app" is a description of the phone app's Projects screen, or a mix of the two apps. The dashboard has none (Environment fact 10). The new dashboard page is therefore its first projects section, and it gets its own navigation entry.

## Environment facts

Paths are relative to the Hermes repo unless marked "(app)", which means relative to the Hermes Mobile clone under `app/src/main/java/com/m57/hermescontrol/` (or the clone root for `app/src/test/...`).

### Backend

1. **Project storage.** Projects live per profile in `<hermes-home>/projects.db`, with tables `projects`, `project_folders`, `project_meta` and `discovered_repos` (`hermes_cli/projects_db.py:28-67`).
   - There is no owner, main or pinned session, and no memory, instructions or model field.
   - Edits go through `update_project` (`projects_db.py:273`; display fields and `board_slug` only), exposed as the `projects.update` RPC (`tui_gateway/methods_projects.py:72`).
   - `Project.to_dict` is at `projects_db.py:173`.
2. **How a session finds its project.** A session has no project id. Its project is the deepest project folder that contains its `cwd` or git repo root (`projects_db.py:462` `project_for_path`; `tui_gateway/project_tree.py:336`).
   - Sessions with no workspace go to a synthetic "Home" bucket with id `__no_project__` (`project_tree.py:29-30`).
   - The user's home directory and `<hermes-home>` never become auto projects (`methods_projects.py:133-160`).
3. **Project context comes from folder files.** Hermes loads `.hermes.md` / `HERMES.md` and the `AGENTS.md` chain from the session's working folder (`agent/prompt_builder.py:140`, `:1718`).
4. **One project's sessions are already served.**
   - The project tree with per-project session counts, preview sessions and `sessionIds` comes from `GET /api/profiles/projects/tree` (`hermes_cli/web_routers/profiles.py:718`).
   - Its project nodes are built in `tui_gateway/project_tree.py:348` `_project_node`.
   - Over RPC: `projects.tree` and `projects.project_sessions` (`tui_gateway/methods_config.py:138`, `:153`).
   - Only the desktop app calls these today.
5. **Bot Chat for comparison.** The Bot Chat's identity is its exact title, `"Bot Chat"`, with no session-id pointer (`hermes_state.py:1604-1609`). A unique index on `sessions.title` allows one row per title per profile (`hermes_state_schema.py:134-135`).
6. **Where `/new` turns into `/compact` today.** Only in clients, and only for Bot Chat:
   - the desktop composer (`apps/desktop/src/plugins/hermes-bots/plugin.tsx:762-797`);
   - Hermes Mobile, by title check (`ui/chat/ChatViewModel.kt:4669-4677`, app).
   - The TUI, and so the dashboard chat, has no such guard.
7. **Compaction keeps the session id by default** (`compression.in_place: True`, `hermes_cli/config_defaults.py:686`). Alex's config does not override it.
8. **Session flags already exist.** `pinned`, `hidden` and `archived` are session columns, editable with `PATCH /api/sessions/{id}` (`hermes_cli/web_routers/sessions.py:887`).
9. **v0.23.0 changes nothing here.** `projects_db.py` and `project_tree.py` are byte-identical at v0.23.0 (`git diff HEAD v0.23.0`), so the patch should carry over.

### Web dashboard

10. **The dashboard has no projects section, at HEAD or v0.23.0.** Of the places one might look:
    - **Core tabs.** Chat, Sessions, Files, Analytics, Models, Logs, Cron, Skills, Plugins, MCP, Channels, Webhooks, Pairing, Profiles, Config, Keys, System, Docs (`web/src/App.tsx:142-222`).
    - **Plugin tabs.** Achievements, Kanban and Usage (`plugins/hermes-achievements/dashboard/manifest.json`, `plugins/kanban/dashboard/manifest.json`, `plugins/model-routing/dashboard/manifest.json`).
    - **Kanban.** Its only project UI is the "Board settings" dialog, which binds a board to a project and sets the board's default project directory (`plugins/kanban/dashboard/plugin_api.py:1301-1330`, `:1398`). Live, there is only the default board and no project has a `board_slug`, so Alex has not used it.
    - **Workspace picker.** It chooses a folder for a new chat (`web/src/components/ChatWorkspacePicker.tsx`).
    - **The phone app.** The screen that matches "I can only edit project settings" is Hermes Mobile's Projects screen (fact 13).
11. **What the Sessions page lacks.** It has no project grouping. The web `SessionInfo` type lacks `cwd`, `git_repo_root` and `pinned` (`web/src/lib/api.ts:2118-2136`).
12. **What the dashboard can already do.** It can open any session with `/chat?resume=<id>` (`web/src/pages/ChatPage.tsx:372`) and start a fresh chat in a chosen folder (`ChatPage.tsx:1228-1230`). It has no PWA manifest or service worker (`web/public/` holds only the favicon and fonts).

### Hermes Mobile

13. **The Projects screen only edits.** Tapping a project card opens the edit sheet (`ui/projects/ProjectsScreen.kt:281`, app), and the screen never lists sessions.
    - History groups by project with its own rules (`ui/sessions/SessionProject.kt:27-55`, app). They have no home-directory rule.
    - Dashboard and phone chats record the service user's home directory as `cwd`, whose last segment is `hermes`. That is the "hermes" group.
    - New project chats use the first folder, not the primary one (`data/model/ProjectLaunch.kt:5`, app).
14. **The app already handles the pieces.** It has a pinned section in History (`ui/sessions/components/PinnedSectionHeader.kt`, app) and opens a bot's canonical chat from its roster (`ui/bots/BotsScreen.kt:403-433`, app). So "open the owner chat on tap" has a pattern to copy.
15. **The app is active and takes requests.** Its project features shipped through issues (#1526, #1527, #1581, #1669 in github.com/Hy4ri/hermes-mobile, read on 2026-11-08). Feature requests use `.github/ISSUE_TEMPLATE/feature_request.yml`. An official Nous mobile app is in beta (hermes-agent.nousresearch.com/mobile; the community app's issue #1752 discusses it).

### Live data (metadata only, read 2026-11-08)

16. **Projects and pinned sessions.** There are six projects. Nine sessions are pinned, including:
    - five "<Project> — Orchestrator" sessions, one each for Hermes Improvement, SDLC, Budgeting, Home Eng and Minecrafting;
    - "Model Master" (Model Testing folder);
    - "Llama-bored" (Home Eng folder);
    - "Home" (no `cwd`);
    - the default profile's "Bot Chat".

## Options map

Only the choice still open after refinement: where the dashboard Projects page lives.

| Option | Ugly part | Fit |
|---|---|---|
| **A core dashboard page** (`web/src/pages/`, a "Projects" nav entry next to Sessions) | Touches core `web/` files, so more rebase work until upstream takes it | Can be offered upstream as a general feature; links straight into Chat and Sessions |
| **A dashboard plugin tab** (`plugins/<name>/dashboard/`, like Kanban and Usage) | It is a tab among plugins, not core navigation, and it is less likely upstream wants it as a plugin | No core `web/` edits; the fork already ships the model-routing plugin this way |

Prior art from round 1 (Claude Projects, ChatGPT Projects: a project page that lists its chats) still holds. Neither has an owner chat.

## Questions for Alex

❓ **Q1** — **Is `/new` turning into a compaction needed in slice 1?** Your scope list said "`/new` compacts instead of forking, like a Bot Chat".

The refiner proposes dropping it. With a pointer, `/new` in the owner chat just starts a separate new chat in the same folder. The owner chat stays pinned and untouched, and automatic compaction already makes it "just compact". Bot Chat needs the guard only because its identity is its title.

The alternative is to keep a guard. Cheapest: ask Hermes Mobile, in the issue 1 draft, to treat the chat whose id is the project's `owner_session_id` like Bot Chat. The app already has that code path (`ChatViewModel.kt:4669`). Costliest: a server/TUI guard that also covers the dashboard.

➡️ No server or TUI guard in slice 1. Do add one sentence to the issue 1 draft asking the app to reuse its Bot Chat `/new` → `/compact` path for owner chats. That gives your main surface the behaviour at no Hermes cost. Revisit a dashboard guard only if you find yourself starting over in an owner chat by accident.

---

❓ **Q2** — **Which session owns each project at seeding?**

➡️ The five "<Project> — Orchestrator" sessions, plus "Model Master" for Model Testing. "Llama-bored" stays pinned but is not Home Eng's owner; "Home Eng — Orchestrator" is.

---

❓ **Q3** — **Is the dashboard Projects page a core page or a plugin tab?** (See the options map.)

➡️ A core page, with a "Projects" entry next to Sessions. It is a general feature worth offering upstream, it sits beside the pages it links to, and the code it reads (`project_tree.py`) has not changed in v0.23.0. A plugin tab is the fallback if upstream declines.

## Open (not answerable by talking)

- What the project page looks like on a phone (how many sessions, where the "new chat" button goes). This needs a mock-up at the Plan/UX gate.
- Whether upstream Hermes wants `owner_session_id`. This needs the upstream proposal sent with the fork patch.
- Whether the Hermes Mobile maintainer adopts a field that only our fork serves until upstream takes it. This needs the drafted issue and the answer.

## Verify later

- **Opening a project** on the dashboard (laptop and phone browser) opens its owner chat, and the page lists the same sessions `/api/profiles/projects/tree` returns for that project.
- **`projects.list` and `projects.get`** return `owner_session_id`, and `projects.update` sets and clears it. A test against a temporary Hermes home covers the migration on an existing `projects.db`.
- **A project with no owner,** or whose owner session was deleted, shows its list and "new chat here" with no error.
- **The seeding fix** sets six owners and its undo file restores them.
- **The current Hermes Mobile build** works unchanged against the patched backend.
- **The issue drafts** exist for Alex to review, and nothing is posted.
- **The backend patch** rebases onto v0.23.0 without conflicts in `projects_db.py` or `project_tree.py`.
