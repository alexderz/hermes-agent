# Story — Alex keeps control of message turns

- Id: `sm-10-alex-keeps-control`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` (J6, J8, F9, F11)
- Person: Alex

## Required

- **As** Alex
- **I want** to steer or stop any turn a message started or joined, wherever it runs, and to keep my draft when a message arrives while I type
- **So that** sessions talking to each other never take a session away from me
- **Done when**
  - [ ] A turn started by a message runs where the session is hosted (a terminal, a Webapp or desktop chat, a Telegram topic), all in the gateway owner, or, when cold, in the session the gateway reopened; Alex can steer and stop it there as with any turn (from the Webapp on his phone).
  - [ ] A turn Alex stops, or one that fails, sends no reply and wakes no one, and `status` shows `no reply recorded` (the reply hook does not run for it; Trial Q9).
  - [ ] When a message starts a turn while Alex is typing in that session, his draft is unchanged, and his send follows his client's busy rule.
  - [ ] A message with `steer` or `queue` never redirects his running turn. One with `interrupt` does, says so in its first line ("interrupt"), and Alex can stop or steer the new turn.
- **Out of scope** — approval gates or holds (settled: none); notifications.

## Optional

- Notes: stopping is the only way Alex ends a debate early, since nothing is capped.
