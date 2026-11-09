# HLD — project-centric Hermes UI

- Slug: `project-centric-ui`
- Track / chunk ids: Epic `DER-686`; project-main `integrate/project-centric-ui`
- Brief: `docs/project-centric-ui/brief.md` (round 2) as refined by `docs/project-centric-ui/brief-refine.md` (Refine: pass)
- Date: `2026-11-08`

Alex has not yet answered the brief's Questions for Alex (Q1–Q3). This HLD designs on the
recommended answers, except where it says otherwise (Q3, see Shape §2), and marks in **Open**
each place where a different answer changes the shape.

## Required

### Problem

Alex organizes his work into Hermes projects, and the backend already groups sessions by project
correctly (a session belongs to the deepest project folder containing its `cwd` or git root,
`tui_gateway/project_tree.py`). No surface he uses shows that grouping:

- Hermes Mobile (his main surface): the Projects screen only edits settings, and History's
  "group by project" uses its own client rules, which produce a bogus "hermes" group.
- The web dashboard has no projects section at all.

There is also no notion of a project's **owner chat**: one permanent, long-lived session per
project that tapping the project opens, the way a Bot opens its Bot Chat.

### Goals

1. A project has an optional owner chat, stored as data (`owner_session_id`) and served through
   the calls both clients already load (`projects.list`, `projects.get`, the tree).
2. The six existing projects get their owners once, by a reversible data fix.
3. A dashboard Projects page (laptop and phone browser): project list → project page with the
   owner chat on top, the project's other sessions by recency, and "new chat here".
4. Two Hermes Mobile issue drafts and one upstream Hermes issue draft, for Alex to review and post.
5. One deploy with one announced dashboard restart; current Hermes Mobile builds keep working.

### Non-goals

- `/new` → compaction in the owner chat on any server, TUI or dashboard path (brief Q1; deferred).
- A "get or create owner" RPC, compression-tip following, a "make owner" button, a Home
  pseudo-project, rename protection, the PWA (all "Deferred after slice 1").
- Per-project memory, instructions or model settings (context already comes from folder files).
- Writing Hermes Mobile code; the desktop Electron app beyond keeping the backend contract
  compatible; upgrading the fork to v0.23.0; model routing (DER-675), Titan, Home Assistant.

### Users / operators

- **Alex** — sole user. Hermes Mobile on Android first, the dashboard in a laptop or phone
  browser second. Approves restarts, the seeding run, and every public post.
- **Operator agents** (manager, builders) — work on fork branches only; never touch the live
  install, its services or `<hermes-home>` except the seeding run Alex approves.
- **Hermes Mobile maintainer** and **upstream Hermes maintainers** — receive drafted issues
  (posted by Alex), decide adoption.

### UX / stories

`docs/project-centric-ui/ux.md` and `docs/project-centric-ui/stories/` (designer, written in
parallel). Operator acceptance pending; mockups of the project page on a phone are Spec.

### Comparables

`docs/project-centric-ui/comparables.md` — Claude Projects, ChatGPT Projects, Hermes Bot Chat,
the Hermes desktop project sidebar.

### Shape

```
                         per-profile <hermes-home>/projects.db
                         projects.owner_session_id  (NEW, nullable TEXT)
                                       │
            ┌──────────────────────────┼──────────────────────────────┐
  [1] core fork patch                  │                              │
  projects_db.Project.to_dict ──► projects.list / projects.get / projects.update (JSON-RPC, /api/ws)
  project_tree._project_node  ──► projects.tree RPC, GET /api/profiles/projects/tree (REST)
            │                                                         │
  [2] bundled dashboard plugin                               Hermes Mobile (no code from us;
  plugins/<projects>/dashboard/  tab after:sessions           [4] drafted issues read the
  reads GET /api/profiles/projects/tree only                  optional field from projects.list)
  links: /chat?resume=<owner id>   (existing)
         "new chat here" → fresh /chat in the project's primary folder
  [3] one-time seed + undo file via projects.update            [5] upstream Hermes issue draft
```

**Parts**

1. **Owner pointer — core fork patch** (one item, small, offered upstream).
   - Column `owner_session_id TEXT NULL` on `projects`, added through the existing additive
     migration list (`_OPTIONAL_PROJECT_COLUMNS`) and returned by `Project.to_dict`
     (`_OPTIONAL_ROW_FIELDS`), so `projects.list` / `projects.get` carry it with no new RPC.
   - `update_project` / `projects.update` accept `owner_session_id` with the module's existing
     convention: omitted or `None` leaves it, `""` clears it.
   - Project nodes of the tree carry the owner (camelCase like the other node keys). The
     all-profiles REST tree merges projects across profiles by folder; the merged node keeps
     the owner of the declared project together with that owner's profile, never a guess.
   - Profiles are islands: one owner per project per profile (assumption A2).
