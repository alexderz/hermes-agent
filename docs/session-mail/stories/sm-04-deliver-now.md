# Story — Deliver now, without disturbing work

- Id: `sm-04-deliver-now`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` (J4–J6)
- Person: a sender, and Alex watching the target

## Required

- **As a** sender
- **I want** my mail to land right away: steered into a running turn, queued behind it if a steer is refused, or started as a turn if the session is idle or not loaded
- **So that** the target sees it now, while its work and Alex's work carry on untouched
- **Done when**
  - [ ] Mail into a running turn returns `steered`, and the target's transcript has a separate user row, at the point it landed, whose mail starts with the 📨 header and ends with `📨 End of mail <id>` (the header is the row's first line unless Hermes joined the steer with other text; `ux.md` F8).
  - [ ] Mail into a busy session that refuses the steer (for example, while it compacts) returns `queued`, and runs as the next turn after the current one ends.
  - [ ] Mail into an idle session, loaded or not, returns `started`, and the turn runs in the dashboard, where Hermes Mobile can open it.
  - [ ] No delivery cancels, interrupts or redirects a running turn, Alex's or an agent's.
  - [ ] Mail is delivered at once whether or not Alex is active in the target (no hold).
  - [ ] No mail is stored with `display_kind: "hidden"`.
- **Out of scope** — holding mail while Alex types; ordering or rate rules beyond the order Hermes already keeps; a background delivery worker.
