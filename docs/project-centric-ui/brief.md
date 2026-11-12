# Brief: project-centric Hermes UI (DER-686)

Gatherer's brief for the SDLC Brief step. Round 4, 2026-11-11, written headless from:
- Alex's dictated request (2026-11-08) and his 21:00 addition;
- the research note and the project vault;
- the refiner's review (`brief-refine.md`);
- a fresh read of the code on the new base.

**What changed in round 4.** The base moved to Hermes v0.23: branch `integrate/project-centric-ui-023`, cut from the deployed fork branch `alex/v0.23.1-canary-1110` (v0.23.1 plus our carried fork commits).
- Alex's surface is now the gateway Webapp, the desktop app's interface served as a web app, on laptop and phone.
- Alex stopped using Hermes Mobile.
- One combined gateway process now owns every session.

The plan below is re-cut for that base and surface. What the move removed is listed under "Dropped by the v0.23 move". Nothing here is decided beyond what Alex settled; the questions at the end are his to answer.

## Reflection (Alex's dump, tightened)

Alex groups his work into Hermes projects so each one carries its own context. The interfaces do not reflect that: a project's chats are hard to see, and nothing marks a project's main chat.

He wants the project to be the main thing. Tapping a project opens its main chat and shows the chats that belong to it. Each project has one owner chat: permanent, always there, long-lived, a session that "just compacts", like a Bot Chat but tied to a project.

Since 2026-11-11 his surface is the v0.23 Webapp, in a laptop browser and installed to his phone's home screen. His 21:00 requirement still stands: an owner chat must be reachable and steerable from the phone while it works.

## Intent (slice 1, on v0.23)

1. **An owner chat per project, as data.** The `projects` table gets one nullable column, `owner_session_id`.
   - It is returned by the existing `projects.list` and `projects.get` calls, and by the project nodes of the project tree (`projects.tree`, `projects.project_sessions`, `GET /api/profiles/projects/tree`).
   - It is set through the existing `projects.update` call.
   - There are no new remote procedure calls (RPCs).
   - **Session Mail consumes this field:** its planned `@project` addressing resolves to the project's owner session, and it stays switched off until this field exists (Environment fact 27).
2. **Owners seeded once, by session id.** The six owner chats are set with `projects.update`, as a reversible data fix that keeps an undo file. They are identified by id, never by title, because titles have changed and will change again (fact 25).
3. **Project-first in the Webapp.** Tapping a project opens its owner chat and shows the project's chats, with the owner chat marked and listed first. Where this lives is Q1.
4. **The owner chat compacts instead of starting over,** if Alex confirms Q2. In the Webapp this is a composer rule like Bot Chat's: `/new` and `/reset` in an owner chat become `/compact`.
5. **Steerable while it works (the 21:00 requirement).** On v0.23 this is met by the base for every turn the combined gateway runs, including command-line one-shots (facts 17-19). Slice 1 builds nothing for it; it only verifies it live (Verify later).

A project with no owner (or whose owner session is gone) behaves as today.

## Out of scope

- Model routing (DER-675), the GPU host, Home Assistant (settled by Alex).
- The SDLC's shape and the branch/deploy flow (settled; `rules.md` rule 19).
- Per-project memory, instructions or model settings. Project context already comes from files in the project folder (fact 3).
- Session Mail itself. We only provide the field it reads.
- The standalone web dashboard (`web/`). Alex reaches Hermes through the Webapp now (fact 22).
- Hermes Mobile (Alex stopped using it, 2026-11-11).
- Two processes writing one session at once. Hermes forbids this on purpose, and the v0.23 design routes every client to the one owner (fact 17).

## Dropped by the v0.23 move

