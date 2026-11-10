# Story — Spot mail in the dashboard and the desktop app

- Id: `sm-09-mail-on-dashboard-desktop`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` § "Web dashboard", § "Desktop app"
- Person: Alex

## Required

- **As** Alex, at the web dashboard chat or the desktop app
- **I want** mail to read the same as on the phone: a user row that starts with the 📨 header (or, in a row Hermes joined with other text, shows the header and the closing line)
- **So that** I can tell mail from my own words on every surface, with nothing new to learn
- **Done when**
  - [ ] In the dashboard's terminal chat, a mail row that Hermes did not join with other text has the 📨 header as its first line, on the paths steered, queued and started, at least after a transcript reload.
  - [ ] In the desktop app, a mail row that was not joined is a user bubble whose first line is the 📨 header, and the steer wrapper is not shown.
  - [ ] On both surfaces, a joined row shows the mail's header and `📨 End of mail <id>` line, so the mail's start and end are visible (ux.md F8).
  - [ ] The desktop does not fold the answer that follows a mail row under "Replied to …" (the header never starts with `Message from`).
  - [ ] No dashboard page, tab or badge is added, and no desktop or terminal UI code is changed.
- **Out of scope** — a Mail tab; the desktop's Bot Mode notice look (open question U1).

## Optional

- Notes: whether the terminal chat shows mail live while the session is open is checked in the Trial.
