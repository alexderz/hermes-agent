# Story — Projects list on the dashboard

- Id: `pcu-01-project-list`
- HLD / UX: `docs/project-centric-ui/hld.md`, `docs/project-centric-ui/ux.md`
- Person: Alex

## Required

- **As a** Hermes user who groups work into projects
- **I want** a Projects entry in the dashboard that lists my projects, each naming its main chat
- **So that** the project, not a flat list of sessions, is where I start
- **Done when**
  - [ ] A **Projects** entry sits directly above **Sessions** in the dashboard navigation, on laptop and in the narrow-screen drawer.
  - [ ] `/projects` lists every declared, non-archived project from `GET /api/profiles/projects/tree`, most recently active first.
  - [ ] Each card shows the colour dot and name, "Main chat: <title>" (or "No main chat" / "Main chat missing"), the chat count, and time since last activity.
  - [ ] A card shows the **Live** badge (colour plus the word) when any of its chats is running a turn.
  - [ ] Auto-found folders and **Home** appear below the declared projects under "Other chats", and open the same project page.
  - [ ] While loading, the page shows a spinner with "Loading projects…".
  - [ ] A failed request shows the standard load-error notice with **Retry**, and the rest of the dashboard keeps working.
  - [ ] If some profiles fail, the projects that loaded are shown, with one line naming the profiles that failed.
- **Out of scope** — creating, editing, archiving or reordering projects; changing the landing page.

## Optional

- Notes: the project tree already sorts by last activity. Whether "Other chats" is shown at all is open question U4 in `ux.md`.
- Linked mockup: at Spec.
