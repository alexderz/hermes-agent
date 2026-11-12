# Story — Spot a message in the desktop app; admin-dashboard chats are not addressable

- Id: `sm-09-mail-on-dashboard-desktop`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` § "Desktop app, and chats in the admin dashboard"
- Person: Alex

## Required

- **As** Alex, at the desktop app or the Webapp on a computer
- **I want** a message to read the same as on the phone: a user row that starts with the 📡 header (or, in a joined row, shows the header and the closing line)
- **So that** I can tell a message from my own words on every surface, with nothing new to learn
- **Done when**
  - [ ] In the desktop app (and the Webapp at desktop width), a message row that was not joined is a user card whose first line is the 📡 header, without the steer wrapper.
  - [ ] A queued message shows once.
  - [ ] A joined row shows the header and `📡 End of message <id>`.
  - [ ] The chat view does not fold the answer after a message under "Replied to …" (the header never starts with `Message from`).
  - [ ] A message to a chat held by the admin dashboard (`hermes dashboard`) is refused with `not-addressable` and the wording in `ux.md`; nothing appears there.
  - [ ] No page, tab or badge is added, and no desktop or Webapp UI code changes.
- **Out of scope** — a Mail tab; the Bot Mode notice look (U1); reaching admin-dashboard chats.