These were in the round-3 brief or the plan built on it. Each is gone because of the new base or surface:
- **Both Hermes Mobile issue drafts:** the project page with owner chat on top, and the "hermes" History group and first-folder bugs. Hermes Mobile is no longer a target surface.
- **The "working elsewhere" ask to Hermes Mobile.** Same reason.
- **The Projects page or plugin tab in the standalone web dashboard.** Alex does not use the standalone dashboard; the public address serves the Webapp.
- **The dashboard-socket kickoff command (round-3 option A).** On v0.23 a plain `hermes chat -q --oneshot` turn runs in the combined gateway, where the Webapp can steer it (fact 18). Sending kickoffs to the standalone dashboard would now do the opposite: those turns run outside the gateway, where the Webapp cannot steer them (fact 21). The fork's `scripts/dashboard_dispatch.py` now belongs to Session Mail, which is redesigning it for the gateway.
- **The question about rebasing onto v0.23.0 sooner.** Done.
- **The `session.compress` ownership fix as part of this chunk.** On the gateway, compaction is an owner-run session mutation (fact 20). The gap remains only in the legacy chat backend that the standalone dashboard uses, which is a separate fork bug, outside DER-686.
- **The Hermes Mobile constraints:** tolerance of unknown JSON fields, the pinned contract file, and restarts cutting the app off.

## Deferred after slice 1

- **A server or terminal `/new` guard.** The Webapp rule (Intent 4) covers Alex's surface. The command line and terminal interface keep plain `/new`.
- **A "get or create the owner chat" RPC.** The owner chats already exist.
- **A "make owner" button.** Seeding covers the six projects; a later project needs one `projects.update` call.
- **A "Home" pseudo-project with its own owner chat.**
- **Following the compression chain to its tip.** Compaction runs in place and keeps the id (fact 7).
- **The progressive web app (PWA) service worker.** The fork's Webapp already has a manifest, so it installs to the home screen. Offline caching is not asked for.
- **A separate Projects page,** if Q1 lands on the sidebar.

## Constraints

- **Branches only.** Every change goes on a feature branch of the fork, is fast-forwarded into the deployed branch, and is deployed with `git pull --ff-only`. No live edits and no side repos (`rules.md` 19). This also rules out a runtime plugin dropped into `<hermes-home>/desktop-plugins/` (fact 13).
- **The Webapp is rebuilt from the checkout.** Hermes builds the Webapp bundle from `apps/desktop` into `apps/desktop/dist-webapp`, and a build receipt decides freshness (`hermes_cli/webapp.py:1-8, 40-41`). A deploy that changes `apps/desktop` therefore also rebuilds the bundle.
- **One gateway restart.** The combined gateway hosts every surface and every running turn. Slice 1 is one announced gateway restart, scheduled when no owner turn is running.
- **Prompt caching** (`AGENTS.md` invariants). Nothing in slice 1 touches a system prompt. The field is read by clients, and `/compact` is the one allowed rewrite.
- **Narrow core.** One column and one optional `projects.update` field. No model tool and no new RPC.
- **Size ratchet.** `apps/desktop/src/app/chat/sidebar/index.tsx` is 2,078 lines, over the 2,000-line file cap (`scripts/code_health/config.py:26`; `.tsx` files are covered, `:175`). Any change there must move code into a sibling under `sidebar/projects/` so the file shrinks.
- **Profiles are islands.** The column lives in the per-profile `projects.db`, and `projects.update` already takes `profile`.
- **Titles are not identity.** Seeding, the Webapp and Session Mail key on `owner_session_id`, never on a title convention (Alex, 2026-11-11, via the Session Mail notes).

## Decisions

Settled by Alex:
- **Surface (2026-11-11).** The v0.23 Webapp, on laptop and phone. Hermes Mobile is no longer a target.
- **Base.** The fork runs v0.23.1 (`alex/v0.23.1-canary-1110`). Fork changes are offered upstream where they fit.
- **Pins live on the server** (`sessions.pinned`), one flag for the desktop app, the Webapp and other clients (vault, T3-Q2).
- **Session titles use project codes** (`CODE - Role`, for example "HIM - Orchestrator").
- **Already done.** The owner sessions were re-homed into their project folders (undo file under `<hermes-home>/backups/`), and command-line sessions record their `cwd` (carried fork commit `0d2cd4bc6f`).

Taken in refinement and kept (Alex can overturn):
- **Pointer column over a title convention.** It survives renames, which have now happened twice.
- **Existing calls over new RPCs.**

## Assumptions (now explicit)

