# Story — Open a project's main chat in one tap

- Id: `pcu-02-open-main-chat`
- HLD / UX: `docs/project-centric-ui/hld.md`, `docs/project-centric-ui/ux.md`
- Person: Alex

## Required

- **As** Alex
- **I want** an **Open main chat** button on each project card
- **So that** I am back in the project's long-lived chat with as little friction as possible
- **Done when**
  - [ ] On a project with a main chat, **Open main chat** goes to `/chat?resume=<owner_session_id>`, and the terminal shows that chat's history.
  - [ ] On a laptop, reaching a main chat from any dashboard page takes two clicks: **Projects**, then **Open main chat**.
  - [ ] On a phone, it takes three taps: the menu, **Projects**, **Open main chat**. From a home-screen bookmark to the Projects list, it takes one tap.
  - [ ] Browser Back from Chat returns to the Projects list.
  - [ ] On a project with no main chat, or a missing one, the button reads **Open project** and opens the project page. It never opens an empty or wrong chat.
- **Out of scope** — a project breadcrumb inside the Chat page; compacting on `/new` in the dashboard (Q1).

## Optional

- Notes: if Alex prefers the whole card to open the main chat, this story changes (open question U1 in `ux.md`).
