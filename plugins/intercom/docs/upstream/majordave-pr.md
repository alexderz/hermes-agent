# Draft: pull request to majordave/hermes-intercom

Status: nothing was posted, opened, or commented. This file is for review only. No pull request exists.

Where it would go: a pull request to <https://github.com/majordave/hermes-intercom>, onto current main (`ae90a2a`, v0.2.0).

Suggested title: Deliver through the profile's gateway owner (v0.3.0)

Asks: review and merge the v0.3.0 plugin. The change is the owner client, the A′ frame, replies, the removed caps, and the legacy socket path kept for a Hermes build that has no owner client. Echo, the CLI, the tool text, addressing, the chat rule, and the record ship with them.

Compared with `ae90a2a`:

- New: `client.py`, `route.py`, `address.py`, `scope.py`, `frame.py`, `echo.py`, `record.py`, `replies.py`, `cli.py`, and `tests/test_client.py`, `test_route.py`, `test_address.py`, `test_scope.py`, `test_frame.py`, `test_echo.py`, `test_record.py`, `test_replies.py`, `test_cli.py`.
- Changed: `__init__.py`, `inbox.py`, `plugin.yaml` (version 0.3.0; hooks `post_llm_call`, `pre_llm_call`, `pre_api_request`).
- Unchanged at the time of the draft: `README.md`, `docs/findings.md`, `tests/test_protocol.py`. The PoC guide that was `docs/AGENTS.md` is now `docs/agents-guide.md` (same text, renamed so a host AGENTS chain does not load it). The README and the manifest description still describe the socket inbox.

## Text to post

## Summary

On a Hermes build that publishes `hermes_cli.gateway_client.connect_gateway` and `hermes_cli.gateway_runtime.discover_gateway_endpoint`, intercom delivers through the profile's gateway owner. The `intercom` tool keeps `list`, `send`, `ask`, and `reply`. `hermes intercom` is the script client.

The Unix-socket inbox, the registry, and the GC lookup of `HermesCLI` stay. They run only when those two names cannot be imported, and only beside a classic CLI. An owner that is down is `no-owner` or `owner-restarting`. The plugin does not fall back to the socket.

Version 0.3.0. Default delivery is `steer`. There is no message-length cap, no per-sender rate cap, no identical-message dedupe, no hold, no retry, and no approval gate on delivery. An empty message is refused. `[SILENT]` sends nothing back.

The README and the one-line manifest description still describe the socket inbox. They should be rewritten before this is announced as the current behavior.

## Owner client

`client.py` is the client.

- `discover_gateway_endpoint(get_hermes_home(), timeout=2.0)` is read-only. It never starts an owner. No endpoint is `no-owner` (exit 5). A `starting` or `draining` endpoint is `owner-restarting` (exit 5).
- `connect_gateway` is called with that endpoint only. `None` would start an owner or honor `HERMES_TUI_GATEWAY_URL`. This module never reads `HERMES_TUI_GATEWAY_URL`.
- The call runs `asyncio.run` on a fresh thread started with `contextvars.copy_context().run`, so the caller's profile context carries over.
- Every delivery starts with `session.resume` and `omit_messages: true`. Only `running` and `execution_generation` are read. Nothing else from the handle is logged, returned, or put in an error string.
- `submission_id` is `intercom-<message id>`. The owner admits it once. Nothing is re-sent.

An idle target always starts a turn.

| Requested | Target running | Calls | Applied |
|---|---|---|---|
| any | no | `prompt.submit` | `start` |
| `queue` | yes | `prompt.submit` with `queued: true` | `queue` |
| `steer` | yes | `session.steer`. `queued` is done. `rejected` falls through to a queued submit | `steer`, or `queue` |
| `interrupt` | yes | `session.redirect`. `redirected` is done. `rejected` is `session.interrupt`, then a queued submit | `interrupt` / `redirect`, or `interrupt` / `hard-interrupt` |

`stale_generation` on steer or redirect resumes once more and applies the idle row. That is one sequence, not a second send.

`admission_id` is `prompt.submit`'s id when the sequence ends in a submit, and `None` when steer or redirect took the message.

Owner refusals:

| Owner answer | Detail | Exit |
|---|---|---|
| `runtime_coordination_required` | `not-addressable` | 4 |
| `permission_denied`, `unsupported_control`, `invalid_params`, and any other refusal | `refused-by-owner`, code kept | 4 |
| connection lost before the verb was sent | `not-reachable` | 5 |
| connection lost after the verb was sent | `delivery-unknown` | 6 |

Error text is a fixed sentence plus the exception's type name. A connect error is never stringified (that string can carry a URL or a ticket). `GatewayRPCError`'s own `str()` is the owner's bounded reason code, and that code is kept.

