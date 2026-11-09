# Story — Hermes Mobile project screen (drafted issue 1)

- Id: `pcu-11-mobile-project-screen`
- HLD / UX: `docs/project-centric-ui/hld.md`, `docs/project-centric-ui/ux.md`
- Person: Alex

## Required

- **As** Alex on Hermes Mobile
- **I want** tapping a project to open a screen with its main chat on top and its chats below
- **So that** my main surface treats the project as the front door, like the Bots roster does for Bot Chat
- **Done when** (for this chunk: the draft; the app work is the maintainer's)
  - [ ] An issue draft for the Hermes Mobile repository exists in the fork's docs, using its feature-request template, for Alex to review. Nothing is posted.
  - [ ] The draft asks that tapping a project card open a project screen, with edit, archive and delete behind an **Edit** action.
  - [ ] The draft asks for a **Main chat** card on top, read from `owner_session_id` in `projects.list`, opening the chat like a bot's canonical chat (`BotsScreen.kt`). Its running state is shown with a label, not colour alone.
  - [ ] The draft asks for the project's chats below, newest first, and a **New chat** action.
  - [ ] The draft says that a missing field or a missing chat simply hides the Main chat card, with no error.
  - [ ] The draft includes the "working elsewhere" ask from `pcu-17`.
  - [ ] The draft links the server change and says which server versions send the field.
  - [ ] The draft carries no AI-authorship trailer, per the app's contributing rules.
- **Out of scope** — writing app code; posting the issue.
