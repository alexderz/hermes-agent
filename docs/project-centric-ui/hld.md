# HLD — project-centric Hermes UI

- Slug: `project-centric-ui`
- Track / chunk ids: Epic `DER-686`; project-main `integrate/project-centric-ui`
- Brief: `docs/project-centric-ui/brief.md` (round 3) as refined by `docs/project-centric-ui/brief-refine.md` (round 3, Refine: pass)
- Date: `2026-11-08` (round 2 of Plan: adds part 6, owner turns steerable from the phone)

Alex has not yet answered the brief's Questions for Alex (Q1–Q4; Q5 became a note in
refinement). This HLD designs on the recommended answers as refined, except where it says
otherwise (Q3, see Shape §2), and marks in **Open** each place where a different answer changes
the shape.

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

And an owner chat that is working cannot be reached from the phone. Owner turns are started by
a kickoff unit running `hermes chat -q --oneshot`, which holds the session's lease for the whole
turn, often hours. A phone send then fails with `prompt.submit` 4090 `SESSION_NOT_OWNED`, and
the app can only offer "start a new conversation" (brief facts 18–21, 26; Alex, 21:00).

### Goals

1. A project has an optional owner chat, stored as data (`owner_session_id`) and served through
   the calls both clients already load (`projects.list`, `projects.get`, the tree).
2. The six existing projects get their owners once, by a reversible data fix.
3. A dashboard Projects page (laptop and phone browser): project list → project page with the
   owner chat on top, the project's other sessions by recency, and "new chat here".
4. Two Hermes Mobile issue drafts and one upstream Hermes issue draft, for Alex to review and post.
5. One deploy with one announced dashboard restart; current Hermes Mobile builds keep working.
6. While an owner chat is working, Alex can open it in Hermes Mobile and queue, steer
   ("guide"), correct or stop the running turn with the app's existing busy-send controls, with
   no Hermes core change and no refusal (brief Intent 5, A7).

### Non-goals

- `/new` → compaction in the owner chat on any server, TUI or dashboard path (brief Q1; deferred).
- A "get or create owner" RPC, compression-tip following, a "make owner" button, a Home
  pseudo-project, rename protection, the PWA (all "Deferred after slice 1").
- Per-project memory, instructions or model settings (context already comes from folder files).
- Writing Hermes Mobile code; the desktop Electron app beyond keeping the backend contract
  compatible; upgrading the fork to v0.23.0; model routing (DER-675), the GPU host, Home Assistant.
- For part 6 (refiner, round 3): a cross-process queue into a held session (option B); a
  v0.23.0 spike in this chunk (it moves to fork upkeep, work item 3); reconnect logic in the
  kickoff client; steering turns that ad-hoc `hermes chat` sessions still run elsewhere.
- The `session.compress` lease bug (brief fact 22): filed as its own fork bug, not part of
  DER-686.

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

  [6] owner turns run INSIDE the dashboard process (option A; no core change)
  kickoff unit ─► `hermes <project-turn>` (CLI command of the same fork plugin)
       │  mint 60 s access token in memory (password provider code, profile's signing secret)
       │  POST /api/auth/ws-ticket (Bearer) ─► single-use ticket
       │  /api/ws, ticket in Sec-WebSocket-Protocol ─► session.resume + prompt.submit ─► wait ─► exit
       ▼
  dashboard process (tui_gateway): ONE live session, ONE lease, the turn runs here
       ▲
  Hermes Mobile: session.resume (reuses that live session, running: true)
                 ─► steer / queue / correct / interrupt (existing app controls)
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
6. **Owner turns steerable from the phone — a kickoff client** (brief Q4, option A + D as
   refined; Trial: `poc/poc.md`, 18/18 checks).
   - **What changes.** The kickoff unit stops running `hermes chat -q --oneshot` for owner
     sessions and runs a fork plugin CLI command instead (decision below). The command opens the
     dashboard's `/api/ws`, sends a cold `session.resume` of the stored session (or
     `session.create` in the project's folder when the session does not exist yet, as
     `--create-if-missing` does today), then `prompt.submit`, and stays connected until that
     turn's `message.complete`; then it exits. The turn therefore runs inside the dashboard
     process, which holds the one lease.
   - **Why the phone can then steer.** A phone `session.resume` on a session already live in the
     dashboard process reuses that live session (`_claim_or_reuse_live` → `_resume_reuse_live`),
     so it returns `running: true` and the app's busy-send setting applies: `session.steer`,
     `session.redirect`, `prompt.submit {queued: true}`, `session.interrupt` all act on the
     running turn, with no 4090. Proven in the Trial (checks 4–10).
   - **Target resolution:** the command takes the same inputs as today's kickoff (project folder,
     session title, create-if-missing) and may take a project slug to use its
     `owner_session_id`. Exact flags are Spec.
   - **Outcomes:** exit 0 when the turn completes (also when Alex interrupts it from the phone);
     non-zero on refusal (4090 because an ad-hoc CLI elsewhere holds the session), on auth
     failure, and on a dropped socket. **No reconnect logic** and **no silent fallback to
     `--oneshot`**: a failure is visible in the unit's status and the kickoff is re-run.
   - **Issue draft 1** gains one sentence (option D): show "working elsewhere" from
     `last_activity_at` and offer "retry when it finishes" instead of only "new conversation"
     on 4090. Under part 6 this only matters for ad-hoc CLI use.
   - **Unit change:** the kickoff unit's command line is Alex's tooling, outside the fork. Its
     one-line change (`hermes chat … --oneshot` → the new command) is a chunk item done where
     that unit is defined, after the command is deployed.