- **A1.** "Project memories and context" means the context Hermes already loads from the session's working folder. Getting `cwd` right is what ties a chat to its project.
- **A2.** One owner chat per project per profile, because the column lives in the per-profile `projects.db`.
- **A3.** Alex runs the default in-place compaction, so the owner session id never changes.
- **A4.** Alex no longer opens the standalone dashboard. The public address has served the Webapp since 2026-11-10, and the dashboard unit is reached only on the local machine (fact 22).
- **A5.** Owner-session kickoffs keep using `hermes chat --in <project-folder> -c "<title>" --create-if-missing -q "<prompt>" --oneshot -Q`. On v0.23 that runs the turn in the gateway.
- **A6.** An ended owner session can be the owner. Several owner sessions have an end time (live data, fact 25), and resuming one continues the same session.

## Environment facts

Re-verified on the new base. Paths are relative to the worktree; line numbers are this checkout's. Each fact says whether it was kept, changed or is obsolete since round 3.

### Backend: projects

1. **Project storage. Kept.** Projects live per profile in `<hermes-home>/projects.db`, with tables `projects` (:29), `project_folders` (:42), `project_meta` (:54) and `discovered_repos` (:62), all in `hermes_cli/projects_db.py:28-67`.
   - There is no owner, main or pinned session column (:30-39).
   - `update_project` patches only name, description, icon, color and `board_slug` (`:273-295`, fields `:286-291`).
   - `Project.to_dict` is at :173 and `project_for_path` at :462.
2. **How a session finds its project. Kept.** The sessions table still has no project id (`hermes_state_common.py:467`; `cwd` :496, `pinned` :528). A session's project is the deepest project folder containing its `cwd` or repo root (`tui_gateway/project_tree.py:336`).
   - Unplaced sessions go to the synthetic "Home" bucket `__no_project__` (`project_tree.py:29-30`).
   - The home directory and `<hermes-home>` never become auto projects (`tui_gateway/methods_projects.py:133-160`).
   - The project tree leaves out cron, kanban and one-shot sessions (`methods_projects.py:321`, used at :350). This matters because cron runs make up most sessions in the project folders (fact 25).
3. **Project context comes from folder files. Kept, lines moved.** `.hermes.md` is found by `_find_hermes_md` (`agent/prompt_builder.py:141-147`, loaded at :1668). The `AGENTS.md` chain is at :1589 and :1599-1605 (loaded at :1676-1697).
4. **The project RPCs. Kept.**
   - `projects.update` is registered at `tui_gateway/methods_projects.py:71-73`, with list :81, get :86, create :91, archive :104, delete :111, set_active :117 and for_cwd :123.
   - `projects.tree` and `projects.project_sessions` are at `tui_gateway/methods_config.py:137` and `:152`.
   - REST `GET /api/profiles/projects/tree` is at `hermes_cli/web_routers/profiles.py:718`, and the tree's project nodes are built in `project_tree.py:348`.
5. **Nothing project-first upstream. Kept.** v0.23 adds no project home, main chat or owner field. The `owner_session_id` names already in the code mean something else: background-completion pins (`gateway/run_notifications.py:203`) and subagents (`tui_gateway/methods_session.py:2224`). The new field needs a name that cannot be confused with these, or a clear docstring.

### Backend: chats, pins, compaction

6. **Bot Chat for comparison. Kept, lines moved.** Its identity is the exact title "Bot Chat" (`hermes_state.py:1629`), held unique by the title index (`hermes_state_schema.py:136-137`).
7. **Compaction keeps the session id. Kept, line moved** (`compression.in_place: True`, `hermes_cli/config_defaults.py:671`).
8. **Pins are server-side. Changed.** `PATCH /api/sessions/{id}` is at `hermes_cli/web_routers/sessions.py:933-941`. It now goes through `_mutate_session_request` (`hermes_cli/web_server_sessions.py:271`), which is revision-fenced and handled by the session's owner. `set_session_pinned` is at `hermes_state_sessions.py:1062`.

### Webapp (the desktop app's interface in a browser)

