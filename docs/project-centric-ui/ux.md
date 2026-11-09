# UX — project-centric Hermes UI

High-level. How it feels and who does what, not pixels. **designer.**
Human gate: operator accepts, or writes `UX verification not required`.

- Slug: `project-centric-ui` (DER-686)
- Brief: [`brief.md`](brief.md) (refined, round 2; review in [`brief-refine.md`](brief-refine.md))
- HLD: [`hld.md`](hld.md) (architect)
- Comparables: [`comparables.md`](comparables.md) (architect)
- Stories: [`stories/`](stories/)
- Date: `2026-11-08`
- Agent review (requirements only): agreed `2026-11-08` (round 5, including the steer-from-phone additions; `reviews/ux-review-r1..r5.md`)
- Operator: pending

This design assumes the brief's recommended answers to Alex's open questions, and the HLD's decision where it departs from them:
- **Q1.** No server or terminal-UI `/new` guard. The Hermes Mobile issue asks the app to compact the main chat on `/new`, the same way it treats Bot Chat.
- **Q2.** The five "<Project> — Orchestrator" chats and "Model Master" are the main chats.
- **Q3.** The HLD chose a bundled dashboard plugin tab instead of the brief's core page. It sits directly after **Sessions** in the navigation (`after:sessions`), which is the same place a core page would take, so Alex sees no difference in the navigation.
- **Q4.** Owner-chat turns started by Alex's scripts run inside the dashboard process. The kickoff becomes a `hermes` command of the Projects plugin (HLD part 6) that sends the turn through the dashboard's chat socket, instead of a separate command-line run. Switching the kickoff unit to that command is Alex's tooling. The phone and the dashboard chat then join the same live turn. Hermes Mobile issue 1 also gets a "working elsewhere" ask for the case where a command-line run still holds the chat. (Brief Intent 5, refined in `brief-refine.md` round 3; HLD part 6.)

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
1. Alex opens the dashboard and picks **Projects** in the side navigation, directly after Sessions.
2. He sees his six projects, each showing its colour and name, when it was last active, how many chats it has, and the name of its main chat.
3. He clicks **Open main chat** on the "Hermes Improvement" card. The Chat page opens on "Hermes Improvement — Orchestrator", resumed where he left off.

That is two clicks from anywhere in the dashboard on a laptop. On a phone it is three taps (the menu, **Projects**, **Open main chat**), or one tap after a home-screen bookmark to the Projects list.

**J2. Alex looks at everything in a project.**
1. On the Projects list, Alex clicks the "Budgeting" card itself, not its button.
2. The project page opens:
   - the project's name;
   - the **Main chat** card on top, with its title, last activity and an **Open** button;
   - a **New chat here** button;
   - the project's other chats, newest first.
3. He taps an older chat and it opens in Chat. Browser Back brings him back to the project page.

**J3. Alex starts a side chat in a project.**
1. On the project page, Alex taps **New chat here**.
2. Chat opens a fresh chat whose working folder is the project's primary folder. Because of that folder, Hermes loads the project's context files.
3. The new chat shows up in that project's list, not under "Home" and not under a stray folder name.
4. Side effect in slice 1: **New chat here** works by setting the Chat page's remembered folder for new chats (the same setting as the folder picker on the Chat page). The next fresh chat Alex starts from Chat itself also starts in that project's folder, until he picks another folder there. The picker shows the folder, so this is visible, not hidden. A cleaner link that leaves the setting alone is an HLD open item (`/chat?cwd=`).

**J4. Alex does J1–J3 on his phone browser.** Same steps, one column, thumb-sized targets (see "Dashboard on a phone browser"). **Projects** is in the dashboard's narrow-screen menu, so a home-screen bookmark to the Projects list is the shortest path.

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
The page shows the project's name, an empty-state line ("No chats in this project yet."), and **New chat here** as the main button. If a declared project has no folder, **New chat here** is disabled and the reason is written beside it: "Add a folder to this project to start chats here." No screen in slice 1 edits folders, so the text names Hermes Mobile's Projects screen as the place to do it. Home is not a project and never shows this line (F8).

