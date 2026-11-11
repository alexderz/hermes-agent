# Story — Spot a message on the phone

- Id: `sm-08-mail-on-phone`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` § "The Webapp in a phone browser", J7
- Person: Alex

## Required

- **As** Alex, watching sessions from the Webapp in my phone's browser
- **I want** every message to say, in its first words, that it is not from me and whether a reply is expected, then who sent it
- **So that** I never mistake a message for something I typed, and know at a glance whether an answer is coming
- **Done when**
  - [ ] In the Webapp's chat view on a phone-width screen (narrower than 768 px), a steered message that Hermes did not join with other text shows as its own user row where it landed, and the row's first wrapped line reads `📡 Not Alex · reply expected` (or the matching label), at least after a transcript reload.
  - [ ] A queued or started message that was not joined shows the same first wrapped line, followed by that turn's answer. A queued one shows once.
  - [ ] A message sent with interrupt has a first line that reads `📡 Not Alex · interrupt asked · …`; after a redirect it follows the stopped answer.
  - [ ] In a row joined with Alex's own steer or queued text, the 📡 header and `📡 End of message <id>` are both visible.
  - [ ] The sender's chat shows the `intercom` tool row with the target and the receipt.
  - [ ] Nothing relies on colour.
- **Out of scope** — Webapp UI changes (SM-Q11); Hermes Mobile (SM-Q22).
