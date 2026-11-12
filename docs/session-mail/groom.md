# Groom — session-mail: session-to-session messaging, built on intercom (gateway only)

DRAFT (pre-review)

<!-- At freeze, replace the draft marker above with this sentence and
delete this comment: Frozen record of the plan as reviewed at Groom on
<YYYY-MM-DD>. Not live: the tracker is the source of truth for tickets,
blockers and state. -->

- Chunk: `DER-701` · LLD: `docs/session-mail/lld.md` (round 9; accepted by Alex 2026-11-11,
  SM-Q18 "Accepted, go") · Date: `2026-11-11`
- Review: `<groom reviewer label>` — pass on `<date>` at `<SHA of the reviewed draft commit>`;
  `pending` until filled at freeze
- Tickets: `G1` = `<id>`, … (filled at freeze)

**How the items map to the LLD.** `G1` … `G13` are the LLD's G-1 … G-13, in order. There is one
split:
- **`G14` (owner E2E) is split out of G-2.** G-2 bundles the owner client with "the owner E2E
  harness".
- The E2E's cells prove the **integrated** plugin, not the client alone:
  - Trial round 3's 24 cells go through the send path (G3);
  - the R5-1 socket and drain-hook check needs the legacy-path selection (G10);
  - G-6's fake-ntfy E2E and O21 need the echo (G6).
- It also lives in another repo: hermes-agent, where the LLD's Land table puts "G-12 vendor and
  E2E".
- So it cannot be built when the client is. It is its own item: the gate before deploy.

**Two LLD dependencies are not blockers here** (groom-step § Blockers, rules 1 and 3):
- **G-2 ← G-1** and **G-7 ← G-1 (L-2):** the names they use (`connect_gateway`,
  `discover_gateway_endpoint`, the client errors, `CONTROL_FRAME_OPENERS`,
  `sanitize_user_prompt_text`) already exist at the base. Also, B5 keeps a literal fallback for
  `CONTROL_FRAME_OPENERS`.
- The listing only makes the **vendored** plugin pass boundary lint, so it blocks G12, not G2 or
  G7.

**Common to every item:**
- The LLD lives on `alexderz/hermes-agent` `integrate/session-mail-023`. Intercom items link it
  there.
- Every test runs on a **temporary `HERMES_HOME` with a fake model**, never the live home.
  `<hermes-test-python>` is the Python of the hermes-agent test environment (`CONTRIBUTING.md`).
  `<intercom-repo>` is a checkout of `alexderz/hermes-intercom`.
- **Intercom item branches** are `der-701/<slug>` in `alexderz/hermes-intercom`, cut from its
  project-main `integrate/session-mail`, which the manager cuts from its `main`.
- **hermes-agent item branches** are `der-701/<slug>`, cut from `integrate/session-mail-023`.
- **Out of scope for every item:**
  - the accepted design and Alex's settled decisions: no caps, holds, retries or approval
    gates; default `steer`; three modes; the A′ frame; gateway only (SM-Q20);
  - any core behaviour change (only the G1 listings);
  - the live install, its config, its dashboard and its services;
  - posting anything upstream.

## Items

### G1: Listing PR: publish the owner-client and framing names in `plugin_api.json`

- Type: Task
- Parent: `DER-701`
- LLD: `docs/session-mail/lld.md#paths--modules` (L-1, L-2); `#verify` (G-1 row)
- Branch: `der-701/listing` in `alexderz/hermes-agent`, from `integrate/session-mail-023`
- Builder: Claude Opus

**Outcome:** a bundled plugin may import the owner client and the two framing helpers through
the published plugin API. No behaviour changes anywhere.

**Acceptance:**
- **L-1:** `hermes_cli/data/plugin_api.json` lists:
  - `hermes_cli.gateway_client:connect_gateway`;
  - `hermes_cli.gateway_client:GatewayClientError`;
  - `hermes_cli.gateway_client:GatewayRPCError`;
  - `hermes_cli.gateway_runtime:discover_gateway_endpoint`.
- **L-2:** it also lists `agent.prompt_builder:CONTROL_FRAME_OPENERS` and
  `hermes_cli.input_sanitize:sanitize_user_prompt_text`.
- **Docs:** `website/docs/developer-guide/plugins/public-api.md` is regenerated with
  `scripts/gen_plugin_api_docs.py`. It has a short section on attaching to the profile's owner
  from a plugin.
- **Behaviour test:** new `tests/plugins/test_plugin_api_owner_client.py`. A bundled test
  plugin, loaded through real discovery in a temp `HERMES_HOME` with a running owner, attaches
  with the listed names and runs `session.resume` then `prompt.submit` on a session of its own
  profile.
- **No behaviour change:** no non-listing source line changes.

**Verify:**
```
HERMES_HOME="$(mktemp -d)" scripts/run_tests.sh tests/plugins/test_plugin_api_owner_client.py
python scripts/gen_plugin_api_docs.py --check
python scripts/boundary_lint.py
python scripts/check
```

- **Blocked by:** none
- **Blocks:** G12, G13
- **Out of scope:**
  - the `ctx.owner_client()` wrapper alternative (only if upstream asks; HLD O20);
  - `sanitize_title`, which is copied into the plugin (G7), not listed;
  - opening the upstream pull request (G13 drafts it).
