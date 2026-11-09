# UX — project-centric Hermes UI

High-level. How it feels and who does what, not pixels. **designer.**
Human gate: operator accepts, or writes `UX verification not required`.

- Slug: `project-centric-ui` (DER-686)
- Brief: [`brief.md`](brief.md) (refined, round 2; review in [`brief-refine.md`](brief-refine.md))
- HLD: [`hld.md`](hld.md) (architect, written in parallel)
- Comparables: [`comparables.md`](comparables.md) (architect, written in parallel)
- Stories: [`stories/`](stories/)
- Date: `2026-11-08`
- Agent review (requirements only): pending
- Operator: pending

This design assumes the brief's recommended answers to Alex's open questions:
- **Q1.** No server or terminal-UI `/new` guard. The Hermes Mobile issue asks the app to compact the main chat on `/new`, the same way it treats Bot Chat.
- **Q2.** The five "<Project> — Orchestrator" chats and "Model Master" are the main chats.
- **Q3.** The dashboard Projects page is a core page, listed next to Sessions.

"Open questions" at the end lists every place where a different answer changes what the user sees.

**Words used on screen.** The data field is `owner_session_id`. Screens call it the **Main chat**, which is Alex's own wording ("the project's main chat") and needs no explanation for family members. This document says "main chat" from here on.

## People

| Person | Where they are | What they need | What they will not tolerate |
|---|---|---|---|
| **Alex** (owner, daily user) | Hermes Mobile on Android first. The web dashboard in a phone browser second, and on a laptop. | Each project as the front door: one tap to its long-lived main chat, a glance at its other chats, and new chats that land in the right folder. | Extra taps on the phone. Chats grouped under names he never created, such as "hermes". Losing track of a main chat. |
| **Family members** (occasional users) | Mostly a chat app or Hermes Mobile; sometimes the dashboard in a phone browser. Usually no projects of their own. | Things they already know stay where they are. | Technical words, error codes, or a new screen they have to understand before they can chat. |

## Journeys

### Happy paths

**J1. Alex opens a project's main chat from his laptop.**
1. Alex opens the dashboard and picks **Projects** in the side navigation, next to Sessions.
2. He sees his six projects, each showing its colour and name, when it was last active, how many chats it has, and the name of its main chat.
3. He clicks **Open main chat** on the "Hermes Improvement" card. The Chat page opens on "Hermes Improvement — Orchestrator", resumed where he left off.

That is two clicks from anywhere in the dashboard.

**J2. Alex looks at everything in a project.**
1. On the Projects list, Alex clicks the "Budgeting" card itself, not its button.
2. The project page opens:
   - the project's name;
   - the **Main chat** card on top, with its title, last activity, a **Live** label if a turn is running, and an **Open** button;
   - a **New chat here** button;
   - the project's other chats, newest first.
3. He taps an older chat and it opens in Chat. Browser Back brings him back to the project page.

**J3. Alex starts a side chat in a project.**
1. On the project page, Alex taps **New chat here**.
2. Chat opens a fresh chat whose working folder is the project's primary folder. Because of that folder, Hermes loads the project's context files.
3. The new chat shows up in that project's list, not under "Home" and not under a stray folder name.

**J4. Alex does J1–J3 on his phone browser.** Same steps, one column, thumb-sized targets (see "Dashboard on a phone browser").

**J5. Alex on Hermes Mobile, once the maintainer ships the drafted issue.**
1. Alex taps **Projects**, then a project card.
2. The project screen opens: the main chat on top, then the project's chats. Settings move behind an **Edit** action.
3. He taps the main chat and lands in it, the way tapping a bot opens its Bot Chat.
4. If he types `/new` in the main chat, the app compacts it instead of starting over. It tells him so and points to **New chat** for a separate chat.

### Important failures and edge cases

**F1. Project with no main chat yet.**
The project page shows no Main chat card. **New chat here** moves to the top, and the chats list follows. There is no error and no "set one up" prompt: slice 1 has no button for that. On the Projects list the card shows "No main chat". Its **Open main chat** button is replaced by **Open project**, so the card's one button never opens nothing.

