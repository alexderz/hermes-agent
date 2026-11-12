# HLD — project-centric Hermes UI (v0.23, Webapp surface)

- Slug: `project-centric-ui`
- Track / chunk ids: Epic `DER-686`; project-main `integrate/project-centric-ui-023`
- Brief: `docs/project-centric-ui/brief.md` (round 4) as refined by
  `docs/project-centric-ui/brief-refine.md` (round 4, Refine: pass, with cuts)
- Date: `2026-11-11` (Plan round 3; rewrites the v0.22 HLD for the v0.23.1 base and the Webapp)

Base: branch `integrate/project-centric-ui-023`, cut from the fork's deployed
`alex/v0.23.1-canary-1110` (v0.23.1 plus carried fork commits). Alex's surface is the gateway
Webapp (the desktop app's interface served as a web app) on laptop and phone; he no longer uses
Hermes Mobile. Alex has not answered the brief's Q1–Q3; this HLD designs on the recommended
answers as refined and marks in **Open** each place where a different answer changes the shape.

## Required

### Problem

Alex organizes his work into Hermes projects, and the backend groups sessions by project
correctly (deepest project folder containing the session's `cwd` or repo root,
`tui_gateway/project_tree.py`). In the Webapp, tapping a project only scopes the sidebar to it
(`enterProject`, `apps/desktop/src/store/projects.ts`: "Never opens a session"). Nothing marks a
project's main chat, so in a folder holding "HIM - Orchestrator", "HIM - Project UI" and
"HIM - Session Mail" all look alike. A pinned chat leaves its project's list entirely, so
"HME - Orchestrator" (pinned) is missing from Home Engineering. And `/new` in a long-lived main
chat starts over instead of compacting.

### Goals

1. A project has an optional owner chat, stored as data (`projects.owner_session_id`), served by
   the calls the Webapp and other clients already load (`projects.list`, `projects.get`, the
   project tree), set through `projects.update`. No new RPC.
2. The six existing projects get their owners once, **by session id**, with an undo record.
3. In the Webapp (laptop and phone): tapping a project that has an owner scopes the sidebar to
   the project **and opens its owner chat**; the project's list shows the owner first, marked
   "Main chat", **even when it is pinned**. A project with no owner behaves exactly as today.
4. If Alex says yes to Q2: `/new` and `/reset` in an owner chat in the Webapp compact it instead,
   with a notice, as Bot Chat does.
5. Steering a working owner chat from the phone: met by the v0.23 base; **nothing is built**
   (Trial `poc/v023/poc.md`, 14/14).
6. One announced, drain-first gateway restart; the Webapp bundle rebuilt from the checkout.

### Non-goals

- **Dropped by the v0.23 move** (were in the v0.22 HLD):
  - Every Hermes Mobile part: both issue drafts (project page; "hermes" group and first-folder
    bugs), the "working elsewhere" sentence, and the Mobile constraints (unknown-field tolerance,
    pinned contract file, restarts cutting the app off).
  - The Projects tab in the standalone web dashboard (`web/`, a bundled dashboard plugin).
    Alex does not use the standalone dashboard; the public address serves the Webapp.
  - **Part 6, the kickoff command** (owner turns sent through the dashboard socket, with
    in-memory token minting). On v0.23 a plain `hermes chat -q --oneshot` turn already runs in
    the gateway, where the Webapp steers it (Trial); sending kickoffs to the dashboard would
    now do the opposite.
  - The rebase-timing question (done) and the `session.compress` ownership fix (on the gateway
    compaction is owner-run; the gap remains only in the legacy backend, a separate fork bug).
- Cut in refinement (round 4): a session-row "Main chat" badge plugin, a separate Projects page or
  route, a runtime plugin under `<hermes-home>/desktop-plugins/` (`rules.md` 19), pinning owners
  at seeding.
- Deferred after slice 1: a server or terminal `/new` guard (CLI and TUI keep plain `/new`), a
  "get or create owner" RPC, a "make owner" button, a Home pseudo-project, compression-tip
  following, the PWA service worker (the Webapp already installs from its manifest).
- Out of scope: Session Mail itself (we only provide the field), per-project memory or model
  settings, model routing (DER-675), the GPU host, Home Assistant, two writers on one session.

### Users / operators

- **Alex** — sole user, the Webapp in a laptop browser and installed to his phone's home screen.
  Approves the restart window, the seeding run, and every public post.
- **Operator agents** (manager, builders) — fork branches only; never touch the live install,
  its services or `<hermes-home>` except the seeding run Alex approves.
- **Session Mail** (another chunk) — a consumer of `owner_session_id`: its `@project` addressing
  resolves to the project's owner session (brief fact 27). The switch it needs is the server
  field alone (refiner round 4: a note to that chunk, not a question for Alex).
- **Upstream Hermes maintainers** — receive a drafted issue (posted by Alex).

### UX / stories

`docs/project-centric-ui/ux.md` and `docs/project-centric-ui/stories/` (designer, being revised
for the Webapp in parallel). Operator acceptance pending; the narrow-screen drawer layout is a
mock-up at the gate.

### Comparables

`docs/project-centric-ui/comparables.md` — the Webapp's own project sidebar, Bot Chat in the
Webapp, Claude Projects, ChatGPT Projects.

### Shape

```
 per-profile <hermes-home>/projects.db: projects.owner_session_id (NEW, nullable TEXT)
        │  [1] core fork patch (Python)
        ├─► Project.to_dict ─► projects.list / projects.get / projects.update
        ├─► project_tree._project_node ─► projects.tree / projects.project_sessions,
        │                                  GET /api/profiles/projects/tree
        ├─► `hermes project set-owner <project> <session-id> | --clear`   [4] seeding uses it
        │
        │   all served INSIDE the combined gateway: projects.* are not authority verbs, so the
        │   gateway's /api/ws hands them to the legacy handlers (legacy_fallback_allowed)
        ▼
 Webapp (apps/desktop, built to dist-webapp, served by the gateway)
   [2] core sidebar change: tap → enterProject + open owner; owner row first, "Main chat",
       exempt from the pin filter in its own project; logic in a sidebar/projects/ sibling
   [3] bundled fork plugin (only if Q2 = yes): composer.middleware /new|/reset → /compact
       in the owner chat, owner ids read with host.request('projects.list')
        ▲
 Steering a working owner (Goal 5): base behaviour, nothing built —
   `hermes chat -q --oneshot` kickoff ─► turn runs in the gateway ◄─ Webapp resumes, steers,
   queues, stops (Trial 14/14, also after the CLI is killed)
 Session Mail (other chunk) ─► reads owner_session_id via projects.list / projects.get
```

**Parts**

1. **Owner pointer — core fork patch** (decision 1).
   - Column `owner_session_id TEXT NULL` through the existing additive migration list
     (`_OPTIONAL_PROJECT_COLUMNS`), returned by `Project.to_dict` (`_OPTIONAL_ROW_FIELDS`).
   - `update_project` / `projects.update` accept it with the module's convention: omitted or
     `None` leaves it, `""` clears it.
   - Tree project nodes carry it (camelCase, like the other node keys); the all-profiles REST
     tree keeps the declared project's owner when it merges profiles.
   - The value is the session's **durable stored id** (what pins store). Legacy rows keep their
     historical id as the logical id when the gateway adopts them; compaction may move the
     physical row, never the logical id (`gateway/session_local_migration.py`). Readers match
     it against either identity a row carries (`id` or `_lineage_root_id`), like the pin matcher.
   - Name kept as `owner_session_id` (Session Mail already plans to read it), with a docstring
     saying it is the project's main chat, unrelated to the other `owner_session_id` names in
     `gateway/run_notifications.py` and `tui_gateway/methods_session.py`.
   - One owner per project per profile (profiles are islands).
2. **Webapp sidebar — core change** (decision 2).
   - Tap: `onEnterProject` keeps scoping the sidebar and, when the project node has an owner,
     also calls the sidebar's existing `onResumeSession(owner)`. No owner → exactly today's tap.
   - Entered view: the owner row is pulled out above the lanes, marked "Main chat"; the rest of
     the list is unchanged. The pin filter (`isHiddenFromProjects`) exempts the owner row **in
     its own project only**; it still shows in Pinned too, so a pinned owner appears twice, once
     marked.
   - An owner id that matches no row in the project (session gone, archived, beyond the tree's
     window) shows no owner row and changes nothing else.
   - Size ratchet: `sidebar/index.tsx` is 2,078 lines (cap 2,000) and `ChatSidebar` runs from
     line 399 to the end, far over the 300-line function cap; both may only shrink. The pin
     identity set, `isPinnedSession`, `isHiddenFromProjects` and `onEnterProject` (about 50 lines
     today, `index.tsx` ~708–748 and ~1243–1254) move into a new
     `sidebar/projects/use-project-owner.ts` hook that also owns the owner logic; the "Main
     chat" row renders in `projects/entered-content.tsx` (327 lines). Net: both units shrink.
3. **`/new` → compact — bundled fork plugin, only if Q2 = yes** (decision 3).
4. **Seeding by session id** (decision 4).
5. **Upstream offer** (decision 5).

**Data.** New: one nullable session-id string per project per profile. Read: what the tree and
`projects.list` already serve. Nothing reaches the model; no system prompt, toolset or memory
change. `/compact` is the one allowed context rewrite.

**Trust boundaries**

- Browser ↔ gateway: unchanged. The Webapp's socket ticket and grant are as today; `projects.*`
  run through the existing legacy fallback, which requires the interactive grant
  (`tui_gateway/ws_legacy_fallback.py`).
- `projects.update` and `hermes project set-owner` gain one field. Whoever can already rename a
  project can set its owner; no new privilege. The value is an opaque pointer, never executed or
  used as a path; `set-owner` checks the session exists in the same profile.
- The plugin (part 3) runs in the Webapp with the same host API as `hermes-bots`; it reads
  `projects.list` and rewrites one composer draft. No new server surface.
- Session Mail's use of the field (addressing another session) is that chunk's boundary.
- Public posting (the upstream issue) is a boundary only Alex crosses; agents draft.

#### Decision 1: the owner pointer patch on v0.23

What changed since the v0.22 base (`git diff integrate/project-centric-ui HEAD`):
`hermes_cli/projects_db.py` and `tui_gateway/project_tree.py` are **unchanged**;
`tui_gateway/methods_projects.py` only gains a null-db guard; `tui_gateway/methods_config.py`
(tree and discovery) and `hermes_cli/web_routers/profiles.py` (REST tree gains `profile`) change
in unrelated places. On the gateway, `projects.*` are not in the authority's handler table
(`gateway/session_controls.py`), so `/api/ws` passes them to the legacy handlers in the same
process (`tui_gateway/ws.py`, `legacy_fallback_allowed`: only `session.`, `prompt.`, `message.`
verbs are refused).

| Option | For | Against | Verdict |
|---|---|---|---|
| **Same core patch as v0.22**: column, `to_dict`, `projects.update`, tree node | ~4 small additive edits in files that already own project fields, unchanged on v0.23; the gateway serves it with no gateway change; Session Mail reads it server-side | A core edit to carry until upstream takes it | **Chosen** |
| A gateway authority verb (`projects.set_owner`) | Fits the v0.23 authority model | A new RPC for one field, against "existing calls over new RPCs" | Rejected |
| A plugin-owned store | No core edit | No plugin surface adds fields to `projects.*` replies; Session Mail and the sidebar would need a second source | Rejected |

#### Decision 2: the Webapp sidebar change — core edit versus desktop plugin

What desktop plugins can hook, from the code: routes and sidebar navigation (`app/routes.ts`),
session-row badges (`lib/session-row-slots.ts`, keyed on the durable stored id), composer
middleware (`app/chat/composer/contrib.ts`), the command palette, and server calls through
`host.request`. **There is no contribution area on the project row or the project list**, so
what a tap does and the order of an entered project's list can only change in core.

| Option | For | Against | Verdict |
|---|---|---|---|
| **Core sidebar edit**, logic in a `sidebar/projects/` sibling | Where Alex taps; reuses the entered view; the pinned-owner exemption sits next to the pin filter; offerable upstream with the column | Core interface files; must shrink an over-cap file and function | **Chosen** |
| A plugin Projects page (route + nav entry) | No core interface edits | Duplicates the sidebar list; the tap still only scopes; two places show the same thing (cut in refinement) | Rejected |
| A new project-row slot in core, plus a plugin | Generic seam | A hook with one consumer (`AGENTS.md` rejects it), and more code than the change itself | Rejected |
| Runtime plugin in `<hermes-home>/desktop-plugins/` | — | Outside the fork (`rules.md` 19) | Rejected |

How a pinned owner still shows in its project: the owner hook's matcher exempts the owner row
from `isHiddenFromProjects` only inside the owner's own project, so it renders first, marked
"Main chat", while also staying in Pinned. Pins themselves are untouched (seeding does not pin).

#### Decision 3: the `/new` → compact rule (brief Q2) and where it lives

| Option | For | Against | Verdict |
|---|---|---|---|
| **Bundled fork desktop plugin** (`apps/desktop/src/plugins/<project-owner>/plugin.tsx`), one `composer.middleware` | The hook exists and Bot Chat already does exactly this (`hermes-bots/plugin.tsx`); no core file; keyed on `host.state.focusedStoredSessionId` against owner ids from `host.request('projects.list')` | One more bundled plugin in the fork | **Chosen, if Q2 = yes** |
| Fold it into the core composer | One place | Core edit for a rule a hook already serves | Rejected |
| A server or TUI guard | Covers every surface | Changes slash handling in TUI, CLI and gateway; Alex's surface is the Webapp | Deferred |

The rule matches `/^\/(new|reset)\s*$/`, only in a chat whose stored id is an owner of the
profile's projects, and shows a notice ("This is the project's main chat — compacting instead").
On the gateway, `/compact` is an owner-run `session.mutate` that keeps the session id
(`compression.in_place: true`). If Q2 = no, part 3 is not built.

#### Decision 4: seeding by session id, with an undo record

| Option | For | Against | Verdict |
|---|---|---|---|
| **A `hermes project set-owner <project> <session-id>` / `--clear` verb** in `hermes_cli/projects_cmd.py`, run six times | Same shape as `bind-board`; per profile like every `hermes project` verb; checks the session exists; prints the previous value, which the run records as the undo file; covers a later project without a UI button; upstreamable | One more CLI verb | **Chosen** |
| `projects.update` over the gateway socket from a one-off script | No CLI change | Needs a ticketed client; a one-off script is either a side repo or throwaway code in the fork | Rejected |
| Direct SQL on `projects.db` | Smallest | Bypasses validation and the module's conventions | Rejected |

The run, with Alex's go: for each of the six projects (brief fact 25), `set-owner` with the
listed id, appending `{project, previous, new}` to an undo file under `<hermes-home>/backups/`
(outside git, it holds real ids); undo = `set-owner <project> <previous>` or `--clear`. Ids, never
titles. Pins are not changed. Five of the six owners have ended; opening one resumes it.

#### Decision 5: the upstream offer

| Option | For | Against | Verdict |
|---|---|---|---|
| **One issue draft** (Alex posts) proposing the field, the `set-owner` verb and the sidebar behaviour, fork commits linked as ready patches | Asks intent first; one coherent feature; costs nothing if declined | Slower than PRs | **Chosen** |
| Pull requests directly | Faster if wanted | Agents never post; unasked | Only if maintainers ask |
| Keep it fork-only | No effort | Permanent carry of a core sidebar edit in a busy file | Rejected |

The `/new` plugin is mentioned as an optional follow-up, not part of the ask (upstream keeps
bundled plugins to real shipped ones, `apps/desktop/src/plugins/README.md`).

#### Decision 6: deploy on the combined gateway

How the fork ships Webapp changes, from the live install (read-only metadata): the gateway unit
has run since 2026-11-10 22:11 with no restart, yet the bundle's receipt
(`apps/desktop/dist-webapp/hermes-build.json`) was written at 2026-11-11 19:57:19, 16 s after the
last `webapp:` commit (`44d37bcc5d`, 19:57:03). So front-end-only commits ship as pull →
rebuild the bundle → browsers reload; the gateway serves the bundle from disk per request.
`git pull --ff-only` does not rebuild it (only `hermes update` does, `_rebuild_served_webapp`);
the explicit step is `hermes webapp --build-only` (it reuses a current bundle by its receipt).

| Process | Reads the change? | Restart? | What it interrupts |
|---|---|---|---|
| **Gateway** (`hermes-gateway`: Webapp, `/api/ws`, legacy `projects.*`, messaging, cron) | Yes: parts 1 and 4's Python run in-process | **Yes, once, drain-first** | Every running turn on every surface (Webapp chats, one-shot kickoff turns, messaging, cron) and every socket; Webapp tabs reconnect |
| Webapp bundle (parts 2–3) | Built from `apps/desktop` | No restart: `hermes webapp --build-only`, then reload | Nothing |
| `hermes project set-owner` | Per invocation | No | Nothing |
| Standalone dashboard (`hermes-dashboard`) | Imports the same modules, but Alex does not use it | Not needed for the feature | If restarted: turns its legacy backend runs (Session Mail's dispatch script) |

The restart: `hermes gateway restart` **without** `--interrupt` (SIGUSR1): it refuses new work,
waits up to `agent.restart_after_turn_timeout` (1,800 s) for running turns, then exits 75, which
the unit restarts (`Restart=always`, `RestartForceExitStatus=75`). A plain `systemctl restart`
would interrupt at once (`restart_drain_timeout: 0`). Interrupted chat turns auto-continue on the
next message within `agent.gateway_auto_continue_freshness` (1 h).

Sequence (Alex's go): check no owner turn is running → `git pull --ff-only` on the deployed
branch → `hermes webapp --build-only` → one drain-first gateway restart → verify (`projects.list`
shows the field; tap and ordering in the Webapp; a project without owner unchanged) → seeding run
with its undo file → reload the Webapp on laptop and phone. Restarts are run by Alex or with his
explicit go, never by a builder.

### Persistence

| What | Where | Durable how |
|---|---|---|
| `owner_session_id` | per-profile `<hermes-home>/projects.db`, table `projects` | Additive column, created on first open; old code ignores it |
| Seeding undo file | `<hermes-home>/backups/` (outside git; real ids) | Written during the run; restores prior values |
| Sidebar change, `/new` plugin, `set-owner` verb | Fork tree (`apps/desktop/src/...`, `hermes_cli/projects_cmd.py`) | Git |
| Webapp bundle | `apps/desktop/dist-webapp` in the install, with its build receipt | Rebuilt per deploy; not in git |
| Pins | `sessions.pinned` (server) | Unchanged by this chunk |
| Issue draft (upstream) | Git, under `docs/project-centric-ui/` (path set at Groom) | Alex reviews and posts |
| Design records | Git on project-main | Plan/Spec artifacts; `poc/` (v0.22) and `poc/v023/` frozen |

### Worker rules

- **Who implements:** builders, one item per fork feature branch cut from
  `integrate/project-centric-ui-023`; land by the chunk's land path; deploy by fast-forwarding the
  deployed branch (`rules.md` 19). No live edits, no side repos, no runtime plugins in
  `<hermes-home>/desktop-plugins/`.
- **Items:** the core Python patch with the `set-owner` verb (part 1); the sidebar change
  (part 2); the `/new` plugin only if Q2 = yes (part 3); the seeding run (part 4); the upstream
  issue draft (part 5). Part 1 lands first; part 2 must behave exactly as today when the field is
  absent.
- **Tests:** Python through `scripts/run_tests.sh` against a temporary `HERMES_HOME` (migration on
  an existing `projects.db`; set, clear, read through `projects.update`, `projects.list` and the
  tree; `set-owner` refuses an unknown session). Webapp logic in the `apps/desktop` vitest suite
  (tap opens the owner; owner first and marked; pinned owner still in its project; no owner →
  unchanged; the `/new` rule only in owner chats). Behaviour contracts, never source-reading
  tests; each fix proven red on the base.
- **Size ratchet:** `sidebar/index.tsx` and `ChatSidebar` must end smaller than on the base; new
  units meet the caps.
- **Builders run nothing against the live home:** no hooks, `scripts/check`, tests or `hermes`
  commands with the live `HERMES_HOME`; anything that runs uses a temporary one.
- **HITL (Alex):** the restart window, the seeding run, the upstream post, answers to Q1–Q3.
- **Must not bypass:** agents never post issues or PRs, never restart services, never write to
  the live `<hermes-home>` except the approved seeding run, and never stage secrets, hostnames,
  local paths or session dumps (the seed's ids stay in the undo file outside git).

### Open

Places where a different answer from Alex changes the shape:

- **Q1 (what a tap does, where the code lives).** Designed on option A (core sidebar change) plus
  the `/new` plugin only under Q2; the badge plugin was cut. If Alex wants a separate Projects
  page instead (option B), part 2 becomes a bundled plugin route, the tap stays scope-only, and
  the "Main chat" mark moves to a session-row badge.
- **Q2 (`/new` compacts the owner chat).** Recommended yes, Webapp only. No → part 3 is not built;
  nothing else changes. Yes on every surface → a TUI/CLI/gateway slash guard: a reshape, escalate.
- **Q3 (seed set, pins).** Recommended: the six ids of brief fact 25, pins unchanged. A different
  set changes only the seed data. "Pin the owners too" would need nothing new (part 2 already
  keeps a pinned owner in its project).
- **Session Mail's switch** (was brief Q4): the server field alone; sent to that chunk as a note.
- Not answerable by talking: the narrow-screen drawer layout (it does not close when a chat is
  picked; the tap now opens a chat, so Spec decides whether the drawer closes) — mock-up at the
  gate; upstream interest; the real Webapp on the phone steering a real multi-hour turn (checked
  live after deploy).

## Optional

### PoC questions (Trial)

**v0.23 round: Trial run** — `docs/project-centric-ui/poc/v023/poc.md`. Question: does a
`hermes chat -q --oneshot` kickoff turn run inside the gateway so that another interactive client
(what a Webapp socket is) can steer, queue and stop it, also after the CLI exits mid-turn (the
brief's open point)? It was the premise for dropping part 6 and cheap to prove: a real gateway
daemon and CLI on a temporary `HERMES_HOME`, a fake local model, no credentials. Result: **14/14**,
including steer and stop after the CLI was killed. Not proven: the browser sign-in path, hours,
a real model; checked live after deploy.

No trial for the rest: the owner patch files are unchanged from v0.22 (diff above); the
legacy-fallback path for `projects.*` is read from code; the sidebar and plugin changes are
ordinary front-end work covered by Build's vitest tests.

The v0.22 trial (`poc/`) stays a frozen record; its subject (owner turns in the dashboard
process) is dropped.

### Risks

- **The sidebar file is busy upstream and over its cap.** Rebase conflicts in `index.tsx` are
  likely; moving the owner and pin logic into a sibling keeps the carried diff small.
- **Pinned owner shown twice** (Pinned and its project). Intended; the project copy is marked.
- **Tree window.** The tree reads up to `session_limit` recent sessions; a long-idle owner could
  fall outside it and lose its row. Spec decides whether the hook fetches the owner row on its
  own (`session.info`) when absent.
- **Name clash** of `owner_session_id` with unrelated fields elsewhere; mitigated by the
  docstring, kept for Session Mail.
- **A plain `systemctl restart`** would interrupt running turns at once; the deploy uses the
  drain-first restart.
