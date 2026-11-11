# v0.23 delta check — session-mail (DER-701)

- Date: `2026-11-11`
- Base checked: `integrate/session-mail-023`, cut from `alex/v0.23.1-canary-1110` (`625906ab22`,
  upstream canary `da06acacc9`), with the fork's v0.22 commits ported
- Design checked: `hld.md` (round 2 and later notes) and `lld.md` (round 4, security accepted)
- Not touched: the live install, its home, keys and services

Paths are relative to the Hermes repository root in this worktree. `intercom:` is the unedited
clone at `ae90a2a`.

## What v0.23 changed underneath us

1. **One process hosts every session of a profile.** The profile's **gateway owner**
   (`hermes gateway run`, started on demand) holds a `SessionAuthority`
   (`gateway/session_authority.py:134`) with a durable per-session FIFO, the "authority FIFO".
   - **Ink TUI and Desktop attach** to it over `/api/ws` (`tui_gateway/AGENTS.md`
     § Process model).
   - **The classic CLI is a client too.** "The gateway builds the agent now … the gateway runs
     the turn" (`hermes_cli/cli_init_mixin.py:310-324`). `PluginManager._cli_ref` is never set
     any more (`hermes_cli/plugins.py:282` is its only assignment).
   - **Messaging chats** are in the same authority.
   - **The dashboard** is mounted inside the gateway listener (`gateway/run_api.py:1-14`).
     A standalone `hermes dashboard` / `hermes serve` backend still exists. Its `/api/ws` uses
     the authority when one is attached, and otherwise falls back to the legacy in-process
     `tui_gateway` dispatch (`tui_gateway/ws.py:377-400`). Its session writes are forwarded to the
     owner (`hermes_cli/web_server_sessions.py:205-240`).
2. **The three delivery modes already exist as canonical client verbs** on the owner's ticketed
   `/api/ws`:
   - `session.steer`, `session.redirect`, `session.interrupt`;
   - `prompt.submit` (queue, or start when idle);
   - `prompt.steer_queued`;
   - `session.resume`, which restores a cold session in the owner.

   They are declared in `tui_gateway/contracts/canonical_sessions.py`, served by
   `gateway/session_busy_controls.py:176-225` (`correct`, verb `steer`/`redirect`, with a
   `rejected` answer meaning "queue it as the next prompt") and
   `gateway/session_authority.py:694` (`submit`), `:934` (`interrupt`) and `:991`
   (`steer_agent`). `Submission.intent` is `"queue" | "steer" | "redirect"`
   (`gateway/session_contract.py:45-50`).
3. **A plugin's keyed `inject_message` becomes a queued producer admission** in the target's
   FIFO (`gateway/run_plugin_injection.py:363-392`, `_admit_plugin_injection` →
   `authority.admit_automation`), for local and messaging sessions alike
   (`_dispatch_plugin_local_injection`, `:233-245`). It never steers or interrupts.
4. **A key-less `inject_message`** (no `session_key`, no `origin`) goes to the session the call
   is working for (`gateway/plugin_keyless_inject.py`, from `f7322744fc`), via
   `gateway.session_context.bound_session_key()`. It only ever reaches the caller's **own**
   session, so it does not replace session-to-session delivery.
5. **New `PluginContext` methods:** `session_surface()`, `session_cwd()`, `post_message()`,
   `ask_choice()` (`hermes_cli/plugins_context.py:395-430`). `PluginContext` moved from
   `hermes_cli/plugins.py` to `hermes_cli/plugins_context.py`.
6. **Boundary lint.** A bundled plugin may import only names in
   `hermes_cli/data/plugin_api.json`, and CI fails otherwise (`scripts/boundary_lint.py`,
   `plugins/AGENTS.md` § Boundary lint). That applies to vendored `plugins/intercom`.
   - **Listed:** `hermes_constants`, `hermes_state`, `plugins.plugin_storage`,
     `gateway.status`.
   - **Not listed** (the LLD uses them): `tools.thread_context`, `hermes_cli.active_sessions`,
     `agent.prompt_builder`, `hermes_cli.gateway_client`, `hermes_cli.gateway_runtime`,
     `hermes_cli.input_sanitize`, `hermes_state_titles`.
7. **No peer messaging and no inject `mode` upstream** in v0.23 core: no `peer_messaging`
   tool, and `inject_message` has no `mode`. miyu4u's fork (`gateway_peers.py`) is a client of
   the owner's `/api/ws` through `hermes_cli.gateway_client` / `discover_gateway_endpoint`,
   which all exist here.