- **Proposed fix:** n/a — split from accepted Spec
- **Removal alternative:** n/a — split from accepted Spec
- **Pick:** n/a — split from accepted Spec
- **Plan / Spec:** n/a — split from accepted Spec

### G2: Owner client `client.py`

- Type: Task
- Parent: `DER-701`
- LLD: `docs/session-mail/lld.md#b1-owner-client-clientpy-the-verbs-from-trial-round-3` (B1)
- Branch: `der-701/owner-client` in `alexderz/hermes-intercom`, from `integrate/session-mail`
- Builder: Claude Opus

**Outcome:** intercom can deliver to any owner-hosted session in every mode, and read the
owner's session list, through the owner's existing verbs.

**Acceptance:**
- **Discovery:** `discover_gateway_endpoint(get_hermes_home(), timeout=2.0)`.
  - `None` → `no-owner`; `starting` or `draining` → `owner-restarting` (both exit 5).
  - Neither ever selects the legacy path.
- **Endpoint (R5-5):** `connect_gateway` is called only with the discovered endpoint, never
  `None`. `HERMES_TUI_GATEWAY_URL` is never read.
- **Thread:** `deliver_sync(target, text, delivery, submission_id)` runs `asyncio.run` on a
  fresh thread started with `contextvars.copy_context().run`.
- **Resume (R5-4):** every delivery starts with `session.resume{omit_messages: true}`. Only
  `running` and `execution_generation` are read. No other handle field reaches a receipt, a log
  or an exception text.
- **Modes:** the B1 mode table, row for row:
  - idle → start;
  - `queue` → queued submit;
  - `steer` → `session.steer`, else a queued submit;
  - `interrupt` → `session.redirect`, else `session.interrupt` and a queued submit;
  - `stale_generation` → one more resume, then the idle row.
- **Idempotence:** `submission_id = f"intercom-{message_id}"`. Nothing is ever re-sent.
- **Error mapping (B1):**
  - `runtime_coordination_required` → `not-addressable`;
  - `permission_denied`, `unsupported_control` and `invalid_params` → `refused-by-owner`, with
    the code kept;
  - not sent → `not-reachable`;
  - sent, no answer → `delivery-unknown`.

  Error texts are a fixed sentence plus the exception's type name, with no URL or ticket.
- **List:** `list_sessions(scope, picker)` wraps `session.list` (read only) for G4's `list` and
  candidates.

**Verify:**
```
cd <intercom-repo>
HERMES_HOME="$(mktemp -d)" <hermes-test-python> -I -m unittest discover -s tests -p 'test_client.py' -t . -v
```
`test_client.py` runs against a fake owner and covers the G-2 rows of LLD § Verify. The
real-owner E2E is G14.

- **Blocked by:** none (the names exist at the base; the listing is needed only for vendoring,
  G12)
- **Blocks:** G3
- **Out of scope:** the E2E harness (G14); the send path (G3); boundary lint (G12).
- **Proposed fix:** n/a — split from accepted Spec
- **Removal alternative:** n/a — split from accepted Spec
- **Pick:** n/a — split from accepted Spec
- **Plan / Spec:** n/a — split from accepted Spec

**Notes for the builder:**
- The trial code in `docs/session-mail/poc/round3/` (hermes-agent) shows the call sequence. It is
  not product code; rebuild it.
- `connect_gateway` is an async context manager.
- A new connection must `session.resume` before it may submit.

### G3: Send path `route.py`

- Type: Task
- Parent: `DER-701`
- LLD: `docs/session-mail/lld.md#b2-send-path-routepysend` (B2)
- Branch: `der-701/send-path` in `alexderz/hermes-intercom`, from `integrate/session-mail`
- Builder: Claude Opus

**Outcome:** `route.send(...)` takes a message from a session or a script to one resolved
target. It records the message, frames and hashes it, delivers it through the owner, and returns
the B9 receipt.

**Acceptance:**
- **Inputs (B2):** `sender`, `to`, `message`, `delivery` (default `steer`), `reply_mode`,
  `kind`, `reply_to`.
  - A tool `send` without `reply` is refused `reply-missing` and records nothing.
  - The tool cannot pass `optional`; only B8 sets it.
- **Steps 0–7 in order:**
  - empty → `empty`;
  - resolve (G4) → `ambiguous` / `unknown` with candidates, or `own-session` for the same
    session;
  - the scopes (G5);
  - consent for **every** delivery: `allow_gateway_injection` not `true` → `injection-off`
    (exit 4), read fresh;
  - the record row before delivery (G8);
  - `frame.build`, then `sanitize_user_prompt_text`, then `header_sha` over the span (G7);
  - `client.deliver_sync` (G2);
  - the record update and the receipt.
- **Receipt:** carries `target_session` for every delivery and for every refusal after step 1,
  and `shared_chat = (target_chat_scope == "shared")`.
- **Framing:** the CLI always frames as a script. Every submitted `text` starts with `📡` (N2).
- **Operator power (R5-2, accepted SM-Q23):** a stored messaging chat whose user is no longer on
  the allowlist is still delivered. The test pins this.

