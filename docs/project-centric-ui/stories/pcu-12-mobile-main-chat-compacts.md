# Story — `/new` in the main chat compacts on Hermes Mobile

- Id: `pcu-12-mobile-main-chat-compacts`
- HLD / UX: `docs/project-centric-ui/hld.md`, `docs/project-centric-ui/ux.md`
- Person: Alex

## Required

- **As** Alex
- **I want** `/new` typed in a project's main chat on my phone to compact it instead of starting over
- **So that** the main chat behaves like Bot Chat: one continuous conversation
- **Done when** (for this chunk: the draft)
  - [ ] Drafted issue 1 includes one request: treat the chat whose id is the project's `owner_session_id` like Bot Chat on `/new` (`ChatViewModel.kt`), with a line such as "This is <project>'s main chat — compacting instead. For a separate chat, use New chat on the project."
  - [ ] Nothing in the dashboard or terminal UI changes for `/new`.
- **Out of scope** — a server or terminal-UI guard (deferred, Q1).

## Optional

- Notes: depends on Q1. If Alex wants no guard, this story is dropped.
