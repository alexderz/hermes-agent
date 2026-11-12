# LLD — session-mail: session-to-session messaging, built on intercom (gateway only)

- Slug: `session-mail` (chunk working name; the shipped plugin is `intercom`)
- HLD: `docs/session-mail/hld.md` (round 3, gateway only)
- UX: `docs/session-mail/ux.md` (round 7); stories `docs/session-mail/stories/sm-01` … `sm-22`
- Trials:
  - `docs/session-mail/poc/poc.md` (round 1, v0.22);
  - `poc/round2/poc.md` (round 2, v0.22);
  - **`poc/round3/poc.md` (round 3, v0.23: the base of this design)**.
- Base: `integrate/session-mail-023`, from `alex/v0.23.1-canary-1110`
- Tickets this LLD covers: Epic `DER-701`. Items G-1 … G-13 below; the manager files them at Groom
- Date: `2026-11-11` (round 7: security notes N6-1, N6-2 and the steered-echo gap GW-4; round 6: security review round 5 folded in; round 5: gateway only, SM-Q20)

## Round 7: security round 6 notes and the steered-echo gap

Security round 6 accepted the trust boundaries at `6ccea9121f`. R5-2 / O23 is Alex's decision
with the LLD (SM-Q18).

| Item | Where |
|---|---|
| **N6-1:** the capability check fails safe on an in-between build | B12 states it; G-10's simulated old build makes the names **absent** (the import fails), the only legacy trigger |
| **N6-2:** keep the escaper list beside the escapers | B6: `frame.ECHO_ESCAPERS` is the one list; a platform missing from it gets no echo plus one warning; G-6 tests the warning |
| **GW-4 (UX "For the architect" 1):** a steered message whose turn ends without another tool step is never echoed | **Fixed in the plugin** (B6): the steered echo is posted from `pre_api_request`, which fires before every model request, including the one that writes the final answer. A steer too late for any request becomes a later turn and is echoed by `pre_llm_call`. No core change; `pre_api_request` is a documented hook registered through `ctx` |

## Round 6: security review round 5 (on `b8e1f2ed38`)

| Finding | Where fixed |
|---|---|
| **R5-1 (blocker):** legacy inbox chosen by load-time liveness, so it could start in the owner or the admin dashboard | **B12:** the legacy path is chosen by **capability**: only on a build whose owner-client names are not importable, never by liveness. It never starts in a multi-session host, and its `pre_llm_call` drain is registered only together with it. Tests in G-10 and G-2 |
| **R5-2:** the current-authorisation recheck for chat targets is gone | **Option (b), stated for Alex:** no published predicate exists (`_is_user_authorized_for_source` is a runner method, and "listings only" rules out a new core function). New TB-4 row "operator power"; G-3 test pins it; HLD O23 asks Alex to accept it with the LLD (SM-Q18) |
| **R5-3:** consent narrower than v0.22, and the LLD said "as before" | **B2 step 3:** `allow_gateway_injection` is now required for **every** delivery, matching every v0.22 host apart from classic CLI, which is no longer a host. No source test, so nothing to fail open |
| **R5-4:** `session.resume` returns the whole transcript | **B1:** `session.resume{omit_messages: true}`; only `running` and `execution_generation` are read; nothing from the handle reaches a receipt, a log or an exception text. G-2 asserts it |
| **R5-5:** `connect_gateway(None)` would start an owner or dial a remote URL | **B1 invariant:** always the discovered endpoint, never `None`; `HERMES_TUI_GATEWAY_URL` is never read. G-2 asserts it |
| **N1:** a forger can also write the record | F3 row: "…which only the Hermes user can write" |
| **N2:** inertness rests only on the leading `📡` | B5: an invariant, plus G-7 and G-3 assertions that every submitted `text` starts with `📡` after `sanitize_user_prompt_text` |
| **N3:** echo escaping must match each adapter | B6: escaping per platform renderer; G-6 runs the cases through the real ntfy adapter, plus per-platform unit tests for the platforms in `echo_chats` |
| **N4:** the owner must never post operator input to the chat | G-6 E2E: after a delivery into an unlisted group, the fake ntfy server received only the turn's answer |

## What changed in round 5, and why

Alex settled on 2026-11-11:
- **SM-Q20, gateway only.** On the live v0.23 install, every chat surface Alex uses runs in the
  profile's **gateway owner**: the Webapp at the main hostname (served by the gateway,
  `webapp.enabled`, listener 127.0.0.1:9120), desktop, Ink TUI, classic CLI and messaging. The
  old standalone dashboard stays only as an admin panel. Chats started there are **not
  addressable** by intercom: the owner refuses them (`runtime_coordination_required`, Trial
  round 3), and intercom reports `not-addressable` with no dashboard leg.
- **SM-Q22.** Hermes Mobile is dropped and out of scope.
- **No core behaviour patch.** This replaces settled decision 11. The only core changes are
  `plugin_api.json` listing PRs, each upstreamable with docs and a behaviour test.

Trial round 3 showed what the design rests on. From **inside the owner**, intercom drives every
mode for owner-hosted sessions with the owner's **existing canonical verbs**, and replies route
back from `post_llm_call` in the owner.

**Removed** (each was correct for v0.22 and has no place on the v0.23 gateway; see § Removed
security fixes):
- the core seam: `inject_message(mode=…)`, `InjectResult`, the tui, CLI and gateway host branches,
  `InjectedDelivery`, and the `run_busy.py` change;
- the fork-only wake module (`hermes_cli/dashboard_dispatch.py`), the agent-key wake path, and
  the dashboard route;
- lease-pid routing, per-process socket routing, envelope v2, the gateway endpoint role, F3's
  peer-pid binding and F11's gateway pid;
- `gateway/chat_scope.py` and `ctx.session_chat_scope`, `ctx.injection_allowed` (core
  additions): the chat rule moves into the plugin;
- the gateway-side echo in core: the echo moves to the published `ctx.post_message`.

**Kept unchanged:**
- Alex's decisions (intercom base; three modes with fallback, default steer, idle start;
  addressing; replies and `[SILENT]`; no caps; record; CLI);
- the A′ framing and the one relabel rule;
- the record schema (two columns change);
- addressing;
- the chat rule for messaging sessions;
- replies;
- the CLI and its exit codes;
- the Tool Search wording;
- the caps removal;
- the O17 correction (a queued message shows once; transcript reads filter
  `active = 1 OR compacted = 1`).

