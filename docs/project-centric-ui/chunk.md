# Chunk — project-centric Hermes UI (v0.23, Webapp surface)

- Slug: `project-centric-ui`
- Type: Epic
- Track: Hermes Improvement (`PROJECT.md` work item 2, Alex's web surface); n/a as a tracker id
- HLD: `docs/project-centric-ui/hld.md` (v0.23 rewrite, 2026-11-11)
- LLD: n/a until Spec (`docs/project-centric-ui/lld.md`)
- Groom: `.agents/design/project-centric-ui/groom.md` (frozen)
- project-main: `integrate/project-centric-ui-023` (cut from the deployed `alex/v0.23.1-canary-1110`;
  the v0.22 project-main `integrate/project-centric-ui` is frozen)
- Land path: merge-and-delete after explicit Review (local, serialized);
  push item branches and project-main; no internal PRs

Epic: `DER-686`.

## Required

- **Why this slice, why now** — Alex works by project, the backend groups sessions by project,
  and since 2026-11-11 his only surface is the v0.23 Webapp, where tapping a project only scopes
  the sidebar, nothing marks the main chat, and a pinned main chat disappears from its project.
  The owner sessions are already re-homed into their folders, and on v0.23 a working owner chat
  is already steerable from the phone (Trial `poc/v023/`), so the slice is small: one column, a
  CLI verb, one sidebar change, an optional `/new` rule, a seed, one restart.
- **Done** — Trunk: project-main on trunk (fast-forwarded into the deployed branch per
  `rules.md` 19, deployed with `hermes webapp --build-only` and one announced drain-first gateway
  restart); tickets landed+verified:
  - `projects.list` / `projects.get` / the tree carry `owner_session_id`; `projects.update` and
    `hermes project set-owner` set and clear it;
  - the six owners are seeded by id with an undo file;
  - in the Webapp on laptop and phone, tapping a project with an owner opens its owner chat, the
    owner is listed first and marked "Main chat" even when pinned, and a project without an owner
    is unchanged;
  - if Q2 = yes, `/new` in an owner chat compacts it with a notice and keeps the session id;
  - a working owner chat started by a `--oneshot` kickoff is steered from the phone with no
    "Chat open somewhere else" card (live check);
  - the upstream issue draft is in git for Alex and nothing is posted.
- **Children** — none filed yet. Planned items (the manager files them at Groom):
  1. Backend: `owner_session_id` through `projects.update` / `list` / `get` and the tree, plus
     `hermes project set-owner` (core fork patch).
  2. Webapp: sidebar tap opens the owner; owner first and marked, also when pinned; logic moved
     into a `sidebar/projects/` sibling so the over-cap file shrinks. Behaves as today without
     the field.
  3. Webapp: bundled fork plugin with the `/new` → `/compact` rule for owner chats. **Only if
     Q2 = yes.**
  4. Deploy: pull, `hermes webapp --build-only`, one drain-first gateway restart (Alex's go).
     Blocked by 1, 2 (and 3 if built).
  5. Seed the six owners by id with an undo file (data fix; Alex's go). Blocked by 4.
  6. Draft the upstream issue offering 1 and 2. Blocked by 1 and 2 landed.
  7. Live check after deploy: steer a running `--oneshot` owner turn from the phone. Blocked by 4.

  Not children: the legacy `session.compress` ownership gap (its own fork bug); the note to
  Session Mail that its `@project` switch is the server field alone.
- **Wave view** — not kept here; manager posts one Epic comment only on reshape (item added or
  canceled, blocker set)
- **Blocked by** — none (Alex's answers to brief Q1–Q3 are a gate on Spec, not a tracker blocker)
- **Blocks** — Session Mail's `@project` addressing waits on item 1 (that chunk's own gate)

## Optional

- **Risks that only this chunk carries** — the gateway restart interrupts every running turn on
  every surface, so it is drain-first and scheduled when no owner turn runs; `sidebar/index.tsx`
  is over its size cap and busy upstream; the narrow-screen drawer does not close when the tap
  opens a chat (Spec decides).
- **Dropped by the v0.23 move** (were children in the v0.22 chunk): the dashboard Projects tab,
  both Hermes Mobile issue drafts, the dashboard-socket kickoff command and its unit switch.
- **Operator timezone for after-act** — US Central.