9. **Same code as the desktop app. New.** The Webapp is the same React source as Electron, built by `pnpm build:webapp` into `apps/desktop/dist-webapp` (`apps/desktop/package.json:31`; `scripts/build-webapp.mjs:50-53`).
   - The gateway serves it (`gateway/run_api.py:100-106`; `gateway/webapp_listener.py:200-208`).
   - A browser bridge stands in for Electron (`apps/desktop/src/main.tsx:5`; `src/lib/browser-desktop-bridge.ts`).
   - Host differences go through one table (`src/lib/host-capabilities.ts:19-84`), and none of them touch projects or Bot Mode.
   - The fork's manifest is `apps/desktop/public/assets/manifest.webmanifest` (`display: standalone`), linked at `apps/desktop/index.html:12`.
10. **Tapping a project only scopes the sidebar. New** (paths under `apps/desktop/src/app/chat/sidebar/`).
    - The project row calls `onEnterProject` (`index.tsx:1243-1254`), which runs `enterProject` (`apps/desktop/src/store/projects.ts:107-120`). That narrows the sidebar and, for real projects, calls `projects.set_active`; it never opens a chat.
    - The entered view lists the project's chats from `projects.project_sessions` (`index.tsx:1057-1086`; `projects/entered-content.tsx:41-90`): main-checkout chats flat, worktrees by branch.
    - Each overview row previews three chats with "Show all" (`projects/overview-row.tsx:139-178`).
    - So "shows the chats that belong to it" already exists. "Opens the main chat" and "main chat first" do not.
11. **New chat in a project, and editing projects. New.**
    - The row's "+" starts a chat in the project's primary path, else its first repo (`projects/overview-row.tsx:159-162, 221`; `resolveNewSessionCwd`, `store/projects.ts:166-188`).
    - Projects can be created, renamed, recoloured and given folders from the Webapp (`projects/project-dialog.tsx:122-170`, `projects/project-menu.tsx:97-115, 209, 293`).
12. **Pinned chats leave their project's list. New.**
    - Pins sync both ways with the server (`apps/desktop/src/store/session-pin-sync.ts:1-22, 193-314`).
    - The Pinned section is global and sits above the project list (`index.tsx:693-706, 1757-1782`).
    - Pinned rows are filtered out of every project list, including the entered project (`index.tsx:708-745, 1079-1086`).
    - So a pinned owner chat would appear in Pinned, not in its project. A pinned row has no badge; only its menu says "Unpin".
13. **Plugins can add everything slice 1 needs, without touching core interface files. New.**
    - Bundled plugins live in `apps/desktop/src/plugins/<name>/plugin.tsx` and load at boot (`apps/desktop/src/plugins/README.md`). The bundled ones today: hermes-bots, kanban, radio, hello-runtime.
    - Contribution areas include:
      - routes (`src/app/routes.ts:88`);
      - sidebar navigation (`routes.ts:128`);
      - session-row badges (`src/lib/session-row-slots.ts:19-22`, keyed on the durable stored id, which survives compaction);
      - composer middleware (`src/app/chat/composer/contrib.ts:32`);
      - the command palette (`src/app/command-palette/contrib.ts:10`).
    - There is no area on the project row itself, so changing what a tap does needs a core change.
    - Runtime plugins can also load from `<hermes-home>/desktop-plugins/<name>/plugin.js`, which `rules.md` 19 excludes.
14. **Bot Mode in the Webapp. Kept, now on Alex's surface.**
    - The hermes-bots plugin is active in the Webapp. It hides Bot Chats from the sidebar (`apps/desktop/src/plugins/hermes-bots/session-sweep.ts:35-55, 222-247`).
    - Its composer middleware rewrites `/new` and `/reset` to `/compact` with a notice, only in that bot's canonical chat (`plugin.tsx:761-804`; regex :774, check :790).
    - That is the pattern Intent 4 would copy, keyed on `owner_session_id` instead of a title.
