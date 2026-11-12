# Story — Read who sent what, and the reply

- Id: `sm-12-cli-outbox`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` § "Command line"
- Person: Alex, or a script that sent a message

## Required

- **As** Alex, or a script that sent a message
- **I want** `hermes intercom status <id>` and `hermes intercom log` to show every message's sender, target, requested and applied mode, and reply
- **So that** I can see who said what to whom, read an answer a script cannot be woken for, and spot messages that never got a reply
- **Done when**
  - [ ] `status <id>` shows from, to (title and id), sent time, delivery (applied, with `asked: …` when weaker, or `refused`, `error`, `unknown`), and reply: `no reply recorded`, `silent`, `stored`, `sent as message <id>`, `stored, not delivered` (with the reply message's id and reason), or for an `ask` `answered by reply`, each with its time and the text where there is one.
  - [ ] For `unknown` or `error (delivery unknown)`, `status` reads the target's transcript without changing it and adds `found in the target's transcript (<time>)` or `not found in the target's transcript (yet)`, matching only a line that starts with that message's header line 1 and ends `· message <id>):`; the "not found" advice is as written in `ux.md`.
  - [ ] For `unknown` or `error (delivery unknown)`, `status` reads, without changing anything, the owner's admission receipt for a queued or started message (`admitted: queued / started / finished` or `not admitted`), or, for a steered message, the target's transcript for its header line (found or not found).
  - [ ] `status` of an unknown id exits 1 with a one-line message.
  - [ ] `log` shows the last 24 hours newest first, one line per message, with sender, target, applied mode and reply state; `--since`, `--to` and `--from` narrow or widen it. A reply that was not delivered shows as `reply: <id> not delivered (<reason>)`. A reply held back because the sender's chat is shared and the target wrote no block shows as `reply: stored (shared chat, no [REPLY] block)`.
  - [ ] A message lost after handover shows its delivery result with `no reply recorded`, never as answered.
  - [ ] `list` prints this profile's sessions from the owner (title, id, last active).
  - [ ] None of these starts a turn; all take `--json`.
- **Out of scope** — a dashboard Mail tab; editing the record.