## Table

| LLD section | v0.22 reference | v0.23 status | What the LLD must change |
|---|---|---|---|
| B1 seam signature | `PluginContext.inject_message` in `hermes_cli/plugins.py:~602` | **moved**: `hermes_cli/plugins_context.py:395` | Path (applied). The design question is below (D-1) |
| B1 consent read | `_gateway_injection_allowed`, `hermes_cli/plugins.py:622-630` | **moved**: `plugins_context.py:431-439`, same logic | Path (applied) |
| B1 routing table (`inject_plugin_message`) | CLI branch via `_cli_ref`; tui slot; gateway slot | **changed**: `_cli_ref` is never set (dead branch); new key-less branch; every keyed target goes to the authority's queued admission | **Design (D-1):** the per-host table collapses to one host, the authority |
| B1.1 tui_gateway host | `inject_tui_session_message`, `_handle_busy_submit` (`session_auto_continue.py:400-455`), `_load_busy_input_mode` | **unchanged** code at the same lines; `prompt.submit`'s author check moved to `methods_prompt.py:844-848` | Paths (applied). It applies only to a standalone dashboard or serve backend **without** an authority. Whether the live dashboard is that, or the gateway-mounted one, is a Trial question (D-1) |
| B1.2 classic CLI host | `_tui_enter_while_busy` (`cli_tui_mixin.py:1505-1551`), `_cli_ref` | **changed**: `_tui_enter_while_busy(..., mode=None)` at `:1475` already takes a mode, but the CLI no longer hosts its session, so plugins cannot reach it | **Design (D-1):** drop the CLI host; CLI sessions are delivered by the authority |
| B1.3 gateway host | internal-event branch `run_busy.py:843-849`; `_dispatch_plugin_message_injection` | **changed**: the branch is at `run_busy.py:985`; plugin injection goes through `_admit_plugin_injection` (authority FIFO) | **Design (D-1):** a mode would go on the authority admission (`admit_automation` with an intent), or through the canonical verbs |
| B1 `ctx.session_chat_scope` / `gateway/chat_scope.py` | new | still new; inputs exist: `sessions.origin_json`/`transport_profile` (`hermes_state_common.py:479,524`), `gateway_routing` (`:651`), `restore_identity` (`gateway/session_identity.py:161-167`), `_restored_source` (`gateway/authz_mixin.py:462`) | Paths (applied); the design holds |
| B2 wake module | `scripts/dashboard_dispatch.py` and the agent key, dashboard `/api/ws` | **ported** (`21c985667c`, `2b67caf851`, `39854e8929`); but the owner restores cold sessions itself (`session.resume` in the authority) | **Design (D-2):** waking "live nowhere" becomes `session.resume` plus `prompt.submit` against the owner. The agent-key path may not be needed. TB-1, F2's wake clause, F8, F13 and F14 would change |
| B3 registry / lease lookup | intercom one entry per process; `runtime/active_sessions.json` lease `pid` | **changed in effect**: all local and messaging sessions live in the owner, so every lease pid is the owner's | **Design (D-3):** lease-pid routing becomes "the profile's owner" (`discover_gateway_endpoint`); the gateway role (F11) and peer-pid binding (F3) need rethinking |
| B4 routing / envelope v2 | socket to the lease pid; gateway step; wake | **changed**, as D-3 | **Design (D-3)** |
| B5 addressing | `get_session_by_title`, `resolve_session_id`, `get_compression_tip` | unchanged (`hermes_state_titles.py`, `hermes_state_sessions.py`) | None |
| B6 framing; relabel | `STEER_MARKER_OPEN`, `STEER_CHANNEL_NOTE` ("same authority"), `CONTROL_FRAME_OPENERS` (`prompt_builder.py:561-611`, `:571-574`) | **unchanged in content**, lines `:562-608`, `:572` | Paths (applied); A′ still needed. `CONTROL_FRAME_OPENERS` is not in `plugin_api.json` (D-4) |
| B6 steer buffer | `AIAgent.steer(text)` joins under one marker (`interrupt_control.py:267-278`) | **changed**: `steer(text, *, ticket=None)` at `:310`, per-part `(ticket, text)` buffer (`:91-120`), `withdraw_steer(ticket)` at `:419` | None for the design: still one marker per drain; tickets are a delivery detail of the authority |
| B6 field sanitising | `sanitize_title` (`hermes_state_titles.py:49-61`) | **moved**: `:62` | Path (applied); not in `plugin_api.json` (D-4) |
| B7 record | `plugin_db` (`plugins/plugin_storage.py:36`), `_secure_state_db_files` (`hermes_state.py:243-298`) | unchanged / **moved** to `:247` | Path (applied) |
| B8 reply hook | `post_llm_call` (`turn_finalizer.py:453-479`) | **moved**: fires at `:474-495`, same payload | Path (applied). It now runs in the owner for every session, so the reply hook is always in one process |
| B8 silence | `SILENT_MARKER` (`cron/scheduler.py:526`) | **moved**: `:542` | Path (applied) |
| B9 / B11 Tool Search catalog | `_short_desc`, 60 characters (`tool_search_catalog.py:215`) | **changed**: `CATALOG_SUMMARY_MAX_CHARS = 80` (`:217`), `_short_desc` at `:220`; `tools.tool_search.enabled` still `auto` | Wording only: the 60-character sentence still fits (applied) |
| B10 caps | intercom `inbox.py:35-39`… | unchanged (intercom unedited) | None |
| Reapers | `ws_orphan_reap_grace_s`, queued-prompt budget (`tui_gateway/server.py:165`) | **unchanged** at `:149`, `:160`, `:171` (legacy tui path); the authority's FIFO has its own durable recovery (`gateway-internals.md`, "started admission … interrupted") | None for the design; the loss cases move to the authority (Persistence row) |
| gateway session store | `lookup_by_session_id` (`gateway/session.py:1311`) | **moved**: `:1374` | Path (applied) |
| `get_running_pid` (F11) | `gateway/status.py:2022` | **moved**: `:1953` | Path (applied); F11 may be moot (D-3) |
| hosted-room relabel model | `gateway/hosted_room_discussion.py:44-47` | **moved**: `:48` | Path (applied) |
| redirect support flag | `agent/agent_init.py:544` | **moved**: `:434` | Path (applied) |
| gateway publishes its host | `gateway/run_startup.py:1654`, `plugins.py:1242` | **moved**: `run_startup.py:1776`, `plugins.py:356` | Path (applied) |
| `_run_async` 300 s limit | `model_tools.py:94-135` | **moved**: `:95` | Path (applied) |
| `bot_live_delivery` | durable tickets, `find_canonical_owner` | **changed**: rewritten over the authority (`authority_delivery`, `find_canonical_live_owner`) | None (only a comparable) |
| Intercom itself | `ae90a2a` | **loads** on v0.23 (tool and both hooks registered, socket bound in a temp home). **17 of 17 tests pass**. But in the owner it finds no `HermesCLI`, so it would park every message and drain it into whichever session runs next | Confirms why the LLD replaces parking; no change |

