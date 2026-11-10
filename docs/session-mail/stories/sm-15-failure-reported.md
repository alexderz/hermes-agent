# Story — A failed delivery is reported at once

- Id: `sm-15-failure-reported`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` (F2, F3)
- Person: a sender (session, cron job or script)

## Required

- **As a** sender whose mail cannot be delivered
- **I want** to be told at once that nothing was delivered, or that delivery is unknown, and why
- **So that** I can decide myself whether to send again, instead of trusting a hidden retry
- **Done when**
  - [ ] Mail to a session held by a command-line process returns `error` (`SESSION_NOT_OWNED`) with the wording in `ux.md`; the CLI exits 4.
  - [ ] Mail sent while the dashboard cannot be reached returns `error` (not reachable) with "Not delivered"; the CLI exits 5.
  - [ ] A send where the dashboard stops answering after the connection was made (a restart, or a call that timed out) returns `error` (delivery unknown) with the wording "Delivery of mail <id> is unknown … check status before you send it again"; the CLI exits 6.
  - [ ] Any other dashboard error returns `error` with that error's code and text.
  - [ ] Each failure is recorded in the outbox with result `error` and the code.
  - [ ] A reply whose delivery fails is recorded on the reply mail with result `error` and its code, and nothing retries it.
  - [ ] Nothing is retried, held or redelivered later, and no target session changes.
- **Out of scope** — retries, backoff, give-up timers, redelivery after a restart (settled).
