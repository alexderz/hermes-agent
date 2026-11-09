# Story — Steer a working main chat from the phone or the dashboard

- Id: `pcu-16-steer-working-main-chat`
- HLD / UX: `docs/project-centric-ui/hld.md`, `docs/project-centric-ui/ux.md` (J6, J7, F11)
- Person: Alex

## Required

- **As** Alex, whose scripts start long turns in a project's main chat
- **I want** to open that chat while it works, on Hermes Mobile or the dashboard, and queue, steer or stop the turn
- **So that** I can follow and redirect project work from my phone instead of being locked out
- **Done when** (with the owner-chat kickoff sending its turn through the dashboard's chat socket, Q4)
  - [ ] While a kickoff-started turn runs in a main chat, opening that chat on today's Hermes Mobile build shows the transcript and the live reply with the app's working indicator. It shows no "open in another window" card.
  - [ ] On the phone, each **While the agent is working** mode acts on that running turn:
    - **Queue next turn** runs the message after the turn ends;
    - **Guide at next safe point** injects it into the running turn;
    - **Correct current turn** redirects the running turn;
    - **Hard interrupt, then send** stops the turn and sends.
  - [ ] On the phone, `/queue` and `/btw` also work on the running turn.
  - [ ] The phone's stop control stops the turn, and the chat then accepts a normal message.
  - [ ] For a main chat in the dashboard's own profile (all six of Alex's), **Open main chat** on the dashboard (laptop or phone browser) joins the same running turn. `/queue <text>` and `/steer <text>` work, and the interrupt key stops it. Another profile's working main chat is F9 and `pcu-15`.
  - [ ] Typing a plain message (without `/queue` or `/steer`) into a working main chat on the dashboard stops the turn and sends the message, as the terminal UI's default busy-input setting does. `ux.md` J7 says so, and U11 offers the setting change.
  - [ ] With the phone and the dashboard both open on the chat, a stop from either ends the turn on both, and both then show the same transcript.
  - [ ] When the turn finishes on its own, the kickoff command exits and the chat is idle on both surfaces.
  - [ ] After a dashboard restart or a dropped kickoff connection during a turn, both surfaces show the chat idle with the transcript up to the last saved message, or, for a turn started less than 15 minutes ago, auto-continued with a recovery note. No error card appears, and re-running the kickoff with a "continue" prompt works (F11).
  - [ ] A planned dashboard restart is not made while a main-chat turn runs, unless Alex chooses to stop it.
- **Out of scope** — any Hermes Mobile or dashboard code change; a running badge on the Projects pages (U7); steering a turn held by a separate command-line process (`pcu-17`); reconnect handling in the kickoff command.

## Optional

- Notes: the kickoff is a `hermes` CLI command in the Projects plugin (HLD part 6); switching the kickoff unit to it is Alex's tooling. The phone joining the same live turn is verified in code, not yet run live; this story's checks are that live run.
