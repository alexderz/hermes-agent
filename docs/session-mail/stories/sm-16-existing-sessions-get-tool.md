# Story — Long-lived sessions can find and use intercom after the deploy

- Id: `sm-16-existing-sessions-get-tool`
- HLD / UX: `docs/session-mail/hld.md` (D6, O11, O12), `docs/session-mail/ux.md` § "How a session learns the tool exists"
- Person: an owner session created before the plugin was enabled; Alex

## Required

- **As a** long-lived owner session such as "Hermes Improvement — Orchestrator"
- **I want** to be able to call `intercom` after the deploy, and to learn that it exists
- **So that** the sessions Alex already works in can message others without being recreated, and without paying for it on every turn
- **Done when**
  - [ ] With Tool Search on (the default), a session created before the plugin was enabled keeps byte-identical tool definitions after the restart (no prompt-cache miss), and can call `intercom` through `tool_call`.
  - [ ] `tool_describe` on `intercom` returns the full description from `ux.md`.
  - [ ] A pre-deploy session that receives a message can name `intercom` and call it (`tool_describe`, then `tool_call`) using only that message's footer.
  - [ ] With Tool Search off (O12), the session lists `intercom` after the restart and pays one prompt-cache miss on its first turn, not one on every turn.
  - [ ] Its stored system prompt is not rebuilt.
- **Out of scope** — adding the tool without a restart; a system-prompt section; the relay-skill edit itself (HLD O11, done by the manager at deploy). Terminal and gateway processes started after the deploy load the plugin when they start.
