# Story — Hermes Mobile shows "working elsewhere" (drafted issue 1)

- Id: `pcu-17-mobile-working-elsewhere`
- HLD / UX: `docs/project-centric-ui/hld.md`, `docs/project-centric-ui/ux.md` (F10)
- Person: Alex

## Required

- **As** Alex on Hermes Mobile
- **I want** a chat that another process holds to say it is working elsewhere, and my message kept for when it finishes
- **So that** I am not pushed to "New conversation", which leaves the main chat behind
- **Done when** (for this chunk: the draft; the app work is the maintainer's)
  - [ ] Drafted issue 1 describes today's behaviour: the chat looks idle, and a send ends in the card "This chat is open in another window. Start a new conversation with this message?" with only **Discard** and **New conversation** (`PendingSendRecovery.kt`, `strings.xml`).
  - [ ] It asks for a "Working in another window" state in the chat, as words, not colour alone, using the same activity signal History already uses (`SessionSharedStatus.kt`).
  - [ ] It asks that a refused send keep the message and offer **Send when it finishes** first, then **Discard**, with **New conversation** last.
  - [ ] It says that **Send when it finishes** sends once the other run releases the chat, and tells the user if it still cannot send.
  - [ ] It says plainly that this does not steer or stop the other run, and does not ask for that.
  - [ ] The draft is for Alex to review, carries no AI-authorship trailer, and is not posted.
- **Out of scope** — app code; server changes; a "take over" action.

## Optional

- Notes: the wording ("Working in another window") is open question U10 in `ux.md`. Under Q4 this case should only arise for ad-hoc command-line use.
