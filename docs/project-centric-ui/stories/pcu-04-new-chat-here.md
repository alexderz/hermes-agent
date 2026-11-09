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
  - [ ] Starting a chat here does not change the main chat.
  - [ ] The chat always starts in the project's own profile, even if the dashboard was left on another profile (for example after opening a chat from another profile, `pcu-15`). This uses the same profile handling as the HLD's Profiles open item. If Spec finds it needs a new HLD part, this line becomes a known side effect beside U8 in `ux.md`.
  - [ ] The side effect is visible: afterwards, the Chat page's folder picker shows the project's folder, and the next fresh chat started from Chat also starts there until another folder is picked.
  - [ ] For a declared project with no folder, the button is disabled and the reason is written beside it.
  - [ ] Home's page has no **New chat here**. It shows "These chats have no project folder. To start one, use New chat on the Chat page." with a link to Chat.
  - [ ] An auto-found folder's page has **New chat here**, and it starts in that folder.
- **Out of scope** — choosing a different folder of the project; naming the chat up front.

## Optional

- Notes: per the HLD, slice 1 sets the Chat page's remembered folder (the folder picker's stored value) and opens Chat. A `/chat?cwd=` deep link that avoids the side effect is an HLD open item (`ux.md`, U8).
