# Story — Address a session by name

- Id: `sm-02-address-by-name`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md`
- Person: a session, a cron job or script

## Required

- **As a** sender
- **I want** to address a session as `@<project-slug>`, by its exact title, by its id or the start of it, or as `Home`
- **So that** I can reach a project's main session without knowing its id, and the address keeps working after that session compacts its context
- **Done when**
  - [ ] `@hermes-improvement` reaches "Hermes Improvement — Orchestrator" (the `<Project name> — Orchestrator` rule until DER-686's owner field exists, then that field).
  - [ ] An exact title, a full id, a unique id prefix and `Home` each reach the right session.
  - [ ] After the target runs `/compress`, each of those addresses reaches the newest session in its compression chain (the compression tip), and the result names that session's title and id.
  - [ ] The tool and the CLI accept the same addresses and resolve them the same way.
- **Out of scope** — alias maps (SM-Q10 recommends a rename instead); addresses in other profiles or on other machines; partial-title search as a way to send.

## Optional

- Notes: if Alex answers SM-Q10 differently, `@model-testing` follows that answer (`ux.md`, Open questions).
