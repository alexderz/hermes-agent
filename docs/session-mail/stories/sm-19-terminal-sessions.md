# Story — See a message arrive in a terminal session

- Id: `sm-19-terminal-sessions`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` § "Terminal sessions", J10
- Person: Alex at a classic CLI or Ink TUI; the session in it

## Required

- **As** Alex, working in `hermes chat` or the Ink TUI
- **I want** a message to my terminal session to be delivered by that terminal, and to see it arrive the way my own typed input would
- **So that** sessions can reach me where I actually work, and I can tell at once what arrived and what it did to my turn
- **Done when**
  - [ ] A message to a session open in a classic CLI is delivered by that CLI's process, in the requested mode or the strongest weaker one.
  - [ ] The classic CLI prints its existing notice with the first 80 characters of the message, which start `📡 Not Alex · …`: `⏩ Steered: '…'` for a steer; `Queued for the next turn: …` for a queue; `↪ Redirected current turn: '…'` or `⚡ New message detected, interrupting...` for an interrupt; for an idle prompt, the message in the scrollback and a turn starts.
  - [ ] A `steer` into a running CLI turn does not interrupt it (today's injection would).
  - [ ] In the Ink TUI, the message appears as a user row starting with the 📡 header, delivered by the TUI's own backend.
  - [ ] At an idle classic CLI prompt with half-typed input, the message starts its turn and the half-typed text survives in the prompt (Trial-backed).
  - [ ] Half-typed input or a composer draft is never touched; Ctrl+C, typing and `/steer` work as with any turn.
  - [ ] A message to a session open in a terminal that has not run a turn yet takes the dashboard wake path (HLD O18): the receipt says `started`, and the turn runs in the dashboard, as `ux.md` F13 describes.
- **Out of scope** — new terminal notices or colours; delivering into a terminal before its first turn (O18, accepted for v1).

## Optional

- Notes: whether the Ink TUI shows a note for a steer or queue it did not type is checked in the Trial.
