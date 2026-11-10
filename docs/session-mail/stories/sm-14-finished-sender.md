# Story — A reply to a cron run, oneshot or subagent is stored, not woken

- Id: `sm-14-finished-sender`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` (F6; SM-Q9)
- Person: a cron run, oneshot or subagent that sent mail; the target; Alex

## Required

- **As** Alex
- **I want** replies to mail sent by a cron run, a oneshot or a subagent to be stored in the outbox instead of waking that session
- **So that** I do not get turns nobody reads in cron, oneshot or subagent transcripts, while owner sessions closed in a terminal still get their replies
- **Done when**
  - [ ] A reply to a sender whose session source is `cron`, `subagent` or `oneshot` is stored and starts, steers or queues nothing, whatever its end reason.
  - [ ] A reply to a `cli` owner session whose terminal was closed (`cli_close`) wakes it by the usual rule.
  - [ ] The mail such a sender sends carries the footer variant "stored in the outbox for session "<title>", a <source>. It wakes no one", naming only the one source that applies (`cron run`, `oneshot` or `subagent`); its tool result says the same.
  - [ ] Its header line 1 still says `reply expected` (deliberately: the answer is wanted and is read later from the outbox).
  - [ ] `status` shows the stored reply.
- **Out of scope** — telling desktop subagent windows (source `desktop`) apart from other sessions.

## Optional

- Notes: built on SM-Q9 (b). Other answers change this story (`ux.md`, Open questions).