**F2. Main chat deleted or archived.**
The project's data still names a main chat, but that chat is no longer among the project's chats (the project tree leaves out archived chats).
- The page looks like F1, plus one quiet line where the Main chat card would be: "This project's main chat isn't here. It may have been archived or deleted." This is plain text, not a warning colour.
- The line links to the Sessions page, where archived chats can be found and restored.
- Once the chat is restored, the Main chat card comes back on its own, because the pointer never changed.
- The Projects list card shows "Main chat missing" in text, so Alex notices it at a glance.

**F3. Project with no chats.**
The page shows the project's name, an empty-state line ("No chats in this project yet."), and **New chat here** as the main button. If the project has no folder, **New chat here** is disabled and the reason is written beside it: "Add a folder to this project to start chats here." No screen in slice 1 edits folders, so the text names Hermes Mobile's Projects screen as the place to do it.

**F4. Server too old for the main-chat field.**
- *Dashboard:* the page ships in the same build as the server change, so a dashboard with the page always gets the field. The page still treats a missing field the same as "no main chat" (F1), never as an error.
- *Hermes Mobile against an unpatched server* (upstream Hermes without the fork's change): the project screen shows its chats and **New chat**, with no Main chat card and no message about upgrading. That is how the drafted issue asks the app to behave.

**F5. Phone app without the feature (today's build).**
- Nothing in Hermes Mobile changes. The extra field is ignored, the Projects screen still opens the edit sheet, and History still shows the "hermes" group until the maintainer fixes it.
- Alex gets the project view on his phone through the dashboard in the phone browser (J4), for example from a home-screen bookmark to the Projects page. The installable web app is deferred.

**F6. Loading and errors on the dashboard page.**
- While loading, the list area shows a spinner with "Loading projects…".
- If the request fails, the page shows the dashboard's standard load-error notice with **Retry**. The rest of the dashboard keeps working.
- If only some profiles fail to load, the page shows the projects it has, plus a one-line note naming the profiles it could not read.

**F7. Family member with no projects opens Projects.**
- The page shows the empty state: "No projects yet. Projects group chats that work in the same folder. All your chats are on the Sessions page." The line links to Sessions.
- The dashboard still opens on Sessions as it does today, so nobody who ignores projects is affected.

## Stories

| Id | Story |
|---|---|
| [`pcu-01-project-list`](stories/pcu-01-project-list.md) | Alex sees his projects on the dashboard, each with its main chat named |
| [`pcu-02-open-main-chat`](stories/pcu-02-open-main-chat.md) | Alex opens a project's main chat in one tap from the Projects list |
| [`pcu-03-project-page`](stories/pcu-03-project-page.md) | Alex sees a project's chats on one page, main chat on top |
| [`pcu-04-new-chat-here`](stories/pcu-04-new-chat-here.md) | Alex starts a new chat that runs in the project's primary folder |
| [`pcu-05-no-main-chat`](stories/pcu-05-no-main-chat.md) | A project with no main chat, or a missing one, still works and says so plainly |
| [`pcu-06-empty-project`](stories/pcu-06-empty-project.md) | A project with no chats invites the first one |
| [`pcu-07-phone-browser`](stories/pcu-07-phone-browser.md) | The whole Projects flow works in a phone browser |
| [`pcu-08-main-chats-seeded`](stories/pcu-08-main-chats-seeded.md) | Alex's six projects each know their main chat, set once and undoable |
| [`pcu-09-old-app-unchanged`](stories/pcu-09-old-app-unchanged.md) | Today's Hermes Mobile keeps working against the updated server |
| [`pcu-10-family-unaffected`](stories/pcu-10-family-unaffected.md) | Family members who ignore projects see nothing new in their way |
| [`pcu-11-mobile-project-screen`](stories/pcu-11-mobile-project-screen.md) | Hermes Mobile project screen with the main chat on top (drafted issue 1) |
| [`pcu-12-mobile-main-chat-compacts`](stories/pcu-12-mobile-main-chat-compacts.md) | `/new` in the main chat compacts on Hermes Mobile (one sentence in issue 1) |
| [`pcu-13-mobile-history-home-group`](stories/pcu-13-mobile-history-home-group.md) | History stops showing a "hermes" group (drafted issue 2) |
| [`pcu-14-mobile-new-chat-primary-folder`](stories/pcu-14-mobile-new-chat-primary-folder.md) | New project chats on Hermes Mobile start in the primary folder (drafted issue 2) |

## High-level UX

All dashboard screens use the dashboard's existing components and theme: list items, cards, badges, buttons, the spinner and the load-error notice from `@nous-research/ui`. They are not a new look. Status always pairs colour with a word: the existing green **Live** badge, and text labels such as "Main chat", "No main chat" and "Main chat missing". A project's colour appears only as a small dot beside its name, never as the only thing that identifies it.

### Dashboard on a laptop

**Navigation.** A **Projects** entry sits directly above **Sessions** in the side navigation, with a folder-style icon. The dashboard still opens on Sessions (see open question U2).

**Projects list (`/projects`).**
- A single column of project cards, most recently active first. The project tree already returns them in that order.
- Each card shows:
  - the colour dot and project name;
  - "Main chat: <title>" (or "No main chat" / "Main chat missing");
  - "<n> chats · active <time ago>";
  - a **Live** badge if any of its chats is running a turn now;
  - one button: **Open main chat** (or **Open project** when there is none).
- Clicking anywhere else on the card opens the project page.
- Below Alex's projects, in a quieter section headed "Other chats":
  - folders Hermes found on its own that are not declared projects (auto projects);
  - **Home**: chats with no project folder.

  These rows open the same project page, without a Main chat card.
- Cards are not edited here. Editing projects stays in Hermes Mobile and the desktop app in slice 1.

**Project page (`/projects/<id>`).** From top to bottom:
1. A back link to "Projects", then the colour dot, the project name and its primary folder in small muted text.
2. **Main chat card.** It is visually heavier than the rows below: the chat's title, a "Main chat" label, last activity, message count, the **Live** badge when running, and an **Open** button. Clicking the card or the button resumes the chat (`/chat?resume=<id>`).
3. **New chat here.** A secondary button that opens Chat on a fresh chat in the project's primary folder.
4. **Chats.** The project's other chats, newest first, as the same compact rows the Chat page's session switcher uses: title or first-message preview, time ago, and the **Live** badge. Clicking a row resumes that chat. Rows have no bulk actions, delete or rename: those stay on the Sessions page. When a project has many chats, the list shows the most recent ones and a **Show more** button (the count is for the mockups).
5. If chats come from more than one profile, each row from a profile other than the one in use shows that profile's name as a small text label.

Going to Chat is an ordinary page navigation. Browser Back returns to the project page with its scroll position kept.

### Dashboard on a phone browser

- The same two screens and order, in one column. The dashboard's existing narrow-screen navigation drawer holds the **Projects** entry.
- **Projects list:** full-width cards. The **Open main chat** button spans the card's width at the bottom, so it is an easy thumb target. Tapping the card's upper part opens the project page.
- **Project page:** the Main chat card fills the width and its **Open** button is full width. **New chat here** is a full-width button directly under it, not a floating button, so it never covers the chat list or competes with the terminal's own keyboard once in Chat. Chats rows are at least the platform's minimum touch height.
- There is no horizontal scrolling. Long titles shorten with an ellipsis and the time stays visible.
- To get back from Chat to the project, Alex uses the browser's Back gesture.

### Hermes Mobile, once the maintainer ships the drafted issues

This is what the drafted issues ask for. We write no app code; the maintainer decides the final look within the app's Material design.

- **Projects screen.** Tapping a project card opens a new **project screen** instead of the edit sheet. Edit, archive and delete move behind an **Edit** action (a pencil icon in the project screen's top bar, and the card's existing overflow menu).
- **Project screen:**
  - the top bar shows the project name and **Edit**;
  - first comes a **Main chat** card, read from `owner_session_id` in `projects.list`, with the chat's title, last activity and a running indicator paired with a label. Tapping it opens the chat exactly as tapping a bot opens its Bot Chat;
  - next, the project's chats, newest first, as History rows;
  - a **New chat** floating action button starts a chat in the project's **primary** folder.
- **Main chat behaviour.** Typing `/new` in a project's main chat compacts it and shows one line: "This is <project>'s main chat — compacting instead. For a separate chat, use New chat on the project." This reuses the app's Bot Chat path, keyed on the chat's id instead of its title.
- **No main chat, or an unpatched server.** The Main chat card is absent and the rest works (F1, F4).
- **History.** Chats whose working folder is the home directory are grouped as **Home**, not "hermes" (drafted issue 2).

## Comparables (look and flow)

The full write-up is the architect's [`comparables.md`](comparables.md). For look and flow:

| Product / screen | Steal | Reject |
|---|---|---|
| **Claude Projects** (project page) | The project page as a hub: name on top, a clear "start a chat in this project", then the project's chats by recency. | The project knowledge and instructions panel. Project context already comes from folder files, and per-project settings are out of scope. |
| **ChatGPT Projects** (sidebar folders plus project page) | Projects as a first-class navigation entry, not a filter on History. A new chat started from the project lands in the project with no extra step. | A message composer on the project page itself. Chat stays the embedded terminal UI, so a second composer would be a second chat surface, which `web/AGENTS.md` forbids. Also no "Move to project" action: in Hermes, a chat belongs to a project because of its folder. |
| **Hermes Mobile Bots roster → Bot Chat** | One tap on the card opens the long-lived canonical chat; `/new` there compacts with an explanatory line. This is the model for the main chat. | Identity by exact title. The main chat is a pointer, so renames such as "Model Master" stay. |
| **Hermes desktop app sidebar** (project tree with sessions) | The same project grouping and labels the backend already computes, so all surfaces agree on which chat belongs where. | A dense expandable tree in a narrow rail. It does not suit a phone; a list leading to a page does. |

## Not this

- No chat transcript or composer in React. Every "open" goes to the embedded terminal UI with `/chat?resume=<id>`.
- No "Make main chat" button, project creation, folder editing or project settings on the dashboard.
- No `/new` guard in the dashboard's chat or the terminal UI.
- No "Home" main chat. Home stays a plain bucket of folder-less chats.
- No project grouping or filter added to the dashboard's Sessions page.
- No installable web app (manifest or service worker), and no change to the dashboard's landing page.
- No mockups in this document. They come at Spec, with variants.
- No Hermes Mobile code, and no issues posted. Drafts are for Alex.

## Accessibility notes

- Every status has a text label: "Main chat", "Live", "No main chat", "Main chat missing". Colour only reinforces it. The project colour dot is decorative; the name carries identity.
- Cards and rows are keyboard-focusable. Enter opens the card's main action, and buttons inside a card are separate tab stops.
- Touch targets on the phone are at least 44 by 44 pixels.
- The empty, missing and error lines are plain sentences with no codes.

## Open questions

Places where a different answer from Alex changes what the user sees:

1. **Q1, the `/new` guard.**
   - If Alex wants a guard on the dashboard too, `/new` in a main chat on the dashboard would compact and show the explanatory line, as the app does.
   - If he wants no guard anywhere, the sentence leaves drafted issue 1, `pcu-12` is dropped, and `/new` in the main chat starts a separate chat on every surface.
2. **Q2, which chat is main.** A different pick changes the "Main chat" shown on that project's card and page, for example "Llama-bored" for Home Eng instead of "Home Eng — Orchestrator".
3. **Q3, core page or plugin tab.** As a plugin tab, Projects appears among the plugin tabs (Kanban, Usage) further down the navigation instead of beside Sessions, and its address changes. The screens are otherwise the same.
4. **U1, what a click on a project does.**
   - The design: the card body opens the project page, and its button opens the main chat directly.
   - The alternative: the whole card opens the main chat at once, and the project page is reached by a smaller "All chats" link.

   The second is one tap fewer for Alex but hides the chat list. This is the main variant to mock up at Spec.
5. **U2, landing page.** Should the dashboard open on Projects instead of Sessions? It would help Alex on the phone browser, but would change the first screen for family members and for upstream users. The design keeps Sessions.
6. **U3, wording.** Is the on-screen label "Main chat", "Owner chat" or "Orchestrator"?
7. **U4, "Other chats" section.** Should auto-found folders and Home show on the Projects list, or only Alex's declared projects? Hiding them is cleaner but makes those chats reachable only from Sessions.
8. **U5, a missing main chat.** Should the dashboard still try to open the chat it points to, which works if the chat is only archived, rather than showing the "isn't here" line? That needs the HLD to confirm whether an archived chat can be resumed.
9. **U6, phone list length.** How many chats show before **Show more** (for the Spec mockups).