2. **Dashboard Projects page — bundled fork plugin**, not a core page (decision below).
   - `plugins/<projects>/dashboard/` with `manifest.json`, a prebuilt `dist/index.js` (IIFE, SDK
     React like `plugins/model-routing/`), no `plugin_api.py`: the page needs no backend route of
     its own and reads only `GET /api/profiles/projects/tree` through `SDK.fetchJSON`.
   - `tab.position: "after:sessions"`: the nav entry sits next to Sessions
     (`web/src/App.tsx` splices plugin tabs at `after:<path>`).
   - Owner chat opens `/chat?resume=<id>`; the chat page already follows a compressed session
     to its latest descendant (`ChatPage.tsx`, `getSessionLatestDescendant`), so a rotated id
     still lands in the right chat.
   - "New chat here" starts a fresh dashboard chat in the project's primary folder. The
     dashboard has no URL parameter for a fresh chat's folder; the fresh chat's folder is the
     per-profile picker value in `localStorage` (`web/src/lib/chat-workspaces.ts`). Slice 1 sets
     that value and opens `/chat` (contained in one plugin function); see Open for the
     `/chat?cwd=` deep-link alternative.
   - Missing owner, or an owner id not in the project's session ids → no owner row; list and
     "new chat here" still work.
3. **Seeding — one-time data fix**, run once with Alex's go after the deploy: `projects.update`
   per project (Q2: five "<Project> — Orchestrator" sessions plus "Model Master"), writing an
   undo file under `<hermes-home>/backups/` first, like the earlier session re-homing.
4. **Hermes Mobile — two issue drafts** in git for Alex (decision below): (1) project page with
   the owner chat on top read from the optional `owner_session_id` in `projects.list`, plus one
   sentence asking the app to reuse its Bot Chat `/new` → `/compact` path for owner chats
   (Q1 recommendation); (2) the "hermes" History group (no home-directory rule) and new project
   chats starting in the first folder instead of the primary one.
5. **Upstream Hermes — one issue draft** offering the backend patch (decision below).

**Data.** New: one nullable session-id string per project per profile. Read: project nodes,
session ids, titles and recency the tree already serves. Nothing new reaches the model; no
system prompt, toolset or memory changes (prompt caching untouched).

**Trust boundaries**

- Browser/app ↔ dashboard: unchanged. The plugin adds no route; it calls an existing route
  behind the dashboard's session-token gate. Bundled plugins are trusted and loaded by default
  (`_plugin_api_mount_skip_reason`); this one has no Python to load.
- `projects.update` gains one field. Whoever can already rename a project can set its owner;
  no new privilege. The value is an opaque pointer, never executed or used as a path; Spec
  decides whether set-time validates that the session exists in the same profile.
- Data class: session ids and titles of Alex's own chats, already served to the same clients.
- Public posting (GitHub issues on Hermes Mobile and upstream Hermes) is a boundary only Alex
  crosses; agents draft.

#### Decision: plugin versus core patch, per part

What plugins can do here, from the code: a bundled dashboard plugin can add a nav tab at
`after:sessions`, render React through `window.__HERMES_PLUGIN_SDK__`, call any authenticated
route with `fetchJSON`, and mount its own FastAPI router (`/api/plugins/<name>/`, needs a
restart). A general plugin can register tools, hooks and CLI commands. **No plugin surface can
add a column to `projects.db` or a field to `projects.list` / `projects.get` / `projects.update`
or the tree**, and `plugins/AGENTS.md` forbids plugins touching core and rejects new hooks with a
single consumer.

| Part | Plugin | Core patch | Decision |
|---|---|---|---|
| Owner pointer | Plugin-owned store + plugin route: Hermes Mobile would have to call a fork-only plugin endpoint, which its maintainer has no reason to adopt; a new hook to inject into `projects.*` replies is a one-consumer hook (rejected by `AGENTS.md`) | ~4 small additive edits in files that already own project fields; served by calls both clients load; upstreamable | **Core patch** |
| Dashboard page | Zero core `web/` edits (no rebase cost; `App.tsx` and the SDK changed at v0.23.0, additively); prebuilt dist so no web rebuild at deploy; same nav slot via `after:sessions`; matches the project rule "prefer a Hermes plugin" | Sits in core navigation by default; easiest for upstream to take; needs a web build and carries `web/` rebase work until upstream merges | **Plugin**, port to a core page only if upstream asks for it |

