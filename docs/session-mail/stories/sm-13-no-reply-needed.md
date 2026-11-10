# Story — Send a note that needs no reply

- Id: `sm-13-no-reply-needed`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` (J3; open question U2)
- Person: a sender (session, cron job or script); the target session

## Required

- **As a** sender with a status note or an FYI
- **I want** to mark it "no reply needed"
- **So that** the target stays silent unless something is wrong, and Alex can see that no answer is coming
- **Done when**
  - [ ] `session_message(..., expect_reply=false)` and `send --no-reply` put `no reply needed` in header line 1.
  - [ ] The footer's third line becomes: `No reply is needed. Answer [SILENT] unless something here is wrong, blocks you, or needs a question back.`
  - [ ] The tool result for such a send ends with `No answer was asked for.`
  - [ ] If the target answers anyway with something that is not silent, that answer goes back by the usual reply rule (it is not dropped).
- **Out of scope** — blocking replies to such notes.

## Optional

- Notes: this flag is beyond the brief's smallest slice. If Alex rejects U2, this story is dropped.
