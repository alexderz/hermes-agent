# Story — Interrupt work that is wrong, with a clean fallback

- Id: `sm-18-interrupt-on-intent`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` (J8, J9)
- Person: a sender that knows the target's current work is wrong or obsolete; the target; Alex

## Required

- **As a** sender who knows another session is doing work that is now wrong
- **I want** `delivery="interrupt"` to stop that work and run my message now, and, where the owner cannot redirect, to have the turn stopped hard instead, and be told which
- **So that** wrong work stops as soon as possible, and I never believe I stopped something I did not
- **Done when**
  - [ ] Into a running turn, the owner redirects it and the message runs now (`interrupted`, `redirect`). If the owner refuses the redirect, it stops the turn hard and the message runs as the next turn (`interrupted`, `hard-interrupt`), with the receipt sentence "… stopped the running turn …; it runs as that session's next turn".
  - [ ] The delivered message's line 1 says `interrupt asked` (the request; the frame is built before the owner reports what it applied), and line 3 says: "The sender asked to interrupt. If your previous work in this session was stopped for this message, decide yourself whether to go back to it."
  - [ ] An interrupt never falls back to steer or queue; the header still says `interrupt asked`, and its conditional line 3 stays true after a redirect or a hard interrupt.
  - [ ] Alex sees the usual redirect in the Webapp and desktop: the stopped answer, the message row, then the new answer. What a classic CLI prints is checked in the E2E.
  - [ ] Nothing is retried after a fallback.
- **Out of scope** — interrupting a turn the sender's own session is running (own-session messages are refused).
