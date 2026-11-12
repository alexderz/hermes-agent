# Story — See a message in its Telegram topic

- Id: `sm-20-telegram-topic`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` § "Messaging-gateway sessions", J11 (SM-Q15 b)
- Person: Alex, reading a Telegram topic; the gateway session in it

## Required

- **As** Alex, following a gateway session in a Telegram topic
- **I want** a message to that session to show in the topic before the answer
- **So that** the answer does not appear out of nowhere, and I can see who asked what
- **Done when**
  - [ ] As the turn that carries the message runs, and before its answer, one bot message is posted into the target's topic, from that turn (as a queued or started turn begins; for a steer, just before the model's next request reads it), only if that chat is private: a DM with a user in `plugins.entries.intercom.settings.owner_user_ids`, or a chat in `plugins.entries.intercom.settings.echo_chats` (values `"<platform>:<id>"`, for example `"telegram:<chat id>"`). The post is header line 1 (`📡 Not Alex · … hermes@<title> says (…):`) and the body, escaped for the chat's renderer so links and mentions are inert; a platform with no escaper gets no echo; lines 2–3, the shared-chat line and the footer are never posted.
  - [ ] A shared chat (any other group, topic or DM) gets the message delivered but nothing posted, so only the answer appears; the sender's receipt adds "Its chat is shared with other people; the body is now in that chat's context."
  - [ ] An idle topic starts a turn in that chat; a busy one gets the requested mode or its fallback; the receipt says which.
  - [ ] A steered message is echoed just before the model's next request reads it, whether that step is a tool call or the answer (LLD B6, `pre_api_request`); a steer that arrives after the turn's last request is echoed as the next turn begins. Each message is echoed at most once.
  - [ ] The turn's answer is posted in the topic as usual, with any `[REPLY <id>]` block visible.
  - [ ] A reply to a Telegram sender is delivered into its own topic, starting a turn there if it is idle.
  - [ ] A message cannot run gateway commands: its text starts with `📡`, never `/`.
  - [ ] Whether a bare `[SILENT]` answer is kept out of the topic on the v0.23 owner path is checked in the E2E (`ux.md` "Still to check"); on v0.22 it was (Trial round 2, R4).
  - [ ] A message from a Telegram-source sender names the platform and chat type in its header (`hermes@<title> (Telegram group)` or `(Telegram DM)`), uses the platform authority line, and, if its chat is shared, carries the reply-destination footer line; only an explicit `[REPLY]` block goes back to it.
- **Out of scope** — other platforms' look (they follow the same rule where their adapter can post); a Telegram client change.

## Optional

- Notes: If the echo hooks do not fire for messaging chats (HLD O21), the echo is dropped for v1 and the topic shows only the answer (SM-Q15 a).
