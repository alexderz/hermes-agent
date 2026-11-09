# Story — Main chats set for Alex's projects

- Id: `pcu-08-main-chats-seeded`
- HLD / UX: `docs/project-centric-ui/hld.md`, `docs/project-centric-ui/ux.md`
- Person: Alex

## Required

- **As** Alex
- **I want** each of my six projects to know its main chat from day one, and the change to be undoable
- **So that** the new screens show my Orchestrator chats without my setting anything
- **Done when**
  - [ ] After the data fix, `projects.list` returns these main chats:
    - "Hermes Improvement — Orchestrator", "SDLC — Orchestrator", "Budgeting — Orchestrator", "Home Eng — Orchestrator" and "Minecrafting — Orchestrator" for their projects;
    - "Model Master" for Model Testing.
  - [ ] "Llama-bored" stays pinned and is not a main chat.
  - [ ] The fix writes an undo file. Running the undo clears the six pointers and changes nothing else.
  - [ ] Each project's card on the dashboard names the expected main chat.
- **Out of scope** — a user interface for choosing the main chat; main chats for profiles other than Alex's.

## Optional

- Notes: the choice of chats is Q2 in the brief; a different answer changes only the names above.