Paths without a prefix are in **alexderz/hermes-agent** (`integrate/session-mail-023`).
`intercom:<path>` is **alexderz/hermes-intercom** (fork of `majordave/hermes-intercom` at
`ae90a2a`); after vendoring, the same file is `plugins/intercom/<path>`.

## Required

### Paths / modules

**alexderz/hermes-agent: listing PRs only (no behaviour change)**

| Path | Change |
|---|---|
| `hermes_cli/data/plugin_api.json` | **L-1:** list `hermes_cli.gateway_client:connect_gateway`, `hermes_cli.gateway_client:GatewayClientError`, `hermes_cli.gateway_client:GatewayRPCError`, `hermes_cli.gateway_runtime:discover_gateway_endpoint`. **L-2:** list `agent.prompt_builder:CONTROL_FRAME_OPENERS` and `hermes_cli.input_sanitize:sanitize_user_prompt_text` |
| `website/docs/developer-guide/plugins/public-api.md` | Regenerated with `scripts/gen_plugin_api_docs.py`, with a short section on attaching to the profile's owner from a plugin (`plugins/AGENTS.md` § Boundary lint) |
| `tests/plugins/test_plugin_api_owner_client.py` (new) | Behaviour test: a bundled plugin, loaded through real discovery in a temp `HERMES_HOME` with a running owner, attaches with the listed names and runs `session.resume` / `prompt.submit` on a session of its own profile |
| `plugins/intercom/` | The vendored plugin (`git subtree`, G-12) |
| `scripts/dashboard_dispatch.py` | **Unchanged.** It still targets the admin dashboard. Relays move to `hermes intercom send` (G-11) |

Alternative to L-1, if upstream prefers it: one `ctx` wrapper (`ctx.owner_client()` returning an
attached client). That is a new `ctx` method, which is still not a behaviour change to any host,
but it is more code to upstream. Recommended: the listing.

`sanitize_title` is a `SessionDB` method, not a module-level name, so it is **copied** into
`intercom:frame.py` (a few lines) rather than listed.

**alexderz/hermes-intercom: the plugin**

| Path | Change |
|---|---|
| `intercom:plugin.yaml` | Version 0.3.0. `provides_tools: [intercom]`, `provides_hooks: [post_llm_call, pre_llm_call, pre_api_request]`. On a v0.23 build `pre_llm_call` is only the echo hook; the legacy drain is registered only on an old build (B12) |
| `intercom:__init__.py` | Tool schema and description (B11). `register()` wires the client, hooks and CLI command. The legacy inbox is set up only on a build without the owner-client names, and only in a classic CLI process (B12) |
| `intercom:client.py` (new) | **The owner client** (B1): discovery, attach, the verbs per mode, the error mapping |
| `intercom:route.py` (new) | The send path (B2) |
| `intercom:address.py` (new) | Addressing (B3) |
| `intercom:scope.py` (new) | The chat rule for messaging sessions, from the stored origin (B4) |
| `intercom:frame.py` (new) | Header, authority lines, footer, closing line, the relabel rule, field cleaning, echo text (B5) |
| `intercom:echo.py` (new) | The SM-Q15 echo through `ctx.post_message` from the target's own turn (B6) |
| `intercom:record.py` (new) | The SQLite record (B7) |
| `intercom:replies.py` (new) | The reply hook, silence, SM-Q9 (b), the in-process `ask` waiter (B8) |
| `intercom:cli.py` (new) | `hermes intercom send\|list\|status\|log` (B9) |
| `intercom:inbox.py` | Caps removed (B10). The socket, registry and GC lookup stay **only** as the legacy path for a Hermes build with no owner client (B12) |
| `intercom:tests/…` | The existing 17 tests, the changed cap tests, and new `test_client.py`, `test_route.py`, `test_scope.py`, `test_frame.py`, `test_address.py`, `test_record.py`, `test_replies.py`, `test_cli.py`, `test_echo.py`, in intercom's `unittest` style |
| `intercom:docs/upstream/…` | Drafts: the #81885 update, the majordave pull request, the two listing pull requests (G-13) |

**Config (house-infra `hosts/<gateway-host>/hermes.py`, not this repo):**
- `plugins.enabled += [intercom]`;
- `plugins.entries.intercom.allow_gateway_injection: true` (the existing consent key, required for
  every delivery, B2 step 3);
- `plugins.entries.intercom.settings`:
  - `user_name: Alex`;
  - `echo_chats: ["telegram:<chat id>", …]`;
  - `owner_user_ids: ["telegram:<Alex's user id>", …]`.

  `echo_chats` and `owner_user_ids` move under `settings`, because the plugin reads them itself
  now (B4).

### Behavior

#### B1. Owner client (`client.py`): the verbs from Trial round 3

- **Endpoint:** `discover_gateway_endpoint(get_hermes_home(), timeout=2.0).endpoint`. It is
  read-only and never starts an owner. `None` → `error` / `no-owner` (exit 5); a `starting` or
  `draining` state → `owner-restarting` (exit 5). Neither is ever a reason to use the legacy path
  (B12).
- **Invariant (R5-5):** `connect_gateway` is always called with the discovered endpoint, never
  `None`. With `None` it would ensure (start) an owner or honour `HERMES_TUI_GATEWAY_URL` as a
  remote target. `client.py` never reads `HERMES_TUI_GATEWAY_URL`.
- **Profile:** the home is the calling context's profile, because the tool and hooks run bound
  to their session. For the CLI it is the process's own `HERMES_HOME`.
- **Attach:** `async with connect_gateway(endpoint) as c:`. The ticket is minted over the
  profile's same-UID control socket (`hermes_cli/gateway_client.py:273-300`, `_session_ticket`).
  No key file, no URL setting, no TCP credential.
- **Thread:** `deliver_sync(...)` runs the coroutine with `asyncio.run` on a **fresh thread**,
  started as `contextvars.copy_context().run`. That is stdlib, and it replaces the unpublished
  `tools.thread_context`. The calling profile's context carries over.
- **Every delivery starts with `session.resume(session_id=target, omit_messages=true)`.** Trial
  round 3: a connection must attach to a session before it may submit to it. Resume returns the
  handle and **restores a cold session** in the owner (Trial R3: 0.7 s after an owner restart).
  - **Only `running` and `execution_generation` are read (R5-4).** `omit_messages` keeps the
    transcript out of the answer (`tui_gateway/contracts/canonical_sessions.py:81`).
  - Nothing else from the handle (`todo_state`, `pending`, prompts, and so on) is kept, logged,
    returned in a receipt, or put into an exception text. The sending model must never read
    another session's state through a tool result.
- **The mode table** (the strongest supported mode at or below the request; an idle target
  always starts a turn):

