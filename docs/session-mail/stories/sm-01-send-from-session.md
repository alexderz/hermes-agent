# Story — Send a message from a session

- Id: `sm-01-send-from-session`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md`
- Person: a session (the model)

## Required

- **As a** session that needs something from another session
- **I want** to send it a message with one `intercom(action="send", …)` call and get a final receipt back in the same call
- **So that** I know at once whether it landed and how, and can carry on without waiting for the answer
- **Done when**
  - [ ] `intercom` is callable from every default-profile session whose process loaded the plugin: in its tool list when Tool Search is off, or through `tool_call` when it is on (see sm-16).
  - [ ] `tool_describe` (or the tool list, with Tool Search off) returns the description in `ux.md` § "Tool description", word for word. Its first sentence is at most 60 characters, so the Tool Search catalog shows all of it: `Message another Hermes session; never send an empty message.`
  - [ ] It keeps intercom's `action` values (`list`, `send`, `ask`, `reply`) and `to`, `message`, `timeout`, `request_id`, and adds `delivery` (default `steer`) and `expect_reply` (default `true`).
  - [ ] A delivered `send` returns the message id, the target's title and id, the requested and applied mode, and the `message` sentence from `ux.md` § "Receipts".
  - [ ] The sender is taken from the calling session, never from the model's input: a `message` that claims another sender changes nothing in the header.
  - [ ] The record has a row for the message: sender, target, body, requested and applied mode, timestamps.
  - [ ] No receipt says "pending", "held" or "will retry".
- **Out of scope** — an `inbox` action; polling for replies; several targets in one call.
