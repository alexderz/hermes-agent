# Story — The answer to a send goes back by itself

- Id: `sm-06-automatic-reply`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` (J1, footer)
- Person: a sender session, and the target session

## Required

- **As a** session that sent another session a question with `send`
- **I want** the target's answer to come back to me as a message, steered into my turn (or starting one), without anyone calling a tool
- **So that** I can delegate a question and act on the answer when it arrives
- **Done when**
  - [ ] When a turn that received a `send` with `reply: requested` or `waiting` ends, the content of its `[REPLY <id>] … [/REPLY]` block goes to that message's sender as a new message whose line 1 starts `📡 Not Alex · reply optional ·` and names `reply to your message <id>`.
  - [ ] A `reply: none` note never sends anything back: no block is captured and there is no whole-answer fallback.
  - [ ] A reply (`reply optional`) is answered only from an explicit `[REPLY <id>]` block, never from the whole answer, and its footer says so in line 1 ("Only a [REPLY <id>] … [/REPLY] block is sent back …; nothing else is"), with no line saying the final answer goes back.
  - [ ] For a `requested` or `waiting` message with no block, the whole final answer is sent, except to a sender in a shared chat: then nothing is sent, and the record says `stored (shared chat, no [REPLY] block)`.
  - [ ] Two messages with two blocks in one turn: each block goes to its own sender, nothing else to either.
  - [ ] For a message that has its own block, only that block is mailed; a `[SILENT]` block sends nothing, even in a turn that also answers Alex.
  - [ ] Footer line 2 tells the model to always write the block when the turn also answers Alex or other work.
  - [ ] A sender acting on a reply ends the exchange simply by writing no block while it reports to Alex (J1 step 6); nothing goes back.
  - [ ] The reply is delivered with the default `steer` by the gateway owner (which reopens the sender's session if it is not open), and the record links it to the message it answers.
  - [ ] Messages sent with `ask` get no automatic reply (sm-21).
  - [ ] Ending the target's turn does not wait for the reply to be delivered.
- **Out of scope** — replies by calling `send` (SM-Q8 option 3); redelivering a reply lost in a restart.
