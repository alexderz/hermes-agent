# Story — Open a project chat from another profile

- Id: `pcu-15-other-profile-chat`
- HLD / UX: `docs/project-centric-ui/hld.md`, `docs/project-centric-ui/ux.md`
- Person: Alex

## Required

- **As** Alex, whose projects can hold chats from more than one profile
- **I want** opening a main chat or a chat row that belongs to another profile to land in that chat
- **So that** a tap never resumes the wrong chat or an empty one
- **Done when**
  - [ ] A Main chat card or chat row from a profile other than the one in use shows that profile's name as a text label.
  - [ ] Spec picks **one** of these two alternatives (U9 in `ux.md`):
    - [ ] **(a)** Opening it, from the Main chat card or a row, shows that chat's history in Chat, never an empty or different chat. After opening, the dashboard's profile is the chat's profile; the banner shows it when that is not the dashboard's own profile. The switch persists, and the story says so: new chats from Chat, config and keys apply to that profile until Alex switches back.
    - [ ] **(b)** The tap shows "This chat is in the <profile> profile. Switch profile to open it." and opens nothing; the dashboard's profile does not change.
  - [ ] Whichever is picked, **New chat here** on a project afterwards still starts in that project's own profile (see `pcu-04`).
- **Out of scope** — moving chats between profiles; a main chat per profile on one project card.

## Optional

- Notes: depends on the HLD's "Profiles" open item (owners open in the dashboard's current profile; Spec settles the link). See F9 and U9 in `ux.md`.
