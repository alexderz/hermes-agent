# Story — Main chat from the phone's home-screen Webapp

- Id: `pcu-21-phone-webapp`
- HLD / UX: `docs/project-centric-ui/hld.md`, `docs/project-centric-ui/ux.md` (J3)
- Person: Alex

## Required

- **As** Alex on my phone
- **I want** tapping a project in the Webapp's sidebar drawer to open its main chat where I can see it
- **So that** my main surface reaches a project's main chat in two taps
- **Done when**
  - [ ] In the Webapp installed to the phone's home screen, at a width below 640 pixels, tapping a project with a main chat in the drawer opens that chat.
  - [ ] The drawer then closes so the chat is visible (pending `ux.md` U1; if U1 is no, the chat opens behind the drawer instead).
  - [ ] From the home screen, reaching a main chat takes two taps: the menu, then the project.
  - [ ] Reopening the drawer shows the entered project with the **Main chat** row first, at the same touch size as other rows.
  - [ ] **Main chat** and its status words (`pcu-19`) are readable without hover.
  - [ ] After the deploy, closing and reopening the home-screen copy once shows the new behaviour: tapping a project opens its main chat. Before the reopen, the old behaviour stays, with no error (`ux.md` F9).
  - [ ] Nothing scrolls sideways at a 360-pixel-wide viewport.
- **Out of scope** — a service worker or offline mode; changing when the drawer closes for other rows.
