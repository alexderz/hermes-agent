# Story — Address a session by id, title or Home; by project only when the project feature is there

- Id: `sm-02-address-by-name`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` (§ "Project addressing", F1, F1b)
- Person: a session, a cron job or script

## Required

- **As a** sender
- **I want** to address a session by its id or the start of it, by its exact title, or as `Home`, and as `@<project-slug>` only when Hermes really knows each project's owner session
- **So that** I reach the right session without guessing from names, and the address keeps working after it compacts its context
- **Done when**
  - [ ] An exact title, a full id (a v0.23 `local-…` id or a v0.22 id), a unique id prefix and `Home` each reach the right session.
  - [ ] After the target runs `/compress`, each address reaches the compression tip, and the receipt names that session's title and id.
  - [ ] `list` and every receipt give the target's session id, and the tool description tells the model to use it for follow-ups; an id still reaches the session after compaction. `list` shows each session's project (from Hermes's project folders and its working directory), filterable with `query`.
  - [ ] **Project feature absent** (DER-686's projects plugin, named by `settings.project_plugin`, not enabled in this profile, or `projects.db` without `owner_session_id`): the tool description and schema never mention `@`, and a `to` starting with `@` is refused `project-addressing-unavailable` with `Project addressing is not available on this Hermes. Use list (filter by project) and address the session by id.`
  - [ ] **Project feature present:** the description's `to` sentence offers `@<project-slug> (that project's owner session)`; `@<slug>` reaches the session in `owner_session_id`; a project with no owner set is refused `no-owner-set` with `Project @<slug> has no owner session set. Address a session by id (from list).`; an unknown `@<slug>` is refused `unknown` with up to five of the closest project slugs.
  - [ ] No address is ever resolved through a title convention (`<name> — Orchestrator`), and no session needs renaming (SM-Q10 withdrawn).
  - [ ] The address works wherever the target is open in the gateway owner (Webapp, desktop, Ink TUI, classic CLI, a messaging chat), or when it is not open (then the gateway reopens it).
  - [ ] The tool and `hermes intercom send` resolve addresses the same way.
- **Out of scope** — alias maps; guessing a project's owner; other profiles or machines; partial-title search as a way to send.