**Verify:**
```
cd <intercom-repo>
HERMES_HOME="$(mktemp -d)" <hermes-test-python> -I -m unittest discover -s tests -p 'test_route.py' -t . -v
```
This covers the G-3 row of LLD § Verify.

- **Blocked by:**
  - G2 — step 6 calls `client.deliver_sync`;
  - G4 — step 1 calls `address.resolve`;
  - G5 — step 2 calls `scope.chat_scope`;
  - G7 — step 5 calls `frame.build`;
  - G8 — steps 4 and 7 write the record.
- **Blocks:** G9, G10
- **Out of scope:** replies (G9); the tool schema and the CLI (G10).
- **Proposed fix:** n/a — split from accepted Spec
- **Removal alternative:** n/a — split from accepted Spec
- **Pick:** n/a — split from accepted Spec
- **Plan / Spec:** n/a — split from accepted Spec

### G4: Addressing `address.py`, and `list`

- Type: Task
- Parent: `DER-701`
- LLD: `docs/session-mail/lld.md#b3-addressing-addresspy` (B3, including `list` and project
  addressing)
- Branch: `der-701/addressing` in `alexderz/hermes-intercom`, from `integrate/session-mail`
- Builder: Grok 4.7

**Outcome:** a `to` string resolves to exactly one session, or to a refusal with candidates.
`list` gives each session's id, title, project, last active and state.

**Acceptance:**
- **Rules, first match wins:**
  1. `Home` or an exact title;
  2. a session id or id prefix (`local-…` and v0.22), where several matches are ambiguous;
  3. `@<slug>`, only when project addressing is available;
  4. then the compression tip.
- **Project addressing:**
  - `check_project_addressing()` is true only when `settings.project_plugin` is in the profile's
    `plugins.enabled` **and** `PRAGMA table_info(projects)` lists `owner_session_id`;
  - it reads `get_hermes_home() / "projects.db"` opened `file:…?mode=ro`, never through
    `hermes_cli.projects_db.connect`;
  - a missing file or any read error means "not available";
  - it is checked at `register()` and on every resolve.
- **Project refusals:**
  - without the feature, `@…` → `project-addressing-unavailable`, with the B3 text;
  - an unknown slug → `unknown`, with slugs;
  - no owner set → `no-owner-set`;
  - no title convention, ever.
- **Candidates:** at most 5, each with title, id, last active, and `open` / `not open` /
  `admin dashboard`.
- **`list` (B3):**
  - reads stored and live `session.list`;
  - `id` is the compression tip's id;
  - `project` comes from `project_folders` (the longest matching path), else the folder name;
  - `state` is `running`, `idle` or `closed`;
  - `cron`, `subagent` and `oneshot` sessions are left out unless `include_runs`;
  - `query` filters on title or project; newest first; `limit` default 30;
  - the sender's own session is marked `(this session)`.
- **`session.list` input:** the rows come through an injected lister callable, which G2's
  `client.list_sessions` fills in production. So G4 is tested with a fake lister.

**Verify:**
```
cd <intercom-repo>
HERMES_HOME="$(mktemp -d)" <hermes-test-python> -I -m unittest discover -s tests -p 'test_address.py' -t . -v
```
This covers the G-4 row of LLD § Verify, against a temp `projects.db`: the file is unchanged
after the read. It also covers the `list` filtering cases from the G-10 row that belong to B3:
runs left out, ids, `query`, `limit`, states and `project`.

- **Blocked by:** none (the owner rows come through an injected lister; see Acceptance)
- **Blocks:** G3
- **Out of scope:** the CLI's `list` output format and the tool schema (G10); DER-686 itself.
- **Proposed fix:** n/a — split from accepted Spec
- **Removal alternative:** n/a — split from accepted Spec
- **Pick:** n/a — split from accepted Spec
- **Plan / Spec:** n/a — split from accepted Spec

### G5: Chat scope `scope.py`

- Type: Task
- Parent: `DER-701`
- LLD: `docs/session-mail/lld.md#b4-chat-scope-scopepy-the-rule-for-messaging-sessions-inside-the-plugin`
  (B4)
- Branch: `der-701/chat-scope` in `alexderz/hermes-intercom`, from `integrate/session-mail`
- Builder: Claude Opus

**Outcome:** every session has a chat scope: `private`, `shared`, or `None` for local
sessions. It comes from one rule inside the plugin that fails closed.

**Acceptance:**
- **Origin:** read from `hermes_state.SessionDB(read_only=True)`. Only the raw `platform`,
  `chat_id`, `chat_type` and `user_id` are used.
- **Local sources:** the B4 set, which G14 confirms against a real owner.
- **Rule:** `private` only when `"<platform>:<chat_id>"` is in `settings.echo_chats`, or the chat
  is a DM and `"<platform>:<user_id>"` is in `settings.owner_user_ids`. Every other messaging
  chat is `shared`.
- **Entries:** a non-string or unprefixed entry is ignored with one warning.
- **Fresh reads:** settings are read with `ctx.get_config` on every call.
- **Fail closed:** a messaging source with no resolvable origin, a read error or a missing row
  → `shared`.

