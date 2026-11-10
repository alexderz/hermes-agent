# Story — Spot mail on the phone

- Id: `sm-08-mail-on-phone`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` § "Hermes Mobile", J7
- Person: Alex

## Required

- **As** Alex, watching sessions from Hermes Mobile
- **I want** every mail to show which session (or script) sent it, that it is not from me, and whether a reply is expected, in its first line
- **So that** I never mistake mail for something I typed, and know at a glance whether an answer is coming
- **Done when**
  - [ ] With today's app and no app change, a steered mail shows as its own bubble at the point it landed, after the turn it joined ends (within about 30 seconds), and its first visible line is the 📨 header line 1.
  - [ ] A queued or started mail shows as a bubble whose first visible line is the 📨 header line 1, followed by that turn's answer.
  - [ ] Header line 1 names the sender and reads "not Alex" and one of "reply expected", "no reply needed", "reply optional", in words.
  - [ ] The sender's transcript shows the `session_message` tool row with the target and the result.
  - [ ] Nothing about mail relies on colour.
- **Out of scope** — app changes (badges, a sender chip, live mail rows); an upstream issue for the app in this chunk (SM-Q11).
