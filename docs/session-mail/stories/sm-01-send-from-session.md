# Story — Send mail from a session

- Id: `sm-01-send-from-session`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md`
- Person: a session (the model)

## Required

- **As a** session that needs something from another session
- **I want** to send it mail with one `session_message` call and get a final result back in the same call
- **So that** I know at once whether it landed, and can carry on without waiting for the answer
- **Done when**
  - [ ] `session_message` is callable from every default-profile session whose process loaded the plugin (the dashboard after the deploy restart, and new CLI, TUI and gateway processes; see sm-16): in its tool list when Tool Search is off, or through `tool_call` when it is on.
  - [ ] `tool_describe` (or the tool list, with Tool Search off) returns the description in `ux.md` § "Tool description", word for word; its first sentence names the job and the no-empty-messages rule.
  - [ ] It takes `to` and `message` (required) and `expect_reply` (optional, default `true`).
  - [ ] A successful call returns the mail id, the target's full title and id, and one of `steered`, `queued`, `started`, with the `message` text from `ux.md` § "Tool results".
  - [ ] The sender is taken from the calling session, never from the model's input: a `message` that claims another sender changes nothing in the header.
  - [ ] The outbox has a row for the mail with sender, target, body, delivery result and timestamps.
  - [ ] A start with no activity seen within the start wait returns `started` with the "may still be building; do not send it again" wording.
  - [ ] No result says "pending" or "will retry".
- **Out of scope** — an `inbox` action; polling for replies; sending to several targets in one call.

## Optional

- Notes: the handler is synchronous (brief, Constraints), so a `started` result may take a few seconds while the target's agent is built.
