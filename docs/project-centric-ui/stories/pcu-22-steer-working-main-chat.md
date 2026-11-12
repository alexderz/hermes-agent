# Story — Follow and steer a working main chat from the Webapp

- Id: `pcu-22-steer-working-main-chat`
- HLD / UX: `docs/project-centric-ui/hld.md`, `docs/project-centric-ui/ux.md` (J4, F5, F6)
- Person: Alex
- Replaces the retired `pcu-16`.

## Required

- **As** Alex, whose kickoffs start long turns in a project's main chat
- **I want** to open that chat while it works, on phone or laptop, and steer, queue or stop the turn
- **So that** I can follow and redirect project work from my phone (the 21:00 requirement)
- **Done when** (a live check on the v0.23 base; slice 1 builds nothing for it)
  - [ ] While a kickoff started with `hermes chat -q --oneshot` runs a turn in a main chat, tapping the project in the Webapp on the phone opens the chat. It shows the reply so far, streaming live, and the composer in its working state.
  - [ ] The sidebar row reads **Main chat · Working** until the turn ends, then **Main chat**.
  - [ ] **Steer the current run** guides the turn, and the reply reflects it after the next tool call.
  - [ ] **Queue message** holds the message; the queue strip shows it, and it runs after the turn.
  - [ ] **Stop** ends the turn.
  - [ ] `/queue` and `/steer` typed in the composer do the same.
  - [ ] No "Chat open somewhere else" card appears at any point.
  - [ ] With the laptop and the phone both open on the chat, both show the same live turn, and a stop from either ends it on both.
  - [ ] If the command-line process that started the turn is killed mid-turn, the turn keeps running in the gateway, and steer, queue and stop from the Webapp still work. The HLD's Trial showed this on a temporary home; this is the live check.
  - [ ] Plain **Send** with text follows the server's busy-input setting. With the default (interrupt), it stops the turn and sends; `ux.md` J4 says so.
- **Out of scope** — new steering controls; changing the "Chat open somewhere else" card (`ux.md` U7).

## Optional

- Notes: the Trial (HLD, 14/14) covered steer and stop after the CLI was killed, on a temporary home with a fake model; the live run adds the real sign-in path, a real model and hours. If a check fails, this story records it, not a fix.
