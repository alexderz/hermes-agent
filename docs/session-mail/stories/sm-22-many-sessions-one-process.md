# Story — Two sessions in one gateway owner message each other

- Id: `sm-22-many-sessions-one-process`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` (F2)
- Person: two chats (for example two Webapp chats, or a Webapp chat and a terminal) in the profile's one gateway owner; Alex

## Required

- **As a** session in the gateway owner, where every chat of the profile shares one process
- **I want** to message another session in the same owner, and have it reach that session only
- **So that** owner sessions can talk to each other at all, and a message never lands in a session it was not for
- **Done when**
  - [ ] Chat A messages chat B in the same owner: it is delivered to B, in the requested mode, and appears in B's transcript only.
  - [ ] No message is drained into whichever turn runs next (intercom's process-wide `pre_llm_call` drain is not used with the owner client).
  - [ ] A message to the sender's own session is refused; one to a different session in the same owner is not.
  - [ ] After B runs `/compress`, A's message reaches B's compression tip.
- **Out of scope** — messaging across profiles.