| Requested | Target running | Calls (in order) | `applied` / `detail` |
|---|---|---|---|
| any | no | `session.resume{omit_messages}` → `prompt.submit{text, submission_id}` | `start` |
| `queue` | yes | `session.resume` → `prompt.submit{text, queued: true, submission_id}` | `queue` |
| `steer` | yes | `session.resume` → `session.steer{text, execution_generation}`. `status: "queued"` → done; `rejected` → `prompt.submit{queued: true}` | `steer`, or `queue` |
| `interrupt` | yes | `session.resume` → `session.redirect{text, execution_generation}`. `redirected` → done; `rejected` → `session.interrupt{execution_generation}` → `prompt.submit{queued: true}` | `interrupt` / `redirect`, or `interrupt` / `hard-interrupt` |

- `submission_id` is `f"intercom-{message_id}"`. Canonical `prompt.submit` is idempotent per
  actor, session and submission id (`gateway/session_controls.py:806-809`), so one message is
  never admitted twice even if a sender process restarts mid-send. This is not a retry: intercom
  never re-sends.
- **Error mapping** (`GatewayRPCError.code` → `detail`):

| Owner answer | `detail` | Exit |
|---|---|---|
| `runtime_coordination_required` (the session is held by another runtime: the admin dashboard) | `not-addressable` | 4 |
| `permission_denied`, `unsupported_control`, `invalid_params` | `refused-by-owner` (code kept) | 4 |
| `stale_generation` on steer or redirect (the turn ended between resume and the call) | Resume once more and apply the idle row: one call sequence, not a retry of a failed delivery | — |
| connection lost or timed out **before** steer/redirect/submit was sent | `not-reachable` | 5 |
| …**after** it was sent | `delivery-unknown` | 6 |

  Error texts are a fixed sentence per code plus the exception's type name, never `str(exc)` of
  a connect error (the analogue of F13).

#### B2. Send path (`route.py::send(...)`)

Inputs:
- `sender` (session id, from the tool handler's `session_id` keyword; or a script label from the
  CLI);
- `to`, `message`;
- `delivery` (default `steer`);
- `expect_reply` (default true);
- `kind` (`send` or `ask`);
- `reply_to`.

