# Story — Projects without a main chat behave as today

- Id: `pcu-20-no-main-chat-unchanged`
- HLD / UX: `docs/project-centric-ui/hld.md`, `docs/project-centric-ui/ux.md` (F1, F2, F4)
- Person: Alex; family members
- Absorbs the retired `pcu-05`, `pcu-06` and `pcu-10`.

## Required

- **As** a Webapp user whose project has no main chat, or whose main chat is gone
- **I want** the project to behave exactly as it does today
- **So that** nothing breaks or changes for projects, people or servers that don't use main chats
- **Done when**
  - [ ] A project with no `owner_session_id` (or a server that does not send the field): tapping it only enters the project, nothing opens, no row is marked, and no message appears.
  - [ ] One rule: the tap opens the main chat only when it is found among the project's chats (or by a direct lookup, if Spec adds one).
  - [ ] A project whose main chat is archived or deleted behaves as with no main chat, with no error, and never tries to open it, unless Spec's direct lookup covers archived chats (HLD Risks). After an archived chat is restored, tapping opens it again and it is marked **Main chat**.
  - [ ] A main chat that has fallen outside the tree's window of recent chats: the project shows no **Main chat** row, and the tap only enters it, with no error. Once a message is sent in it (the tree keeps chats by last activity), the row and the tap come back. (If Spec adds the direct lookup, the row and the tap keep working instead; this line then checks that.)
  - [ ] A project with a main chat but no other chats shows only the **Main chat** row, and its "+" works as today.
  - [ ] Auto-found folders and Home behave exactly as today.
  - [ ] A profile with no main chats (a family member's) shows no visible change anywhere in the Webapp.
- **Out of scope** — a "set a main chat" prompt or button; opening an archived main chat on tap (the one rule in `ux.md` F2 excludes it).