`list_sessions` is a read-only `session.list`. `receipt` is a read-only `prompt.receipt` (`queued`, `started`, `terminal`, or `unknown`).

## Send path

`route.send` is the one path for a tool call and for the CLI.

1. A tool `send` with no `reply` is `reply-missing` and records nothing. `optional` is set only when the caller is the reply hook.
2. An empty or whitespace-only message is `empty`.
3. `address.resolve` picks a target: exact title or `Home`, then a session id or id prefix, then `@<slug>` only when project addressing is available. Anything else gets the closest titles. The sender's own session is `own-session`. Several matches, or none, send nothing and return candidates.
4. Chat scope is read for the target and, for a session sender, for the sender.
5. Every delivery requires `plugins.entries.intercom.allow_gateway_injection: true`, read fresh. Otherwise `injection-off`. Local sessions are included. Classic CLI is no longer a host, so nothing is exempt.
6. The record row is written before delivery.
7. The frame is built, `sanitize_user_prompt_text` runs once, and the SHA-256 of the span from the header line through `📡 End of message <id>` is stored.
8. `client.deliver_sync` runs.
9. The row is updated and the receipt is returned, including the target session id.

Project addressing is on only when the configured projects plugin is enabled and `projects.owner_session_id` exists. The tool text is chosen at `register()` from that check. Every resolve checks again. Without it, a `to` that starts with `@` is `project-addressing-unavailable` and is never tried as a title. A project with no owner session is `no-owner-set`.

The owner admits this client as operator input and does not re-check a chat's current platform allowlist. A messaging chat that is not listed in settings is framed as shared, and it is not echoed.

## A′ frame

`frame.build` returns the text the target reads and a separate echo (header line plus the body). Every submitted text starts with `📡`.

Header line, session sender:

`📡 Not <user_name> · [interrupt asked · ]<reply label> · hermes@<title> says (session <id> · [reply to your message <id> · ]message <id>):`

A script sender (the CLI always frames as a script) is `hermes@script <label> says (message <id>):`. A messaging-platform sender adds the platform and chat type, for example `hermes@<title> (Telegram DM)`.

Reply labels: `no reply needed`, `reply requested`, `waiting on your reply`, `reply optional`. An `ask` is labelled `sender paused: use intercom reply`.

After the header: the authority line (a peer note, or a script note, naming the configured user); the interrupt note only when interrupt was asked; the shared-chat line when the target chat is shared; a blank line; the relabelled body; the footer for that reply mode; `📡 End of message <id>`.

`none` tells the target that nothing will be sent back. `requested` and `waiting` ask for a `[REPLY <id>]` block and otherwise send the whole answer. `waiting` adds that the sender cannot go on until the answer. `optional` sends only a block. A reply to a script or to a finished run (`cron`, `oneshot`, `subagent`) says the reply is stored. An `ask` footer tells the target to call `reply` with the request id, which is the ask's message id.

`user_name` comes from settings. The authority line uses the pronoun "his". The tool description addresses the operator as Alex. Interpolated fields are cleaned (control characters, the marker, brackets); an empty field becomes `unknown`. `sanitize_title` is copied into the plugin, because it is a `SessionDB` method and not a module-level name.

Relabel, on the body:

- A line whose visible start is `📡`, or `Not <user_name> … says`, is prefixed with `[quoted] `. Invisible prefixes (Cf, Zs, Mn, space, tab) do not hide that.
- A `[` that opens a Hermes control frame becomes `[peer-quoted `. The pattern is built from `CONTROL_FRAME_OPENERS` with `re.IGNORECASE`, the same way hosted rooms build it. When that name cannot be imported, a literal fallback tuple is used.
- Leading echoed headers (`📡 Not … says (` and the legacy `📡 hermes@… says:`) are stripped before relabel.

The echo is escaped for the platform at post time (`escape_echo`). Telegram (MarkdownV2 or HTML), Discord, and Slack break links and `@everyone` / `@here` before the adapter renders them. A platform with no escaper returns `None`, and nothing is posted.

## Replies

`replies.py` registers `post_llm_call` in the owner.

The hook finds spans in the turn's user text and in later `display_kind: "steer"` rows: a line `📡 Not … message <8 hex>):` through `📡 End of message <id>`, whose SHA-256 equals the row's `header_sha`. A `send` whose `reply` is not `none`, whose reply state is still empty, and whose target is this session or its compression lineage is a candidate. A `none` note is never a candidate.

