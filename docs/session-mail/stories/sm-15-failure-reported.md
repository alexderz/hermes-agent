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
  - [ ] Mail sent while the dashboard cannot be reached, or whose resume fails before the steer or submit call is sent, returns `error` (not reachable) with "Not delivered"; the CLI exits 5.
  - [ ] A send whose steer or submit call was sent and got no answer (a restart, or a timeout) returns `error` (delivery unknown) with the wording in `ux.md`, which points to `status`; the CLI exits 6.
  - [ ] After such a send, `status` says whether the mail is in the target's transcript, so the sender can decide to send again or not without guessing.
  - [ ] Any other dashboard error returns `error` with that error's code and text.
  - [ ] Each failure is recorded in the outbox with result `error` and the code.
  - [ ] A reply whose delivery fails is recorded on the reply mail with result `error` and its code, and nothing retries it.
  - [ ] Nothing is retried, held or redelivered later, and no target session changes.
- **Out of scope** — retries, backoff, give-up timers, redelivery after a restart (settled).
