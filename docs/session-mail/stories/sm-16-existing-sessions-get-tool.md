# Story — Long-lived sessions can send after the deploy

- Id: `sm-16-existing-sessions-get-tool`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md`
- Person: an owner session created before the plugin existed; Alex

## Required

- **As a** long-lived owner session such as "Hermes Improvement — Orchestrator"
- **I want** `session_message` in my tools after the one deploy restart
- **So that** the sessions Alex already works in can use mail without being recreated
- **Done when**
  - [ ] A session created before the plugin was enabled lists `session_message`, with the full description, after the dashboard restart, and can call it.
  - [ ] That session pays one prompt-cache miss on its first turn after the restart, not one on every turn.
  - [ ] Its stored system prompt is not rebuilt.
- **Out of scope** — adding the tool without a restart; a system-prompt section about mail; sessions hosted by the messaging gateway, which get the tool at its next routine restart and can send with `hermes session-mail send` until then (HLD D6, O6).
