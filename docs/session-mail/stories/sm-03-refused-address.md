# Story — Refuse an unclear address, with candidates

- Id: `sm-03-refused-address`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` (F1)
- Person: a session, a cron job or script

## Required

- **As a** sender who gave an address that matches several sessions, or none
- **I want** nothing to be sent, and to be shown the sessions I probably meant
- **So that** mail never lands in the wrong session, and I can send again correctly in one step
- **Done when**
  - [ ] An address that matches more than one session sends nothing and returns `refused` (ambiguous), listing every match with its exact title, id and last activity.
  - [ ] An address that matches nothing sends nothing and returns `refused` (unknown), listing the closest project addresses and titles, or saying that nothing is close.
  - [ ] The wording is the one in `ux.md` § "Tool results", and it tells the sender to send again with an exact title or id.
  - [ ] The CLI prints the same text and list to standard error and exits 3.
  - [ ] No target session gets a row, a turn or a steer.
- **Out of scope** — guessing the best match and sending to it; fuzzy matching as a way to deliver.
