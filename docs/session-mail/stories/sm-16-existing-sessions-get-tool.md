# Story — Long-lived sessions can find and use the tool after the deploy

- Id: `sm-16-existing-sessions-get-tool`
- HLD / UX: `docs/session-mail/hld.md` (D6, O11, O12), `docs/session-mail/ux.md` § "How a session learns the tool exists"
- Person: an owner session created before the plugin existed; Alex

## Required

- **As a** long-lived owner session such as "Hermes Improvement — Orchestrator"
- **I want** to be able to call `session_message` after the one deploy restart, and to learn that it exists
- **So that** the sessions Alex already works in can use mail without being recreated, and without paying for it on every turn
- **Done when**
  - [ ] With Tool Search on (the default), a session created before the plugin was enabled keeps byte-identical tool definitions after the restart (no prompt-cache miss), and can call `session_message` through `tool_call`.
  - [ ] `tool_describe` on `session_message` returns the full description from `ux.md`, so the no-empty-messages rule is one call away.
  - [ ] Such a session learns the name from at least one of: the footer of any mail it receives (footer line 1 names `session_message` for new mail), the relay skills if Alex agrees to the O11 edit, or Alex.
  - [ ] With Tool Search off (O12), the session lists `session_message` after the restart and pays one prompt-cache miss on its first turn, not one on every turn.
  - [ ] Its stored system prompt is not rebuilt.
- **Out of scope** — adding the tool without a restart; a system-prompt section about mail; editing the relay skills in the live home without Alex (O11); sessions hosted by the messaging gateway, which get the tool at its next routine restart and can send with `hermes session-mail send` until then (HLD D6, O6).

## Optional

- Notes: rewritten after the Trial (Q8 failed as first worded: Hermes never names a deferred plugin tool to a session created before it). Which Tool Search row applies live is read at deploy planning (O12).