## Design items (left Open; not applied)

- **D-1: the seam.** With one host, either:
  - **(a)** a smaller core seam: the authority's plugin admission takes an intent
    (`queue`/`steer`/`redirect`, plus interrupt) and reports what it applied; or
  - **(b) no behaviour patch at all:** intercom delivers as a **client of the profile's owner**
    (`hermes_cli.gateway_client.connect_gateway`, ticket from the same-user control socket),
    using the canonical verbs. The fallback chain is intercom's: `session.redirect`, else
    `session.interrupt` plus `prompt.submit`; `session.steer`, else `prompt.submit`. That is
    miyu4u's approach.

  (b) still needs `hermes_cli.gateway_client` / `gateway_runtime` published in `plugin_api.json`,
  or an equivalent `ctx` method (boundary lint, D-4). Recommended: (b), because it reuses
  upstream's verbs and is closest to what intercom forks already do.
- **D-2: the wake path.** A cold session is restored by the owner (`session.resume`), so the
  dashboard dispatcher and agent key are not needed for waking. TB-1 shrinks to "same-user
  control socket, ticketed `/api/ws`".
- **D-3: routing.** Lease-pid and per-process sockets give way to "the profile's owner"
  (`discover_gateway_endpoint`). Sender identity comes from the calling session's context (a
  tool runs in the owner) or the ticket's subject (a CLI script). F3's peer-pid binding and
  F11's gateway-pid check are replaced by the owner's own authorisation
  (`authorize(actor, ref, …)`).
- **D-4: boundary lint.** Each core name intercom needs that is not in `plugin_api.json`
  becomes either a `ctx` method or a listed name, each in its own PR (`plugins/AGENTS.md`):
  `tools.thread_context`, `hermes_cli.active_sessions` (maybe unneeded after D-3),
  `agent.prompt_builder:CONTROL_FRAME_OPENERS`, `hermes_cli.gateway_client`,
  `hermes_cli.gateway_runtime`, `hermes_cli.input_sanitize`, `hermes_state_titles`.
