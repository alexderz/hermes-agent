# Story — Address a session by name

- Id: `sm-02-address-by-name`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md`
- Person: a session, a cron job or script

## Required

- **As a** sender
- **I want** to address a session as `@<project-slug>`, by its exact title, by its id or the start of it, as `Home`, or by an intercom endpoint name
- **So that** I can reach a project's main session without knowing its id or where it is open, and the address keeps working after it compacts its context
- **Done when**
  - [ ] `@hermes-improvement` reaches "Hermes Improvement — Orchestrator" (the `<Project name> — Orchestrator` rule until DER-686's owner field exists, then that field).
  - [ ] An exact title, a full id, a unique id prefix, `Home` and a live endpoint name from `list` each reach the right session.
  - [ ] After the target runs `/compress`, each address reaches the compression tip, and the receipt names that session's title and id.
  - [ ] The address works whatever hosts the target: the dashboard, an Ink TUI, a classic CLI, the gateway, or nothing (then it is woken).
  - [ ] The tool and `hermes intercom send` resolve addresses the same way.
- **Out of scope** — alias maps (SM-Q10 recommends a rename); other profiles or machines; partial-title search as a way to send.
