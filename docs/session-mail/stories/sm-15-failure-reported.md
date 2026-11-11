# Story — A failed or unknown delivery is reported at once

- Id: `sm-15-failure-reported`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` (F3–F7)
- Person: a sender (session, cron job or script)

## Required

- **As a** sender whose message cannot be delivered, or whose delivery is uncertain
- **I want** to be told at once, and why
- **So that** I can decide myself whether to send again, instead of trusting a hidden retry
- **Done when**
  - [ ] A dashboard, Ink TUI or gateway target open in a process without the seam (`no-seam`) is refused with the "cannot take messages for this kind of session" error; nothing is parked; the CLI exits 4. A classic CLI target in such a process still gets intercom's own delivery.
  - [ ] A dashboard, desktop, Ink TUI or gateway host without `allow_gateway_injection: true` returns `error` (`injection-off`) with the wording in `ux.md`; nothing is queued; the CLI exits 4.
  - [ ] A message to a chat held by the admin dashboard returns `error` (`not-addressable`): `"<title>" is open in the admin dashboard, which intercom cannot reach. Nothing was sent.`; the CLI exits 4.
  - [ ] A host that refuses (for example 4090 when the waking path finds the session just opened in a terminal) returns `error` with its reason; the CLI exits 4.
  - [ ] `no-dashboard` (live nowhere, no dashboard), `no-endpoint` (open in a process started before intercom was enabled), `no-gateway` (a platform chat with no gateway running; never woken in the dashboard instead) and `not-reachable` each return "Not delivered" with the wording in `ux.md`; the CLI exits 5.
  - [ ] A message handed over with no answer returns `error` (delivery unknown), with the wording in `ux.md`, which points to `status`; the CLI exits 6. After it, `status` says whether the message is in the target's transcript, and for a classic CLI or gateway target that is still busy, tells the sender to wait for its current turn to end before sending again.
  - [ ] A reply whose delivery fails is recorded on the reply message with its error, and `log` shows it on the original message's line.
  - [ ] Each failure is recorded with its result and reason; nothing is retried, held or redelivered later, and no target session changes.
- **Out of scope** — retries, backoff, give-up timers, redelivery (settled).
