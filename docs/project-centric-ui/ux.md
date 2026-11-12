# UX — project-centric Hermes UI (v0.23 Webapp)

High-level. How it feels and who does what, not pixels. **designer.**
Human gate: operator accepts, or writes `UX verification not required`.

- Slug: `project-centric-ui` (DER-686)
- Brief: [`brief.md`](brief.md) (gather round 4, on the v0.23 base); review in [`brief-refine.md`](brief-refine.md) round 4 (pass)
- HLD: [`hld.md`](hld.md) (architect; v0.23 rewrite committed at a3404cae4d, clarifications at 3b4e3a2f9f)
- Comparables: [`comparables.md`](comparables.md) (architect)
- Stories: [`stories/`](stories/)
- Date: `2026-11-11`
- Agent review (requirements only): agreed `2026-11-11` (v0.23 rewrite, rounds 6-8; `reviews/ux-review-r6..r8.md`; earlier rounds covered the retired dashboard and Hermes Mobile design)
- Operator: pending

**What changed.** The base is Hermes v0.23, and Alex's surface is the gateway **Webapp**: the desktop app's interface served as a web app, in a laptop browser and installed to his phone's home screen. He no longer uses Hermes Mobile or the standalone dashboard. The earlier design (a dashboard Projects page, Hermes Mobile issue drafts, a kickoff command) is retired; its stories are marked "Retired (v0.23 move)".

**Assumptions.** This design follows the brief's recommended answers, as narrowed by the refiner:
- **Q1.** One small core change to the Webapp's Projects sidebar. Tapping a project that has an owner chat opens that chat and scopes the sidebar to the project. The project's list shows the owner chat first, marked **Main chat**, even when it is pinned. There is no separate Projects page and no row-badge plugin.
- **Q2.** `/new` and `/reset` in an owner chat compact it instead, in the Webapp only, with a notice like Bot Chat's. This ships only if Alex says yes. If he says no, `pcu-23` is dropped.
- **Q3.** The six owner chats are seeded by session id with a new `hermes project set-owner <project> <session-id>` command (`--clear` removes one), run once per project: the five "<CODE> - Orchestrator" chats and "MDL - Model Master". Each run appends the previous and new value to an undo file. Pins are left as they are.
- **Steering** a working owner chat comes from the v0.23 base: one gateway runs every turn, including command-line one-shots. Slice 1 builds nothing for it and checks it live (`pcu-22`).

**Words on screen.** The data field is `owner_session_id`. The screen calls it **Main chat**, Alex's own words, which also avoids the Webapp's existing "owner" wording for gateways. This document says "main chat".

## People

| Person | Where they are | What they need | What they will not tolerate |
|---|---|---|---|
| **Alex** (owner, daily user) | The Webapp, installed on his phone's home screen first, and in a laptop browser. | Tap a project and land in its long-lived main chat, with the project's other chats beside it. Follow and steer the main chat while it works. | Extra taps on the phone. Hunting for the main chat among similar titles ("HIM - Project UI", "HIM - Session Mail" sit next to "HIM - Orchestrator"). Losing a pinned main chat from its project. |
| **Family members** (occasional users) | The Webapp now and then, often on a phone. Usually no projects with a main chat. | Everything they already know stays the same. | Technical words, error codes, a screen that changed under them. |

## Journeys

### Happy paths

**J1. Alex opens a project's main chat on the laptop.**
1. In the Webapp sidebar's Projects list, Alex clicks "HIM - Hermes Improvement".
2. The main pane opens "HIM - Orchestrator", resumed where he left off. This is the same as clicking that chat's row today, so an ended chat simply resumes.
3. At the same time the sidebar enters the project, as it does today: the back row, then the project's chats. The first row is "HIM - Orchestrator", marked **Main chat**, followed by the other chats, newest first, as today.

That is one click from the Projects list.

**J2. Alex looks at, or starts, other chats in the project.**
1. With the project entered, he clicks any other row ("HIM - Project UI") and it opens as today.
2. The project's "+" starts a new chat in the project's primary folder, as today. The main chat is untouched.
3. From the entered project, the main chat is always the first row. To switch, he taps the back row, then another project, which opens that project's main chat.

**J3. Alex does the same on his phone (home-screen Webapp).**
1. He opens the Webapp from his home screen and taps the menu to open the sidebar drawer.
2. He taps "BDG - Budgeting". "BDG - Orchestrator" opens, and the drawer closes so he sees the chat (recommended; see open question U1).
3. Opening the drawer again shows the entered project, with the main chat first.

