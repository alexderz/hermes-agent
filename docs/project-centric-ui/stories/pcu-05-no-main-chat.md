# Story — Projects without a working main chat

- Id: `pcu-05-no-main-chat`
- HLD / UX: `docs/project-centric-ui/hld.md`, `docs/project-centric-ui/ux.md`
- Person: Alex

## Required

- **As** Alex
- **I want** a project with no main chat, or whose main chat was archived or deleted, to still show its chats and let me start one
- **So that** a missing pointer never blocks me or shows me an error
- **Done when**
  - [ ] With no `owner_session_id` (or the field absent from the response), the project page has no Main chat card, puts **New chat here** first, and shows the chats list. No error appears.
  - [ ] With an `owner_session_id` that is not among the project's sessions, the page shows: "This project's main chat isn't here. It may have been archived or deleted." This is plain text, with a link to the Sessions page.
  - [ ] The Projects list card reads "No main chat" or "Main chat missing" in those two cases.
  - [ ] Restoring an archived main chat on the Sessions page brings the Main chat card back on the next visit, with no other step.
- **Out of scope** — a "Make main chat" button; clearing the pointer automatically.

## Optional

- Notes: whether the dashboard should still try to open an archived main chat is open question U5.
