# Refine: project-centric Hermes UI (DER-686)

## Round 4 (2026-11-11, base v0.23.1, surface the gateway Webapp)

Checked only the round-4 delta against Alex's words (unchanged apart from the surface) and the v0.23 code in this worktree. Alex's ask on this surface: tap a project → see its chats and open "the project's main chat"; one permanent owner chat that "just compacts"; steer it from the phone while it works.

| Item | Verdict | Reason |
|---|---|---|
| "Dropped by the v0.23 move" (Mobile drafts, dashboard page, socket kickoff, rebase question, compress fix, Mobile constraints) | **Keep** | Each drop follows from the new base or surface. The legacy `session.compress` gap stays a separate fork bug. |
| Intent 1: `owner_session_id` column through existing `projects.*` calls | **Keep** | Unchanged and still the smallest. Keep the name (Session Mail already references it) and add a one-line docstring for the name clash in fact 5. Don't open a rename. |
| Intent 1 bullet: "Session Mail consumes this field" | **Simplify** | True, but DER-686 builds nothing for it. Keep it as a note, not an intent item. |
| Intent 2: seed six owners by id with an undo file | **Keep** | Titles changed twice, so seeding by id is right. |
| Intent 3 / Q1 option C: core sidebar change **plus** a bundled plugin for a row badge and the `/new` rule | **Simplify** | Alex asked for the main chat to open and come first in its project; he didn't ask for a badge on every list. The core change already lists the owner first, marked "Main chat", so the session-row badge plugin is a duplicate. Drop it. The bundled plugin exists only if Q2 is yes, and then holds only the `/new` composer rule. With Q2 no, slice 1 is option A alone. |
| Option B (plugin Projects page), option D (runtime plugin) | **Kill** | B duplicates the sidebar list and leaves the tap unchanged; D breaks `rules.md` 19. The brief already advises against both. |
| Pins option "pin every owner at seeding" | **Kill** | Pinned rows leave their project list (fact 12), so this would hide owners from the place Alex taps. Q3 already recommends leaving pins alone. |
| Owner shown first "even if pinned" | **Keep** | Needed: "HME - Orchestrator" is pinned today and would otherwise be missing from its project. |
| Intent 4 / Q2: `/new` → `/compact` in the Webapp only | **Keep as Alex's question** | In his scope list; on v0.23 it is a copy of Bot Chat's middleware, and compaction is owner-run on the gateway. |
| Intent 5: steering met by the base, verify only | **Keep** | Verified in code (below). The CLI-exits-mid-turn case stays a live check. |
| Q3 (seed the five Orchestrators plus "MDL - Model Master", pins untouched) | **Keep** | |
| Q4 (Session Mail's `@project` switch) | **Simplify** | This is an interface note for the Session Mail chunk, not a choice for Alex. The answer ("the server field alone") costs DER-686 nothing. Send it to Session Mail, drop it from Alex's questions, and drop the matching "Verify later" line. |
| Deferred PWA service worker | **Keep deferred** | The manifest is already linked (`apps/desktop/index.html:12`), so the Webapp installs to the home screen as Alex uses it. |
| Size ratchet on `sidebar/index.tsx` | **Keep** | 2,078 lines, confirmed. The tap and ordering logic goes in a `sidebar/projects/` sibling. |

Fact checks (code, read-only; no hooks or tools run against any Hermes home):
- 10: `enterProject` "Never opens a session" (`apps/desktop/src/store/projects.ts:107-120`); the row handler only syncs the cwd and scopes (`sidebar/index.tsx:1243-1254`). Verified.
- 12: pinned rows "belong to the Pinned section and nowhere else", and the entered project's lanes go through `excludeProjectSessions` (`sidebar/index.tsx:708-745, 1079-1086`). Verified.
- 13: session-row slots (`src/lib/session-row-slots.ts:19-22`) and `composer.middleware` (`src/app/chat/composer/contrib.ts:38, 88`) exist. No project-row slot, so the tap needs core code. Verified.
- 14: the Bot Chat rule matches `/^\/(new|reset)\s*$/` and reroutes to `/compact` with a notice (`plugins/hermes-bots/plugin.tsx`, around 774-795). Verified.
- 18: the CLI imports `GatewayAgent` "the gateway runs the turn" (`hermes_cli/cli_agent_setup_mixin.py:647`); `gateway_agent.py:1-6` says the CLI never builds an agent. Verified.
- 19: the gateway authority's `authorize` checks profile and capability (`gateway/session_authority.py:200-210`). Nothing in `gateway/session_controls.py`, `session_busy_controls.py` or `session_authority.py` reads the lease file or `SESSION_NOT_OWNED`. Verified in code; still to be run live, as the brief says.
- 20: `session.mutate` handles `compress` on the gateway (`gateway/session_mutations.py:116-143`). Verified.
- Added: `projects.*` is not in the gateway's own handler table (`gateway/session_controls.py:221-246`). It reaches the legacy dispatcher through `legacy_fallback_allowed` (`tui_gateway/ws.py:401-409`; `ws_legacy_fallback.py:53-62`), which allows any non-session verb on an interactive grant. So the new field and `projects.update` work from the Webapp with no gateway change. Verified.
- 5: the other `owner_session_id` names exist (`gateway/run_notifications.py:203`). Verified.
- Not re-checked: live data (fact 25), fact 15's drawer behaviour, fact 21's dispatch script.

Net: slice 1 is the column, the seeding, one core sidebar change (tap opens the owner; owner first and marked, even if pinned), and, only if Q2 is yes, a small plugin with the `/new` rule. Alex's questions shrink to Q1–Q3; Q4 becomes a note to Session Mail. No requirement of Alex's dies and no new open point appears, so the Plan step can apply these cuts.

Refine: pass

---

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