**Verify:**
```
cd <intercom-repo>
HERMES_HOME="$(mktemp -d)" <hermes-test-python> -I -m unittest discover -s tests -p 'test_scope.py' -t . -v
```
This covers the G-5 row of LLD § Verify.

- **Blocked by:** none
- **Blocks:** G3
- **Out of scope:** the echo (G6); the reply data-class rule (G9).
- **Proposed fix:** n/a — split from accepted Spec
- **Removal alternative:** n/a — split from accepted Spec
- **Pick:** n/a — split from accepted Spec
- **Plan / Spec:** n/a — split from accepted Spec

### G6: Echo `echo.py`

- Type: Task
- Parent: `DER-701`
- LLD: `docs/session-mail/lld.md#b6-echo-into-a-private-chat-sm-q15-b-through-ctxpost_message`
  (B6)
- Branch: `der-701/echo` in `alexderz/hermes-intercom`, from `integrate/session-mail`
- Builder: Claude Opus

**Outcome:** a message to a private messaging chat is also posted into that chat, escaped for
its renderer, from the target's own turn and before the answer. A shared chat never gets a
post.

**Acceptance:**
- **Hooks:**
  - queued or started messages: `pre_llm_call` of the turn whose prompt carries the header;
  - steered messages: the first `pre_api_request` whose `request_messages` carry the steer row
    (GW-4);
  - a steer that lands after the last request is echoed by the later turn's `pre_llm_call`.
- **What the hook reads:** only the user rows after the newest assistant row, enough to find a
  `📡` span and check its hash with G9's span finder. Nothing is kept or logged.
- **Once only:** the claim `UPDATE … SET echoed_at = ? WHERE id = ? AND echoed_at IS NULL`;
  retries never post twice.
- **When:** only for a `private` target scope with a matching `header_sha`.
- **Escaping:** per renderer, from `frame.ECHO_ESCAPERS`. A platform missing from it gets no
  post and one warning (N6-2).
- **Delivery is never affected:** the hook schedules `ctx.post_message` and returns. A failed or
  refused post is logged only. The owner never mirrors the body (N4).
- **Registration:** this item registers its own hooks in `register()`, next to G10's schema
  wiring.

**Verify:**
```
cd <intercom-repo>
HERMES_HOME="$(mktemp -d)" <hermes-test-python> -I -m unittest discover -s tests -p 'test_echo.py' -t . -v
```
This covers the unit part of the G-6 row of LLD § Verify: hook selection, the claim,
`ECHO_ESCAPERS` and the missing-escaper warning. The fake-ntfy E2E and O21 run in G14.

- **Blocked by:** G9 — the echo reuses B8 step 2's span finder and hash check (G5's scope,
  G7's escapers and G8's `echoed_at` reach it through G9 → G3)
- **Blocks:** G13, G14
- **Out of scope:** the real-owner E2E (G14); any core patch if O21 fails (the LLD's fallback is
  no echo for v1).
- **Proposed fix:** n/a — split from accepted Spec
- **Removal alternative:** n/a — split from accepted Spec
- **Pick:** n/a — split from accepted Spec
- **Plan / Spec:** n/a — split from accepted Spec

### G7: Framing `frame.py`

- Type: Task
- Parent: `DER-701`
- LLD: `docs/session-mail/lld.md#b5-framing-and-the-one-relabel-rule-framepy` (B5; the echo
  escapers of B6)
- Branch: `der-701/framing` in `alexderz/hermes-intercom`, from `integrate/session-mail`
- Builder: Grok 4.7

**Outcome:** every message is framed as A′, exactly as in `ux.md`, and model-written text
cannot pass for Alex's words or a control frame.

**Acceptance:**
- **Signature:** `build(message_id, sender, body, *, reply_mode, requested_interrupt, kind,
  reply_to, user_name, sender_scope, target_scope) -> (text, echo)`.
- **Text:**
  - header line 1 in its session, script and messaging variants;
  - the authority line, the interrupt note, the shared-chat line and the reply-destination line;
  - the relabelled body;
  - the footer chosen by `reply_mode` (B5 table);
  - the closing line.
- **Field cleaning:** removes Cc, Cf, Zl, Zp, `📡`, `[` and `]`, and collapses whitespace.
  `sanitize_title` is copied in, not imported.
- **The relabel rule (F4)** as written in B5. `_CONTROL_FRAME_RE` is built from
  `CONTROL_FRAME_OPENERS`, with the literal fallback tuple when the name is absent.
- **Inert (N2):** every variant's text starts with `📡` after `sanitize_user_prompt_text`.
- **Echo text and escapers:** `ECHO_ESCAPERS` maps platform → escaper (Telegram HTML or
  MarkdownV2, Discord, Slack, ntfy). Each covers link text, `@everyone`, `@here` and the
  `<@…>`, `<!…>` and `<#…>` forms.
- **`_short_desc`:** produces the 60-character first sentence.

**Verify:**
```
cd <intercom-repo>
HERMES_HOME="$(mktemp -d)" <hermes-test-python> -I -m unittest discover -s tests -p 'test_frame.py' -t . -v
```
This covers the G-7 row of LLD § Verify.

- **Blocked by:** none (`CONTROL_FRAME_OPENERS` and `sanitize_user_prompt_text` exist at the
  base, and B5 has a fallback; the listing matters only at vendoring, G12)
