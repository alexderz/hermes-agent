# Refine: project-centric Hermes UI (DER-686)

## Round 3 (2026-11-08)

Only the delta from Alex's 21:00 addition is checked: Intent 5, A6–A7, facts 17–29, the five steering options, the Q1 note, Q4 and Q5. Alex's words: owner sessions "must be reachable and steerable from the phone while they work. Either run them inside the dashboard/gateway that the app talks to, or let the app queue or interject into a session that another process holds."

| Item | Verdict | Reason |
|---|---|---|
| Intent 5 (open, queue, steer, stop from the phone while a turn runs) | **Keep** | This is Alex's requirement. "Stop" comes free with option A. |
| A6 (owner turns come from a kickoff unit running `hermes chat -q --oneshot`) | **Keep** | It locates the problem in Alex's tooling, not in Hermes. |
| A7 ("steerable" = the app's existing queue/guide/correct/interrupt) | **Keep** | No new control. |
| Option A (kickoff submits through the dashboard's `/api/ws`; the phone attaches to the same live turn) | **Keep, simplify** | This is Alex's first suggested route, with no Hermes change. The script only connects, sends `session.resume` plus `prompt.submit`, waits for completion and exits. Drop "handle reconnects": if the socket drops, the turn may be reaped and the kickoff is re-run. Add reconnects only if that happens in practice. The script is Alex's tooling, outside the fork branch. |
| Option D (one "working elsewhere / retry when done" sentence in issue draft 1) | **Keep** | One sentence. Under A, it only matters for ad-hoc CLI use. |
| Option B (cross-process mailbox patch) | **Kill** | It is a core turn-path patch that v0.23.0 replaces (facts 28–29), and it gives queueing only. The brief already advises skipping it; drop it from the options shown to Alex. |
| Option E (start owner work by hand only) | **Kill as an option** | It is the status quo with automation removed, and option A already covers hand use. |
| Option C / Q5 (move the v0.23.0 rebase earlier; first a v0.23.0 spike) | **Simplify** | The recommendation "not yet" keeps Alex's settled order. Drop the v0.23.0 spike from this run and put it in work item 3 (fork upkeep), where it decides whether option A's script retires. This run needs nothing from v0.23.0, since option A meets the requirement on v0.22.0. Q5 then becomes a note, not a question. |
| Q1 note: the app compacts an owner chat "only when not busy elsewhere" | **Simplify** | The app cannot see a turn running elsewhere (fact 27), so it cannot implement that condition. Under option A the owner turn runs in the dashboard process, where `session.compress` already refuses while the session is busy (`_manual_compress_turn` raises `CompressionBusy`, `tui_gateway/session_compression.py:242-249`). Drop the clause. |
| Q1 note: fix `session.compress` ignoring a foreign process's lease (fact 22) | **Move out** | It is a genuine bug, but Alex didn't ask for this fix and option A removes the owner-chat case. File it as its own fork bug, not part of DER-686. |

Fact checks (code, read-only):
- 18: lease identity is (pid, live session id) (`hermes_cli/active_sessions.py:136-148`). Verified.
- 19: the one-shot claims the lease before its turn (`hermes_cli/cli_single_query.py:522`). Verified.
- 20: `prompt.submit` checks the lease before the busy/queue path and returns 4090 (`tui_gateway/methods_prompt.py:774-778`); `session.create` and `session.resume` claim nothing (`session_lifecycle.py:121-125`). Verified.
- **Option A's key premise:** a phone `session.resume` on a session already live in the dashboard process reattaches to the same live session alongside the existing client (`_claim_or_reuse_live` → `_resume_reuse_live`, `tui_gateway/methods_session.py:657-662, 868-891`). It does not mint a second live id that would trip the (pid, live id) check. So the phone's queue, guide and interrupt act on the running turn. Verified in code, not run live.
- Hermes Mobile connects to `/api/ws` (`data/remote/ServerEndpoint.kt:38`, app), the same route as `hermes_cli/web_routers/chat_ws.py:701`. Verified.
- 22: `session.compress` has an in-process busy guard and a DB lock against concurrent compactions, but no check for a turn in another process (`tui_gateway/methods_session.py:2136-2160`). Substance verified; "no ownership check" is accurate.
- 25, 26: `BusySendMode` has the four modes, and the 4090 recovery text is as quoted (`res/values/strings.xml:2143`, app). Verified.
- 29: v0.23.0 has `tui_gateway/owner_forward.py` and `_slot_refusal` sending ledger refusals to the owner's queue (`methods_prompt.py:720-730` @v0.23.0). Verified. "Queue only, no steer" and the co-viewer path were not checked; with Q5 moved out, nothing here depends on them.
- 17, 27 (live session row, app busy detection): not re-checked; they don't change the recommendation.

Net change to the brief: Intent 5 is met by option A plus one sentence in issue draft 1, with no Hermes code. Options B and E, the Q5 spike, the Q1 "busy elsewhere" clause and the compress fix leave this run. These cut the gatherer's additions, not Alex's requirements, and no new open point appears. The Plan step can apply them directly.

Refine: pass

---

## Round 2 (2026-11-08)

Re-checked only what changed against the round-1 delta and Alex's words.

| Round-1 delta | Round-2 brief | Verdict |
|---|---|---|
| Drop the `/new` guard (client and server/TUI) | Deferred; Q1 asks Alex, recommends no server/TUI guard plus one sentence in issue draft 1 asking the app to reuse its Bot Chat `/new` → `/compact` path | **Keep.** Costs Hermes nothing and gives the main surface the behaviour from Alex's scope list. |
| Drop get-or-create RPC, tip resolution, Home owner, "make owner" UI | All listed under "Deferred after slice 1" | **Keep.** |
| Owner = one column through existing `projects.*` calls | Intent 1, no new RPCs | **Keep.** `to_dict` builds from `_OPTIONAL_ROW_FIELDS` (`projects_db.py:173`) and `projects.update` picks params at `methods_projects.py:72`, so the change is small, as claimed. |
| Ask which "projects section in the web app" Alex means | Answered by fact (fact 10, A5): the dashboard has none; the Kanban board-settings binding is unused (no project has a `board_slug`) | **Keep.** Checked: core routes and plugin tabs (Achievements, Kanban, Usage) match; live `board_slug` is empty for all six projects. Asking Alex is no longer needed. |

New in round 2, checked:
- **Q2 (seed owners)**: five Orchestrators plus "Model Master"; "Llama-bored" not an owner. Fine; the undo file matches the earlier re-homing.
- **Q3 (core page vs plugin tab)**: a real open choice for the Plan step, not added scope. The recommendation (core page) is reasonable.
- **Old app builds**: `ignoreUnknownKeys = true` with snake_case naming (`data/remote/OkHttpProvider.kt:92-97`, used by `HermesWsClient.kt:94-96`, app). Verified.
- **Prior pattern in the app**: `BotsScreen.kt:403-433` (app) opens `canonical_session.resolved_id ?: id`. Verified. `PinnedSectionHeader.kt` path corrected to `ui/sessions/components/`. Verified.

Nothing new is speculative, nothing Alex asked for is lost, and no new unresolved point needs the gatherer. Q1–Q3 are Alex's to answer at the gate.

Refine: pass

---

## Round 1


Refiner's pass on `brief.md`, 2026-11-08. Checked against Alex's dictated words, the research note, `lessons.md` ("Too much process for a small feature": build a small working slice, show it, then harden) and the code in the fork and the Hermes Mobile clone.

## What Alex asked for (his words, reduced)

1. Tapping a project shows its chats and opens "the project's main chat or something like that".
2. Each project has one owner chat: "special, long-lived, always-there, permanent", "a long-lived session that just compacts".
3. History's "group by project" shows his projects, not "hermes".
4. It works in Hermes Mobile (main surface) and in the web app on laptop and phone.

He did not ask for: a `/new` guard on every surface, a "Home" pseudo-project, per-project settings, a get-or-create RPC, or rename protection. "Just compacts" is already true: automatic compaction runs in place and keeps the session id (verified below).

## Keep / simplify / kill

| Item in brief | Verdict | Reason |
|---|---|---|
| Intent 1: project page lists its sessions, owner chat on top, opening the project opens it | **Keep** | This is Alex's core ask. |
| Intent 2: one owner chat per project, as a backend field | **Simplify** | One nullable column `projects.owner_session_id`, returned by the existing `projects.list` / `projects.get` and the project nodes of `/api/profiles/projects/tree`, and set through the existing `projects.update`. No new RPCs. Old app builds ignore the extra field (the app's wire JSON uses `ignoreUnknownKeys = true`), so the -32601 "method not found" fallback is not needed at all. |
| Intent 2: "`/new` compacts instead of a new session" | **Kill for slice 1** | With a pointer, `/new` in the owner chat starts a new chat in the same folder; the owner chat stays pinned and untouched, so nothing is lost. Bot Chat needs the guard because its identity is a title; a pointer does not. Automatic compaction already gives "just compacts". Revisit only if Alex finds himself forking the owner chat by accident. |
| Q2: server/TUI `/new` guard keyed on an owner flag | **Kill** | A core slash-handling change for a need the pointer removes. It also touches the TUI, CLI and gateway, which is the most expensive part of the brief. |
| Q1 option A's "get or create" RPC | **Kill** | The owner chats already exist (A3). A project with no owner shows its list and a "new chat here" button; making one the owner is one `projects.update` call. |
| Q1 option A's "pointer resolves to the compression tip, deleted session clears it" | **Simplify** | Alex runs the default `compression.in_place: true` (his config does not override it), so the id never rotates. Clients treat a missing session as "no owner". No tip resolution, no cascade code. |
| Setting the owner from the UI | **Kill for slice 1** | Seed the six owners once with `projects.update` (the same kind of reversible data fix as the re-homing already done). A "make owner" button can come later if new projects need it. |
| Intent 3: dashboard project view on laptop and phone browser | **Keep, simplify** | One Projects page in the dashboard: project list → project page with the owner chat on top (`/chat?resume=<id>`), then sessions by recency, and a "new chat here" button. Reads only from `/api/profiles/projects/tree`, so no REST write endpoint is needed. This also delivers the feature on Alex's phone (in the browser) without waiting for the app maintainer. |
| Intent 3: PWA | **Keep deferred** | Already a separate follow-up after routing step 1 (settled). |
| Intent 4: no "hermes" group in History | **Keep** | It is a Hermes Mobile bug (no home-directory rule in `SessionProject.kt`); drafted upstream issue only. The dashboard has no History grouping, so nothing to fix there. |
| "New chat uses the first folder, not the primary" app bug | **Keep, as an issue draft only** | Small and real (`ProjectLaunch.kt:5` uses `folders.firstOrNull()`). Costs one paragraph in a drafted issue. |
| Q3: Hermes Mobile via drafted upstream issues | **Keep** | Settled path. Shrink to two drafts: (1) project page with owner chat on top, reading `owner_session_id` from `projects.list`; (2) the "hermes" group and first-folder bugs together. Drop "Alex should name the wait time" as a gate; he can decide when the draft is in front of him. |
| Q5 / A6: "Home" gets an owner chat as a pseudo-project | **Kill** | Alex used "the main Home session" as an example of an owner chat, not as a request. Home is not a project, and the pinned "Home" chat already sits in the pinned section on the phone. |
| Q6 / A1: per-project memory and instructions out of scope; context comes from folder files | **Keep** | Verified: `agent/prompt_builder.py:140` finds `.hermes.md` / `HERMES.md` from the session's cwd. |
| A2: one owner per project per profile | **Keep** | Falls out of the column living in the per-profile `projects.db`. |
| A3: existing pinned sessions become the first owners | **Keep** | "Llama-bored" is pinned but its project is not named in the brief; Alex picks or leaves it out when seeding. |
| A4: dashboard opens chat with `/chat?resume=<id>` | **Keep** | Verified (`web/src/pages/ChatPage.tsx:372`). |
| A5: compaction keeps the session id | **Keep** | Verified default and live config. |
| Constraint: prompt caching | **Keep** | Nothing in the simplified slice touches the system prompt. |
| Constraint: `profile` parameter on new RPCs | **Simplify** | There are no new RPCs; `projects.update` already takes it. |
| Constraint: pinned OpenRPC contract, -32601 fallback | **Simplify** | Only an added response field and an added optional `projects.update` param; contract tests may need the new field listed. |
| "Verify later": rename keeps the link; `/new` compacts on every surface; tip resolution | **Kill those three lines** | Rename is free with a pointer; the other two are killed above. |
| Open: upstream wants `owner_session_id`? | **Keep** | Still true; draft the upstream proposal with the fork patch. |
| Options map, prior-art tables | **Trim** | Useful once; the Plan step needs only option A as simplified here. |

## Smallest first slice

1. **Backend (fork branch, ~100 lines plus a temp-`HERMES_HOME` test):** add `owner_session_id` to `projects` (migration), to `Project.to_dict()`, to `update_project` / `projects.update`, and to the project nodes of the tree builder. Seed the owners for Alex's six projects with `projects.update`.
2. **Dashboard (fork branch, one page):** Projects list → project page: owner chat on top (opens `/chat?resume=<id>`), the rest by recency, "new chat here". Works on the laptop and the phone browser.
3. **Hermes Mobile (no code from us):** two issue drafts for Alex to review: the project page reading `owner_session_id`, and the "hermes" group plus primary-folder bugs.

One deploy, one dashboard restart. Show it to Alex, then decide on the `/new` guard, a "make owner" button, the PWA and Home.

## Fact checks

Verified in code:
- 1, 2: `projects.db` schema has no owner/pinned/memory column; `project_for_path` at `hermes_cli/projects_db.py:462`; `__no_project__` at `tui_gateway/project_tree.py:29`; home and `<hermes-home>` are never auto projects (`methods_projects.py:133-160`).
- 3: the app's `resolveSessionProject` falls back to the cwd leaf with no home-directory rule, so a home-directory cwd shows as its leaf name. Correct.
- 4: `projects.tree` / `projects.project_sessions` exist (`tui_gateway/methods_config.py`); `GET /api/profiles/projects/tree` at `hermes_cli/web_routers/profiles.py:718`; nothing in `web/src` calls them.
- 6: Bot Chat identity is the exact title (`hermes_state.py:1604-1609`); the unique title index exists (`hermes_state_schema.py`).
- 7: the desktop rewrite (`hermes-bots/plugin.tsx`) and the app's title check (`ChatViewModel.kt`, around line 4670) exist; no guard in `ui-tui` or `tui_gateway`.
- 8: `compression.in_place: True` default (`config_defaults.py:686`); Alex's config does not override it.
- 9: `pinned` column and `PATCH /api/sessions/{id}` setters exist.
- 11: no Projects route in `web/src/App.tsx`; web `SessionInfo` lacks `cwd`, `git_repo_root`, `pinned`; `/chat?resume=` works.
- 12: `web/public/` holds only the favicon and fonts.
- 14: tapping a project card calls `onEdit` (`ProjectsScreen.kt:281`); new chats use the first folder (`ProjectLaunch.kt:5`).
- Constraints: the app's contract pins hermes-agent v0.22.7 (`gateway-contract/SOURCE`); its `CONTRIBUTING.md` bans AI co-author trailers.

Imprecise:
- 11 is true for the core dashboard, but Alex says the web app has "a projects section" where he can edit settings. The only project UI in the dashboard is the Kanban plugin's board-to-project binding (`plugins/kanban/dashboard/plugin_api.py:1398`, list only). Either Alex means that, or he means the phone app's screen. This matters only for where the new page goes; see delta.
- Line numbers drift by a few lines in places (for example `ChatViewModel.kt`); substance holds.

Not verified (no network from this pass): 10 (v0.23.0 byte-identical), 15 (the shipped issue numbers; the local clone shows #1741 only), 16 (official Nous app), 17 (live session counts).

## Back to Gather?

Yes. Requirements die and one small point is new:
- **Killed:** the `/new` → compact guard (client and server/TUI), the get-or-create RPC, compression-tip resolution, the Home pseudo-project owner, owner-setting UI in slice 1. Alex should confirm he is fine without the `/new` guard at first, since "compacts instead of starting over" was in the session's scope list.
- **New:** which "projects section in the web app" Alex means (the Kanban plugin's project binding, or the phone app's Projects screen), so the dashboard page lands where he looks.

Refine: back to Gather — drop the `/new` guard, get-or-create RPC, tip resolution and Home owner from slice 1 (confirm with Alex); owner is one column exposed through existing `projects.*` calls; ask which "projects section in the web app" Alex means.
