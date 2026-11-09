# Story — Project page with the main chat on top

- Id: `pcu-03-project-page`
- HLD / UX: `docs/project-centric-ui/hld.md`, `docs/project-centric-ui/ux.md`
- Person: Alex

## Required

- **As** Alex
- **I want** a page for each project that shows its main chat first and then its other chats, newest first
- **So that** I can see everything I have going on in a project and jump into any of it
- **Done when**
  - [ ] Each project page has its own address (Spec picks it), and it shows, in order:
    - a back link and the project name;
    - the primary folder in muted text;
    - the **Main chat** card;
    - **New chat here**;
    - the chats list.
  - [ ] The Main chat card shows the chat's title, a "Main chat" text label and last activity. Clicking it resumes that chat.
  - [ ] The chats list holds exactly the sessions `GET /api/profiles/projects/tree` assigns to the project (minus the main chat), newest first. Each row shows its title or preview and time ago.
  - [ ] Clicking a row opens `/chat?resume=<id>`. Browser Back returns to the project page at the same scroll position, and a bookmark to the project page opens it directly.
  - [ ] A chat from a profile other than the one in use shows that profile's name as a text label; opening it is `pcu-15`.
  - [ ] Long lists show the most recent chats and a **Show more** button.
  - [ ] Rows have no delete, rename, export or bulk actions.
  - [ ] While loading, the page shows a spinner with "Loading project…".
  - [ ] If the request fails, the page shows the dashboard's load-error notice with **Retry**, and the back link to Projects still works.
  - [ ] A link to a project that was deleted or archived shows "This project isn't available any more. It may have been archived or deleted." with a link back to Projects, and no error code.
- **Out of scope** — search or filters on the project page; session management (it stays on Sessions); running state and message counts on rows (`ux.md`, Not this).

## Optional

- Notes: rows reuse the compact look of the Chat page's session switcher. The number shown before **Show more** is open question U6.
