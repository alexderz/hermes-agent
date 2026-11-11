# Story — Deliver now, by the target's host, in the mode asked for

- Id: `sm-04-deliver-now`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` (J4–J6)
- Person: a sender, and Alex watching the target

## Required

- **As a** sender
- **I want** my message to land right away, delivered by whichever Hermes process has the target open, in the mode I asked for or the strongest weaker one it supports
- **So that** the target sees it now, on whatever surface it lives, and its work is only stopped when I meant it
- **Done when**
  - [ ] With no `delivery`, a message into a running turn is `steered`: the turn carries on, and the transcript has a user row where it landed, starting with the 📡 header and ending with `📡 End of message <id>` (the header is the row's first line unless Hermes joined it with other text; `ux.md` F10).
  - [ ] A steer the host refuses (for example while compacting) is `queued`, runs after the current turn, and the receipt says "asked: steer".
  - [ ] An idle target starts a turn in every mode, on its own host (a terminal, a dashboard chat, a Telegram topic).
  - [ ] A target that is live nowhere is woken in the dashboard and returns `started`; the turn runs where Hermes Mobile can open it. Its receipt names the dashboard: `"<title>" was not open anywhere that could take it, so message <id> started a turn in the dashboard.`
  - [ ] Only `delivery="interrupt"` ever stops or redirects a running turn.
  - [ ] Each message is delivered once, by the process named in the target's lease (or by the gateway for an idle gateway session).
  - [ ] A message is delivered at once whether or not Alex is active in the target (no hold), and never as `display_kind: "hidden"`.
- **Out of scope** — holding messages while Alex types; a background delivery worker; redelivery.
