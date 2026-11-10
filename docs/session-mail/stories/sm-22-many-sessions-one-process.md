# Story — Two sessions in one process message each other

- Id: `sm-22-many-sessions-one-process`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` (F2)
- Person: two dashboard chats (or desktop windows) in one dashboard process; Alex

## Required

- **As a** session in the dashboard, where many sessions share one process
- **I want** to message another session in the same process, and have it reach that session only
- **So that** owner sessions, all hosted by the one dashboard, can talk to each other at all, and a message never lands in a session it was not for
- **Done when**
  - [ ] Chat A messages chat B in the same dashboard process: it is delivered to B, in the requested mode, and appears in B's transcript only.
  - [ ] No message is drained into whichever turn runs next in that process (intercom's process-wide `pre_llm_call` drain is not used where the seam exists).
  - [ ] A message to the sender's own session is refused; one to a different session in the same process is not.
  - [ ] After B runs `/compress`, A's message reaches B's compression tip.
- **Out of scope** — messaging across profiles.
