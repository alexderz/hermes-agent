# Story — Deliver now, by the gateway owner, in the mode asked for

- Id: `sm-04-deliver-now`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` (J4–J6)
- Person: a sender, and Alex watching the target

## Required

- **As a** sender
- **I want** my message to land right away, delivered by the gateway owner that hosts the target, in the mode I asked for or its fallback
- **So that** the target sees it now, on whatever surface it lives, and its work is only stopped when I meant it
- **Done when**
  - [ ] With no `delivery`, a message into a running turn is `steered`: the turn carries on, and the transcript has a user row where it landed, starting with the 📡 header and ending with `📡 End of message <id>` (the header is the row's first line unless Hermes joined it with other text; `ux.md` F10).
  - [ ] A steer the owner refuses (for example while compacting) is `queued`, runs after the current turn, and the receipt says "asked: steer".
  - [ ] An idle target starts a turn in every mode, where it is open (a terminal, a Webapp or desktop chat, a Telegram topic).
  - [ ] A target that is not open (cold) is reopened by the gateway and returns `started`; the turn runs in the gateway owner, where Alex can open it from the Webapp. Its receipt says: `"<title>" was not open, so the gateway reopened it and message <id> started a turn there.`
  - [ ] Only `delivery="interrupt"` ever stops or redirects a running turn.
  - [ ] Each message is delivered once: the owner admits each message id once, even if a sender process repeats the call.
  - [ ] A message is delivered at once whether or not Alex is active in the target (no hold), and never as `display_kind: "hidden"`.
- **Out of scope** — holding messages while Alex types; a background delivery worker; redelivery.
