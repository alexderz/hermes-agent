# Comparables — project-centric Hermes UI

How others have done a thing like this. **Before** locking HLD shape
(and UX, if there are screens). Real examples with sources — not "industry
standard."

- Slug: `project-centric-ui`
- Brief / options map: `docs/project-centric-ui/brief.md` (Options map; prior art: Claude Projects, ChatGPT Projects)
- Date: `2026-11-08`

## Required

### 1. Claude Projects (Anthropic)

- **Who / what** — Projects in claude.ai.
  [What are projects?](https://support.claude.com/en/articles/9517075-what-are-projects),
  [How can I create and manage projects?](https://support.claude.com/en/articles/9519177-how-can-i-create-and-manage-projects)
- **What they did** — A project is a self-contained workspace with its own chat history and
  knowledge base. The project's main page lists its chats and holds the knowledge panel;
  instructions and files apply to every chat in it. Chats in a project do not share context
  with each other unless it is added to the project knowledge.
- **Steal** — The project page is the entry point: open the project, see its chats by recency,
  start a new chat from there. Context is attached to the project, not to one chat (for us,
  the project folder's `.hermes.md` / `AGENTS.md` already do that job).
- **Won't copy** — There is no owner or "main" chat; every chat is equal. Alex wants one
  permanent chat on top. Per-project knowledge uploads and instructions are out of scope
  (Hermes reads them from the folder).

### 2. ChatGPT Projects (OpenAI)

- **Who / what** — Projects in ChatGPT.
  [Projects in ChatGPT](https://help.openai.com/en/articles/10169521)
- **What they did** — A project groups chats and files, with project-scoped instructions that
  override global ones. Existing chats can be moved in ("Move to project").
- **Steal** — Membership is explicit and visible; the project list is a first-class place in
  navigation, not a filter on History.
- **Won't copy** — Explicit "move a chat into a project". In Hermes, membership falls out of
  the session's folder (`cwd` / git root against project folders); a second membership
  mechanism would disagree with the backend grouping that Alex says already works. No owner
  chat here either.

### 3. Hermes Bot Chat (in-tree, desktop app and Hermes Mobile)

- **Who / what** — The long-lived "Bot Chat" session. Identity is the exact title `"Bot Chat"`
  (`hermes_state.py`, unique title index in `hermes_state_schema.py`). The desktop composer
  rewrites `/new` to `/compact` for it (`apps/desktop/src/plugins/hermes-bots/plugin.tsx`);
  Hermes Mobile does the same by title (`ui/chat/ChatViewModel.kt`) and opens a bot's canonical
  chat from its roster (`ui/bots/BotsScreen.kt`) — repo
  [Hy4ri/hermes-mobile](https://github.com/Hy4ri/hermes-mobile).
- **What they did** — One permanent chat per bot that "just compacts"; tapping the bot opens it.
- **Steal** — Tap-to-open the canonical chat; the app's existing `/new` → `/compact` path, which
  the issue draft can ask the app to reuse for owner chats (brief Q1).
- **Won't copy** — Identity by title. A title is renamable and collides with existing titles
  ("Model Master"); a pointer (`owner_session_id`) survives renames.

### 4. Hermes desktop app's project sidebar (in-tree)

- **Who / what** — The Electron app groups sessions by project from `projects.tree`
  (`apps/desktop/src/app/chat/sidebar/index.tsx`, `sidebar/projects/workspace-groups.ts`).
- **What they did** — The backend already computes the authoritative project → sessions tree
  (`tui_gateway/project_tree.py`); the desktop renders it, and only the desktop calls it today.
- **Steal** — Read the same tree (`GET /api/profiles/projects/tree`) instead of re-deriving
  membership in a client. Hermes Mobile's own grouping rules (`ui/sessions/SessionProject.kt`)
  are exactly what produce the wrong "hermes" group; the shared tree avoids that class of bug.
- **Won't copy** — The desktop's lane/worktree structure (repos → groups → lanes). The phone
  needs a flat list: owner on top, then recent sessions.

## Optional

Note on the mobile landscape (context for the delivery decision, not a comparable): an official
Nous Hermes mobile app is in beta ([review](https://www.tonyreviewsthings.com/hermes-mobile-beta-review/)),
and upstream has an open pull request for a WebView mobile shell around the desktop renderer
([NousResearch/hermes-agent#52673](https://github.com/NousResearch/hermes-agent/pull/52673)).
The community app is on [F-Droid](https://f-droid.org/packages/com.m57.hermescontrol/).
