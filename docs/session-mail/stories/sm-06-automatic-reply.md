# Story — The answer goes back by itself

- Id: `sm-06-automatic-reply`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` (J1, footer)
- Person: a sender session, and the target session

## Required

- **As a** session that asked another session something
- **I want** the target's answer to come back to me as mail, delivered by the same steer → queue → start rule, without anyone calling a tool
- **So that** I can delegate a question and act on the answer when it arrives
- **Done when**
  - [ ] When a turn that received a mail ends, the content of its `[REPLY <id>] … [/REPLY]` block is delivered to that mail's sender as a new mail whose line 1 starts `📨 Reply (not Alex)` and names the mail it answers.
  - [ ] With no block for that mail, the whole final answer is sent.
  - [ ] A turn that received two mails with two blocks sends each block to its own sender, and nothing else to either.
  - [ ] When the mail was steered into Alex's turn, only the block (if present) is sent, not his whole answer.
  - [ ] In a turn that holds both Alex's message and a mail, a block containing `[SILENT]` sends nothing, and no text outside a block is ever mailed when a block is present.
  - [ ] The footer's second line tells the model to always write the block when the turn also answers Alex or other work, as written in `ux.md`.
  - [ ] A sender acting on a reply can end the exchange with `[REPLY <reply id>][SILENT][/REPLY]` while its answer reports to Alex (J1 step 6).
  - [ ] The reply is delivered steered, queued or started, like any mail, and the outbox links it to the mail it answers.
  - [ ] Ending the target's turn does not wait for the reply to be delivered.
- **Out of scope** — replies from the target calling `session_message` (SM-Q8 option 3); redelivering a reply lost in a restart.

## Optional

- Notes: built on SM-Q8 option 2. Other answers change this story (`ux.md`, Open questions).