15. **Narrow screens. New.** Below 640 pixels the sidebar becomes a drawer (`apps/desktop/src/app/layout-constants.ts:30-32`; `src/components/pane-shell/tree/renderer/narrow-overlays.tsx`). The drawer does not close when a chat is picked (no dismiss on row tap found). The fork's short-viewport work is in `apps/desktop/src/lib/short-viewport.ts` and `src/lib/browser-viewport.ts`.
16. **Busy chats in the Webapp. New.**
    - The composer follows the backend's busy mode (interrupt, queue, steer; `apps/desktop/src/store/busy-input-mode.ts:3-16`; `src/app/chat/composer/busy-submit-state.ts:22-55`).
    - Opening a chat whose turn is running elsewhere joins it live: `running`, the partial reply and the queue come back on resume (`src/types/hermes.ts:820-907`; `src/app/chat/use-session-actions/index.ts:1564-1597`).
    - A refusal `SESSION_NOT_OWNED` shows "Chat open somewhere else" with "Start new session" (`src/app/chat/use-prompt-actions/utils.ts:317-367`; `src/i18n/en_error_codes.ts:139-141`).

### Session ownership on the combined gateway

17. **One gateway owns every session. Changed.**
    - The session authority owns live sessions and their durable queue, one per profile home, all in one gateway (`gateway/session_authority.py:1-4`; `gateway/session_authorities.py:1-10`).
    - The gateway also serves `/api/ws` and the Webapp: a socket gets the authority (`tui_gateway/ws.py:377-401`; `hermes_cli/web_routers/chat_ws.py:650-692`), and socket tickets come from `hermes_cli/web_routers/webapp.py:182`.
18. **A command-line one-shot's turn runs in the gateway. Changed** (was: in the CLI process).
    - The CLI imports `GatewayAgent` "the gateway runs the turn" (`hermes_cli/cli_agent_setup_mixin.py:647`). It never builds an agent or writes the state database (`hermes_cli/gateway_agent.py:1-6`).
    - It connects through `connect_gateway`, which starts the gateway if needed (`hermes_cli/gateway_client.py:319-331`).
    - The CLI still writes a lease to `<hermes-home>/runtime/active_sessions.json` (`hermes_cli/cli_single_query.py:504`; `cli.py:914-938`; `hermes_cli/active_sessions.py:183, 540`).
19. **The Webapp can steer, queue and stop a gateway turn without `SESSION_NOT_OWNED`. Changed** (was: refused with 4090).
    - Requests on the gateway go to its own handler table (`gateway/session_controls.py:221-246`). It checks capabilities, profile and session (`gateway/session_authority.py:200-230`), not the lease file.
    - Steer and redirect: `gateway/session_busy_controls.py:176-211`. Queued submits: `gateway/session_controls.py:855-875`.
    - The CLI's lease refuses only legacy, non-gateway backends (`tui_gateway/session_lifecycle.py:121-139`).
    - Not verified: what happens to a gateway turn if the CLI process exits mid-turn.
20. **Compaction on the gateway is run by the owner. Changed** (was: a hazard). On the gateway, compaction is a `session.mutate` operation handled by the owning authority (`gateway/session_mutations.py:116-143, 240`).
    - The missing ownership check on the legacy `session.compress` remains (`tui_gateway/methods_session.py:2118-2142`), but only the legacy backend reaches it.
21. **The legacy chat backend still runs its own turns. Changed.**
    - The standalone dashboard's `/api/ws` has no session authority, so it uses the legacy `tui_gateway` dispatcher and runs turns in its own process (`tui_gateway/ws.py:382, 399`).
    - A prompt it receives while the gateway's queue holds work for that session is forwarded to the gateway (`tui_gateway/methods_prompt.py:721-766`; `tui_gateway/owner_forward.py:1-17`). Its steer, interrupt and compress stay local.
    - The fork's `scripts/dashboard_dispatch.py` targets this backend by default (local port 9119; `:137-138, :168`). On the gateway it would be refused: its steer lacks `execution_generation` and its submit lacks `submission_id` (`gateway/session_busy_controls.py:177-180`; `gateway/session_controls.py:864-866`).

### Standalone dashboard

22. **Still a separate process with no Projects page. Kept.**
    - `hermes dashboard` runs its own server (`hermes_cli/main.py:2597`; `hermes_cli/web_server.py:1415`).
    - Its REST session edits are forwarded to the live gateway (`hermes_cli/web_server_sessions.py:188-261`).
    - `web/src/App.tsx:141-221` still has no projects route.
    - Live: both `hermes-gateway` and `hermes-dashboard` user units are running (2026-11-11).
    - Since 2026-11-10 the public address serves the gateway Webapp (project vault, Session Mail notes 2026-11-09, entry of 2026-11-11).

