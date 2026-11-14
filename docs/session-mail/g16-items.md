# G16 build items (groomed 2026-11-14)
Accepted plan: `passive.md`. Groom review: `reviews/g16-groom-review.md` (15 findings, all applied with the reviewer's text). Builders: claude = Claude Opus, grok = Grok 4.7. Build order is serial.

## G16a — Passive send path and record (passive, key, to: all)

Repo: `intercom` · branch `der-767/send` · builder claude · blocked by none

- Type: Task · Parent: `DER-767` (under `DER-701`)
- Design: `docs/session-mail/passive.md` sections 1, 2, 5 (P1), 6 — accepted by Alex 2026-11-14 ("27 yez, have at it")
- Builder: Claude Opus

**Outcome:** a sender can store a passive note (optionally keyed, optionally to `all` in its own profile); nothing is delivered yet (G16b hands notes over).

**Acceptance:**
- Tool schema: `delivery` gains `passive`; new optional `key` (string). CLI `send` gains `--delivery passive` and `--key KEY`; `--to all` accepted. Tool description gains one line: "passive: held until the target's next turn, never wakes it; key: a newer message with the same key replaces a held one".
- `route.send`: `passive` is handled before the live-delivery enum check; `all` is matched before `address.resolve` (like `Home`).
- Usage errors, refused before a message id exists, nothing recorded, CLI exit 2, each message giving the reason in plain words: `key` with steer or interrupt or ask; `to: all` without passive and a key; `to: all` with reply other than `none`; passive with `reply: waiting`; passive with `ask`; passive on the legacy socket path → `no-seam`. (`key` with `queue` is accepted here: delivered as plain queue, with `note_key` recorded and no other effect, until G16c. Do not refuse it.)
- Consent: `injection_allowed()` checked at send for passive.
- Record (`record.py`): notes are rows in `messages`. Guarded migration in `connect()`: `note_key`, `offered_turn`, `sender_profile` columns via `ALTER TABLE ADD COLUMN` checked with `PRAGMA table_info`, inside `BEGIN IMMEDIATE` (or "duplicate column name" counts as success; gateway and CLI both open the record); new table `note_seen(root_id, note_key, message_id, turn_id, delivered_at, PRIMARY KEY(root_id, note_key))` as its own statement. `_UPDATE_FIELDS` and the module writer list updated. An `all` note is one row (`address='all'`, no target). Stored result `pending` (plain queue keeps `held`). `requested='passive'`.
- Keyed replacement in one `BEGIN IMMEDIATE`: the pending row with the same key **and the same mode** for the same target lineage (per target: compaction lineage via the existing lineage helpers; for `all`: the pending `all` row) is marked `replaced` with `detail='replaced by <id>'`, then the new row is inserted (newest place). Different modes never replace each other.
- Receipt: `held` + message id (never "delivered"). `status <id>`: `held`, `delivered <time> (turn <id>)`, `replaced by <id>` (`replaced by <id> (handed over in turn <T>)` when the row also has `delivered_at`); for an `all` row `held for all · handed to N sessions` (N = confirmed `note_seen` rows), plus `replaced by <id>` when replaced. `log` lists passive rows with their state and key.
- Tests: new `tests/test_passive_send.py` covering every usage error, migration on an old-schema record (create one with the pre-G16 schema, open it twice from two connections), replacement order and same-mode scoping, lineage replacement across a compaction (real `SessionDB` in the temp home: `end_session(<id>, "compression")` plus a child with `parent_session_id`, as `tests/test_replies.py:470-473` does), `all` as one row, receipts and status text.

**Verify:**
```
cd <intercom-repo>
HERMES_HOME="$(mktemp -d)" <hermes-test-python> -I -m unittest discover -s tests -p 'test_passive_send.py' -t . -v
HERMES_HOME="$(mktemp -d)" <hermes-test-python> -I -m unittest discover -s tests -p 'test_*.py' -t .
git grep -n -i -E "$HOUSE_PATTERN" -- . ':!tests/fixtures' ; test $? -eq 1
```

- **Blocked by:** none · **Blocks:** G16b, G16c, G16d
- **Out of scope:** everything the plan marks settled (no caps, holds, expiry, retries or approval gates on delivery; gateway only; published plugin API only, no core change; reply modes; `[SILENT]`; no general notifications or forwarding); the live install; the subscription monitor's own sender (built elsewhere).

## G16b — Turn-start handover of held notes (offer, confirm, answers, echo)

Repo: `intercom` · branch `der-767/handover` · builder claude · blocked by G16a

- Type: Task · Parent: `DER-767`
- Design: `docs/session-mail/passive.md` section 3 and P2 in section 5 — accepted 2026-11-14
- Builder: Claude Opus

**Outcome:** held notes reach the target at the start of its next turn, exactly once, in the compact or full frame; answers return only from `[REPLY <id>]` blocks.

**Acceptance:**
- New `passive.py`, registered in `register()` beside echo (published hooks only): `pre_llm_call` selects the target lineage's `pending` per-target rows with `requested='passive'` (G16c adds keyed queued rows whose wake is dead) and the newest unseen `all` row per key (own profile; session `source` not in `address.RUN_SOURCES`; not the sender's own lineage; `injection_allowed()` true at handover), oldest first, and returns them as the turn's context. Lineage root falls back to the session id when no lineage row exists.
- Offer/confirm: offer writes `messages.offered_turn` (per-target) or upserts `note_seen(root_id, note_key) = (message_id, turn_id, NULL)` (`all`), in one `BEGIN IMMEDIATE`; `pre_api_request` on the first request with that `turn_id` confirms: `UPDATE messages SET delivered_at=?, result=CASE WHEN result='replaced' THEN result ELSE 'delivered' END WHERE offered_turn=? AND delivered_at IS NULL` and `UPDATE note_seen SET delivered_at=? WHERE root_id=? AND turn_id=? AND delivered_at IS NULL`. Unconfirmed offers are offered again on the next turn. A vetoed turn or one that makes no generic API request leaves notes held.
- Frames (`frame.py`): compact one line per note when no offered note asks for a reply — `📡 Held note (<sender label>, <HH:MM>; not from <user>, no reply): <body>` (several notes: one such line each); full block from section 3 when any note asks for a reply, with the answering instructions in the first line and `📡 End of held notes` last. `<user>` from the configured user name via the existing helper. Bodies relabelled with the existing lookalike/control-frame relabelling.
- Answers: `replies.py` adds the notes **confirmed** in this turn (`offered_turn = turn_id AND delivered_at IS NOT NULL`, looked up by the hook's `turn_id`) to its candidates; passive rows take the existing `optional` branch: only a `[REPLY <id>]` block is sent; no block → nothing sent, `reply_state='no-block'`.
- Echo: per-target passive notes into private chats (existing scope rule) are echoed at confirmed handover with their own echo text (header line plus relabelled body) and the existing once-only claim; `all` notes are never echoed.
- Code pointers: `on_post_llm_call` returns early when no span is found (`replies.py:134-136`), so the turn-id candidates are added before that return; the block-only rule keys on `requested='passive'`, not on "found by turn id" (keyed queued rows found by turn id keep the normal `requested` branch); `reply_for`'s `optional` branch tests `row["reply_mode"]` (`replies.py:167-169`); `passive.py` uses the dual `from . import …` / `import …` pattern (`echo.py:399-406`); per-target frames carry the existing shared-chat line when the target's stored scope is shared, and for `all` notes the scope is computed per recipient at handover.
- Legacy drain hook unaffected; the steer path (no turn start) hands nothing over.
- Tests: new `tests/test_passive_handover.py`: compact vs full frame; oldest-first order; once-only across two turns; veto (no `pre_api_request`) → re-offered next turn; confirm after offer; failed model call after the first request → delivered, not re-offered; replaced while its offering turn runs → stays `replaced`, marked handed over; compaction between send and handover → delivered once to the new tip; `all` once per version, not to cron/subagent/oneshot sessions, not to the sender's lineage, a later-created session gets it; injection off at handover → stays held; reply by block, reply without block (`no-block`), a typed lookalike block for an unconfirmed note ignored; echo for a private chat, none for `all`.

**Verify:**
```
cd <intercom-repo>
HERMES_HOME="$(mktemp -d)" <hermes-test-python> -I -m unittest discover -s tests -p 'test_passive_handover.py' -t . -v
HERMES_HOME="$(mktemp -d)" <hermes-test-python> -I -m unittest discover -s tests -p 'test_*.py' -t .
git grep -n -i -E "$HOUSE_PATTERN" -- . ':!tests/fixtures' ; test $? -eq 1
```

- **Blocked by:** G16a · **Blocks:** G16c, G16d
- **Out of scope:** everything the plan marks settled (no caps, holds, expiry, retries or approval gates on delivery; gateway only; published plugin API only, no core change; reply modes; `[SILENT]`; no general notifications or forwarding); the live install; the subscription monitor's own sender (built elsewhere).

## G16c — Keyed queue: wake through Hermes's queue, newest version from the record

Repo: `intercom` · branch `der-767/keyed-queue` · builder claude · blocked by G16b

- Type: Task · Parent: `DER-767`
- Design: `docs/session-mail/passive.md` section 1 (keyed queue paragraph), section 2 (keys), P5 in section 5 — accepted 2026-11-14 (scope addition "Key should work with queue too?")
- Builder: Claude Opus

**Outcome:** several keyed queued messages sent while the target is busy produce one next turn carrying only the newest; to an idle target one starts at once.

**Acceptance:**
- A keyed `queue` send stores a `pending` row with its key and a wake marker column (`wake_admission` or equivalent, added by the same guarded migration pattern). In the same `BEGIN IMMEDIATE`: if no earlier pending row with this key, mode and lineage has an outstanding wake, the send submits one after commit: a framed session-mail line (`frame.build`, `header_sha` recorded on the row whose send submitted it, framed with `reply_mode='none'`; `echo._echo` skips rows that carry a wake marker; the only reply candidate in the wake turn is the newest row, through G16b's turn-id lookup) saying "keyed update `<key>` from `<sender>`; the current version follows", through the existing queue path (`client.deliver_sync(target, wake, "queue", submission_id)`). Otherwise the new row inherits the outstanding wake (older row `replaced`).
- When the wake's turn starts, G16b's `pre_llm_call` finds the wake span in `user_message` with the existing span finder and offers the newest pending row for that key, mode and lineage, with G16b's offer/confirm. Outside its wake turn, a keyed queued row is offered only when its wake is dead (the restart rule below); a row with a live wake waits for its wake turn. Answers to it use the normal `requested` branch (the turn exists for the message), not the block-only passive branch.
- Restart: the wake marker stores the owner's `instance_id` (from the discovered endpoint, `GatewayEndpoint.instance_id`; `client.deliver_sync` returns it in its outcome) with the admission id. A wake is outstanding only when its `instance_id` equals the current owner's. A send compares against the endpoint it discovers for delivery; `pre_llm_call` compares against the owner instance id, discovered once per process and cached. A marker from an earlier instance is dead: the next keyed send queues a new wake, and the pending row rides the target's next turn as a held note. Nothing clears markers at `register()` (it also runs in every `hermes intercom` CLI process).
- Receipt: `started` (idle target) or `queued (replaceable, key <k>)` (busy). The wake line is never echoed; the newest version is echoed at confirmed handover in private chats as in G16b.
- Plain unkeyed queue is unchanged.
- Tests: new `tests/test_keyed_queue.py`: two keyed queued sends while busy → one wake, the turn carries the newer text; idle target starts at once; a send committed exactly as the wake turn claims (hold the record transaction) → either it is in this turn or a second wake is queued, never lost; wake turn interrupted during its API call, or a non-retryable API error → the note is delivered (confirmed at the first request), is not re-offered, and no second wake is queued; a wake turn that stops before its first request → the note stays pending and the next turn gets it; restart clears wake markers and the row rides the next turn; passive and queued with the same key do not replace each other; `key` with `ask` refused (already in G16a; assert still true); a private-chat target gets one echo (the newest version), never the wake line; a `requested` keyed queued message gets exactly one reply; a CLI `register()` between two keyed queued sends does not cause a second wake; a marker from a different owner instance is treated as dead.

**Verify:**
```
cd <intercom-repo>
HERMES_HOME="$(mktemp -d)" <hermes-test-python> -I -m unittest discover -s tests -p 'test_keyed_queue.py' -t . -v
HERMES_HOME="$(mktemp -d)" <hermes-test-python> -I -m unittest discover -s tests -p 'test_*.py' -t .
git grep -n -i -E "$HOUSE_PATTERN" -- . ':!tests/fixtures' ; test $? -eq 1
```

- **Blocked by:** G16b · **Blocks:** G16d
- **Out of scope:** everything the plan marks settled (no caps, holds, expiry, retries or approval gates on delivery; gateway only; published plugin API only, no core change; reply modes; `[SILENT]`; no general notifications or forwarding); the live install; the subscription monitor's own sender (built elsewhere).

## G16d — Other profiles, explicitly (profile on send and list)

Repo: `intercom` · branch `der-767/profiles` · builder claude · blocked by G16c

- Type: Task · Parent: `DER-767`
- Design: `docs/session-mail/passive.md` P6 in section 5 (architect round 4) — accepted 2026-11-14 (scope addition "sessions can explicitly message other profiles chats and bot sessions")
- Builder: Claude Opus

**Outcome:** `send` and `list` take an optional `profile`; without it nothing changes.

**Acceptance:**
- Tool: optional `profile` on `send` and `list` (schema and description: "profile: another Hermes profile on this machine; reach its bot with to: \"Bot Chat\""). No new CLI flag (`hermes -p <name> intercom ...` already exists); the README in G16e says so.
- Name to home: `default` → the default root; others → `<root>/profiles/<name>`, validated with the published helpers `hermes_constants.get_default_hermes_root`, `PROFILE_ID_RE` and `named_profile_is_live`; the override is `set_hermes_home_override`/`reset_hermes_home_override`. Unknown or deleted → refused. "Intercom enabled" means `intercom` is in the target's `plugins.enabled` and not in `plugins.disabled`, read with `load_config_readonly()` under the helper.
- One helper `in_profile(name)` wrapping `set_hermes_home_override(home)` / `reset_hermes_home_override(token)` in try/finally. `route.send(..., profile=...)` computes sender facts first (its own profile), then runs resolve, chat scope, consent, record insert, frame, hash and deliver inside the helper. The client attaches as the socket peer; never pass `subject`. `list profile=` runs `address.list_sessions` inside the helper.
- Rows are written in the target profile's record with `sender_profile` set (NULL = same profile). The reply hook's `_deliver` sends the answer back with `profile=row['sender_profile']`.
- Target settings govern: `allow_gateway_injection`, `echo_chats`, `owner_user_ids` and `user_name` read from the target's config (`load_config_readonly()` under the helper), not from the sender's plugin `ctx`.
- Refused with reasons: `profile` with `to: all`; `profile` with `ask`; `profile` with `@project`; intercom not enabled in the target profile ("session mail is not enabled in profile <name>").
- Framing: on a send with `profile` (a different profile from the sender's), the sender label carries its profile (`hermes@<profile>/<title>`), keeping the header shape the reply regex needs, and the receipt names `<profile>/<title>`; same-profile frames are unchanged. `profile` naming the sender's own profile is the same as no `profile`.
- Tests: new `tests/test_profiles.py` with two temp homes (a root and `profiles/<name>`; a fake `client.deliver_sync`/`list_sessions` as `tests/test_route.py` does, and a real `SessionDB` in each temp home; the named home needs an identity marker (a `config.yaml`) to pass `hermes_constants.named_profile_is_live`): send default → named and named → default (the fake `deliver_sync` asserts `get_hermes_home()` is the target home when called, and the row, `state.db` lookups and config reads are the target's; discovery and the ticket mint are proven end to end in G16f); reply comes back to the sender's profile; passive note lands in the target's record; target injection off → refused; intercom disabled in target → refused; each refusal; `to: "Bot Chat"` resolves by exact title; the override is reset after errors.

**Verify:**
```
cd <intercom-repo>
HERMES_HOME="$(mktemp -d)" <hermes-test-python> -I -m unittest discover -s tests -p 'test_profiles.py' -t . -v
HERMES_HOME="$(mktemp -d)" <hermes-test-python> -I -m unittest discover -s tests -p 'test_*.py' -t .
git grep -n -i -E "$HOUSE_PATTERN" -- . ':!tests/fixtures' ; test $? -eq 1
```

- **Blocked by:** G16c · **Blocks:** G16e, G16f
- **Out of scope:** everything the plan marks settled (no caps, holds, expiry, retries or approval gates on delivery; gateway only; published plugin API only, no core change; reply modes; `[SILENT]`; no general notifications or forwarding); the live install; the subscription monitor's own sender (built elsewhere).

## G16e — README and version for passive, keys and profiles

Repo: `intercom` · branch `der-767/docs` · builder grok · blocked by G16d

- Type: Task · Parent: `DER-767`
- Design: `docs/session-mail/passive.md` sections 1-4 — accepted 2026-11-14
- Builder: Grok 4.7

**Outcome:** the README documents what G16a-d built, accurately; version 0.4.0.

**Acceptance:**
- `README.md`: a "Passive delivery and keyed messages" section (what passive does; compact and full frames with an example; when a note counts as delivered; keys, same-mode replacement and the shared namespace; keyed queue; `to: all` in the sender's own profile, `all` as a reserved address); a "Choosing a delivery" list matching the plan's section 4 guidance; an "Other profiles" section (`profile` on send and list, reaching a bot with `to: "Bot Chat"`, scripts use `hermes -p <name> intercom ...`, the refusals, target settings govern); the usage errors with their reasons; status/log states (`held`, `delivered`, `replaced`); the new record columns and table in the record section. Every flag, state and refusal stated must match the code (cite nothing that is not implemented).
- `plugin.yaml` version 0.4.0, and its `description` mentions passive and keyed messages (`pyproject.toml` is the test config; leave it).
- `docs/skill-guidance.md`: the plan's section-4 "Choosing a delivery" text, ready to paste; the manager applies it to the installed session-mail skill at deploy.
- No personal names, house names or private paths (`HOUSE_PATTERN` grep clean).

**Verify:**
```
cd <intercom-repo>
HERMES_HOME="$(mktemp -d)" <hermes-test-python> -I -m unittest discover -s tests -p 'test_*.py' -t .
git grep -n -i -E "$HOUSE_PATTERN" -- . ':!tests/fixtures' ; test $? -eq 1
grep -n '^version: 0.4.0$' plugin.yaml
```
The verifier also checks each README claim about flags, states and refusals against the code.

- **Blocked by:** G16d · **Blocks:** deploy (its skill-guidance text)
- **Out of scope:** everything the plan marks settled (no caps, holds, expiry, retries or approval gates on delivery; gateway only; published plugin API only, no core change; reply modes; `[SILENT]`; no general notifications or forwarding); the live install; the subscription monitor's own sender (built elsewhere).

## G16f — End-to-end cells on a real gateway owner for passive, keyed queue and profiles

Repo: `agent` · branch `der-767/e2e` · builder claude · blocked by G16d

- Type: Task · Parent: `DER-767`
- Design: `docs/session-mail/passive.md` section 5 Tests — accepted 2026-11-14
- Builder: Claude Opus

**Outcome:** the existing owner E2E harness (`tests/plugins/intercom/test_e2e_owner.py`, `_owner_world.py`, conftest; real `hermes gateway run` owner in a temp `HERMES_HOME`, fake model) proves the new behaviour before deploy.

**Acceptance (new cells; the existing 34 still pass):**
- passive to a running and to an idle session: neither wakes (no new turn, no steer); both get the note at their next turn (fake model sees the compact line in the user message); `status` shows delivered with that turn;
- keyed passive: three sends with the same key → one note at the next turn, newest text;
- `reply requested` passive note answered by `[REPLY id]` comes back to the sender; answered without a block → nothing comes back;
- veto: a test plugin vetoing `pre_llm_call` for one turn → the note is delivered on the following turn;
- keyed queue: two keyed queued sends during a running turn → exactly one following turn, carrying the newer text; to an idle session it starts at once;
- `to: all` keyed: delivered once to each conversation session and not to the sender (the run-source exclusion is unit-tested in G16b); a second version replaces it;
- other profiles: a named profile served by the owner's multiplexer (`gateway.multiplex_profiles: true`, intercom enabled in both): send default → named, and named → default, each delivered; a reply comes back across; `to: "Bot Chat"` with `profile` reaches the named profile's Bot Chat if the harness can create one cheaply, else that cell is replaced by an exact-title cell and the item records why;
- the subscription monitor's call as written in the plan: `hermes intercom send --to all --delivery passive --key subscription-usage --reply none --from subscription-monitor --message "<line>"` (CLI, exit 0, then handed over).

**Verify:**
```
HERMES_HOME="$(mktemp -d)" scripts/run_tests.sh --fail-on-skip --file-retries 0 --file-timeout <seconds> tests/plugins/intercom/test_e2e_owner.py -- --intercom-src=<intercom-repo>
python scripts/check
```
`<seconds>`: the builder measures the run and records the value (the existing suite took about 110 s). A FLAKY result is a failing verdict.

- **Blocked by:** G16d · **Blocks:** deploy (manager: subtree pull, deployed branch, idle-gated gateway restart, session-mail skill guidance from `docs/skill-guidance.md`)
- **Out of scope:** everything the plan marks settled (no caps, holds, expiry, retries or approval gates on delivery; gateway only; published plugin API only, no core change; reply modes; `[SILENT]`; no general notifications or forwarding); the live install; the subscription monitor's own sender (built elsewhere).
