# Story — Read who sent what, and the reply

- Id: `sm-12-cli-outbox`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` § "Command line"
- Person: Alex, or a script that sent mail

## Required

- **As** Alex, or a script that sent mail
- **I want** `hermes session-mail status <id>` and `hermes session-mail list` to show every mail's sender, target, delivery result and reply
- **So that** I can see who said what to whom, read an answer a script cannot be woken for, and spot mail that never got a reply
- **Done when**
  - [ ] `status <id>` shows from, to (title and id), sent time, delivery result (including `unknown` when none was recorded), and reply: `no reply recorded`, `silent`, `stored`, `sent as mail <id>`, or `stored, not delivered`, each with its time and the reply text where there is one; for a reply, the mail it answers.
  - [ ] `status` of an unknown id exits 1 with a one-line message.
  - [ ] `list` shows the last 24 hours newest first, one line per mail, with sender, target, result and reply state; `--since`, `--to` and `--from` narrow or widen it.
  - [ ] Mail lost in a restart shows its delivery result with `no reply recorded`, and a reply lost in a restart shows `stored, not delivered`; neither ever shows as delivered and answered.
  - [ ] Neither command starts a turn; both take `--json`.
- **Out of scope** — a dashboard Mail tab; deleting or editing outbox rows.