**Data.** New: one nullable session-id string per project per profile. Read: project nodes,
session ids, titles and recency the tree already serves. Nothing new reaches the model; no
system prompt, toolset or memory changes (prompt caching untouched).

**Trust boundaries**

- Browser/app ↔ dashboard: unchanged. The plugin adds no route; it calls an existing route
  behind the dashboard's auth gate. Bundled plugins are trusted and loaded by default
  (`_plugin_api_mount_skip_reason`); the dashboard part has no Python to load.
- **Kickoff client ↔ dashboard (part 6).** The live dashboard binds a non-loopback address, so
  the auth gate is on (`should_require_dashboard_auth`) with the bundled password provider
  (`dashboard.basic_auth`; only a password hash and a signing secret are configured). The
  client uses only existing mechanisms:
  1. it mints a short-lived (60 s) access token **in memory** with the password provider's own
     code (`plugins/dashboard_auth/basic`), signed with the profile's configured
     `dashboard.basic_auth.secret`;
  2. it exchanges it at `POST /api/auth/ws-ticket` (`Authorization: Bearer`, the native bearer
     leg of `gated_auth_middleware`) for a single-use 30 s ticket;
  3. it opens `/api/ws` with the ticket in the `Sec-WebSocket-Protocol` header
     (`hermes-gateway-v1, hermes-gateway-ticket.<ticket>`), which the server never reflects.

  No credential is stored and none appears in argv or a URL; nothing new is added server-side. The trust root is OS access to the profile's `config.yaml` as the `hermes`
  account, which can already mint dashboard sessions; the client runs as that account (the
  kickoff is a user unit of it). Each connection is audited as a minted ws-ticket for the
  configured user. Rejected: storing the dashboard password in `.env` (a new standing
  credential), and `?token=` in the URL (it can reach access logs). If the dashboard is ever
  switched to an OAuth-only provider there is no local mint and the command fails closed with a
  clear message (Open).
- **One writer per session stays true.** The owner turn and the phone act on one live session
  under one lease in the dashboard process; nothing bypasses `try_acquire_active_session`.
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
(`tab.position: "after:sessions"`). A second fact favours the plugin: the live dashboard unit
runs with `--skip-build`, so a core page would add a manual web build to every deploy. See Open.

#### Decision: where the kickoff client lives (part 6)

What a plugin CLI command can do, from the code: `ctx.register_cli_command(name, help,
setup_fn, handler_fn)` adds `hermes <name>` to the argparse tree at startup with no `main.py`
change (`hermes_cli/plugins.py`); it runs in the CLI process with the fork's own modules
importable. Bundled general plugins are opt-in (`plugins.enabled`,
`website/docs/user-guide/features/built-in-plugins.md`); the dashboard tab needs no enable, the
CLI command does.