- **Trial round 3 (v0.23), needed before the LLD is rewritten:**
  - which process hosts dashboard chats on the live canary (the gateway-mounted dashboard, or a
    standalone backend using the legacy `tui_gateway` path);
  - whether a plugin running **in the owner** can open a client connection back to its own
    owner, and drive steer, redirect and queue on local and messaging sessions;
  - whether `session.steer` / `session.redirect` reach messaging-platform sessions for an
    operator principal;
  - `post_llm_call` for authority-run turns;
  - the reply route back.

## Trial round 3 (2026-11-11): answers

The full note is `poc/round3/poc.md`. Run 6 passed 20 of 24; run 7, 6 of 6.

- **Hosts.** The owner hosts owner-attached (Ink/Desktop), classic CLI and messaging sessions.
  A standalone `hermes dashboard` hosts **its own** chats in-process (legacy `tui_gateway`). The
  live canary runs that layout: `hermes-dashboard.service` runs agent turns itself, next to
  `hermes-gateway.service`. **Live has two hosts.**
- **D-1 (b) works for every owner-hosted kind** from inside the owner, with the owner's existing
  verbs: steer, redirect (as interrupt), queue, idle start, and a cold start after an owner
  restart.
  - The owner refuses dashboard-hosted chats (`runtime_coordination_required`).
  - Those are reached through the dashboard: its own `ctx.inject_message` (queue/start), or its
    agent-key `/api/ws` (steer/queue).
  - The published `ctx.inject_message` in the owner returns `True` but never runs a message
    addressed by session id, and is queue-only anyway.
- **Replies:** `post_llm_call` fires in the hosting process. Replies from the owner's hook
  reached senders of other owner-hosted kinds.
- **Core patch:** **no behaviour change** for owner-hosted sessions. Only `plugin_api.json`
  listings (or a `ctx` wrapper) are needed for `hermes_cli.gateway_client:connect_gateway` and
  `hermes_cli.gateway_runtime:discover_gateway_endpoint`, plus the framing helpers (or an
  in-plugin copy).

**Recommendations:**
- **D-1:** option (b), intercom as a client of the owner with its existing verbs; no behaviour
  patch. Settled decision 11's core seam is replaced by listing PRs. For dashboard-hosted chats:
  keep the fork's agent-key dashboard route **or** move the dashboard under the owner
  (**new question for Alex, SM-Q18**).
- **D-2:** wake = owner `session.resume` + `prompt.submit` (cold start proven). Dashboard-only
  sessions use the dashboard route.
- **D-3:** route by host. Try the owner verbs; on `runtime_coordination_required`, use the
  dashboard route. Owner sessions have no lease; dashboard sessions have the dashboard's lease.
  Lease-pid routing, per-process sockets, F3's peer-pid binding and F11's gateway pid are
  replaced by the owner's own authorisation (actor plus session ref) and the dashboard's agent
  key.
- **D-4:** listing PRs for `connect_gateway` and `discover_gateway_endpoint` (or one `ctx`
  method), each with docs and a behaviour test. Use stdlib `contextvars` instead of
  `tools.thread_context`. Copy or list the three framing helpers.

## Verdict

**The shape changes.** Alex's decisions all still hold:
- the intercom base;
- three modes with fallback, default steer;
- A′ framing and the relabel rule;
- automatic replies with `[SILENT]`;
- the record;
- addressing;
- the chat rule.

The security fixes that concern content (F1, F4, F5, F6-style in-process typing, F7, F10) also
still apply.

What changes is the layer underneath. In v0.23 one gateway owner per profile hosts every session,
including the classic CLI, and already offers steer, redirect, interrupt and queue as client
verbs, with cold-session restore. So:
- the per-host seam (D-1);
- the dashboard wake path (D-2);
- lease-pid routing over per-process sockets (D-3)

should be replaced, not ported. And the vendored plugin must respect the new boundary lint
(D-4). That changes settled decision 11 ("one small core seam on every host"), and possibly the
need for a core seam at all. **Alex needs to see it**, after a short v0.23 Trial.

Mechanical edits (moved paths and lines) are applied to `lld.md` and `hld.md`. D-1 to D-4 are
added to the HLD's Open section. Nothing in the design was rewritten.
