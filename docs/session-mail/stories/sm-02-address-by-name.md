# Story — Address a session by name

- Id: `sm-02-address-by-name`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md`
- Person: a session, a cron job or script

## Required

- **As a** sender
- **I want** to address a session as `@<project-slug>`, by its exact title, by its id or the start of it, or as `Home`
- **So that** I can reach a project's main session without knowing its id or where it is open, and the address keeps working after it compacts its context
- **Done when**
  - [ ] `@hermes-improvement` reaches "Hermes Improvement — Orchestrator" (the `<Project name> — Orchestrator` rule until DER-686's owner field exists, then that field).
  - [ ] An exact title, a full id (a v0.23 `local-…` id or a v0.22 id), a unique id prefix and `Home` each reach the right session.
  - [ ] After the target runs `/compress`, each address reaches the compression tip, and the receipt names that session's title and id.
  - [ ] `list` and every receipt give the target's session id, and the tool description tells the model to use it for follow-ups; an id still reaches the session after compaction.
  - [ ] The address works wherever the target is open in the gateway owner (Webapp, desktop, Ink TUI, classic CLI, a messaging chat), or when it is not open (then the gateway reopens it).
  - [ ] The tool and `hermes intercom send` resolve addresses the same way.
- **Out of scope** — alias maps (SM-Q10 recommends a rename); other profiles or machines; partial-title search as a way to send.