| Option | Rule 19 (fork branch, no side repos) | "Prefer a plugin" | Coupling to Hermes internals | Retiring at v0.23.0 | Verdict |
|---|---|---|---|---|---|
| Core CLI flag (`hermes chat --via-dashboard`) | Yes | No: grows the CLI facade and the chat path | Native | v0.23.0 already routes CLI turns through the gateway, so upstream would not take it; a fork patch to carry and then revert | Rejected |
| **CLI command of the same fork plugin** (`plugins/<projects>/__init__.py`) | Yes | Yes | It uses the password provider's minting code and the `/api/ws` RPCs; both version with the fork, so a rebase or test shows a break | Delete the command | **Chosen** |
| Script in the fork's `scripts/` | Yes | No: core tree, not upstreamable, no plugin boundary | Same as above | Delete the script | Rejected |
| Skill script outside the fork (the refiner's "Alex's tooling") | Code outside the fork that drives Hermes internals is the side repo the rule forbids | n/a | It imports the provider's private minting code and depends on RPC shapes from a repo that does not rebase with the fork: breaks silently | Delete the script | Rejected; only the unit's one-line command change stays in Alex's tooling |

Cost of the choice: one `plugins.enabled` entry for the plugin, set where the live config is
managed (house-infra, `rules.md` 19). It needs no restart: the command loads with each `hermes`
invocation.

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
| Kickoff CLI command (part 6) | Loaded per `hermes` invocation once `plugins.enabled` lists the plugin | No | No |

Sequence: Alex announces → `git pull --ff-only` on the deployed branch → one dashboard restart →
verify (`projects.list` shows the field, the Projects tab loads, current app build works) →
seeding run with its undo file (no restart; the column is created on first open) → enable the
plugin's CLI command → switch the kickoff unit's command line. The gateway restart is optional
and does not affect the phone; Alex chooses whether to do it in the same window. Restarts are
run by Alex or with his explicit go, never by a builder.

**Restarts and owner turns.** Once part 6 is live, owner turns run in the dashboard process, so
**a dashboard restart kills a running owner turn** as well as cutting the phone off. What the
code does then (Trial checks 13–15; `tui_gateway/session_auto_continue.py`):

- The kickoff's socket drops and the command exits non-zero; the transcript keeps what was
  persisted.
- A durable turn marker survives. The next **cold** `session.resume` of that session (the
  kickoff re-run, or the phone) auto-continues the turn with a recovery note, but only if the
  turn **started** less than `desktop.auto_continue.freshness_minutes` ago (default 15), at
  most twice. A multi-hour turn is past that window: it is not auto-continued, and the kickoff
  is re-run with a "continue" prompt.

Rules:

1. **No restart while an owner turn runs**, unless Alex chooses to kill it. Before a restart the
   operator checks for running kickoff units and for sessions the dashboard reports running;
   if there are any, wait for them to finish or ask Alex.
2. **This chunk's deploy is ordered so part 6 has nothing to kill:** the one restart happens
   before the kickoff unit is switched to the new command, so no owner turn is in the dashboard
   yet. From then on, rule 1 applies to every later deploy.
3. **After an unplanned restart** (crash, host reboot): re-run the kickoff for any owner session
   whose unit failed; a short turn may already have auto-continued on the phone's resume.
4. The messaging gateway restart never affects owner turns (they are not in that process).

### Persistence

| What | Where | Durable how |
|---|---|---|
| `owner_session_id` | per-profile `<hermes-home>/projects.db`, table `projects` | Additive column, created on first open; old DBs upgrade in place; downgrade-safe (old code ignores the column) |
| Seed undo file | `<hermes-home>/backups/` (outside git; holds real session ids) | Written before the seed run; restores prior values |
| Dashboard plugin and its kickoff CLI command | Fork tree `plugins/<projects>/` | Git; no server state |
| Plugin enable (`plugins.enabled`) and the kickoff unit's command line | Where the live config and units are managed (house-infra; the unit in Alex's tooling) | Versioned there, not in the fork |
| Owner turns (part 6) | The session's transcript in the profile's `state.db`, written by the dashboard process; the crash marker for auto-continue in the profile's runtime folder | Existing session persistence; nothing new. The kickoff client keeps no state and writes no file |
| Dashboard credentials | Unchanged: `dashboard.basic_auth` in the profile config (hash + signing secret) | The client reads them in memory only; it never writes a token or ticket |
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
- **Part 6 (kickoff command):** its own item, in the same fork plugin, no core edits. Tests run
  a real dashboard backend on 127.0.0.1 against a temporary `HERMES_HOME` with a fake local
  model and throwaway auth values (rebuilt from `poc/poc.md`, never imported from `poc/`):
  auth chain, resume and create, turn completion, a second client steering and queueing, the
  exit codes, and refusal on 4090. Tests never use real credentials or the live install.
