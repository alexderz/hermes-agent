# Story — See a message in its Telegram topic

- Id: `sm-20-telegram-topic`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` § "Messaging-gateway sessions", J11 (SM-Q15 b)
- Person: Alex, reading a Telegram topic; the gateway session in it

## Required

- **As** Alex, following a gateway session in a Telegram topic
- **I want** a message to that session to show in the topic before the answer
- **So that** the answer does not appear out of nowhere, and I can see who asked what
- **Done when**
  - [ ] Before the turn starts, the gateway posts one bot message into the target's topic only if that chat is private: a DM with a user in `plugins.entries.intercom.owner_user_ids`, or a chat in `plugins.entries.intercom.echo_chats`. The post is header line 1 (`📡 Not Alex · … hermes@<title> says (…):`) and the body, as plain text with mentions suppressed; lines 2–3, the shared-chat line and the footer are never posted.
  - [ ] A shared chat (any other group, topic or DM) gets the message delivered but nothing posted, so only the answer appears; the sender's receipt adds "Its chat is shared with other people; the body is now in that chat's context."
  - [ ] An idle topic starts a turn in that chat; a busy one gets the requested mode or the strongest weaker one the gateway supports; the receipt says which.
  - [ ] The turn's answer is posted in the topic as usual, with any `[REPLY <id>]` block visible.
  - [ ] A reply to a Telegram sender is delivered into its own topic, starting a turn there if it is idle.
  - [ ] Injected messages still carry no gateway control (`allow_gateway_control=False`): a message cannot run gateway commands.
  - [ ] A bare `[SILENT]` answer to a message is not posted to the topic; real answers are (Trial round 2, R4).
  - [ ] A message from a Telegram-source sender names the platform and chat type in its header (`hermes@<title> (Telegram group)` or `(Telegram DM)`), uses the platform authority line, and, if its chat is shared, carries the reply-destination footer line; only an explicit `[REPLY]` block goes back to it.
- **Out of scope** — other platforms' look (they follow the same rule where their adapter can post); a Telegram client change.

## Optional

- Notes: Security decides at Spec whether group chats are left out of the post (HLD O7); if so, a group chat shows only the answer.