| # | Step | Result |
|---|---|---|
| 0 | Empty or whitespace-only `message` | `refused` / `empty` (3) |
| 1 | `address.resolve(to)` (B3), then the compression tip | `refused` / `ambiguous` or `unknown`, with candidates (3). The target equal to the sender's session → `refused` / `own-session` (3). Only the same **session** is refused |
| 2 | Scopes: `scope.chat_scope(target)` and, for a session sender, `scope.chat_scope(sender)` (B4) | `target_chat_scope`, `sender_chat_scope` |
| 3 | **Consent for every delivery (R5-3):** if `plugins.entries.intercom.allow_gateway_injection` is not `true` (read fresh from the plugin's own profile config) | `error` / `injection-off` (4). This matches v0.22, where every non-CLI host required it. Classic CLI, the one exempt v0.22 host, is no longer a host. It needs no source test, so a failed source read cannot open it |
| 4 | `record.insert(...)`, with `result` empty | The row exists before delivery |
| 5 | `frame.build(...)` (B5), then `sanitize_user_prompt_text(text)` (L-2) once, then `header_sha = sha256(<span>)` stored in the row | The sender is the only writer of the frame and its hash |
| 6 | `client.deliver_sync(target, text, delivery, submission_id)` (B1) | `applied`, `applied_detail`, or an error code |
| 7 | `record.update(...)`; the receipt (B9), with `shared_chat = (target_chat_scope == "shared")` | — |

There is no lease lookup, no socket, no wake module and no gateway role. **The owner hosts every
addressable session, live or cold.** A session the owner cannot take is `not-addressable`.

**Operator power (R5-2, stated for Alex).** Intercom submits as the same-UID operator client, and
the owner admits operator input without re-checking a chat's platform authorisation
(`gateway/session_operator.py`: "already-authorized operator input";
`gateway/session_authority.py:740-748`). So a session can start a turn in **any stored chat of the
profile**, including one whose user Alex has since removed from an allowlist or unpaired. The
turn's answer is then posted to that person, as Alex could do from the Webapp.
- The v0.22 seam re-checked this (`_plugin_injection_authorized`).
- v0.23 has no published predicate for it: `_is_user_authorized_for_source` is a runner method,
  and a new core function would break "listings only".
- **Mitigations:** the chat rule makes such a chat `shared` (unless Alex listed it), so the body
  carries the shared-chat line, and no echo is posted.
- **Accepted by Alex** (SM-Q23 (a), 2026-11-11; HLD O23). No core predicate.

#### B3. Addressing (`address.py`)

The first rule that matches wins:
1. `Home`, or an exact title: `SessionDB.get_session_by_title`.
2. A session id or id prefix (v0.23 `local-…` ids and v0.22 ids alike): `resolve_session_id`.
   More than one match → ambiguous.
3. `@<slug>`: `projects.db` read-only. `owner_session_id` if the column exists and is set
   (DER-686), else the exact title `<name> — Orchestrator`. "Model Master" is renamed at deploy
   (SM-Q10).
4. Then `get_compression_tip`.

`SessionDB` is published (`hermes_state`). The v0.22 **endpoint-name** rule is removed: there
are no per-process endpoints to name.

**Candidates** (at most 5, display only): title, id, last active, and `open` / `not open` /
`admin dashboard`. The last comes from the owner's `session.list` (a read; `session:read`).

#### B4. Chat scope (`scope.py`): the rule for messaging sessions, inside the plugin

The rule is unchanged from LLD round 4 (F1, R2-1, R2-3, N1, N2). It moves from core into the
plugin, and it reads only published names.
- **Origin:** the session row from `hermes_state.SessionDB(read_only=True)`: `source`,
  `user_id`, `chat_id`, `chat_type`, `thread_id`, `origin_json`. Only the raw `platform`,
  `chat_id`, `chat_type` and `user_id` are used (N1); there is no identity re-pin.
- **Local sources:** `cli`, `tui`, `desktop`, `gui`, `acp`, `tool`, `oneshot`, `cron`,
  `subagent`, and the owner's local platform (`local`). **G-2's E2E confirms the exact strings
  the v0.23 owner writes.** Anything else is a messaging platform.
- **Rule:** `private` only when `f"{platform}:{chat_id}"` is in `settings.echo_chats`, or the
  chat type is `dm` and `f"{platform}:{user_id}"` is in `settings.owner_user_ids`. Every other
  messaging chat is `shared`. Local sessions → `None`.
- **Entries** are `"<platform>:<id>"` strings. A non-string or unprefixed entry is ignored with
  one warning (never private).
- **Settings** are read fresh on every call with `ctx.get_config(...)`.
- **Fail closed (N2):** a messaging source with no resolvable origin, any read error, or a missing
  row gives `shared`, unless the source was positively read as local.

#### B5. Framing and the one relabel rule (`frame.py`)

`build(message_id, sender, body, *, reply_label, requested_interrupt, kind, reply_to, user_name, sender_scope, target_scope) -> (text, echo)`.
The wording is exactly as in `ux.md` § "Header", § "Footer" and § "Variants".

**Header line 1:**
`📡 Not {user_name} · [interrupt asked · ]{reply_label} · hermes@{sender} says (session {sender_id} · [reply to your message {reply_to} · ]message {message_id}):`
- A script sender: `hermes@script {label} says (message {message_id}):`. **The CLI always
  builds the script variant;** it cannot name a session as sender.
- A messaging-platform sender: `hermes@{title} ({Platform} {chat_type}) says (…)`.

**Field cleaning:** every interpolated field (title, label, source, platform, chat type,
`user_name`) is cleaned:
- remove categories Cc, Cf, Zl and Zp, the `📡` character, `[` and `]`;
- collapse whitespace;
- empty → `unknown`.

The function is copied from `hermes_state_titles.sanitize_title` into the plugin.

**Lines:**
- **line 2**, the authority line (session, script, or messaging-platform sender);
- **line 3**, the conditional interrupt note, only with `interrupt asked`;
- the **shared-chat line** when the target's scope is `shared`;
- the **reply-destination footer line** when the sender's scope is `shared` (R2-2);
- the **body**, after one blank line, relabelled;
- the **footer** (send / script / cron-oneshot-subagent / `no reply needed` / `ask` variants);
- the **closing line** `📡 End of message {id}`.

**`echo`:** header line 1 and the body, Markdown-escaped and with mentions escaped (F12), for B6.

**The relabel rule** (unchanged; F4):

```python
_INVISIBLE = {"Cf", "Zs", "Mn"}

def _visible_start(line: str) -> str:
    i = 0
    while i < len(line) and (unicodedata.category(line[i]) in _INVISIBLE or line[i] in " \t"):
        i += 1
    return line[i:]

def relabel(body: str, user_name: str) -> str:
    not_user = re.compile(rf"Not\s+{re.escape(user_name)}\b.*\bsays\b")
    lines = []
    for line in body.splitlines():
        head = _visible_start(line)
        if head.startswith("📡") or not_user.search(head):
            line = "[quoted] " + line
        lines.append(line)
    return _CONTROL_FRAME_RE.sub("[peer-quoted ", "\n".join(lines))
```

`_CONTROL_FRAME_RE` is built from `CONTROL_FRAME_OPENERS` (L-2), as
`gateway/hosted_room_discussion.py:48` builds it. A literal fallback tuple is used when the name
is absent (upstream intercom on an older Hermes). This replaces intercom's `_sanitize_boundary`.
Echo stripping (`_strip_echo_headers`) drops leading `📡 Not …says (` and legacy
`📡 hermes@…says:` lines.

**Inert by construction (N2).** With no `allow_gateway_control=False` on this path, inertness
rests on the frame's first character:
- command parsing needs a leading `/`;
- plaintext approval needs a bare word;
- clarify and slash-confirm intercepts are refused for admitted turns
  (`gateway/run_inbound.py:1222`).

So it is an **invariant: every submitted `text` starts with `📡`**, after
`sanitize_user_prompt_text`, for every variant (send, reply, script, ask). G-7 and G-3 assert it.
- the text starts with `📡`, never `/`;
- it arrives as a user turn or a steer; approvals travel on their own requests;
- it is never `display_kind: "hidden"` (intercom never sends `display_kind`).

#### B6. Echo into a private chat (SM-Q15 b) through `ctx.post_message`

- `ctx.post_message(text)` posts into **the session bound to the calling context**
  (`hermes_cli/plugin_messages.py:1-6`). It is published, and a plugin "cannot reach another"
  chat with it. So the echo is posted **from the target's own turn**, by an intercom hook that
  runs for that turn and sees the message:
  - **queued or started** messages: `pre_llm_call` of the turn whose prompt carries the header;
  - **steered** messages: the first `pre_api_request` of the running turn whose
    `request_messages` carry the steer row (GW-4).
- **Why `pre_api_request` for steers (GW-4).** The turn puts a steer into its transcript only
  where the next model request will read it:
  - the pre-request drain inserts the steer row after the newest tool result
    (`agent/turn_iteration_prep.py:284`);
  - the post-tool drain adds it to the final tool result (`agent_runtime_helpers.py:3668`).

  `pre_api_request` fires before every provider attempt of the turn, the final-answer request
  included (`website/docs/user-guide/features/hooks.md`, "API-request observer hooks"). So the
  echo is posted **before the model reads the steer**, whether its next step is a tool call or
  the answer. `post_tool_call` missed the second case.
- **A steer that lands after the last request was sent** is handed back by the turn finalizer
  and becomes a later turn (`agent/turn_finalizer.py:845`, `gateway/run_busy.py:211`). Its
  echo is then the queued case: that turn's `pre_llm_call`. G-6 verifies this.
- **What the hook reads:** only the user rows after the newest assistant row of
  `request_messages`. Only enough to find a `📡` header and hash its span (B8 step 2). Nothing
  from the request is kept, logged or returned. The sanitised `request` envelope is not used,
  because the hash needs the exact text.
- **Once per message:** retries and later requests fire the hook again, so the post is claimed
  with `UPDATE messages SET echoed_at = ? WHERE id = ? AND echoed_at IS NULL` and made only when
  one row changed. The same claim guards `pre_llm_call`.
- **Never blocks the request:** the hook schedules `ctx.post_message` and returns; a failed post
  is logged only.
- **Only when** the target's scope is `private` (B4) and the record row's `header_sha` matches the
  span (B8 step 2), so a typed lookalike never triggers a post.
- **Escaping per renderer (N3).** `post_message` sends with the adapter's default formatting; it
  has no plain-text or no-mentions option (`gateway/plugin_messages.py:124-131`). So `frame.py`
  escapes for **the target platform's renderer** (Telegram HTML or MarkdownV2 as the adapter is
  configured, Discord and Slack mention forms, ntfy plain). It covers link text, `@everyone`,
  `@here` and `<@…>` / `<!…>` / `<#…>`. A platform with no escaper gets **no echo**.