From the home screen, that is two taps to a main chat: the menu, then the project.

**J4. Alex steers a main chat while it works.**
A kickoff has started a long turn in "SDL - Orchestrator" with a command-line one-shot. On v0.23 that turn runs in the gateway, so the Webapp joins it.
1. Alex taps the project on his phone, or on the laptop. The main chat opens showing the reply so far, streaming live, and the composer in its working state. The sidebar row reads **Main chat · Working**. If the agent is asking him something, it reads **Main chat · Needs your answer**.
2. He uses the composer's existing controls:
   - **Steer the current run** guides the turn at its next tool call;
   - **Queue message** holds a message for after the turn, and the queue strip shows "1 Queued";
   - **Stop** ends the turn;
   - `/queue` and `/steer` work as typed commands.
3. Pressing plain **Send** with text follows the server's busy-input setting, which defaults to **interrupt**: it stops the turn and sends the message. To keep the turn running, Alex uses Steer or Queue (open question U5).
4. The laptop and phone show the same turn at once. A stop from either ends it on both.

No "Chat open somewhere else" card appears.

**J5. `/new` in a main chat compacts it (only if Q2 is yes).**
1. In "HIM - Orchestrator", Alex types `/new` or `/reset`.
2. The Webapp runs `/compact` instead and shows a short notice saying this is the project's main chat, so it compacts rather than resets, and that **+** on the project starts a separate chat. The exact text is settled at Spec (the HLD and this document word it slightly differently).
3. The chat keeps its place as the main chat. `/new` in any other chat is unchanged.

### Failures and edge cases

**F1. Project with no main chat.**
Tapping the project behaves exactly as today: the sidebar enters the project and nothing opens in the main pane. No row is marked, and no message or "set one up" prompt appears. Family members' projects, auto-found folders and Home always behave this way.

**F2. Main chat not found among the project's chats.**
One rule covers every case: **the tap opens the main chat only when it is found among the project's chats** (or by a direct lookup, if Spec adds one). Otherwise the project behaves as in F1: the tap only enters the project, nothing opens, there is no error, and no row is marked. The three ways this happens:
- *Archived.* The project tree leaves out archived chats. Restoring it from Archived, as today, brings back the open-on-tap and the **Main chat** mark, because the pointer never changed.
- *Deleted.* The pointer stays but matches nothing. A tap never tries to open a deleted chat.
- *Outside the tree's window.* The tree reads only a limited number of recent chats, so a main chat left idle for a long time can drop out of it. Five of the six main chats have ended, so this is the likeliest way to lose the mark. Alex sees the project without its **Main chat** row, and the tap only enters it. The chat itself is still there. The tree keeps the most recently active chats, so it comes back into the window, with the mark and the tap, once a message is sent in it (opening it alone is not enough). If Spec adds a direct lookup of the main chat (the HLD's `session.info` option), the row and the tap keep working in this case.

**F3. Pinned main chat** ("HME - Orchestrator" is pinned today).
- Today a pinned chat appears only in the global Pinned section and is removed from its project's list.
- The main chat is the one exception: it stays in Pinned **and** appears first in its project, marked **Main chat**. The Pinned row looks as it does today.
- Unpinning changes nothing about the project: it is still listed first and opened on tap.
- Pinning or unpinning never changes which chat is the main chat.

**F4. Project with no other chats.**
The entered project shows only the **Main chat** row. The project's "+" works as today. A project with no main chat and no chats looks exactly as it does today.

**F5. Main chat working when opened.** Covered by J4. If the turn ends while Alex watches, the composer returns to idle, and **Main chat · Working** becomes **Main chat**. If it ends while he is elsewhere, the row reads **Main chat · Finished** until he opens it.

