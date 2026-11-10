# Story — Refuse an unclear address, with candidates

- Id: `sm-03-refused-address`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` (F1, F2)
- Person: a session, a cron job or script

## Required

- **As a** sender who gave an address that matches several sessions, or none
- **I want** nothing to be sent, and to be shown the sessions I probably meant
- **So that** a message never lands in the wrong session, and I can send again correctly in one step
- **Done when**
  - [ ] An address that matches more than one session sends nothing and returns `refused` (ambiguous), listing every match with title, id, host and last activity.
  - [ ] An address that matches nothing sends nothing and returns `refused` (unknown), listing the closest project addresses, titles and endpoint names, or saying none is close.
  - [ ] A message to the sender's own session returns `refused` ("you cannot message your own session"); another session in the same process is not refused.
  - [ ] The CLI prints the same text to standard error and exits 3.
  - [ ] No target session gets a row, a turn or a steer.
- **Out of scope** — guessing the best match and sending to it.
