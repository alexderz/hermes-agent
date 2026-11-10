# Story — The answer to a send goes back by itself

- Id: `sm-06-automatic-reply`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` (J1, footer)
- Person: a sender session, and the target session

## Required

- **As a** session that sent another session a question with `send`
- **I want** the target's answer to come back to me as a message, steered into my turn (or starting one), without anyone calling a tool
- **So that** I can delegate a question and act on the answer when it arrives
- **Done when**
  - [ ] When a turn that received a `send` ends, the content of its `[REPLY <id>] … [/REPLY]` block goes to that message's sender as a new message whose line 1 starts `📡 Not Alex · reply optional ·` and names `reply to your message <id>`.
  - [ ] With no block for that message, the whole final answer is sent.
  - [ ] Two messages with two blocks in one turn: each block goes to its own sender, nothing else to either.
  - [ ] For a message that has its own block, only that block is mailed; a `[SILENT]` block sends nothing, even in a turn that also answers Alex.
  - [ ] Footer line 2 tells the model to always write the block when the turn also answers Alex or other work.
  - [ ] A sender acting on a reply can end the exchange with `[REPLY <reply id>][SILENT][/REPLY]` while reporting to Alex (J1 step 6).
  - [ ] The reply is delivered with the default `steer` by the sender's host (or wakes it), and the record links it to the message it answers.
  - [ ] Messages sent with `ask` get no automatic reply (sm-21).
  - [ ] Ending the target's turn does not wait for the reply to be delivered.
- **Out of scope** — replies by calling `send` (SM-Q8 option 3); redelivering a reply lost in a restart.
