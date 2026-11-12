# Story — Main chats set for Alex's projects, by session id

- Id: `pcu-08-main-chats-seeded`
- HLD / UX: `docs/project-centric-ui/hld.md`, `docs/project-centric-ui/ux.md`
- Person: Alex

## Required

- **As** Alex
- **I want** each of my six projects to know its main chat from day one, set by session id, and undoable
- **So that** tapping a project opens the right chat without my setting anything, whatever the chats are called later
- **Done when**
  - [ ] Seeding is six runs of `hermes project set-owner <project> <session-id>`, one per project; `--clear` removes a main chat. The same command gives a later project its main chat.
  - [ ] After the six runs, `projects.list` returns `owner_session_id` for all six projects, matching the session ids in the brief's live-data table (fact 25):
    - "HIM - Orchestrator", "SDL - Orchestrator", "BDG - Orchestrator", "HME - Orchestrator" and "MCR - Orchestrator";
    - "MDL - Model Master" for "MDL - Model Testing".
  - [ ] Sessions are given by id only; no step matches on a title.
  - [ ] `set-owner` refuses a session id that does not exist in the project's profile, including an id from another profile, and changes nothing.
  - [ ] No pin changes: "HME - Orchestrator" stays pinned, and the other five stay unpinned. "HME - Llama-bored" stays pinned and is not a main chat.
  - [ ] Ended owner sessions are accepted as main chats.
  - [ ] Each change appends its project, previous value and new value to an undo file under backups. The undo puts back the previous values (`set-owner <project> <previous>` or `--clear`), which clears the six pointers and changes nothing else.
  - [ ] In the Webapp, tapping each of the six projects opens the expected chat (`pcu-18`).
- **Out of scope** — a user interface for choosing the main chat; main chats for other profiles.

## Optional

- Notes: the choice of chats is brief Q3; a different answer changes only the list above. The undo file holds real session ids and stays outside git.
