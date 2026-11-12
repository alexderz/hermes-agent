# Story — A failed or unknown delivery is reported at once

- Id: `sm-15-failure-reported`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` (F3–F7)
- Person: a sender (session, cron job or script)

## Required

- **As a** sender whose message cannot be delivered, or whose delivery is uncertain
- **I want** to be told at once, and why
- **So that** I can decide myself whether to send again, instead of trusting a hidden retry
- **Done when**
  - [ ] Without `plugins.entries.intercom.allow_gateway_injection: true`, every delivery returns `error` (`injection-off`) with the wording in `ux.md`; nothing is queued; the CLI exits 4.
  - [ ] An owner refusal returns `error` (`refused-by-owner`, with the owner's code); the CLI exits 4.
  - [ ] `no-owner` (the gateway is not running), `owner-restarting` and `not-reachable` (the connection was lost before the hand-over) each return "Not delivered" with the wording in `ux.md`; the CLI exits 5. Intercom never starts a gateway itself.
  - [ ] A message to a chat held by the admin dashboard returns `error` (`not-addressable`): `"<title>" is open in the admin dashboard, which intercom cannot reach. Nothing was sent.`; the CLI exits 4.
  - [ ] A message handed over with no answer returns `error` (delivery unknown), with the wording in `ux.md`, which points to `status`; the CLI exits 6. After it, `status` shows the owner's admission (`admitted: queued / started / finished` or `not admitted`) or, for a steered message, whether its header is in the target's transcript, as in `ux.md`.
  - [ ] A reply whose delivery fails is recorded on the reply message with its error, and `log` shows it on the original message's line.
  - [ ] Each failure is recorded with its result and reason; nothing is retried, held or redelivered later, and no target session changes.
- **Out of scope** — retries, backoff, give-up timers, redelivery (settled).
