# Comparables — project-centric Hermes UI (v0.23, Webapp surface)

How others have done a thing like this. **Before** locking HLD shape
(and UX, if there are screens). Real examples with sources — not "industry
standard."

- Slug: `project-centric-ui`
- Brief / options map: `docs/project-centric-ui/brief.md` (round 4, Options map)
- Date: `2026-11-11` (re-checked for the v0.23 base; replaces the 2026-11-08 page)

The two in-tree examples now come first: Alex's surface is the v0.23 Webapp, which is the desktop
app's interface in a browser, so its own project sidebar and Bot Chat are what slice 1 changes or
copies. Paths are in this worktree.

## Required

### 1. The Webapp's own project sidebar (in-tree, v0.23)

- **Who / what** — The desktop app's chat sidebar, served unchanged as the Webapp
  (`apps/desktop/src/app/chat/sidebar/index.tsx`, `sidebar/projects/`), fed by the gateway's
  `projects.tree` and `projects.project_sessions` (`tui_gateway/project_tree.py`).
- **What they did** —
  - The overview lists projects, each previewing three chats with "Show all"
    (`projects/overview-row.tsx`).
  - Tapping a project row scopes the sidebar to it (`enterProject`, `store/projects.ts`: "Never
    opens a session") and lists its chats from `projects.project_sessions`: main-checkout chats
    flat, worktrees by branch (`projects/entered-content.tsx`).
  - "+" starts a chat in the project's primary folder (`resolveNewSessionCwd`).
  - Pinned chats sit in one global Pinned section, and every project list filters them out,
    matching either identity a row carries (`isPinnedSession`, `index.tsx`).
- **Steal** — Almost everything: membership from the backend tree (never re-derived in the
  client), the entered view as the project page, "+" as "new chat here", and the pin matcher's
  two-identity rule (live id or lineage root) for recognising the owner row.
- **Won't copy** — Tap-only-scopes: Alex wants the tap to open the main chat. And the blanket
  pin filter: a pinned owner would vanish from its project ("HME - Orchestrator" is pinned today).
  Also, a separate Projects page would duplicate this list; the entered view already is one.

### 2. Bot Chat in the Webapp (in-tree, the `hermes-bots` desktop plugin)

- **Who / what** — Bot Mode's one permanent chat per bot
  (`apps/desktop/src/plugins/hermes-bots/plugin.tsx`), identity the exact title "Bot Chat"
  (`hermes_state.py`, unique title index in `hermes_state_schema.py`).
- **What they did** —
  - A `composer.middleware` contribution rewrites `/new` and `/reset` (`/^\/(new|reset)\s*$/`) to
    `/compact` with an "This chat never resets" notice, only when the focused stored session is
    the bot's canonical chat; every other chat keeps plain `/new`.
  - The plugin reads the server through `host.request(...)` and keys on
    `host.state.focusedStoredSessionId` (the durable id, after an earlier bug keyed on the
    runtime id and never matched).
- **Steal** — The `/new` → `/compact` middleware nearly line for line, keyed on
  `owner_session_id` instead of the bot roster; the stored-id lesson.
- **Won't copy** — Identity by title. Titles have changed twice (to `CODE - Role`), so the owner
  is a pointer (`projects.owner_session_id`). Also not copied: hiding the chat from the sidebar
  (Bot Mode's session sweep); the owner chat should be more visible, not less.

### 3. Claude Projects (Anthropic)

- **Who / what** — Projects in claude.ai.
  [What are projects?](https://support.claude.com/en/articles/9517075-what-are-projects),
  [How can I create and manage projects?](https://support.claude.com/en/articles/9519177-how-can-i-create-and-manage-projects)
- **What they did** — A project is a workspace with its own chat history and knowledge; its
  main page lists its chats, and project instructions and files apply to every chat in it.
- **Steal** — The project as the entry point, its chats by recency, a new chat from there.
- **Won't copy** — No owner or main chat (every chat is equal), and per-project knowledge uploads
  (Hermes reads project context from the folder's `.hermes.md` / `AGENTS.md`).

### 4. ChatGPT Projects (OpenAI)

- **Who / what** — Projects in ChatGPT. [Projects in ChatGPT](https://help.openai.com/en/articles/10169521)
- **What they did** — A project groups chats and files, with project-scoped instructions; chats
  are moved in explicitly ("Move to project").
- **Steal** — The project list as a first-class place in navigation.
- **Won't copy** — Explicit membership. In Hermes a chat belongs to a project by its folder, and a
  second mechanism would disagree with the backend grouping. No owner chat here either.

## Optional

Dropped since the 2026-11-08 page: the Hermes desktop project sidebar as a separate example (it
is now example 1, since the Webapp is the same code), and the Hermes Mobile pieces (Alex stopped
using the app on 2026-11-11).
