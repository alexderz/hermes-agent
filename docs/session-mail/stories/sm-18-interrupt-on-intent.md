# Story — Interrupt work that is wrong, with a clean fallback

- Id: `sm-18-interrupt-on-intent`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` (J8, J9)
- Person: a sender that knows the target's current work is wrong or obsolete; the target; Alex

## Required

- **As a** sender who knows another session is doing work that is now wrong
- **I want** `delivery="interrupt"` to stop that work and run my message now, and, where the host cannot interrupt, to get the next strongest delivery and be told so
- **So that** wrong work stops as soon as possible, and I never believe I stopped something I did not
- **Done when**
  - [ ] Into a running turn on a host that can redirect, the turn is redirected and the message runs now; where it can only stop hard, the turn is stopped and the message is the next turn. Receipt: `interrupted`, whose sentence says "redirected … runs now" for a redirect, and "stopped … runs as that session's next turn" for a hard interrupt.
  - [ ] The delivered message's line 1 says `interrupt`, and line 3 tells the target its previous work was stopped at a peer's request and that it decides whether to go back to it.
  - [ ] Where interrupt is not possible now (the session is compacting, or it is a classic CLI on a Hermes build without the seam), `steer` is applied, else `queue`; the receipt says "asked: interrupt", and the header has no `interrupt` label.
  - [ ] Alex sees the surface's usual redirect: a classic CLI prints "↪ Redirected current turn" or "⚡ New message detected, interrupting…"; the dashboard, desktop and phone show the stopped answer, the message, then the new answer.
  - [ ] Nothing is retried after a fallback.
- **Out of scope** — interrupting a turn the sender's own session is running (own-session messages are refused).
