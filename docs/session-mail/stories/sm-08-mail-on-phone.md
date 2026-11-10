# Story — Spot mail on the phone

- Id: `sm-08-mail-on-phone`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` § "Hermes Mobile", J7
- Person: Alex

## Required

- **As** Alex, watching sessions from Hermes Mobile
- **I want** every mail to show which session (or script) sent it, that it is not from me, and whether a reply is expected, in the first words of the mail
- **So that** I never mistake mail for something I typed, and know at a glance whether an answer is coming
- **Done when**
  - [ ] With today's app and no app change, a steered mail that Hermes did not join with other text shows as its own bubble at the point it landed, after the turn it joined ends (within about 30 seconds), and the bubble's first wrapped line reads `📨 Mail (not Alex) · reply expected` (or the matching reply label).
  - [ ] A queued or started mail that was not joined with other text shows as a bubble with the same first wrapped line, followed by that turn's answer.
  - [ ] In a bubble Hermes joined with Alex's own steer or queued text, the 📨 header and the `📨 End of mail <id>` line are both visible and show where the mail starts and ends (ux.md F8).
  - [ ] Header line 1 reads "not Alex", one of "reply expected", "no reply needed", "reply optional", and the sender, in words.
  - [ ] The sender's transcript shows the `session_message` tool row with the target and the result.
  - [ ] Nothing about mail relies on colour.
- **Out of scope** — app changes (badges, a sender chip, live mail rows); an upstream issue for the app in this chunk (SM-Q11).