- **One list (N6-2):** `frame.ECHO_ESCAPERS` maps platform → escaper and sits beside the
  escapers. It is the only list of echo-capable platforms. A private chat on a platform missing
  from it gets no echo and **one warning** per message ("no echo escaper for <platform>"), never
  an unescaped post. Adding an `echo_chats` entry for a new platform therefore needs an escaper.
- **The body is never mirrored by the owner (N4):** a shared chat receives only the turn's
  answer. G-6's E2E asserts it.
- **Timing changes** from "before the turn starts" to "as the turn that carries it runs" (before
  its answer). The UX words this (designer delta).
- A refused post (no live chat) is logged; delivery is unaffected.
- **Open O21:** whether those hooks fire bound to the target session in the owner for messaging
  chats, and what `post_message` renders there. Verify in G-6's E2E (fake ntfy). If they do not,
  the echo is dropped for v1 (SM-Q15 falls back to (a): answer only), with no core patch.

#### B7. Record schema (`record.py`)

`plugins.plugin_storage.plugin_db("intercom", "record.db")`: WAL, `busy_timeout` 5000 ms.

**File modes (F7):**
- `plugin-data/intercom/` is `0700`, with a `chmod` on every open;
- the first open runs under `os.umask(0o077)`. It creates `record.db` `O_EXCL` `0600`, then
  `chmod 0600` on `-wal` and `-shm` after the first write.

The schema is round 4's. **Changed columns:** `host` and `host_kind` are replaced by
`delivery_path` and `admission_id`.

```sql
CREATE TABLE IF NOT EXISTS messages (
  id TEXT PRIMARY KEY, kind TEXT NOT NULL, in_reply_to TEXT, reply_message_id TEXT, request_id TEXT,
  sender_session_id TEXT, sender_label TEXT NOT NULL, sender_source TEXT NOT NULL,
  target_session_id TEXT, target_title TEXT, address TEXT NOT NULL,
  delivery_path TEXT,                -- 'owner' | 'refused'
  admission_id TEXT,                 -- prompt.submit's admission id (queue / start), for `status`
  body TEXT NOT NULL,
  header_sha TEXT,                   -- sha256 of the whole framed span; written by the SENDER (F10, R2-4)
  sender_chat_scope TEXT, target_chat_scope TEXT,
  expect_reply INTEGER NOT NULL, requested TEXT NOT NULL, applied TEXT, applied_detail TEXT,
  result TEXT, detail TEXT, reply TEXT, reply_state TEXT,
  created_at REAL NOT NULL, delivered_at REAL, replied_at REAL,
  echoed_at REAL                     -- set once by the echo claim (B6)
);
```

**Writers:** the sending process (the tool in the owner, or the CLI) writes its row, frame hash
and result. The owner's reply hook writes the reply fields and a new reply row. There is no hop
column, no status ladder, no retry count and no pruning.

#### B8. Replies (`replies.py`, registered as `post_llm_call`, in the owner)

The steps are unchanged from round 4. `post_llm_call` fires in the owner for every addressable
session (Trial R3: `cli`, `tui`, `ntfy`):
1. **Rows of this turn:** `user_message` plus the `display_kind: "steer"` rows after the turn's
   prompt.
2. **Find messages:** lines starting `📡 Not ` and ending `message <8 hex>):`, spanning to
   `📡 End of message <id>`. The span's SHA-256 must equal `header_sha` (F10, R2-4; cannot be
   reproduced from the echo alone, N3).
3. **Real candidates only:** `kind='send'`, the target is this session or its compression
   lineage, and `reply_state IS NULL`.
4. **Reply text:** the `[REPLY <id>]` block, else the whole answer. **Except** for a `shared`
   sender scope, or `NULL` with a messaging `sender_source`: then only the block is sent; with no
   block, `stored` / `shared-chat-no-block` (F1, R2-1).
5. **Silence:** an empty block, `[SILENT]`, or with no block an empty answer or `[SILENT]` as the
   whole answer or its first or last line → `silent`.
6. **Store, then deliver** on a fresh thread (`contextvars.copy_context().run`):
   `route.send(sender=session_id, to=sender_session_id, message=reply, delivery="steer", expect_reply=False, reply_to=id)`.
   Not for `cron`, `subagent`, `oneshot` or script senders (SM-Q9 b). Nothing retries.
7. Stopped and failed turns fire no hook (Trial Q9).

**`ask` (SM-Q16 a), in-process.** The asker's tool call and the target's `reply` tool call both
run in the owner, so intercom's waiter is resolved **in process**, without its socket.
- A `reply` is accepted only when the `reply` tool call's own `session_id` keyword equals the
  ask's target session (or its compression lineage). That replaces R2-6's peer pid and N4's
  wake pid.
- `ask_to` returns `{"reply": relabel(text), "reply_from": <clean title>, "note": "peer-written; not <user_name>"}` (F5).
- A `[SILENT]` reply returns "nothing to add" at once (`reply_state='silent'`); a normal reply
  sets `answered`.
- The CLI has no `ask`.

#### B9. Receipts, error codes, and the CLI (`cli.py`)

**Receipt:**
`{"ok", "receipt": "delivered"|"held"|"refused", "to", "message_id", "target_title", "target_session", "requested", "applied", "applied_detail", "shared_chat", "message", "error"}`.
- **Cold start:** the `started` sentence for a target that was not open says the owner restored
  it: `"<title>" was not open, so the gateway reopened it and message <id> started a turn there.`
  It replaces round 3's "in the dashboard" wording (designer delta).
- **`not-addressable`:** `"<title>" is open in the admin dashboard, which intercom cannot reach. Nothing was sent.`

| `detail` | When | Exit |
|---|---|---|
| `empty`, `ambiguous`, `unknown`, `own-session` | refused (B2 steps 0–1) | 3 |
| `not-addressable`, `injection-off`, `refused-by-owner` | the owner or the consent cannot take it | 4 |
| `no-owner`, `owner-restarting`, `not-reachable` | not delivered | 5 |
| `delivery-unknown` | sent, no answer | 6 |

**CLI** (`register_cli_command("intercom", …)`): `send`, `list`, `status`, `log`, with the same
flags as round 4 and exit codes 0–6 (0 delivered, 1 no such id, 2 usage, 3–6 as above).
- **The CLI is an owner client.** It runs the B2 send path in its own process, attaches with
  B1, and starts no turn of its own. It always frames as a script.
- **`list`:** the owner's `session.list` for this profile (titles, ids, last active), not
  intercom's peers.
