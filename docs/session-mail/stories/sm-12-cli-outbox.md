# Story — Read who sent what, and the reply

- Id: `sm-12-cli-outbox`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` § "Command line"
- Person: Alex, or a script that sent mail

## Required

- **As** Alex, or a script that sent mail
- **I want** `hermes session-mail status <id>` and `hermes session-mail list` to show every mail's sender, target, delivery result and reply
- **So that** I can see who said what to whom, read an answer a script cannot be woken for, and spot mail that never got a reply
- **Done when**
  - [ ] `status <id>` shows from, to (title and id), sent time, delivery result (including `unknown`, explained as "no result recorded yet: still sending, or the sending process was cut off"), and reply: `no reply recorded`, `silent`, `stored`, `sent as mail <id>`, `stored, not delivered` (with the reply mail's id and code), each with its time and the reply text where there is one; for a reply, the mail it answers.
  - [ ] For a mail whose delivery is `unknown` or `error (delivery unknown)`, `status` reads the target's transcript without changing it and adds `found in the target's transcript (<time>)` or `not found in the target's transcript (yet)`, matching only a line that starts with that mail's header line 1 and ends `· mail <id>` (a quoted id or a relabelled lookalike does not count).
  - [ ] The "not found" advice tells the reader to run `status` again in a minute if the send ended under a minute ago or delivery is still `unknown`, as written in `ux.md`.
  - [ ] `status` of an unknown id exits 1 with a one-line message.
  - [ ] `list` shows the last 24 hours newest first, one line per mail, with sender, target, result and reply state; `--since`, `--to` and `--from` narrow or widen it.
  - [ ] Mail lost in a restart shows its delivery result with `no reply recorded`, and a reply lost in a restart shows `stored, not delivered`; neither ever shows as delivered and answered.
  - [ ] A reply that could not be delivered (the sender was held by a command-line session, or the dashboard was down) shows on the original mail's `list` line as `reply: <id> not delivered (<code>)`.
  - [ ] Neither command starts a turn; both take `--json`.
- **Out of scope** — a dashboard Mail tab; deleting or editing outbox rows.
