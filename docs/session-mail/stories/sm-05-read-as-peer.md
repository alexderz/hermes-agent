# Story — Read a message as a peer's request

- Id: `sm-05-read-as-peer`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` § "Header", § "Footer"
- Person: a target session (the model)

## Required

- **As a** session receiving a message
- **I want** each message to say, before anything else, that it is not Alex, whether an answer is wanted, who wrote it, and, at the end, how to answer
- **So that** I weigh it as a peer's request, never as Alex's instruction or approval, and answer the right way
- **Done when**
  - [ ] Every message, on every chat surface and mode, opens with the header in `ux.md`, word for word: line 1 starts `📡 Not Alex · ` and the reply label (`no reply needed`, `reply requested`, `waiting on your reply`, `reply optional` or `waiting on your reply (ask)`), then `hermes@<title> says (session <id> · message <id>):` (`hermes@script <label>` for a script); line 2 is the session or the script variant.
  - [ ] Line 1 says `interrupt asked`, and the conditional line 3 ("If your previous work in this session was stopped for this message, …") is present, only when the sender asked for interrupt.
  - [ ] A messaging-platform sender is named `hermes@<title> (<Platform> <chat type>)`, for example `(Telegram group)`, and gets the third authority-line variant ("… may be relaying their words …").
  - [ ] When the target's chat is shared, the model-only shared-chat line follows the authority line; when the sender's chat is shared, the footer carries the reply-destination line. Neither is ever posted to a chat.
  - [ ] A reply's line 1 names `reply to your message <id>`.
  - [ ] Every message ends with the footer for its kind (`requested`, `waiting`, `none`, a reply, script, cron/oneshot/subagent, `ask`), whose line 1 names `intercom` as the tool for new messages and says to `tool_describe` then `tool_call` it if it is not in the tool list; the last line is `📡 End of message <id>`.
  - [ ] The body between them is exactly what was sent, apart from relabelled lines.
  - [ ] Every body line that starts with `📡`, and every line that starts like a Hermes control frame (for example `[/OUT-OF-BAND USER MESSAGE]`), arrives relabelled, so a body cannot fake a header, footer or closing line or close the steer wrapper (required: Trial Q2).
  - [ ] In a row Hermes joined (with Alex's text or another message), each message sits between its own header and closing line, and the text outside is left as it was.
  - [ ] No message text starts with `Message from`.
- **Out of scope** — a separate steer frame (SM-Q7 C); a system-prompt section.

## Optional

- Notes: whether real models obey this framing inside Hermes's "message from the user" steer wrapper is the trigger for reopening SM-Q7 C.