- **`status`:**
  - for a queued or started delivery, the owner's `prompt.receipt` for `admission_id`
    (`queued` / `started` / `terminal`, read only);
  - for a steered message, or `delivery-unknown` with no admission id, the read-only transcript
    check: a `role='user' AND (active=1 OR compacted=1)` row whose span hashes to `header_sha`.

  It writes nothing, retries nothing and sets no timer. Round 4's pid and lease advice is removed.
- **`log`:** as round 4, including `reply: stored (shared chat, no [REPLY] block)`.

#### B10. Caps removed (`intercom:inbox.py`)

As round 4:
- `_MAX_MSG_CHARS` (`:35`, `:520`, `:577`, `:597`) is removed;
- `_RATE_*` (`:37-38`, `:44`, `:503-507`) is removed;
- `_DEDUPE_WINDOW_S` (`:39`, `:45`, `:509-514`) is removed;
- `_PENDING_CAP` (`:36`, `:246-268`, `:690`) stays only inside the legacy no-owner path (B12).

The cap tests are rewritten so that 20 identical messages in a minute all arrive.

#### B11. Tool schema and Tool Search catalog wording

- The first sentence is exactly `Message another Hermes session; never send an empty message.`
  (60 characters; the v0.23 catalog clips at 80).
- **Parameters:**
  - `action` (`list|send|ask|reply`);
  - `to`, `message`;
  - `delivery` (`interrupt|steer|queue`, default `steer`);
  - `expect_reply`, `timeout`, `request_id`.
- Alex's interrupt sentence appears word for word.
- The handler is synchronous (`is_async=False`); a cold start plus RPCs stays well under the
  300-second `_run_async` limit, but there is no reason to use the async path. The sender comes
  from the handler's `session_id` keyword.

#### B12. What survives of intercom's transport

Said plainly:
- On a v0.23 install with an owner, **intercom's Unix socket and registry are not used.**
  Delivery, the CLI, `list`, `ask` and replies all go through the owner (B1, B8, B9).
- Cross-profile refusal comes from the owner itself: the ticket is minted for the plugin's
  profile home, and session references carry the profile. It needs no intercom socket.
- **What survives** is intercom's tool and its `send` / `ask` / `reply` / `list` vocabulary, its
  frame style, echo stripping and receipt words.
- **The legacy path, chosen by capability, never by liveness (R5-1).** The socket, registry, GC
  lookup of `HermesCLI`, parking and the process-wide `pre_llm_call` drain are used **only** on a
  Hermes build that cannot host an owner client at all.
  - **Capability:** `register()` checks whether `hermes_cli.gateway_client.connect_gateway` and
    `hermes_cli.gateway_runtime.discover_gateway_endpoint` are importable. On any v0.23 build they
    are, so **the legacy path is never set up**. An owner that is not reachable right now gives
    `no-owner` / `owner-restarting` (exit 5), never a fallback.
  - **Never in a multi-session host:** on an old build, the legacy inbox starts lazily, at the
    first `intercom` call, and only in a process where intercom's own lookup finds a classic
    `HermesCLI` instance (its existing `_find_cli_instance`). It never runs in a `tui_gateway`,
    dashboard or gateway process. No argv is read (HX003). Other old-build processes answer
    `no-seam` (exit 4, the UX code).
  - **Hooks:** the legacy drain hook is registered only on the legacy build, together with the
    inbox. B6's echo `pre_llm_call` is a separate hook and never drains anything.
  - **An in-between build fails safe (N6-1).** `hermes_cli/gateway_client.py` already exists at
    this base. A build that has the names but no working owner takes the owner path and answers
    `no-owner` (exit 5). It loses availability, never isolation. Only absent names select the
    legacy path.
  - This keeps intercom's 17 tests and its upstream behaviour on old builds.

### Removed security fixes, and what replaces each (for security's re-check)