- **Blocks:** G3
- **Out of scope:** posting the echo (G6); the reply rule (G9).
- **Proposed fix:** n/a — split from accepted Spec
- **Removal alternative:** n/a — split from accepted Spec
- **Pick:** n/a — split from accepted Spec
- **Plan / Spec:** n/a — split from accepted Spec

### G8: Record `record.py`

- Type: Task
- Parent: `DER-701`
- LLD: `docs/session-mail/lld.md#b7-record-schema-recordpy` (B7)
- Branch: `der-701/record` in `alexderz/hermes-intercom`, from `integrate/session-mail`
- Builder: Grok 4.7

**Outcome:** a durable, owner-only SQLite record of every message, its delivery and its reply.

**Acceptance:**
- **Database:** `plugins.plugin_storage.plugin_db("intercom", "record.db")`, WAL,
  `busy_timeout` 5000 ms.
- **Modes:** `plugin-data/intercom/` is `0700`. `record.db` is created `O_EXCL` `0600` under
  `umask 077`, and `-wal` and `-shm` are `0600` after the first write.
- **Schema:** exactly the B7 `messages` table.
  - `reply_mode` has a check on the four values, and there is no `expect_reply` column.
  - It includes `delivery_path`, `admission_id`, `header_sha` and `echoed_at`.
  - `reply_state` is `NULL`, `sent`, `silent`, `stored` or `no-block`.
- **Helpers:** insert, update, the echo claim, and lookups by id, span hash and target lineage.
  There is no pruning, retry count or status ladder.

**Verify:**
```
cd <intercom-repo>
HERMES_HOME="$(mktemp -d)" <hermes-test-python> -I -m unittest discover -s tests -p 'test_record.py' -t . -v
```
This covers the G-8 row of LLD § Verify.

- **Blocked by:** none
- **Blocks:** G3
- **Out of scope:** `status` and `log` output (G10).
- **Proposed fix:** n/a — split from accepted Spec
- **Removal alternative:** n/a — split from accepted Spec
- **Pick:** n/a — split from accepted Spec
- **Plan / Spec:** n/a — split from accepted Spec

### G9: Replies and the in-process `ask`, `replies.py`

- Type: Task
- Parent: `DER-701`
- LLD: `docs/session-mail/lld.md#b8-replies-repliespy-registered-as-post_llm_call-in-the-owner`
  (B8)
- Branch: `der-701/replies` in `alexderz/hermes-intercom`, from `integrate/session-mail`
- Builder: Claude Opus

**Outcome:** the target's answer goes back to the sender by the sender's chosen `reply` mode.
`ask` waits for an explicit `reply` in the same process.

**Acceptance:**
- **Hook:** `post_llm_call`, which this item registers in `register()`. Steps 1–7 of B8.
- **Span finder:** finds spans and checks `header_sha`. It is a function G6 reuses.
- **Candidates:** only `kind='send'` rows with `reply_mode != 'none'` and `reply_state IS NULL`,
  targeting this session or its lineage. A `none` note never sends anything back.
- **Reply text by mode:**
  - `requested` and `waiting`: the block, else the whole answer, with the shared-sender rule
    (`stored` / `shared-chat-no-block`);
  - `optional` (a reply): the block only, else `no-block`.
- **Silence:** an empty block, or `[SILENT]` → `silent`.
- **Delivery:** with `route.send(..., delivery="steer", reply_mode="optional", reply_to=id)` on a
  fresh thread (`contextvars.copy_context().run`).
- **No wake for finished senders:** `cron`, `subagent`, `oneshot` and script senders are stored
  only (SM-Q9 b). Nothing retries.
- **`ask`:**
  - an in-process waiter, resolved only by a `reply` tool call whose `session_id` is the ask's
    target or its lineage;
  - returns `{"reply", "reply_from", "note"}` with the text relabelled;
  - `[SILENT]` → "nothing to add";
  - a `waiting` send never blocks.
- **Interface for G10:** the `ask` and `reply` handlers that G10's tool dispatch calls.

**Verify:**
```
cd <intercom-repo>
HERMES_HOME="$(mktemp -d)" <hermes-test-python> -I -m unittest discover -s tests -p 'test_replies.py' -t . -v
```
This covers the G-9 row of LLD § Verify, including all of these:
- a `none` note steered into a busy turn sends nothing back, even with a block in the answer;
- a reply without a block sends nothing back;
- a reply with a block is delivered.

- **Blocked by:** G3 — replies are delivered through `route.send` (G7's relabel and G8's record
  reach it through G3)
- **Blocks:** G6, G10
- **Out of scope:** the CLI (it has no `ask`); the echo (G6).
- **Proposed fix:** n/a — split from accepted Spec
- **Removal alternative:** n/a — split from accepted Spec
- **Pick:** n/a — split from accepted Spec
- **Plan / Spec:** n/a — split from accepted Spec

### G10: CLI, tool schema, caps removal and the legacy path

- Type: Task
- Parent: `DER-701`
- LLD: `docs/session-mail/lld.md#b9-receipts-error-codes-and-the-cli-clipy` (B9);
  `#b10-caps-removed-intercominboxpy` (B10); `#b11-tool-schema-and-tool-search-catalog-wording`
  (B11); `#b12-what-survives-of-intercoms-transport` (B12)
