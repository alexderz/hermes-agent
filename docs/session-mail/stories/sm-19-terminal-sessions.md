# Story — See a message arrive in a terminal session

- Id: `sm-19-terminal-sessions`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` § "Terminal sessions", J10
- Person: Alex at a classic CLI or Ink TUI; the session in it

## Required

- **As** Alex, working in `hermes chat` or the Ink TUI
- **I want** a message to my terminal session to be delivered by that terminal, and to see it arrive the way my own typed input would
- **So that** sessions can reach me where I actually work, and I can tell at once what arrived and what it did to my turn
- **Done when**
  - [ ] A message to a session open in a classic CLI or the Ink TUI is delivered by the gateway owner, which hosts it (the terminal is an owner client), in the requested mode or its fallback.
  - [ ] The message appears in the terminal's transcript as a user row starting with the 📡 header. Whether the classic CLI also prints its existing notices (`⏩ Steered`, `Queued for the next turn`, `↪ Redirected current turn`) for input another client delivered is checked in the E2E (`ux.md` "Still to check"); this story does not require them.
  - [ ] A `steer` into a running terminal turn does not interrupt it.
  - [ ] In the Ink TUI, the message appears as a user row starting with the 📡 header.
  - [ ] At an idle classic CLI prompt with half-typed input, the message starts its turn and the half-typed text survives in the prompt (Trial-backed).
  - [ ] Half-typed input or a composer draft is never touched; Ctrl+C, typing and `/steer` work as with any turn.
- **Out of scope** — new terminal notices or colours.

## Optional

- Notes: whether the Ink TUI shows a note for a steer or queue it did not type is checked in the Trial.