**F6. Main chat held outside the gateway.** This is rare on v0.23. If something outside the gateway holds the chat (for example the standalone dashboard's own chat backend), sending shows the Webapp's existing "Chat open somewhere else" card, with "Start new session". Slice 1 does not change that card. If it happens to a main chat, Alex should close the other window rather than start a new session. Open question U7 asks whether the card should say so.

**F7. Renamed project or main chat.** Renaming either changes nothing: the same chat stays the main chat, because it is found by id, not by title.

**F8. Main chat in another profile.** The tap opens the main chat the way clicking its row would, in the project's own profile, as the Webapp already does for rows. All six of Alex's main chats are in one profile.

**F9. Rollout: the one gateway restart.**
- Shipping slice 1 needs one gateway restart. Alex announces it, and it runs only when no main-chat turn is running. It is drain-first: the gateway stops taking new work and waits up to 30 minutes for running turns to finish.
- Any turn still running after that, on any surface (a family member's chat, a messaging chat, a cron job), is interrupted. Afterwards that chat shows its transcript up to the cut, idle. The next message within an hour continues the interrupted turn automatically.
- Open Webapp tabs reconnect on their own, but they keep the old sidebar until reloaded. Alex reloads the Webapp on the laptop, and closes and reopens the home-screen copy on the phone. Only then does tapping a project open its main chat.
- Seeding the six main chats needs no restart. Until it has run, projects behave as in F1.

## Stories

Active:

| Id | Story |
|---|---|
| [`pcu-08-main-chats-seeded`](stories/pcu-08-main-chats-seeded.md) | The six projects know their main chat, set once by session id, with an undo file |
| [`pcu-18-tap-opens-main-chat`](stories/pcu-18-tap-opens-main-chat.md) | Tapping a project in the Webapp opens its main chat and enters the project |
| [`pcu-19-main-chat-first`](stories/pcu-19-main-chat-first.md) | The main chat is listed first in its project, marked "Main chat", even when pinned |
| [`pcu-20-no-main-chat-unchanged`](stories/pcu-20-no-main-chat-unchanged.md) | Projects without a working main-chat pointer behave exactly as today |
| [`pcu-21-phone-webapp`](stories/pcu-21-phone-webapp.md) | The same works on the phone's home-screen Webapp, in the sidebar drawer |
| [`pcu-22-steer-working-main-chat`](stories/pcu-22-steer-working-main-chat.md) | A working main chat can be followed, steered, queued and stopped from the Webapp |
| [`pcu-23-main-chat-compacts`](stories/pcu-23-main-chat-compacts.md) | `/new` in a main chat compacts it in the Webapp (only if Q2 is yes) |

Retired (v0.23 move), kept for the record: `pcu-01` to `pcu-07` (dashboard Projects page), `pcu-09` (old Hermes Mobile build), `pcu-10` (dashboard family check, now part of `pcu-20`), `pcu-11` to `pcu-14` and `pcu-17` (Hermes Mobile drafts), `pcu-15` (dashboard profile switching), `pcu-16` (dashboard kickoff steering, now `pcu-22`).

## High-level UX

Everything uses the Webapp's existing sidebar rows, project rows, composer and notices. There is no new look, page or navigation entry. Every status is a word. The main chat row's existing status dot keeps its colour and gains a visible word beside it, so the state never rests on colour or a hover tooltip, which a phone does not have:

| Dot state (existing) | Visible text on the main chat row |
|---|---|
| Working (filled accent), and stalled (hollow accent) | **Main chat · Working** |
| Needs input (amber) | **Main chat · Needs your answer** |
| Background process still running (hollow grey) | **Main chat · Background task running** |
| Finished while Alex was elsewhere (green) | **Main chat · Finished** |
| Settled (project colour or plain grey) | **Main chat** |

Other rows keep today's dots; slice 1 adds words only to the main chat row.

### Webapp on a laptop

- **Projects list** (sidebar, grouped mode). It looks the same as today: project rows with colour or icon, the "+", the menu, and the three-chat preview with "Show all".
- **Click a project name whose main chat is found among its chats** (F2):
  - the main pane opens the main chat, the same way clicking its row does (an already-open chat is focused, not opened twice);
  - the sidebar enters the project, as today.
- **Click any other project** (no main chat, or not found): exactly today's behaviour.
- **Entered project:**
  - the back row, then the **Main chat** row first, above the main-checkout chats; worktree groups stay below, as today;
  - the main chat row is a normal session row with the text **Main chat** in its metadata area, plus its status word from the table above;
  - its menu is the usual session menu. Slice 1 adds nothing to it.
- **Overview preview** (the three chats under a project row): unchanged; open question U3.
- **Command palette "go to project":** unchanged; it only scopes. Open question U6.

### Webapp on a phone (home-screen install)

- Below 640 pixels wide, the sidebar is the drawer, as today. The Webapp's manifest already lets it run full-screen from the home screen.
- **Tap a project with a main chat in the drawer:** the main chat opens, and the drawer closes so the chat is visible (U1). Today the drawer does not close on its own when a chat is picked.
- **Reopen the drawer:** the entered project, main chat first, at the same touch size as other rows.
- **Working main chat:** the composer's Steer, Queue and Stop controls are the same as on the laptop. The main chat row's status word (table above) is visible without hover.
- **After the deploy:** close and reopen the home-screen copy once to get the new tap (F9).

### Hermes Mobile and the standalone dashboard

Not targets any more. Nothing in slice 1 changes them; the server field is simply extra data to them.

## Comparables (look and flow)

The full write-up is the architect's [`comparables.md`](comparables.md). For look and flow:

| Product / screen | Steal | Reject |
|---|---|---|
| **Claude Projects** | Opening a project shows its chats, newest first, with "new chat in this project" at hand. | The knowledge and instructions panel: context comes from the project folder. A separate project page: the sidebar already lists the project's chats. |
| **ChatGPT Projects** (projects in the sidebar) | Projects live in the sidebar, and a new chat from a project lands in it. | "Move to project": in Hermes a chat belongs to a project because of its folder. |
| **Hermes Bot Chat in the Webapp** (hermes-bots plugin) | One tap lands in the long-lived chat; `/new` there compacts with a notice. This is the model for the main chat (J5). | Identity by exact title, and hiding the chat from the sidebar. The main chat is a pointer, so renames such as "HIM - Orchestrator" are safe, and it stays visible, first in its project. |
| **Pinned chats in chat apps** (Slack's starred channels, Telegram's pinned chats) | A favourite stays reachable without leaving its group. | Moving it out of its group, which is what the Webapp's Pinned section does today (F3). |

## Not this

- No separate Projects page, plugin tab or navigation entry.
- No row badge plugin. The **Main chat** mark appears only in the main chat's own project.
- No change for projects without a main chat, for auto-found folders or for Home.
- No "Make main chat" button. A later project gets its main chat with one `hermes project set-owner` run.
- No pin changes at seeding.
- No `/new` change on the command line, in the terminal interface, or anywhere except a main chat in the Webapp (and only if Q2 is yes).
- No new steering controls. The composer's existing Steer, Queue and Stop are the controls.
- No change to the "Chat open somewhere else" card (U7).
- No Hermes Mobile or standalone dashboard work, and no kickoff command.
- No service worker or offline mode; the existing manifest is enough to install.
- No mockups here. They come at Spec, with variants.

## Accessibility notes

- **Main chat** and each of its status words (Working, Needs your answer, Background task running, Finished) are visible words, not colour, an icon or a hover tooltip alone.
- The main chat row has the same keyboard focus and touch size as other session rows. Its accessible name includes "Main chat".
- The project row's accessible name says what the tap does: for a project with a main chat, "Open main chat of <project>"; otherwise today's "Enter <project>".

## Open questions

Only the places where a different answer changes what Alex sees.

1. **Q1, what a tap does.** If Alex prefers today's scope-only tap, nothing opens on tap and only the **Main chat** row first remains (`pcu-18` dropped). If he wants a separate Projects page instead, that is a new screen, and the sidebar stays as today.
2. **Q2, `/new` compacts.** Yes: J5 and `pcu-23`. No: `/new` in a main chat starts a separate chat, and the main chat stays as it was.
3. **Q3, which chats are main, and pins.** A different pick changes which row is marked **Main chat** and what opens on tap. Pinning all six would put them all in Pinned too; F3 keeps them in their projects regardless.
4. **U1, phone drawer.** Should a tap that opens a main chat close the drawer? The recommended answer is yes, so Alex sees the chat. If not, the chat opens behind the open drawer and he closes it himself.
5. **U2, the Pinned row of a main chat.** Should it also show **Main chat**? The recommended answer is no: the title already names it, and the mark belongs to the project list.
6. **U3, overview preview.** Should the three-chat preview under a project row also lead with the main chat? The recommended answer is no: the tap already opens it.
7. **U4, wording.** "Main chat", "Orchestrator" or "Owner chat" for the mark?
8. **U5, plain Send in a working chat.** The server default (interrupt) makes plain Send stop the turn. Alex can set the busy-input mode to queue or steer in his config so plain Send no longer stops a working main chat. That is a config choice, not code.
9. **U6, command palette.** Should ⌘K "go to project" also open the main chat, like the tap? The recommended answer is no for slice 1.
10. **U7, "Chat open somewhere else" on a main chat.** Should the card's wording point to closing the other window rather than "Start new session" when the chat is a main chat? The recommended answer is no for slice 1, because it is rare on v0.23 (F6).