- `requested` and `waiting`: the `[REPLY <id>]` block, otherwise the whole answer. A sender in a shared chat gets the block only. With no block, the reply is stored as `shared-chat-no-block` and nothing is sent.
- `optional` (this message is itself a reply): the block only. With no block, `no-block` and nothing is sent. A debate continues only while a side writes a block.
- Empty text, or `[SILENT]` as the whole text or its first or last line, is `silent`. Nothing is sent.

The reply is stored, then delivered on a fresh thread with `route.send(..., delivery="steer", reply_mode="optional", reply_to=<id>)`. `cron`, `oneshot`, `subagent`, and script senders are stored only. Nothing is retried. Stopped and failed turns do not fire the hook.

`ask` still blocks the caller's tool until `reply`, a timeout, or `[SILENT]` ("nothing to add"). The waiter is in-process. A `reply` is accepted only when the tool call's own session id is the ask's target, or is in its compression lineage. The CLI has no `ask`. A `send` with `reply: waiting` returns at once; the answer arrives later as its own message.

## Echo

`echo.py` posts into a private chat from the target's own turn, through the published `ctx.post_message`. That call posts only into the session bound to the caller, so the hook has to run on the target's turn.

- Queued or started messages, and a steer that lands as a later turn: `pre_llm_call` when the prompt carries the header.
- A steer inside the running turn: the first `pre_api_request` whose request messages carry the steer row.

The row's `target_chat_scope` must be `private`. `claim_echo` sets `echoed_at` once, so a later request does not post again. The post is scheduled on a thread. A failed or refused post is logged and does not change delivery. A shared chat gets the shared-chat line in the model text and no post.

These hooks do not drain the legacy inbox.

## Caps removed

In `inbox.py`, on the legacy path as well as the owner path:

- `_MAX_MSG_CHARS` (8000) is gone. The body is not sliced, and the socket read is not cut at four times that size.
- The per-peer rate window (6 messages in 60 seconds) is gone.
- The identical-message dedupe window (120 seconds) is gone. `send_to` still accepts `dedupe` so `reply_to` can pass it, and the flag does nothing.

`_PENDING_CAP` stays at 10, and only inside this legacy inbox. A build that can import the owner client never starts that inbox.

## Legacy path kept

`register()` chooses by capability, not by whether an owner is listening. If `connect_gateway` and `discover_gateway_endpoint` import, the process is on the owner path for its whole life. A missing owner then is `no-owner` or `owner-restarting`, exit 5.

If those names cannot be imported, the first `intercom` call may start the socket inbox:

- `settings.inbound: never` does not start it.
- It starts only when the existing GC lookup finds a classic `HermesCLI` in this process. No argv is read.
- A gateway, dashboard, or other multi-session process gets `no-seam` (exit 4) and starts no socket.
- The legacy `pre_llm_call` drain and `on_session_end` are registered in that same step, and only then.

The CLI is an owner client. It has no socket fallback. `tests/test_protocol.py` is unchanged and still covers the legacy protocol.

## CLI and tool text

`hermes intercom send|list|status|log`.

- `send` takes `--reply none|requested|waiting` (default `none`) and `--delivery interrupt|steer|queue` (default `steer`). `--no-reply` is a usage error. The sender in the frame is `script` plus `--from` (default `cli`).
- `list` prints id, title, project, last active, and state, newest first, 30 by default. Cron, subagent, and oneshot runs are omitted unless `--include-runs`. `--query` filters on title or project.
- `status <id>` reads `prompt.receipt` when there is an admission id, otherwise a read-only transcript check for the span hash. It writes nothing and sets no timer. Exit 1 when the id is unknown.
- `log` prints the same record, including a stored reply that was not delivered.

Exits: 0 delivered, 1 unknown message id from `status`, 2 usage, 3 address or empty or missing reply, 4 the owner refused it, consent is off, or the legacy process has no CLI (`no-seam`), 5 not delivered, 6 the verb was sent and the answer was lost.

The tool's first sentence is `Message another Hermes session; never send an empty message.` `reply` is required for `send` and has no default. `delivery` defaults to `steer`. The interrupt help text is: "Only use interrupt when you intend to stop what the other session is doing right now (it is wrong, or the work is obsolete). Otherwise use steer (default) or queue." The handler is synchronous. The sender is the tool call's session id.

## Record

One SQLite file, `plugin-data/intercom/record.db`, created mode `0600` with its sidecars, directory mode `0700`. The sender writes the row, the frame hash, and the delivery result. The reply hook writes the reply fields and the new reply row. `claim_echo` sets `echoed_at` once. Nothing is pruned and nothing is retried.

## Tests

The new modules are unittest, same as the existing suite. They cover the mode table and the error mapping, the send steps, addressing, the chat rule, the frame and the relabel, the echo claim, the record permissions, reply modes and silence, and the CLI exits. The legacy protocol module is untouched.
