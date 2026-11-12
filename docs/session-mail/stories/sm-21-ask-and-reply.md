# Story — Ask and wait for one explicit reply

- Id: `sm-21-ask-and-reply`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` (J12; SM-Q16 a)
- Person: a session that needs an answer before it can go on; the target

## Required

- **As a** session that cannot continue without an answer
- **I want** `intercom(action="ask", …)` to deliver my question and wait for the target's explicit `reply`
- **So that** I get exactly one answer in my own tool call, as intercom does today
- **Done when**
  - [ ] `ask` takes the same addresses and `delivery` as `send`, and keeps intercom's `timeout` (default 600 seconds, at most 3,600).
  - [ ] The tool description says to use `ask` only when this turn cannot continue without the answer, and otherwise `send` with `reply: waiting` (whose call returns at once).
  - [ ] The delivered message's line 1 says `waiting on your reply (ask)`, and its footer tells the target to answer once with `intercom(action="reply", to="<asker>", request_id="<id>", message="…")`, that its final answer is not sent, and to say so in the reply if it cannot answer, and that if it has nothing to add it replies once with `message="[SILENT]"`.
  - [ ] A `reply` whose message is `[SILENT]` returns to the asker at once with the sentence `"<title>" replied that it has nothing to add.`, and the record shows the reply as silent.
  - [ ] The asker's call returns the reply; only the asked peer's reply is accepted, as in intercom.
  - [ ] No automatic reply is sent for an `ask`, even if the target's turn has a `[REPLY <id>]` block.
  - [ ] On timeout the asker gets intercom's timeout result, and the record shows "no reply recorded".
  - [ ] Intercom's own `ask`/`reply` tests still pass.
- **Out of scope** — an `ask` answered by an automatic reply (SM-Q16 b); an `ask` that survives the asker's process exiting.