- Branch: `der-701/cli-schema` in `alexderz/hermes-intercom`, from `integrate/session-mail`
- Builder: Grok 4.7

**Outcome:** sessions use the `intercom` tool and scripts use `hermes intercom`, with the B9
receipts and exit codes. The caps are gone. The legacy socket path exists only on a Hermes build
without the owner client.

**Acceptance:**
- **Tool (B11):**
  - first sentence exactly `Message another Hermes session; never send an empty message.`;
  - `action` `list|send|ask|reply`; `reply` required for `send` (the handler refuses
    `reply-missing`);
  - `include_runs`, `query` and `limit` for `list`; `timeout` and `request_id` for `ask`;
  - the description sentences of B11, and Alex's interrupt sentence word for word.
  - `register()` builds the `to` wording from `check_project_addressing()` (G4), with no `@`
    anywhere when it is false.
  - The handler is synchronous, and `ask` and `reply` dispatch to G9.
- **CLI (B9):**
  - `send` takes `--reply none|requested|waiting` (default `none`); `--no-reply` is a usage
    error;
  - `list` takes `--include-runs`, `--query` and `--limit`, prints one row per line with the id
    first, and has `--json`;
  - `status` reads `prompt.receipt`, or the hashed transcript check;
  - `log` prints the B9 reply lines;
  - exit codes 0–6, with every receipt carrying `target_session`.
- **Caps (B10):** `_MAX_MSG_CHARS`, `_RATE_*` and `_DEDUPE_WINDOW_S` are removed.
  `_PENDING_CAP` stays only in the legacy path. 20 identical messages in a minute all arrive.
- **Legacy path (B12, R5-1, N6-1):**
  - chosen only when importing the owner-client names **fails**, never by liveness;
  - on such a build it starts lazily, only where `_find_cli_instance` finds a classic
    `HermesCLI`, and never reads argv;
  - its drain hook is registered only together with it;
  - intercom's 17 existing tests still pass.
- **`plugin.yaml`:** version 0.3.0, with `provides_hooks: [post_llm_call, pre_llm_call,
  pre_api_request]`.

**Verify:**
```
cd <intercom-repo>
HERMES_HOME="$(mktemp -d)" <hermes-test-python> -I -m unittest discover -s tests -p 'test_cli.py' -t . -v
HERMES_HOME="$(mktemp -d)" <hermes-test-python> -I -m unittest discover -s tests -p 'test_*.py' -t .
```
This covers the G-10 row of LLD § Verify; the second command runs all of intercom's tests.

- **Blocked by:**
  - G3 — `send` and the CLI run `route.send`;
  - G9 — the tool's `ask` and `reply` actions call B8's waiter.

  G4's `list` and `check_project_addressing`, and G8's record for `status` and `log`, reach it
  through G3.
- **Blocks:** G11, G13, G14
- **Out of scope:** the relay skills (G11); vendoring (G12).
- **Proposed fix:** n/a — split from accepted Spec
- **Removal alternative:** n/a — split from accepted Spec
- **Pick:** n/a — split from accepted Spec
- **Plan / Spec:** n/a — split from accepted Spec

### G11: Relays on `hermes intercom send`

- Type: Task
- Parent: `DER-701`
- LLD: `docs/session-mail/lld.md#planned-items-the-manager-files-them-at-groom-builder-suggested`
  (G-11); `#rollout--rollback` (step 4)
- Branch: `der-701/relays` in `alexderz/hermes-agent`, from `integrate/session-mail-023`
- Builder: Grok 4.7; the manager applies the live skill edit

**Outcome:** the relay skills send through `hermes intercom send`, and
`scripts/dashboard_dispatch.py` says it targets the admin dashboard only.

**Acceptance:**
- **Docstring:** a docstring-only note in `scripts/dashboard_dispatch.py` says it targets the
  admin dashboard, whose chats intercom cannot reach, and that relays use
  `hermes intercom send`. No code line changes (see "For the manager", item 2).
- **Relay text:** the replacement relay skill text is drafted in
  `docs/session-mail/relay-skills.md`, using the real G10 flags (`--to`, `--message` /
  `--file`, `--delivery`, `--reply`, `--from`) and session ids from `hermes intercom list`.
- **Manager-only, at deploy (G12 step 4):** the manager applies that text to the live relay
  skills. The builder never edits live skills.

**Verify:**
```
git diff integrate/session-mail-023 -- scripts/dashboard_dispatch.py   # docstring lines only
grep -n "hermes intercom send" docs/session-mail/relay-skills.md
python scripts/check
```

- **Blocked by:** G10 — the skill text uses the CLI's final flags and output
- **Blocks:** G12
- **Out of scope:** changing `dashboard_dispatch.py`'s behaviour; any rename (SM-Q10 withdrawn).
- **Proposed fix:** n/a — split from accepted Spec
- **Removal alternative:** n/a — split from accepted Spec
- **Pick:** n/a — split from accepted Spec
- **Plan / Spec:** n/a — split from accepted Spec

### G12: Vendor into hermes-agent, then deploy (gateway restart)

