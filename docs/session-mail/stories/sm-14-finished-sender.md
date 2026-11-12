# Story — A reply to a cron run, oneshot or subagent is stored, not woken

- Id: `sm-14-finished-sender`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` (F12; SM-Q9)
- Person: a cron run, oneshot or subagent that sent a message; the target; Alex

## Required

- **As** Alex
- **I want** replies to messages sent by a cron run, a oneshot or a subagent to be stored in the record instead of waking that session
- **So that** I do not get turns nobody reads in those transcripts, while owner sessions closed in a terminal, and Telegram senders, still get their replies
- **Done when**
  - [ ] A reply to a sender whose source is `cron`, `subagent` or `oneshot` is stored and starts, steers or queues nothing, whatever its end reason.
  - [ ] A reply to a `cli` owner session whose terminal was closed wakes it (the gateway reopens it); a reply to a Telegram sender is delivered into its topic.
  - [ ] The message such a sender sends carries the footer variant "stored in the record for session "<title>", a <source>. It wakes no one", naming the one source that applies; its receipt says the same.
  - [ ] Its header line 1 still says `reply expected` (deliberately: the answer is read later from the record).
  - [ ] `status` shows the stored reply.
- **Out of scope** — telling desktop subagent windows (source `desktop`) apart.
