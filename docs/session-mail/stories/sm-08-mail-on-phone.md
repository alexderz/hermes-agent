# Story — Spot a message on the phone

- Id: `sm-08-mail-on-phone`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` § "Hermes Mobile", J7
- Person: Alex

## Required

- **As** Alex, watching sessions from Hermes Mobile
- **I want** every message to say, in its first words, that it is not from me and whether a reply is expected, then who sent it
- **So that** I never mistake a message for something I typed, and know at a glance whether an answer is coming
- **Done when**
  - [ ] With today's app, a steered message that Hermes did not join with other text shows as its own bubble where it landed, after the turn ends (within about 30 seconds), and the bubble's first wrapped line reads `📡 Not Alex · reply expected` (or the matching label).
  - [ ] A queued or started message that was not joined shows the same first wrapped line, followed by that turn's answer.
  - [ ] An interrupting message's first line reads `📡 Not Alex · interrupt · …`, after the stopped answer.
  - [ ] In a bubble joined with Alex's own steer or queued text, the 📡 header and `📡 End of message <id>` are both visible.
  - [ ] The sender's transcript shows the `intercom` tool row with the target and the receipt.
  - [ ] Nothing relies on colour.
- **Out of scope** — app changes (SM-Q11).
