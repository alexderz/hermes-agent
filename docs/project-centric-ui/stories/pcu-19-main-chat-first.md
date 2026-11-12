# Story — Main chat first in its project, marked, even when pinned

- Id: `pcu-19-main-chat-first`
- HLD / UX: `docs/project-centric-ui/hld.md`, `docs/project-centric-ui/ux.md` (J1, F3, F5)
- Person: Alex

## Required

- **As** Alex
- **I want** the entered project's list to start with the main chat, marked in words
- **So that** I can tell it from similar chats ("HIM - Project UI", "HIM - Session Mail") at a glance, and a pinned main chat never leaves its project
- **Done when**
  - [ ] In an entered project with a main chat, the first session row after the back row is the main chat, above the main-checkout chats. Worktree groups stay below, as today.
  - [ ] That row shows the visible text **Main chat**, plus a visible word for its status dot, readable without hover:
    - working or stalled: **Main chat · Working**;
    - needs input: **Main chat · Needs your answer**;
    - background process running: **Main chat · Background task running**;
    - finished while unread: **Main chat · Finished**;
    - settled: **Main chat** alone.
  - [ ] The dot keeps its existing colour beside the word; other rows are unchanged.
  - [ ] Its accessible name includes "Main chat".
  - [ ] A pinned main chat ("HME - Orchestrator") appears both in the Pinned section, unchanged, and first in its project, marked **Main chat**.
  - [ ] Unpinning or pinning it does not move it from first place in its project.
  - [ ] The main chat is listed once in its project, never twice (for example under both its live and its original id after a compaction).
  - [ ] No other row, list or section gains a mark.
- **Out of scope** — marking the Pinned row (`ux.md` U2); the overview preview (U3); a row-badge plugin.
