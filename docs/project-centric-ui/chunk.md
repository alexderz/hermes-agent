# Chunk — project-centric Hermes UI

- Slug: `project-centric-ui`
- Type: Epic
- Track: Hermes Improvement (`PROJECT.md` work item 2, the mobile web UI); n/a as a tracker id
- HLD: `docs/project-centric-ui/hld.md`
- LLD: n/a until Spec (`docs/project-centric-ui/lld.md`)
- Groom: `.agents/design/project-centric-ui/groom.md` (frozen)
- project-main: `integrate/project-centric-ui`
- Land path: merge-and-delete after explicit Review (local, serialized);
  push item branches and project-main; no internal PRs

Epic: `DER-686`.

## Required

- **Why this slice, why now** — Alex works by project and the backend already groups sessions
  by project, but neither Hermes Mobile nor the dashboard shows it, and there is no owner chat.
  The owner sessions were just re-homed into their project folders and the CLI `cwd` bug is
  fixed, so the data is ready. Slice 1 is one column, one dashboard plugin page with a kickoff CLI command, a one-time seed,
  and drafted issues: small enough to show Alex in one deploy before deciding the `/new` guard,
  a "make owner" button, the PWA and Home.
- **Done** — Trunk: project-main on trunk (fast-forwarded into the deployed branch per
  `rules.md` 19 and deployed with one announced dashboard restart); tickets landed+verified:
  `projects.list` / `projects.get` / the tree carry `owner_session_id`; the six owners are
  seeded with an undo file; the dashboard Projects tab opens each owner chat on laptop and phone
  browser; the current Hermes Mobile build works unchanged; the three issue drafts are in git
  for Alex and nothing is posted; an owner turn started by the kickoff runs in the dashboard
  process and Alex can open, steer, queue and stop it from Hermes Mobile.
- **Children** — none filed yet. Planned items (the manager files them at Groom):
  1. Backend: `owner_session_id` on projects, through `projects.update` / `list` / `get` and
     the tree (core fork patch).
  2. Dashboard: Projects plugin tab (bundled fork plugin, after Sessions). Depends on 1 for the
     owner row only.
  3. Seed the six owners with an undo file (data fix; Alex's go). Blocked by 1 deployed.
  4. Draft Hermes Mobile issues 1 and 2 (Alex reviews and posts).
  5. Draft the upstream Hermes issue offering item 1's patch. Blocked by 1 landed.
  6. Deploy: one dashboard restart (Alex's go). Blocked by 1 and 2.
  7. Kickoff CLI command in the same fork plugin: owner turns submitted through the
     dashboard's `/api/ws` (HLD part 6; Trial `poc/poc.md`). Independent of 1.
  8. Enable the plugin's CLI command and switch the kickoff unit to it (Alex's tooling and
     house-infra; Alex's go). Blocked by 6 and 7, so the restart in 6 has no owner turn to kill.

  Not a child: the `session.compress` lease bug (brief fact 22) is filed as its own fork bug.
- **Wave view** — not kept here; manager posts one Epic comment only on reshape (item added or
  canceled, blocker set)
- **Blocked by** — none (Alex's answers to brief Q1–Q4 are a gate on Spec, not a tracker blocker)
- **Blocks** — none

## Optional

- **Risks that only this chunk carries** — each dashboard restart cuts Hermes Mobile off, and
  after item 8 it also kills a running owner turn, so the chunk has exactly one restart, before
  item 8, and later deploys follow the HLD's restart rules; a reshape (for example a dashboard `/new` guard from Q1) must not add a
  second restart without Alex's go. The plugin couples to the chat page's stored-folder key until
  a `/chat?cwd=` deep link exists (HLD, Open).
- **Operator timezone for after-act** — US Central.