### Obsolete since round 3

23. **Hermes Mobile facts. Obsolete as targets.** These covered the app's Projects screen, History grouping, the "hermes" group, its 4090 recovery card and its busy-send modes. The local clone was removed on 2026-11-11.
24. **Round-3 option A** (owner turns run in the dashboard process through a socket script). **Obsolete:** see facts 18, 19 and 21.

### Live data (metadata only, read 2026-11-11)

25. **Projects, owner sessions and pins.**
    - **Six projects,** none archived. Names now carry codes: "HIM - Hermes Improvement", "SDL - SDLC", "BDG - Budgeting", "HME - Home Engineering", "MCR - Minecrafting", "MDL - Model Testing".
    - **The six owner sessions,** by id, all with `cwd` in their own project folder:

      | Title | Session id | Ended? (end reason) | Pinned? |
      |---|---|---|---|
      | HIM - Orchestrator | `20261108_104615_5aa709` | open | no |
      | SDL - Orchestrator | `20261108_104526_a0efdc` | ended (`ws_orphan_reap`) | no |
      | BDG - Orchestrator | `20261108_103344_00ea0d` | ended (`cli_close`) | no |
      | HME - Orchestrator | `20261108_103344_bdbb6c` | ended (`ws_orphan_reap`) | yes |
      | MCR - Orchestrator | `20261108_103344_0fd38b` | ended (`cli_close`) | no |
      | MDL - Model Master | `20261108_103344_8f523b` | ended (`cli_close`) | no |

    - **Pins:** five sessions are pinned now, against nine on 2026-11-08: "HME - Orchestrator", "HME - Llama-bored", "Home", the hidden "Bot Chat", and one chat in a repo folder.
    - **Sessions:** there are 412. Cron accounts for 363, mostly in the Model Testing and SDLC folders, and the project tree leaves these out (fact 2). Twelve have no `cwd`, and 13 use the service user's home directory.
26. **Other chats in the Hermes Improvement folder.** "HIM - Project UI", "HIM - Session Mail" and "HIM - T3 Code Frontend" sit there too, so the owner mark is what tells the main chat apart.
27. **Session Mail depends on this chunk.** Its design offers `@project` only when "DER-686's projects plugin is enabled and `projects.owner_session_id` exists". Otherwise it refuses with `project-addressing-unavailable`, and it is off at launch (vault, Session Mail notes 2026-11-09, entry of 2026-11-11). If slice 1 ships no plugin, that switch needs a different signal (Q4).

## Options map

### Where the project-first behaviour lives in the Webapp

| Option | Ugly part | Fit |
|---|---|---|
| **A. Small core sidebar change.** Tapping a project with an owner scopes the sidebar and opens the owner chat. The entered list shows the owner chat first, marked "Main chat", even if pinned. | Touches core sidebar code. `index.tsx` is over the size cap, so code must move into a `sidebar/projects/` sibling. Needs an upstream-friendly guard: no owner means no change. | Where Alex already taps. Reuses the entered view's chat list (fact 10). Smallest visible change; offerable upstream with the column. |
| **B. A bundled desktop plugin with a Projects page** (`apps/desktop/src/plugins/<name>/`): a route listing the owner chat first and chats by recency, a nav entry, a "Main chat" row badge. | Duplicates the sidebar's project list. A tap on the sidebar row still only scopes. Two places show the same thing. | No core interface files touched. Gives Session Mail its "plugin enabled" switch. |
| **C. Both:** A for the tap and the ordering; a small bundled plugin for the row badge and the `/new` rule. | Two pieces to review. | Each piece sits where its hook is; the plugin also covers Intent 4. |
| **D. A runtime plugin** in `<hermes-home>/desktop-plugins/`. | Lives outside the fork; excluded by `rules.md` 19. | None. |

### The owner chat and pins