**F4. Server too old for the main-chat field.**
- *Dashboard:* the page ships in the same build as the server change, so a dashboard with the page always gets the field. The page still treats a missing field the same as "no main chat" (F1), never as an error.
- *Hermes Mobile against an unpatched server* (upstream Hermes without the fork's change): the project screen shows its chats and **New chat**, with no Main chat card and no message about upgrading. That is how the drafted issue asks the app to behave.

**F5. Phone app without the feature (today's build).**
- Nothing in Hermes Mobile changes. The extra field is ignored, the Projects screen still opens the edit sheet, and History still shows the "hermes" group until the maintainer fixes it.
- Alex gets the project view on his phone through the dashboard in the phone browser (J4), for example from a home-screen bookmark to the Projects page. The installable web app is deferred.

**F6. Loading and errors on the dashboard pages.**
- *Projects list:* while loading, a spinner with "Loading projects…". If the request fails, the dashboard's standard load-error notice with **Retry**; the rest of the dashboard keeps working. If only some profiles fail, the projects that loaded, plus a one-line note naming the profiles it could not read.
- *Project page:* while loading, a spinner with "Loading project…". If the request fails, the same load-error notice with **Retry**, and the back link to Projects still works.
- *Project not found:* a bookmarked or stale link to a project that was deleted or archived shows "This project isn't available any more. It may have been archived or deleted." with a link back to Projects. No error code.

**F7. Family member with no projects opens Projects.**
- The page shows the empty state: "No projects yet. Projects group chats that work in the same folder. All your chats are on the Sessions page." The line links to Sessions.
- The dashboard still opens on Sessions as it does today, so nobody who ignores projects is affected.

**F8. Home and auto-found folders.**
- *Home* (chats with no project folder) opens a page with its chats, newest first. It has no Main chat card and no **New chat here** button. In their place is one line: "These chats have no project folder. To start one, use New chat on the Chat page." with a link to Chat.
- *Auto-found folders* (folders Hermes grouped on its own) open a page like a project's, without a Main chat card. **New chat here** starts in that folder.

**J6. Alex steers a working main chat from his phone.**
This works on today's Hermes Mobile build once the kickoff runs through the dashboard (Q4); no app change is needed.
1. A scripted kickoff has started a long turn in "Hermes Improvement — Orchestrator". Alex opens that chat on Hermes Mobile, from History or from the project screen once it exists.
2. The chat shows the transcript so far and the agent's reply streaming in, with the app's usual working indicator. It does not show a refusal or a "New conversation" offer.
3. He types a message. The app's **While the agent is working** setting decides what happens, as in any busy chat:
   - **Correct current turn** (the app's default);
   - **Queue next turn**;
   - **Guide at next safe point**;
   - **Hard interrupt, then send**.

   `/queue` and `/btw` work as usual.
4. He taps the app's stop control. The turn stops, and the chat is idle and ready for his next message.
5. When the turn ends on its own, the kickoff command finishes and the chat simply goes idle on the phone.

**J7. Alex steers the same working main chat from the dashboard.**
This holds for main chats in the dashboard's own profile, which covers all six of Alex's. For another profile's working main chat, see F9.
1. On the laptop or phone browser, Alex taps **Open main chat** on the project card.
2. Chat opens the session and joins the same live turn the phone sees: the reply keeps streaming in the terminal.
3. He uses the terminal UI's own controls: `/queue <text>` queues the next turn, `/steer <text>` guides at the next tool call, and the interrupt key stops the turn. **Plain typing interrupts by default:** a plain message sent while the turn works stops that turn and sends the message, because the terminal UI's busy-input setting defaults to interrupt. To keep the turn running, Alex uses `/queue` or `/steer`. This differs from the phone, whose default corrects the running turn (U11).
4. The phone and the dashboard show the same turn at the same time; a stop from either ends it for both.

There is no new dashboard screen. The Projects pages still show no running state (U7), so Alex learns the main chat is working when he opens it.

**F10. The main chat is held by a command-line run anyway.**
This happens when Alex, or an old script, starts a command-line run on the main chat (`hermes chat -q` or the interactive command line). That process holds the chat until it finishes, which can be hours.
- *Today, on Hermes Mobile:* the chat looks idle. When Alex sends, the message moves to a recovery card: "This chat is open in another window. Start a new conversation with this message?", with **Discard** and **New conversation**. He cannot queue, steer or stop, and "New conversation" would leave the main chat behind.
- *Today, on the dashboard:* the chat opens and shows the transcript up to the last saved message, but sending is refused with the same "open in another window" message.
- *What issue 1 asks of Hermes Mobile:*
  - in the chat, a "Working in another window" state, as History already shows for chats active elsewhere, in words, not colour alone;
  - on a refused send, keep the message and offer **Send when it finishes** first, then **Discard**, with **New conversation** last;
  - **Send when it finishes** sends the message once the other run lets the chat go.

  It does not ask for queueing into, steering or stopping the other run: on today's server only a turn in the dashboard process can be steered.
- *The fix for Alex's own use* is that owner-chat kickoffs run through the dashboard (Q4), so F10 should only happen for ad-hoc command-line use.

**F11. A main-chat turn is cut off.**
A turn running in the dashboard process dies if the dashboard restarts, and the kickoff command exits with a failure if its connection drops. It does not reconnect, and the failure shows in the kickoff unit's status.
- *Planned restarts wait.* A deploy does not restart the dashboard while a main-chat turn is running. The operator waits for it to finish, or asks Alex whether to stop it (HLD "Restarts and owner turns", rule 1). Restarts stay announced.
- *Long turn* (started more than 15 minutes ago, the usual case for a kickoff): after an unplanned restart or a dropped kickoff, the phone and the dashboard show the chat idle, with the transcript up to the last saved message. Alex re-runs the kickoff with a "continue" prompt.
- *Short turn* (started less than 15 minutes ago): the turn may resume on its own, with a recovery note, the next time the phone, the dashboard or a kickoff re-run reopens the chat. This happens at most twice. So Alex may find the chat working again rather than idle.

**F9. Opening a chat that belongs to another profile.**
The project tree merges all profiles, so a project's main chat or one of its rows can belong to a profile other than the one the dashboard is using. Chat resumes in the current profile.
- The row, or the Main chat card, shows that profile's name as a small text label.
- *A working main chat in another profile:* the dashboard's chat for another profile does not join the dashboard's own live turn. Under F9 (a), opening one while it works is refused like F10 ("open in another window"); Alex can still steer it from the phone if the phone is connected to that profile. Spec settles this with the HLD's Profiles open item (U9). None of Alex's six main chats is in another profile.
- Opening it must land in that chat with its history, never in an empty or different chat. This depends on the HLD's "Profiles" open item; Spec settles the link.
- Spec picks one of two behaviours (U9):
  - **(a) Switch and open.** The dashboard switches to the chat's profile, then opens the chat. **The switch persists.** Until Alex switches back, the dashboard manages that profile: new chats from Chat, config, keys, skills and model all apply to it. The dashboard's profile banner shows this whenever the chosen profile is not the dashboard's own.
  - **(b) Explain and stop.** The tap shows a plain line, "This chat is in the <profile> profile. Switch profile to open it.", and opens nothing. The profile never changes.
- Either way, **New chat here** always starts in the project's own profile, whatever profile the dashboard was left on. It uses the same profile handling as opening a chat, so it needs no HLD part beyond the Profiles open item. If Spec finds otherwise, this becomes a known side effect listed beside U8.

## Stories

| Id | Story |
|---|---|
| [`pcu-01-project-list`](stories/pcu-01-project-list.md) | Alex sees his projects on the dashboard, each with its main chat named |
| [`pcu-02-open-main-chat`](stories/pcu-02-open-main-chat.md) | Alex opens a project's main chat with one tap on its card in the Projects list |
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
| [`pcu-15-other-profile-chat`](stories/pcu-15-other-profile-chat.md) | Opening a project chat that belongs to another profile lands in that chat |
| [`pcu-16-steer-working-main-chat`](stories/pcu-16-steer-working-main-chat.md) | Alex opens a working main chat on the phone or dashboard and can queue, steer or stop it |
| [`pcu-17-mobile-working-elsewhere`](stories/pcu-17-mobile-working-elsewhere.md) | Hermes Mobile says a chat is working elsewhere and offers to send when it finishes (issue 1) |

## High-level UX

All dashboard screens use the dashboard's existing components and theme: list items, cards, badges, buttons, the spinner and the load-error notice from `@nous-research/ui`. They are not a new look. Status is always a word, such as "Main chat", "No main chat" and "Main chat missing"; any colour only reinforces it. A project's colour appears only as a small dot beside its name, never as the only thing that identifies it.

### Dashboard on a laptop

**Navigation.** A **Projects** entry sits directly after **Sessions** in the side navigation, with a folder-style icon. It is a bundled plugin tab (HLD), placed with `after:sessions`. The dashboard still opens on Sessions (see open question U2).

**Projects list.** It has its own address, so a bookmark opens it directly; the address is Spec's.
- A single column of project cards, most recently active first. The project tree already returns them in that order.
- Each card shows:
  - the colour dot and project name;
  - "Main chat: <title>" (or "No main chat" / "Main chat missing");
  - "<n> chats · active <time ago>";
  - one button: **Open main chat** (or **Open project** when there is none).
- Clicking anywhere else on the card opens the project page.
- Below Alex's projects, in a quieter section headed "Other chats":
  - folders Hermes found on its own that are not declared projects (auto projects);
  - **Home**: chats with no project folder.

  These rows open the same project page, without a Main chat card (F8).
- Cards are not edited here. Editing projects stays in Hermes Mobile and the desktop app in slice 1.

**Project page.** Each project page has its own address, so browser Back and bookmarks return to it; the address is Spec's. From top to bottom:
1. A back link to "Projects", then the colour dot, the project name and its primary folder in small muted text.
2. **Main chat card.** It is visually heavier than the rows below: the chat's title, a "Main chat" label, last activity and an **Open** button. Clicking the card or the button resumes the chat (`/chat?resume=<id>`).
3. **New chat here.** A secondary button that opens Chat on a fresh chat in the project's primary folder. It also leaves the Chat page's folder picker set to that folder for later new chats (J3, step 4).
4. **Chats.** The project's other chats, newest first, as the same compact rows the Chat page's session switcher uses: title or first-message preview, and time ago. Clicking a row resumes that chat. Rows have no bulk actions, delete or rename: those stay on the Sessions page. When a project has many chats, the list shows the most recent ones and a **Show more** button (the count is for the mockups).
5. If chats come from more than one profile, each row (and the Main chat card) from a profile other than the one in use shows that profile's name as a small text label. Opening one follows F9.

Going to Chat is an ordinary page navigation. Browser Back returns to the project page with its scroll position kept.

### Dashboard on a phone browser

- The same two screens and order, in one column. The dashboard's existing narrow-screen navigation drawer holds the **Projects** entry.
- **Projects list:** full-width cards. The **Open main chat** button spans the card's width at the bottom, so it is an easy thumb target. Tapping the card's upper part opens the project page.
- **Project page:** the Main chat card fills the width and its **Open** button is full width. **New chat here** is a full-width button directly under it, not a floating button, so it never covers the chat list or competes with the terminal's own keyboard once in Chat. Chats rows are at least the platform's minimum touch height.
- There is no horizontal scrolling. Long titles shorten with an ellipsis and the time stays visible.
- To get back from Chat to the project, Alex uses the browser's Back gesture.
- Reaching a main chat takes three taps from any page (menu, **Projects**, **Open main chat**), or one tap from a home-screen bookmark to the Projects list.

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
- **A working main chat (works today, no app change).** Because owner-chat turns run in the dashboard process (Q4), opening one shows the live reply and the usual working indicator. The existing busy-send setting (Correct, Queue, Guide, Hard interrupt), `/queue`, `/btw` and the stop control act on the running turn (J6).
- **Working elsewhere (issue 1 ask).** When a command-line run holds a chat, the chat says "Working in another window", in words. A refused send keeps the message and offers **Send when it finishes**, then **Discard**, then **New conversation** (F10). Today's card offers only **Discard** and **New conversation**.

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
- No **Live** (running) badge on the dashboard's Projects pages in slice 1. The project tree the page reads carries no running state (open question U7).
- No message counts on dashboard rows or the Main chat card; the tree gives counts per project, not per chat beyond its few preview rows.
- No `/chat?cwd=` link in slice 1; **New chat here** uses the Chat page's remembered folder (J3, step 4; HLD open item).
- No new dashboard screen or control for working chats; the embedded terminal UI's `/queue`, `/steer` and interrupt are the controls (J7).
- No queueing into, steering or stopping a turn held by a separate command-line process, and no "take over" button. On today's server that needs a core change that the later upstream version replaces (brief, refine round 3).
- No early move to the later upstream version (v0.23.0) for this.
- No mockups in this document. They come at Spec, with variants.
- No Hermes Mobile code, and no issues posted. Drafts are for Alex.

## Accessibility notes

- Every status has a text label: "Main chat", "No main chat", "Main chat missing", and on Hermes Mobile the running state. Colour only reinforces it. The project colour dot is decorative; the name carries identity.
- Cards and rows are keyboard-focusable. Enter opens the card's main action, and buttons inside a card are separate tab stops.
- Touch targets on the phone are at least 44 by 44 pixels.
- The empty, missing, not-found and error lines are plain sentences with no ids, paths or codes.

## Open questions

Places where a different answer from Alex changes what the user sees:

1. **Q1, the `/new` guard.**
   - If Alex wants a guard on the dashboard too, `/new` in a main chat on the dashboard would compact and show the explanatory line, as the app does.
   - If he wants no guard anywhere, the sentence leaves drafted issue 1, `pcu-12` is dropped, and `/new` in the main chat starts a separate chat on every surface.
2. **Q2, which chat is main.** A different pick changes the "Main chat" shown on that project's card and page, for example "Llama-bored" for Home Eng instead of "Home Eng — Orchestrator".
3. **Q3, core page or plugin tab.** The HLD chose a plugin tab placed directly after Sessions. Alex sees the same navigation entry in the same place either way, and the same screens. Any remaining difference, such as the page addresses, is Spec's.
4. **U1, what a click on a project does.**
   - The design: the card body opens the project page, and its button opens the main chat directly.
   - The alternative: the whole card opens the main chat at once, and the project page is reached by a smaller "All chats" link.

   The second is one tap fewer for Alex but hides the chat list. This is the main variant to mock up at Spec.
5. **U2, landing page.** Should the dashboard open on Projects instead of Sessions? It would help Alex on the phone browser, but would change the first screen for family members and for upstream users. The design keeps Sessions.
6. **U3, wording.** Is the on-screen label "Main chat", "Owner chat" or "Orchestrator"?
7. **U4, "Other chats" section.** Should auto-found folders and Home show on the Projects list, or only Alex's declared projects? Hiding them is cleaner but makes those chats reachable only from Sessions.
8. **U5, a missing main chat.** Should the dashboard still try to open the chat it points to, which works if the chat is only archived, rather than showing the "isn't here" line? That needs the HLD to confirm whether an archived chat can be resumed.
9. **U6, phone list length.** How many chats show before **Show more** (for the Spec mockups).
10. **U7, Live badge.** Slice 1 shows no running state on the Projects pages, so a working main chat (J7) looks the same as an idle one until opened. If Alex wants it, the HLD must add a read of the sessions list (which carries `is_active`), and the cards, Main chat card and rows gain the **Live** badge (colour plus the word).
    - **U11, typing in a working dashboard chat.** Should Alex set the terminal UI's busy-input setting (`display.busy_input_mode`) to queue or steer, so that plain typing in a working main chat no longer stops it (J7)? This is his config choice and needs no code. The design keeps the default (interrupt) and points to `/queue` and `/steer`.
11. **U8, New chat here side effect.** If Alex minds that **New chat here** also changes the Chat page's remembered folder (J3, step 4), the HLD's `/chat?cwd=` deep link removes it, at the cost of one small core edit.
12. **U9, chats in another profile.** Spec picks F9 (a), which switches the dashboard's profile (and the switch persists), or F9 (b), which explains and opens nothing. This depends on the HLD's Profiles open item. Either way, a working main chat in another profile cannot be steered from the dashboard in slice 1 (F9); Spec decides what the tap says.
13. **Q4, how the main chat becomes steerable.**
    - If Alex prefers moving to the later upstream version first (option C), J6 and J7 wait for that move.
    - If he wants the app change only (option D), J6 and J7 do not happen on today's server. F10 becomes the normal case for scripted owner turns: "Working in another window" plus **Send when it finishes**, with no steering.
14. **U10, wording of the working-elsewhere state.** Is it "Working in another window" (matching the app's current "open in another window"), or "Busy in a terminal run"? The first is plainer for family members; the second is more exact for Alex.
