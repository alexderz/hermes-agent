# Story — New chat in the project

- Id: `pcu-04-new-chat-here`
- HLD / UX: `docs/project-centric-ui/hld.md`, `docs/project-centric-ui/ux.md`
- Person: Alex

## Required

- **As** Alex
- **I want** a **New chat here** button on the project page
- **So that** a side chat starts in the project's folder, gets the project's context, and is listed under the project
- **Done when**
  - [ ] **New chat here** opens Chat on a fresh chat whose working folder is the project's **primary** folder.
  - [ ] After the first message, that chat appears in the project's chats list, and not under Home or a folder name.
  - [ ] Starting a chat here does not change the main chat or the dashboard's saved default folder for other new chats.
  - [ ] For a project with no folder, the button is disabled and the reason is written beside it.
- **Out of scope** — choosing a different folder of the project; naming the chat up front.

## Optional

- Notes: reuses the dashboard's existing "fresh chat in a chosen folder" path (`ChatWorkspacePicker` and `/api/pty?cwd=`). Whether this goes through the picker's saved value is for the HLD.