| Option | Ugly part | Fit |
|---|---|---|
| **Leave pins as they are** and show the owner first in its project by the owner field | An unpinned owner is not in the global Pinned section | Pins stay Alex's own choice, which other clients also use (T3 lists only pinned chats) |
| **Pin every owner at seeding** | Pinned rows leave their project's list (fact 12), so the owner would vanish from the project unless option A also re-adds it | Owners always one tap away |

### Steering from the phone

**No options left to choose.** On v0.23 the base does it (facts 18-19). The only question is a live check.

## Questions for Alex

❓ **Q1** — **What should tapping a project in the Webapp do, and where does the code live?** (Options A, B, C above.)

➡️ Option C:
- **A small core sidebar change.** Tapping a project that has an owner opens its owner chat and scopes the sidebar to the project, with the owner chat first, marked "Main chat".
- **A small bundled plugin** for the row badge and the `/new` rule.

The sidebar already lists a project's chats, so a separate Projects page would duplicate it. The plugin keeps everything that has a hook out of core files.

---

❓ **Q2** — **Should `/new` in an owner chat compact it instead of starting a new chat?** You listed this on 2026-11-08; round 2 deferred it.

What changed on v0.23:
- In the Webapp it is a copy of Bot Chat's composer rule, about 40 lines in a plugin (fact 14).
- Compaction on the gateway is run by the session's owner, so the round-3 hazard is gone (fact 20).

The alternative is plain `/new`, which starts a separate chat while the owner chat stays as it is.

➡️ Yes, in the Webapp only, with the same notice Bot Chat shows. The command line and terminal interface keep plain `/new`.

---

❓ **Q3** — **Which sessions are seeded as owners, and should seeding change pins?**

➡️ The six sessions in fact 25, by id: the five Orchestrators plus "MDL - Model Master". Leave pins as they are. Five of the six have ended, which is fine: opening one resumes it.

---

❓ **Q4** — **What signal turns on Session Mail's `@project`?** Its design waits for "the projects plugin is enabled and `projects.owner_session_id` exists". That is a Webapp plugin plus a server field, but `@project` is used by agents, which never load the Webapp.

➡️ The server field alone. `@project` works when `projects.list` returns `owner_session_id` and the named project has one set. Tell Session Mail before it builds; the Webapp plugin stays a display matter.

## Open (not answerable by talking)

- **The narrow-screen layout:** what the "Main chat" row and the open-on-tap look like in the phone drawer, which does not close on its own when a chat is picked (fact 15). This needs a mock-up at the Plan/UX gate.
- **The CLI exiting mid-turn:** whether a gateway turn started by a command-line one-shot keeps running (and stays steerable) if the CLI process exits mid-turn, for example when its unit hits its time limit. This needs a live check.
- **Upstream interest** in `owner_session_id` and the sidebar change. This needs the upstream proposal.

## Verify later

- **Owner field.** `projects.list`, `projects.get` and the project tree return `owner_session_id`; `projects.update` sets and clears it. A test against a temporary Hermes home covers the migration on an existing `projects.db`.
- **Seeding.** The fix sets the six owners by id, and its undo file restores them.
- **Tap.** In the Webapp, on laptop and phone, tapping a project with an owner opens its owner chat. The project's list shows the owner first, marked "Main chat", whether or not it is pinned. A project with no owner behaves exactly as before.
- **Renames.** Renaming the project or the owner chat changes nothing about which chat is the owner.
- **`/new`** (if Q2 is yes). `/new` in an owner chat in the Webapp compacts it with a notice, and the session id stays the same. `/new` anywhere else is unchanged.
- **Steering from the phone.** While a kickoff started with `hermes chat -q --oneshot` is running an owner turn, Alex opens that chat in the Webapp on his phone. He sees it running, and queue, steer and stop all work. No "Chat open somewhere else" card appears.
- **Session Mail.** `@<project>` resolves to the owner once the field is set (if Q4 is answered as recommended).
- **Size ratchet.** `sidebar/index.tsx` is no longer than 2,078 lines after the change.
- **Rollout.** One announced gateway restart. The Webapp bundle rebuilds on deploy, and nothing else in the live layout changes.
