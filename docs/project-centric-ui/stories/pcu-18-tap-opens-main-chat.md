# Story — Tapping a project opens its main chat

- Id: `pcu-18-tap-opens-main-chat`
- HLD / UX: `docs/project-centric-ui/hld.md`, `docs/project-centric-ui/ux.md` (J1, J2)
- Person: Alex

## Required

- **As** Alex
- **I want** a click or tap on a project in the Webapp sidebar to open its main chat and enter the project
- **So that** the project is my front door: one tap to the long-lived chat, with the project's other chats beside it
- **Done when**
  - [ ] On a laptop, clicking the name of a project whose main chat is found among the project's chats opens that chat in the main pane, the same way clicking its row does. An already-open chat is focused, not opened twice.
  - [ ] The same click also enters the project in the sidebar, exactly as today.
  - [ ] An ended main chat opens and resumes like any ended chat.
  - [ ] From an entered project, tapping the back row and then another project opens that project's main chat and enters it.
  - [ ] The project's "+" still starts a new chat in the project's primary folder, and the main chat stays as it is.
  - [ ] The project row's accessible name says it opens the main chat (for example "Open main chat of HIM - Hermes Improvement").
  - [ ] Renaming the project or the main chat changes nothing about what the tap opens.
  - [ ] If the main chat is not found among the project's chats, the tap only enters the project, as today (`pcu-20`), and never tries to open it.
  - [ ] Size ratchet: both `apps/desktop/src/app/chat/sidebar/index.tsx` and its `ChatSidebar` function end smaller than before the change. The new logic lives in a `sidebar/projects/` sibling.
- **Out of scope** — the command palette's "go to project" (`ux.md` U6); the three-chat overview preview (U3); a separate Projects page.