| Fix | Was | Replaced by |
|---|---|---|
| **TB-1 / F8 / F13 / F14 / F15** | The agent-key loopback wake path: loopback-only URL, fixed error texts, wake profile, attribution | No wake path. The owner restores cold sessions on `session.resume`. Credentials: the owner ticket from the same-UID control socket (TB-1 below). Error texts stay fixed per code (B1, the F13 analogue). Attribution: turns are admitted under the attached actor (the same OS user), and the header says `Not Alex` |
| **F2** | Consent (`allow_gateway_injection`) checked before waking | The same consent key, checked by intercom before **every** delivery (B2 step 3; R5-3). v0.22 required it for every non-CLI host; classic CLI is no longer a host, so nothing is exempt |
| **TB-4 recheck** (`_plugin_injection_authorized`) | The seam re-checked a chat's current platform authorisation before a plugin event ran | **Not replaced; stated for Alex (R5-2 b):** operator power (B2). Mitigated by the chat rule and no echo. HLD O23 |
| **F3** | Sender bound to the socket peer pid's lease | The frame is built only by intercom code in the sending process. The tool takes the sender from the handler's `session_id`; **the CLI always frames as a script**. Any same-UID client can already submit arbitrary text through the owner, so the trust domain is the owner's same-UID ticket (TB-1). A forged frame gets no reply unless its exact span is in the record (F10), which only the Hermes user can write (N1); that stays inside TB-1's domain |
| **F6** | `InjectedDelivery` in-process type for `_delivery_mode` | Nothing to replace: no new RPC key exists. Intercom uses only the owner's canonical verbs, whose parameters are validated by the owner (`extra="forbid"`) |
| **F9** | Per-session profile check in the tui and gateway hosts | The owner's authorisation: ticket bound to the plugin's profile home, session references carry the profile, and addressing reads only this profile's `state.db` |
| **F11** | Gateway role trusted only from `get_running_pid()` | `discover_gateway_endpoint` over the profile's same-UID control socket (the owner's identity and instance id). There is no registry role |
| **R2-5** | Loopback URL parsing | No URL: discovery gives the endpoint |
| **R2-6 / N4** | `ask` reply bound to the peer pid (and the dashboard's pid after a wake) | In-process waiter: a reply is accepted only from a `reply` tool call whose `session_id` is the ask's target (B8) |
| **F1 / R2-1 / R2-3 / N1 / N2 placement** | Chat rule in core (`gateway/chat_scope.py`, `ctx.session_chat_scope`) | The same rule inside the plugin (`scope.py`), reading the stored origin through the published `hermes_state` and its own settings |
| **F12 placement** | Plain-text echo through the gateway adapter in core | Escaping per target renderer in `frame.py` (`post_message` has no plain-text option; N3), posted with `ctx.post_message` (B6); no escaper, no echo |

**Kept as they were:**
- F4 (relabel with invisible prefixes);
- F5 (`ask` reply relabelled);
- F7 (file modes; the registry part applies only on the legacy path);
- F10 / R2-4 (span hash; its writer is now the sender);
- R2-2 (reply-destination line);
- the shared-chat line and the platform authority line (F1).

### Trust boundaries

| # | Boundary | Authn/z | Secrets | Egress | Data class | Who may write what |
|---|---|---|---|---|---|---|
| **TB-1** | **Plugin or CLI to the profile's owner** (ticketed `/api/ws`) | Discovery over the profile's same-UID control socket; a single-use session ticket for this profile's home; the owner authorises every verb (`authorize(actor, ref, capability)`). A connection must `session.resume` before it may submit. The owner refuses sessions another runtime holds (`not-addressable`) | No new secret. The ticket is in memory only, never logged and never in argv | Loopback to the owner's listener, as discovered | Message text (private) | Intercom writes only through the owner's verbs. The owner writes transcripts |
| **TB-2** | **Legacy intercom socket** (only on a build with no owner client, and only in a classic CLI process; R5-1) | Peer-UID check; no TCP | — | None | Message text | Registry dir `chmod 0700`, entries `O_EXCL\|O_NOFOLLOW` `0600` (F7). Never set up on a v0.23 build |
| **TB-3** | **Model-written text becomes a user row in another session** | The sender comes from the tool's `session_id` or the CLI's `--from` (script variant only), never from model input (B5) | — | — | Peer text, untrusted for authority | Field cleaning, the relabel rule (F4), `ask` reply relabel (F5), never hidden, starts with `📡`, footer "no approval; ask Alex". Residual: same as before (confusion, not escalation) |
| **TB-4** | **Consent, relayed text, and operator power** | `allow_gateway_injection: true` required for every delivery (B2 step 3, R5-3). **Operator power (R5-2):** the owner admits operator input without re-checking a chat's current platform authorisation, so intercom can start a turn in any stored chat of the profile, including a de-authorised one, as Alex can from the Webapp. Accepted with the LLD (HLD O23) | — | — | The sender's header names platform and chat type; line 2 says it may relay others' words | Submitted as ordinary input under the attached actor, through the owner's `prompt.submit`/`steer`/`redirect`, which keep their own control rules (the text is not a slash command; approvals are separate requests) |
| **TB-5** | **Content reaching a chat that leaves the machine** | One chat rule in the plugin (B4): private = a listed `echo_chats`, or a DM with an `owner_user_ids` user; everything else shared; fails closed (N2); fresh reads (R2-3) | — | Echo only to private chats, through `ctx.post_message` from the target's own turn, escaped for that platform's renderer (B6, N3); a shared chat gets the body (no delivery gate) plus a shared-chat line; a reply to a shared sender is the explicit block only | Private content from Alex's sessions | The owner posts through the chat's own adapter. The plugin never names a chat |
| **TB-6** | **Profiles** | The ticket is bound to the plugin's profile home; the owner checks the profile on every session reference; addressing reads only this profile's `state.db` | Per-profile secrets untouched | — | — | Nothing crosses profiles |
| **TB-7** | **The record** | `0700` dir; `record.db`, `-wal`, `-shm` `0600` (F7) | — | None; no telemetry | Every body and reply | The sender writes its row and hash; the owner's reply hook writes reply fields; `status` / `log` read |
| **TB-8** | **The `hermes intercom send` CLI** | Any process of the Hermes user, the same domain as TB-1 | — | — | Script-labelled | Runs B2 itself as an owner client; script frame only |

### Mockups

`docs/session-mail/mockups/` (round 3, recommendation A). Hermes Mobile is out of scope
(SM-Q22). The designer updates two texts:
- the cold-start receipt (B9);
- the echo timing (B6).

Operator acceptance: pending.

### Verify

`scripts/run_tests.sh` with a temporary `HERMES_HOME` (hermes-agent). Intercom tests:
`python -I -m unittest discover -s tests -p 'test_*.py'`.

| Item | Proving check |
|---|---|
| G-1 listing PR | `tests/plugins/test_plugin_api_owner_client.py`: a plugin loaded through real discovery attaches with the listed names and runs `session.resume` + `prompt.submit`; `scripts/boundary_lint.py` passes for `plugins/intercom` |
| G-2 owner client | `test_client.py` against a fake owner: each mode row, fallbacks, `stale_generation` → idle row, error mapping (`runtime_coordination_required` → `not-addressable`), `submission_id` idempotent, error text without URL or ticket; `connect_gateway` never called without an endpoint and `HERMES_TUI_GATEWAY_URL` never read (R5-5); resume sent with `omit_messages` and no transcript or handle field in any receipt, log or error (R5-4). **E2E** (`tests/plugins/intercom/test_e2e_owner.py`, real owner in a temp home, fake model, fake ntfy, CLI under a pty): Trial round 3's 24 cells rebuilt from scratch; also the exact `sessions.source` strings for local and owner sessions (B4); after an owner restart, no intercom socket exists under `$HERMES_HOME/intercom/sessions/` and no drain hook is registered (R5-1) |
| G-3 send path | `test_route.py`: steps 0–7; `injection-off` for **every** target kind without consent (R5-3); the CLI frames as a script; own-session refused; a stored messaging chat whose user is not on the current allowlist is still delivered (operator power pinned, R5-2 b); every submitted `text` starts with `📡` (N2) |
| G-4 addressing | `test_address.py`: title, `Home`, `local-…` and v0.22 id prefixes, ambiguous, `@slug` both ways, compression tip |
| G-5 chat scope | `test_scope.py`: owner DM private, non-owner DM shared, unlisted group shared, listed group private, other-platform prefix shared, int entry ignored, corrupt `origin_json` shared, missing row shared, local `None`, fresh read |
| G-6 echo | `test_echo.py`, plus the E2E with fake ntfy: an echo is posted in a private chat from the target's own turn, never in a shared chat, never for a lookalike (O21); the escaping cases (link text, `@everyone`, `<@…>`) through the real ntfy adapter, and per-platform escaper unit tests for the platforms in `echo_chats` (N3); after a delivery into an unlisted group, the fake server received only the turn's answer (N4); a private chat on a platform missing from `ECHO_ESCAPERS` gets no post and one warning (N6-2). **Steered echo (GW-4):** a steer whose turn's next step is the final answer is echoed once, before that answer; a steer that lands during the final request is echoed by the later turn's `pre_llm_call`; retries never post twice |
| G-7 framing | `test_frame.py`: the exact header and variants, relabel cases (F4), cleaning (a newline in `--from` stays on line 1), echo escaping (F12), `_short_desc` → the 60-character sentence; every variant's text starts with `📡` after `sanitize_user_prompt_text` (N2) |
| G-8 record | `test_record.py`: schema, modes on all three files, two writers |
| G-9 replies and `ask` | `test_replies.py`: block / whole / silence, the record check, the shared-sender rule, SM-Q9 (b), reply via the owner client, in-process `ask` accepted only from the target's `reply` call, `[SILENT]` on `ask` |
| G-10 CLI | `test_cli.py`: exit codes 0–6; `list` through `session.list`; `status` through `prompt.receipt` and the hashed transcript check. **Legacy path (R5-1):** on a build that publishes the owner names, with discovery returning `None`, `starting` or `draining`, `inbox.start()` is never called and no drain hook is registered; on a simulated old build, where importing the names **fails** (N6-1), it starts only where a `HermesCLI` instance exists |
| G-11 relays | The relay skill text uses `hermes intercom send`; `scripts/dashboard_dispatch.py` is unchanged |
| G-12 deploy | After the gateway restart: `hermes plugins list` shows intercom enabled in the owner; `hermes intercom send --to Home --message "deploy check" --delivery queue` exits 0; a message to an admin-dashboard chat exits 4 `not-addressable` |
| Code health | `python scripts/check` (and lefthook, which needs ruff 0.15.22 in the build environment) |

### Land

| Repo | project-main | Item branches | Trunk |
|---|---|---|---|
| alexderz/hermes-agent | `integrate/session-mail-023` | `der-701/<item>` (G-1, G-12 vendor and E2E) | project-main → a feature branch onto `alex/v0.23.1-canary-1110` → fast-forward, then `git pull --ff-only` in the install (rule 19). The listing PRs are also drafted upstream (G-13) |
| alexderz/hermes-intercom | `integrate/session-mail` (from `ae90a2a`) | `der-701/<item>` (G-2 … G-11) | merged into the fork's `main` after Review |

**Intercom first, then subtree:**
- first time: `git subtree add --prefix plugins/intercom <intercom-remote> integrate/session-mail`;
- then: `git subtree pull --prefix plugins/intercom <intercom-remote> integrate/session-mail`.

Never `--squash`, and never a fix in `plugins/intercom/` alone. Each commit starts `[DER-701]`
plus the item's ticket id.

## Optional

### Interfaces / schemas

- **The owner verbs used:** `session.resume`, `session.steer`, `session.redirect`,
  `session.interrupt`, `prompt.submit`, `prompt.receipt`, `session.list` (declared in
  `tui_gateway/contracts/canonical_sessions.py` and `canonical.py`).
- **Settings** (`plugins.entries.intercom.settings`): `user_name`, `echo_chats`,
  `owner_user_ids`.
- **Entry level:** `allow_gateway_injection`.

There is no `dashboard_port` and no `HERMES_*` variable.

### Rollout / rollback

1. Land G-1 (listing), then G-2 … G-11 in intercom, then G-12. That means: subtree add, a
   feature branch onto `alex/v0.23.1-canary-1110`, fast-forward, and `git pull --ff-only` in the
   install.
2. House-infra enables intercom and sets `allow_gateway_injection`, `user_name`, `echo_chats`
   and `owner_user_ids`.
3. **One announced gateway restart.** The gateway now hosts every chat, the manager's own
   session included, so the window is scheduled and announced. The admin dashboard needs no
   restart unless its plugins change; it would load intercom at its next start, where intercom
   only sends.
4. The manager switches the relay skills to `hermes intercom send` (G-11) and renames "Model
   Master" (SM-Q10).
5. **Rollback:** remove `intercom` from `plugins.enabled` and restart the gateway, or revert the
   fast-forward. The listings are inert.

### Planned items (the manager files them at Groom; builder suggested)

| # | Item | Repo | Builder | Depends on |
|---|---|---|---|---|
| G-1 | **Listing PR** in `plugin_api.json` (L-1: `connect_gateway`, `GatewayClientError`, `GatewayRPCError`, `discover_gateway_endpoint`; L-2: `CONTROL_FRAME_OPENERS`, `sanitize_user_prompt_text`), regenerated docs, behaviour test, boundary lint | hermes-agent | **Claude Opus** | — |
| G-2 | Owner client `client.py` (B1), plus the owner E2E harness | intercom (+ E2E in hermes-agent) | **Claude Opus** | G-1 |
| G-3 | Send path `route.py` (B2), consent for every delivery | intercom | **Claude Opus** | G-2, G-4, G-5, G-7, G-8 |
| G-4 | Addressing `address.py` (B3) | intercom | Grok 4.7 | — |
| G-5 | Chat scope `scope.py` (B4) | intercom | **Claude Opus** | — |
| G-6 | Echo `echo.py` (B6: `pre_llm_call` and the steered `pre_api_request` hook, the once-only claim), O21 verification | intercom | **Claude Opus** | G-5, G-7, G-9 |
| G-7 | Framing `frame.py` (B5) | intercom | Grok 4.7 | G-1 (L-2) |
| G-8 | Record `record.py` (B7) | intercom | Grok 4.7 | — |
| G-9 | Replies and in-process `ask` `replies.py` (B8) | intercom | **Claude Opus** | G-3 |
| G-10 | CLI `cli.py` (B9), tool schema (B11), caps removal (B10), the capability-selected legacy path (B12, R5-1) | intercom | Grok 4.7 | G-3, G-8 |
| G-11 | **Relays:** relay skill text to `hermes intercom send` (the manager edits the live skills at deploy); a note in `scripts/dashboard_dispatch.py`'s docstring that it targets the admin dashboard only | hermes-agent (docstring) + manager | Grok 4.7; manager | G-10 |
| G-12 | Vendor (subtree), feature branch onto `alex/v0.23.1-canary-1110`, house-infra enable, the announced gateway restart, rename | hermes-agent + house-infra | Grok 4.7; manager for restart | G-1 … G-10 |
| G-13 | Upstream drafts (#81885 update, majordave pull request, listing pull requests) in `intercom:docs/upstream/` for Alex | intercom | Grok 4.7 | G-1 … G-10 |

**Removed items** (round 4's I-1 … I-4, I-11, I-12):
- the core seam on the tui, CLI and gateway hosts;
- the wake module;
- the gateway endpoint role.

### Bot after-act notes

None.