This departs from the brief's Q3 recommendation ("core page"). That recommendation's cost for
the plugin was "a tab among plugins, not core navigation", which the code disproves
(`tab.position: "after:sessions"`). See Open.

#### Decision: Hermes Mobile delivery

| Option | Alex's main surface | Maintainer's record | Official Nous app in beta | Carrying cost | Verdict |
|---|---|---|---|---|---|
| **Drafted upstream issues** (Alex posts) | Slower: waits on the maintainer; the dashboard page covers the phone browser meanwhile | Project features shipped from issues (#1526, #1527, #1581, #1669) | No bet on the app's future | None | **Chosen** |
| Pull requests to the app | Faster if accepted | Unknown for outside PRs; `CONTRIBUTING.md` bans AI authorship trailers, and the field exists only in our fork until upstream Hermes takes it, so a PR asks the maintainer to merge code for a non-upstream field | Same | A Kotlin/Android toolchain and review cycles for us | Fallback if an issue is accepted in principle but stalls on implementation |
| Our own build of the app | Fastest and fully ours | Bypasses it | Worst bet: a fork of a community app that the official app may supersede | Android build, signing; different signing key from F-Droid means uninstalling and losing app data; rebasing an active app forever | Rejected for slice 1 |

Issue 1 must stand on its own if upstream Hermes never adopts the field: the app reads an
optional `owner_session_id` and behaves as today when it is absent.

#### Decision: upstream offer for the backend patch

| Option | For | Against | Verdict |
|---|---|---|---|
| **Issue draft with the fork commit linked as a ready patch** (Alex posts) | Asks intent first, as upstream's rubric expects ("verify the intent"); costs nothing if declined; patch already exists and is tested | Slower than a PR | **Chosen** |
| Open a PR directly | Faster to merge if wanted | Agents never post; an unasked PR from a fork for a fork-driven feature is easy to close | Only if maintainers ask for it |
| Keep it fork-only | No upstream effort | Permanent fork drift; Hermes Mobile maintainer less likely to adopt a fork-only field | Rejected |

The draft states the field, the contract (nullable, additive, ignored by old clients), the test
against a temporary `HERMES_HOME`, and that the files carry onto v0.23.0 (see Risks).

#### Decision: deploy and restarts

| Process | Reads the change? | Restart needed? | Cuts Hermes Mobile? |
|---|---|---|---|
| Dashboard (`/api/ws` JSON-RPC, REST tree, SPA, plugin discovery) | Yes: `projects.*` RPCs run in-process (`web_routers/chat_ws.py` → `tui_gateway`), the tree route, and the per-process dashboard plugin cache | **Yes, once** | **Yes** — announce it |
| Messaging gateway | No: it does not serve `projects.*` or the tree | Not for the feature. After `git pull` it runs stale code, and its code-skew guard refuses `/model` switches until restarted (`gateway/slash_commands_model.py`) | No |
| Web SPA build | No core `web/` change | No rebuild | — |

Sequence: Alex announces → `git pull --ff-only` on the deployed branch → one dashboard restart →
verify (`projects.list` shows the field, the Projects tab loads, current app build works) →
seeding run with its undo file (no restart; the column is created on first open). The gateway
restart is optional and does not affect the phone; Alex chooses whether to do it in the same
window. Restarts are run by Alex or with his explicit go, never by a builder.

### Persistence

| What | Where | Durable how |
|---|---|---|
| `owner_session_id` | per-profile `<hermes-home>/projects.db`, table `projects` | Additive column, created on first open; old DBs upgrade in place; downgrade-safe (old code ignores the column) |
| Seed undo file | `<hermes-home>/backups/` (outside git; holds real session ids) | Written before the seed run; restores prior values |
| Dashboard plugin | Fork tree `plugins/<projects>/` | Git; no server state |
| "New chat here" folder | Browser `localStorage`, per profile (existing picker key) | Same value the workspace picker already writes |
| Issue drafts (2 app, 1 upstream) | Git, under `docs/project-centric-ui/` (path set at Groom) | Alex reviews; posting is his |
| Design records | Git on project-main | Plan/Spec artifacts |

### Worker rules

- **Who implements:** builders, one item per fork feature branch cut from
  `integrate/project-centric-ui`; land by the chunk's land path; deploy by fast-forwarding the
  deployed branch (`rules.md` 19). No live edits, no side repos, no symlinks into
  `<hermes-home>/plugins`.
- **Split:** the core patch (part 1) and the plugin (part 2) are separate items; the plugin
  never edits core files (`plugins/AGENTS.md`). Part 1 lands first; part 2 renders a project
  without an owner correctly until then.
- **Tests:** `scripts/run_tests.sh`, behaviour contracts against a temporary `HERMES_HOME`
  (migration on an existing `projects.db`; set, clear and read through `projects.update` /
  `projects.list`; tree node carries the owner), each proven red on the base. Plugin logic
  (owner row, missing owner) gets a small JS test if the plugin has a test harness; no
  source-reading tests. `python scripts/check` passes.
- **HITL (Alex):** the restart window, the seeding run, every public post, and answers to Q1–Q3.
- **Must not bypass:** agents never post issues or PRs, never restart services, never write to
  the live `<hermes-home>` except the approved seeding run, never add AI authorship trailers to
  anything sent to Hermes Mobile, and never stage secrets, hostnames, local paths or session
  dumps (the seed's real ids stay in the undo file outside git).

### Open

Places where a different answer from Alex changes the shape:

- **Q1 (`/new` compacts in the owner chat).** Recommended: no server/TUI guard; one sentence in
  app issue 1. If Alex wants it on the dashboard too, that is a new part: a guard in the TUI
  slash path keyed on the owner pointer (touches TUI, CLI, gateway slash handling) — a chunk
  reshape, escalate.
- **Q2 (seed owners).** Recommended: five Orchestrators plus "Model Master". A different pick
  changes only the seed data.
- **Q3 (core page or plugin tab).** This HLD chooses the plugin, against the brief's
  recommendation, for the reasons in the table. If Alex wants a core page now: part 2 moves to
  `web/src/pages/` plus a route and nav entry, the deploy adds a web build, and the fork carries
  `web/` rebase work until upstream merges. Parts 1, 3–5 do not change.
- **"New chat here" mechanism.** Slice 1 sets the picker's stored folder (an internal key the
  plugin couples to). The cleaner fix is a generic `/chat?cwd=<folder>` deep link in core
  `ChatPage`; it is a core `web/` edit, so it is offered in the upstream issue rather than
  carried now. If Alex prefers it now, it is one small extra core item plus a web build.
- **Profiles.** Slice 1 opens owners in the dashboard's current profile. An owner in a
  non-default profile needs the profile scope switched first; Spec settles the link.
- Not answerable by talking: whether upstream Hermes wants the field; whether the Hermes
  Mobile maintainer adopts a field only our fork serves; the phone layout (mockups at Spec).

## Optional

### PoC questions (Trial)

**No Trial.** Each technical question is answered by reading code, and the one that could use a
run is not cheap here:

- *Does an added field in `projects.list` break Hermes Mobile's parser?* No: the app's JSON
  config has `ignoreUnknownKeys = true` with snake_case naming (`data/remote/OkHttpProvider.kt`,
  app), and every `ProjectInfo` field except `id` (always sent) has a default
  (`data/model/ProjectModels.kt`, app). Proving it by running needs a JVM and the
  Android/Gradle toolchain, which this host lacks (a network download of several GB); the app's
  pinned contract file only affects the app's own tests. Build verifies "current app build works
  unchanged" on the real phone after deploy (brief, Verify later).
- *Can a plugin tab sit next to Sessions and open chats?* Yes: `after:sessions` handling in
  `web/src/App.tsx`; `/chat?resume=` handling in `ChatPage.tsx`.
- *Does the patch carry onto v0.23.0?* `projects_db.py` and `project_tree.py` are unchanged at
  `v0.23.0`; `methods_projects.py` and `web_routers/profiles.py` change in unrelated hunks.

What remains uncertain is human (maintainer adoption), which no trial can answer.

### Risks

- **Brief fact 9 is imprecise.** At `v0.23.0`, `tui_gateway/methods_projects.py` (null-db guard)
  and `hermes_cli/web_routers/profiles.py` (the tree route gains a `profile` parameter) change;
  `web/src/App.tsx` and the plugin registry change additively (per-profile plugins). Expect small
  rebase conflicts in those two Python files, none in the plugin.
- **The internal picker key** (`hermes-chat-workspace:<profile>`) can change upstream silently;
  the fork's own tree makes that visible on rebase, and the deep link removes it.
- **Large trees on a phone.** The REST tree is unhydrated (preview sessions plus all session
  ids); the page needs more than three recent sessions. Spec picks `preview_limit` or a
  per-project fetch; no new route is expected.
- **Stale messaging gateway** after the pull if it is not restarted: `/model` switches are
  refused until it is (no effect on the phone app or this feature).
