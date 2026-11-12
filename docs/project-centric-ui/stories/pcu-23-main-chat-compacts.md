# Story — `/new` in a main chat compacts it (only if Q2 is yes)

- Id: `pcu-23-main-chat-compacts`
- HLD / UX: `docs/project-centric-ui/hld.md`, `docs/project-centric-ui/ux.md` (J5)
- Person: Alex
- Replaces the retired `pcu-12`.

## Required

- **As** Alex
- **I want** `/new` or `/reset` typed in a project's main chat in the Webapp to compact it instead of starting over
- **So that** the main chat stays one continuous conversation, like Bot Chat
- **Done when** (only if Alex answers brief Q2 "yes")
  - [ ] In a main chat in the Webapp, sending exactly `/new` or `/reset` runs `/compact` instead.
  - [ ] It shows a notice saying this is the project's main chat, so it compacts instead of resetting, and that **+** on the project starts a separate chat. The exact text is settled at Spec (the HLD's and `ux.md`'s wordings differ).
  - [ ] After compaction the session id is unchanged, so it is still the main chat: the tap opens it and it is still marked **Main chat**.
  - [ ] `/new` in any other chat, in Bot Chat, on the command line and in the terminal interface behaves as before.
  - [ ] The rule finds the main chat by `owner_session_id`, never by title.
- **Out of scope** — a server or terminal `/new` guard.

## Optional

- Notes: copies the hermes-bots plugin's composer rule; where it lives is the HLD's call. If the main chat is working, the gateway's compaction rules apply as for any chat.