- Type: Task
- Parent: `DER-701`
- LLD: `docs/session-mail/lld.md#land` (subtree rule); `#rollout--rollback` (steps 1–5)
- Branch: `der-701/vendor` in `alexderz/hermes-agent`, from `integrate/session-mail-023`
- Builder: Grok 4.7 (the vendor branch and its tests); the manager does the steps marked
  manager-only

**Outcome:** `plugins/intercom` in hermes-agent is intercom's project-main, unsquashed. It
passes boundary lint and the owner E2E. After the manager's steps, it runs in the live gateway.

**Acceptance (builder):**
- **Vendor:** `git subtree add --prefix plugins/intercom <intercom-remote> integrate/session-mail`,
  with no `--squash`. No file under `plugins/intercom/` is edited in hermes-agent; fixes go to
  intercom first.
- **Lint:** `scripts/boundary_lint.py` passes for `plugins/intercom` (it needs G1's listings).
- **E2E:** G14's E2E passes against the vendored copy, with no `--intercom-src`.
- **Trunk branch:** the feature branch onto `alex/v0.23.1-canary-1110` is prepared for the
  fast-forward.

**Manager-only steps** (not the builder's):
1. **Manager-only:** fast-forward and `git pull --ff-only` in the install, then house-infra
   enables intercom in `hosts/<gateway-host>/hermes.py`:
   - `plugins.enabled += [intercom]`;
   - `allow_gateway_injection: true`;
   - `settings.user_name`, `settings.echo_chats` and `settings.owner_user_ids`;
   - `settings.project_plugin` only once DER-686 ships (HLD O24).
2. **Manager-only:** the **announced gateway restart**, in the window Alex approves. Then the
   post-restart checks of LLD § Verify (G-12 row) on the live install:
   - intercom is enabled in the owner;
   - `hermes intercom send --to Home --message "deploy check" --delivery queue --reply none`
     exits 0;
   - an admin-dashboard chat exits 4 `not-addressable`.
3. **Manager-only:** apply G11's relay skill text.

  Rollback: remove `intercom` from `plugins.enabled` and restart, or revert the fast-forward.

**Verify (builder, temporary home only):**
```
python scripts/boundary_lint.py
HERMES_HOME="$(mktemp -d)" scripts/run_tests.sh tests/plugins/intercom/
python scripts/check
```

- **Blocked by:**
  - G1 — the vendored plugin passes boundary lint only with the listings;
  - G11 — deploy step 3 applies its relay text;
  - G14 — the integrated plugin must pass the owner E2E before it is vendored and deployed;
  - the operator: Alex approves the restart window (manager-only step 2).
- **Blocks:** none
- **Out of scope:**
  - any `plugins/intercom` edit that is not a subtree operation;
  - the admin dashboard's restart (not needed unless its plugins change).
- **Proposed fix:** n/a — split from accepted Spec
- **Removal alternative:** n/a — split from accepted Spec
- **Pick:** n/a — split from accepted Spec
- **Plan / Spec:** n/a — split from accepted Spec

### G13: Upstream drafts (drafts only; nothing is posted)

- Type: Task
- Parent: `DER-701`
- LLD: `docs/session-mail/lld.md#paths--modules` (`intercom:docs/upstream/…`); HLD Part D
- Branch: `der-701/upstream-drafts` in `alexderz/hermes-intercom`, from `integrate/session-mail`
- Builder: Grok 4.7

**Outcome:** Alex has ready-to-review drafts for upstream. No agent posts, opens or comments
anything.

**Acceptance:** drafts in `docs/upstream/`:
- **the #81885 update:** the gateway-only design, the owner verbs, and the finding that the
  published `ctx.inject_message` returned `True` but ran nothing inside the owner (Trial round
  3);
- **the majordave pull request description:** for intercom's changes (owner client, A′ frame,
  replies, caps removed, legacy path kept);
- **the two listing pull request descriptions:** L-1 and L-2, matching G1's diff.

Each draft names what it asks and states that nothing was posted. No secrets, house host names or
local paths.

**Verify:**
```
cd <intercom-repo>
ls docs/upstream/
grep -nE -i '<house-detail pattern>' docs/upstream/ ; test $? -eq 1   # the manager's house-detail scrub; no match
```
The reviewer reads the drafts against G1's diff and intercom's project-main. No `gh` command
that writes is run.

- **Blocked by:**
  - G1 — the listing drafts describe its diff;
  - G6 and G10 — the majordave draft describes the finished plugin.
- **Blocks:** none
- **Out of scope:** posting, opening or commenting upstream (Alex does that, if he chooses).
- **Proposed fix:** n/a — split from accepted Spec
- **Removal alternative:** n/a — split from accepted Spec
- **Pick:** n/a — split from accepted Spec
- **Plan / Spec:** n/a — split from accepted Spec

### G14: Owner E2E of the integrated plugin (split from G-2)

- Type: Task
- Parent: `DER-701`
- LLD: `docs/session-mail/lld.md#verify` (the E2E parts of the G-2 and G-6 rows); B1, B4, B6,
  B12
- Branch: `der-701/owner-e2e` in `alexderz/hermes-agent`, from `integrate/session-mail-023`
- Builder: Claude Opus

**Outcome:** a real gateway owner in a temporary home proves the whole plugin, with a fake model
and a fake ntfy server. It covers every mode with idle and cold start, replies, the echo and the
legacy-path guarantee, before anything is vendored or deployed.

**Acceptance:**
- **Harness:** `tests/plugins/intercom/test_e2e_owner.py` (with a local conftest) starts:
  - a real `hermes gateway run` owner in a temp `HERMES_HOME`, with a fake-model provider;
  - the bundled ntfy adapter against a fake ntfy server;
  - a classic CLI under a pty;
  - an owner-attached client.
- **Plugin source:** it installs the plugin into `$HERMES_HOME/plugins/intercom`, from
  `plugins/intercom` when vendored, else from the pytest option `--intercom-src <intercom-repo>`.
  With neither, it skips with that reason. It adds no new environment variable.
- **G-2's E2E rows:**
  - Trial round 3's 24 cells, rebuilt from scratch;
  - the exact `sessions.source` strings for local and owner sessions, asserted against G5's
    local set (HLD O22);
  - after an owner restart, no intercom socket exists under `$HERMES_HOME/intercom/sessions/`
    and no drain hook is registered (R5-1).
- **G-6's E2E rows (O21):**
  - an echo is posted in a private chat from the target's own turn, and never in a shared chat
    or for a lookalike;
  - the escaping cases go through the real ntfy adapter;
  - after a delivery into an unlisted group, the fake server received only the answer (N4);
  - steered-echo GW-4: a steer followed by the final answer is echoed once, before the answer.
- **Replies across kinds:** CLI → owner-attached, ntfy → owner-attached, owner-attached → ntfy.
  An admin-dashboard chat is `not-addressable`.
- **Verdict:** the item closes with one, like a review item. A failure is filed as a fix item
  blocked by this one, for example O21 failing (the echo dropped for v1, SM-Q15 → a) or the
  source strings differing (G5).

**Verify:**
```
HERMES_HOME="$(mktemp -d)" scripts/run_tests.sh tests/plugins/intercom/test_e2e_owner.py --intercom-src=<intercom-repo>
python scripts/check
```
Run it with `<intercom-repo>` at intercom's project-main, with G2 … G10 merged.

- **Blocked by:**
  - G6 — the echo E2E and O21 need the echo hooks;
  - G10 — the cells drive the tool and the CLI, and the R5-1 check needs the legacy-path
    selection.

  G2 … G9 reach it through these.
- **Blocks:** G12
- **Out of scope:**
  - the Ink TUI client itself and the Desktop backend (emulated by an owner-attached client, as
    in the Trial);
  - multiplexed profiles;
  - the live install.
- **Proposed fix:** n/a — split from accepted Spec
- **Removal alternative:** n/a — split from accepted Spec
- **Pick:** n/a — split from accepted Spec
- **Plan / Spec:** n/a — split from accepted Spec

## Graph

- Wave 1: G1, G2, G4, G5, G7, G8
- Wave 2: G3 ← G2, G4, G5, G7, G8
- Wave 3: G9 ← G3
- Wave 4: G6 ← G9; G10 ← G3, G9
- Wave 5: G11 ← G10; G13 ← G1, G6, G10; G14 ← G6, G10
- Wave 6: G12 ← G1, G11, G14 (and the operator's restart window)

Gates: `G14` — the end-to-end check of the integrated whole.
- Only a real owner with the whole plugin can prove Trial round 3's cells, O21 (do the echo
  hooks fire bound to the messaging session, and does `post_message` post there), the owner's
  source strings, and the R5-1 socket guarantee.
- One gateway restart deploys the plugin to every chat at once, so this check comes before it.
- G14 waits on all of wave 4 and is the only blocker of G12 that is not already met by an earlier
  wave.
- G13 runs beside it, because the drafts need no E2E result.

## For the manager

1. **E2E ownership is ambiguous in the LLD.** The items table gives "the owner E2E harness" to
   G-2, but the Land table puts "G-12 vendor and E2E" on hermes-agent, and the E2E needs the
   whole plugin. This groom splits it out as G14. The LLD's G-2 row can be read as the client
   only.
2. **`scripts/dashboard_dispatch.py`: unchanged or a docstring note?** The LLD's Paths table and
   its G-11 Verify row say "unchanged". Its G-11 items row asks for a docstring note. G11 plans a
   docstring-only note, which keeps behaviour unchanged. Confirm, or drop the note from G11.
3. **Where the relay skill text lives.** The LLD says the manager edits the live skills at
   deploy, but names no place for the new text. G11 drafts it in
   `docs/session-mail/relay-skills.md`.
4. **Two interface clarifications** that keep wave 1 wide; neither changes behaviour:
   - G4 takes the owner's `session.list` rows through an injected lister, which G2's
     `client.list_sessions` fills;
   - G6 and G9 register their own hooks in `register()`, while G10 owns the schema, the CLI and
     the legacy wiring.
5. **The lefthook incident applies to every hermes-agent branch.** Builders commit in worktrees
   with hooks off or an isolated `HERMES_HOME`, because the hook provisions into the account's
   real home. The cleanup of the earlier live-home artifacts is still the manager's.
