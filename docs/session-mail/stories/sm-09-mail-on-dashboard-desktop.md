# Story — Spot a message in the dashboard and the desktop app

- Id: `sm-09-mail-on-dashboard-desktop`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` § "Web dashboard and desktop app"
- Person: Alex

## Required

- **As** Alex, at the web dashboard chat or the desktop app
- **I want** a message to read the same as on the phone: a user row that starts with the 📡 header (or, in a joined row, shows the header and the closing line)
- **So that** I can tell a message from my own words on every surface, with nothing new to learn
- **Done when**
  - [ ] In the dashboard chat, a message row that was not joined has the 📡 header as its first line, in every mode, at least after a transcript reload.
  - [ ] In the desktop app, a message row that was not joined is a user bubble whose first line is the 📡 header, without the steer wrapper.
  - [ ] A queued message shows once with the O17 fix; without it, twice (identical rows), with one reply.
  - [ ] On both, a joined row shows the header and `📡 End of message <id>`.
  - [ ] The desktop does not fold the answer after a message under "Replied to …" (the header never starts with `Message from`).
  - [ ] No page, tab or badge is added, and no desktop or dashboard UI code changes.
- **Out of scope** — a Mail tab; the Bot Mode notice look (U1).
