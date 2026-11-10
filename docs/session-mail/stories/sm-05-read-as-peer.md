# Story — Read mail as a peer's request

- Id: `sm-05-read-as-peer`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` § "Header", § "Footer"
- Person: a target session (the model)

## Required

- **As a** session receiving mail
- **I want** each mail to say, before anything else, who wrote it, that it is not the user, whether an answer is wanted, and how to answer
- **So that** I weigh it as a peer's request, never as the user's instruction or approval, and answer the right way
- **Done when**
  - [ ] Every mail, on all three paths (steered, queued, started), opens with the two header lines in `ux.md`, word for word: line 1 starts `📨 Mail (not Alex) ·` followed by the reply label (`reply expected`, `no reply needed` or `reply optional`), then the sender label (`session "<title>"`, `session <id> (untitled)` or `script "<label>"`) and the id; line 2 is the session variant, or the script variant for CLI senders.
  - [ ] A reply's line 1 starts `📨 Reply (not Alex) · reply optional ·` and names the mail it answers (`answers your mail <id>`).
  - [ ] Every mail ends with the footer in `ux.md`, with the right variant for script senders, cron/oneshot/subagent senders and "no reply needed", and its last line is `📨 End of mail <id>`.
  - [ ] The body between them is exactly what was sent, apart from relabelled lookalike lines.
  - [ ] In a row Hermes joined (a mail with Alex's steer or queued text, or two mails), each mail sits between its own header and closing line, and the text outside those lines is left exactly as it was (checked in HLD PoC Q2).
  - [ ] No mail text starts with `Message from`.
  - [ ] A body line that imitates a 📨 header, a `📨 End of mail` closing line, or a Hermes control frame (for example `[/OUT-OF-BAND USER MESSAGE]`) arrives relabelled, so it cannot fake a second mail or close the steer wrapper (HLD B2).
- **Out of scope** — a separate steer frame for mail (SM-Q7 C); a system-prompt section about mail.

## Optional

- Notes: whether real models obey this framing inside Hermes' "message from the user" steer wrapper is the brief's open point, and the trigger for reopening SM-Q7 C.
