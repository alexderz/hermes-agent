# Story — Projects list on the dashboard

- Id: `pcu-01-project-list`
- HLD / UX: `docs/project-centric-ui/hld.md`, `docs/project-centric-ui/ux.md`
- Person: Alex

## Required

- **As a** Hermes user who groups work into projects
- **I want** a Projects entry in the dashboard that lists my projects, each naming its main chat
- **So that** the project, not a flat list of sessions, is where I start
- **Done when**
  - [ ] A **Projects** entry sits directly after **Sessions** in the dashboard navigation (the HLD's plugin tab at `after:sessions`), on laptop and in the narrow-screen menu.
  - [ ] The Projects list has its own address, and a bookmark to it opens it directly.
  - [ ] The Projects list shows every declared, non-archived project from `GET /api/profiles/projects/tree`, most recently active first.
  - [ ] Each card shows the colour dot and name, "Main chat: <title>" (or "No main chat" / "Main chat missing"), the chat count, and time since last activity.
  - [ ] Auto-found folders and **Home** appear below the declared projects under "Other chats", and open the same kind of project page (Home's page follows F8 in `ux.md`).
  - [ ] While loading, the page shows a spinner with "Loading projects…".
  - [ ] A failed request shows the standard load-error notice with **Retry**, and the rest of the dashboard keeps working.
  - [ ] If some profiles fail, the projects that loaded are shown, with one line naming the profiles that failed.
- **Out of scope** — creating, editing, archiving or reordering projects; changing the landing page; a running (**Live**) badge, since the tree carries no running state (open question U7).

## Optional

- Notes: the project tree already sorts by last activity. Whether "Other chats" is shown at all is open question U4 in `ux.md`.
- Linked mockup: at Spec.