- **Part 6 must not:** store or print a credential (token, ticket, password or signing secret)
  in a file, argv, URL or log; add a server route, a new auth scheme or a new `HERMES_*` env var
  (the dashboard URL comes from existing config, a flag may override it); add reconnect logic;
  fall back silently to `hermes chat --oneshot`; or touch the lease registry.
- **HITL (Alex):** the restart window (and whether to kill a running owner turn for it), the
  seeding run, enabling the plugin's CLI command and switching the kickoff unit, every public
  post, and answers to Q1–Q4.
- **Must not bypass:** agents never post issues or PRs, never restart services, never write to
  the live `<hermes-home>` except the approved seeding run, never add AI authorship trailers to
  anything sent to Hermes Mobile, and never stage secrets, hostnames, local paths or session
  dumps (the seed's real ids stay in the undo file outside git).

### Open

Places where a different answer from Alex changes the shape:

- **Q1 (`/new` compacts in the owner chat).** Recommended: no server/TUI guard; one sentence in
  app issue 1 (as refined in round 3, without the "only when not busy elsewhere" clause: under
  part 6 the owner turn runs in the dashboard process, where `session.compress` already refuses
  while the session is busy). If Alex wants it on the dashboard too, that is a new part: a guard
  in the TUI slash path keyed on the owner pointer (touches TUI, CLI, gateway slash handling) —
  a chunk reshape, escalate.
- **Q4 (steerable on v0.22.0).** Designed on option A + D (part 6). If Alex prefers option C
  (rebase onto v0.23.0 first, whose gateway owns CLI turns), part 6 is dropped and the chunk
  waits on fork upkeep; parts 1–5 do not change. Option B (a cross-process queue patch) was cut
  in refinement; choosing it would add a core turn-path item that v0.23.0 replaces.
- **Q5 (rebase timing): a note, not a question.** The v0.23.0 check moves to fork upkeep (work
  item 3), where it decides whether part 6's command retires. Nothing in this chunk depends on it.
- **Dashboard auth provider.** Part 6 assumes the password provider (`dashboard.basic_auth`),
  which the live config uses. If Alex switches the dashboard to an OAuth-only provider there is
  no local mint; the command fails closed, and a machine credential (a token route) would be a
  new trust-boundary item: a reshape for the security gate.
- **Security gate (Spec).** Security reviews the local-mint trust root for part 6 (OS access to
  the profile's config as the `hermes` account is treated as equivalent to dashboard access).
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
  Mobile maintainer adopts a field only our fork serves; the phone layout (mockups at Spec);
  for part 6, a real multi-hour owner turn and the dashboard's memory under it (Trial limits,
  `poc/poc.md`), checked on the first real run after deploy.

## Optional

### PoC questions (Trial)

**Round 2: Trial run for part 6** — `docs/project-centric-ui/poc/poc.md`. Question (the
refiner's open point): does a long turn run in the dashboard process survive orphan reaping,
idle timeouts and memory, and can a second client (the phone) attach and queue or steer it?
It was uncertain and cheap to prove: the repo already has a credential-free pattern (a real
backend on 127.0.0.1, a temporary `HERMES_HOME`, a fake local model,
`evals/desktop_bug_campaign/leases_live.py`). Result: **18/18 checks pass**, with the auth gate on:
local-mint auth, phone attach to the live turn, steer, queue, interrupt, survival of a detached
active turn past the orphan grace, and auto-continue of a short turn after a backend kill.
Not proven: hours of runtime, memory under a real model, the real app; Build and the first
real run after deploy check those (poc.md, "What we will not treat as product").

**Round 1: no Trial.** Each technical question is answered by reading code, and the one that
could use a run is not cheap here:

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
- **Owner turns now share the dashboard process** (part 6): its memory cap covers them, a
  dashboard crash takes them down, and each deploy must wait for them (Deploy rules).
- **A silent step over 10 minutes with no client attached** is interrupted by the orphan reaper
  (`ws_orphan_activity_stale_s`, default 600 s). The kickoff staying connected prevents that.
  If the command dies mid-turn and a tool runs silently for more than 10 minutes, the turn stops.
- **Private code in the password provider.** The kickoff mints with the provider's own
  functions, which are not a public API. The fork's tests catch a break on rebase; a small public
  "mint a local session" helper could be offered upstream later.
- **Ad-hoc `hermes chat` sessions** (not started by the kickoff) still lock the phone out on
  v0.22.0; only the issue 1 sentence (option D) softens it until v0.23.0.
