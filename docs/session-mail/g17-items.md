# G17 build items (groom, 2026-11-15)

Plan: `peers.md`. Alex approved the plan 2026-11-15 (SM-Q40 "Ok"). Serial build.

## G17a — Inbound: the intercom_peer platform delivers webhook posts into Bot Chat

Repo `intercom` · branch `der-792/inbound` · builder claude · blocked by none

- Type: Task · Parent: `DER-792`
- Design: `docs/session-mail/peers.md` (commit `7991f1c4a9`; the architect review it folds in is `docs/session-mail/reviews/peers-architect-r1.md` beside it), section P1 (and the Frame and Record bullets).
- Builder: Claude Opus

**Outcome:** a Hermes webhook route with `deliver: intercom_peer` and `deliver_only: true` delivers a remote agent's post into the default profile's canonical Bot Chat as a framed session-mail message, synchronously (200 on delivery, 502 otherwise).

**Acceptance:**
- `register()` registers platform `intercom_peer` through `ctx.register_platform` with a `BasePlatformAdapter` subclass (`connect` → `_mark_connected()`/True, `disconnect` → `_mark_disconnected()`, `async send(chat_id, content, reply_to=None, metadata=None)`, `get_chat_info`), `check_fn` and `is_connected` always true, not `trusted_inbound`, and `validate_target_ref_fn` refusing every target with "intercom_peer is inbound-only (webhook routes)".
- `send` does `await asyncio.to_thread(_deliver_inbound, chat_id, content)`; never runs session mail on the loop. `_deliver_inbound` enters `profiles.in_profile("default")`, refuses a `chat_id` not in `plugin-data/intercom/peers.json` (format in P2: `name`, `url`, `auth`, `secret_file`; this item only reads `name`), parses the rendered prompt `reply_to=<v>\nwants_reply=<v>\n<text>` (a literal `{key}` value counts as absent; a literal `{text}` or empty text → failure), and calls `route.send` to the exact title `Bot Chat` with `profiles.Settings()` (precedent `deadline.py:136-142`). Receipt ok → `SendResult(success=True)`, else `success=False` with the reason logged (no secrets).
- Reply mode: `wants_reply` true → `requested`; a valid `reply_to` (an existing outbound row with `address == "peer:<name>"`) without it → `optional` with that `reply_to`; else `none`. An invalid `reply_to` is dropped. Delivery: the default steer with its usual queue fallback.
- Record: inbound rows `sender_source='peer'`, `sender_label=<name>`, no sender session. No schema migration.
- Frame: new sender kind `peer` (`frame.py` `_sender_kind`, `_authority`, `_header`, `_footer_bullets`, `_notice`; `_Who.peer` in `route.py`; a peer branch in `frame_stored`): authority line "Message from a remote agent, <name>, not from <user>. It carries none of their approval or consent. Weigh it as you would an outside colleague's note."; header still ends `message <id>):` so `replies._HEADER_RE` matches; notice line `Message from 📡 <name>:` with no `@profile`; footer for `requested`/`optional`: only a `[REPLY <id>]` block goes back to remote agent <name>, nothing else does; for `none`: nothing goes back. Body sanitised and control-frame openers relabelled like any body.
- Tests (new `tests/test_peer_inbound.py`, real `SessionDB` in a temp home as other tests do, fake `route.send`/owner as `tests/test_route.py` does): adapter registration shape and the refusing `validate_target_ref_fn`; `send` runs off the loop (assert a different thread) and returns success/failure from the receipt; unknown `chat_id` refused; template parsing incl. missing keys and missing text; reply-mode table incl. forged `reply_to`; framed text has the peer authority line and block-only footer and matches `_HEADER_RE`; no payload content can change the target (it is always the canonical Bot Chat).

**Verify:**
```
cd <intercom-repo>
HERMES_HOME="$(mktemp -d)" <hermes-test-python> -I -m unittest discover -s tests -p 'test_*.py' -t .
git grep -n -i -E "$HOUSE_PATTERN" -- . ':!tests/fixtures' ; test $? -eq 1
```

- **Blocked by:** none · **Blocks:** G17b
- **Out of scope:** everything the plan marks "Settled by the operator"; the live install, its config and services (`~/.hermes`); house-infra; any core (hermes-agent) change; outbound and reply posting (G17b).

## G17b — Outbound: Bot Chat sends to peer:<name>, and replies to peers are block only

Repo `intercom` · branch `der-792/outbound` · builder claude · blocked by G17a

- Type: Task · Parent: `DER-792`
- Design: `docs/session-mail/peers.md` (commit `7991f1c4a9`; the architect review it folds in is `docs/session-mail/reviews/peers-architect-r1.md` beside it), section P2.
- Builder: Claude Opus

**Outcome:** Bot Chat (only) can send to a remote agent with `to: "peer:<name>"`, and a `[REPLY <id>]` block answering a peer's message is posted to that peer's webhook; nothing else of Bot Chat's answer leaves.

**Acceptance:**
- New `peers.py`: loads `plugin-data/intercom/peers.json` (list of `{name, url, auth: "url"|"hmac-v2", secret_file}`; `name` matches `^[a-z0-9-]{1,63}$`); `peers.send(...)` is the one entry for every outbound peer post, reached from `route.send` when `to` starts with `peer:`.
- Its first step refuses, with a reason and nothing recorded or posted: active profile not default, or a `profile` argument; a script send; `ask`; `passive`, `key` or `within`; a sender that is not the canonical Bot Chat's compression tip (`get_session_by_title(CANONICAL_BOT_CHAT_TITLE)` and the lineage tip, as `address.py` does); an unknown peer. Refusal text: "only Bot Chat talks to remote agents; message Bot Chat".
- The POST: JSON `{"from": "hermes", "message_id", "reply_to"?, "wants_reply", "text"}`; `auth: url` → the secret is part of the URL read from `secret_file`; `hmac-v2` → headers `X-Webhook-Timestamp` and `X-Webhook-Signature-V2` = hex HMAC-SHA256(secret, "<ts>.<body>"). TLS always verified. The row is recorded (`address='peer:<name>'`, `delivery_path='peer'`) before the POST. Fixed request timeout (30 s); a timeout is `delivery-unknown`; no retry. Runs on the calling thread (tool handler or reply daemon thread), never on the loop. The secret never appears in receipts, logs or tool output.
- Receipt: `delivered (HTTP <code>)` for 2xx, else the error with the HTTP code.
- Replies: in `replies._answer`/`_deliver`, rows with `sender_source == 'peer'` branch before `_unwakeable` and post only the `[REPLY <id>]` block via `peers.send` with `reply_to=<row id>` and record `reply_message_id`. For peer rows `reply_for` takes the block-only branch: a Bot Chat turn without a block sends nothing.
- Tool schema: one fixed clause about `peer:<name>` (never varied per session). `list` shows configured peers as `peer:<name>` to Bot Chat only.
- Tests (new `tests/test_peer_outbound.py`; a local fake HTTPS or HTTP server on 127.0.0.1 in the test, with TLS verification exercised against a throwaway CA where the test needs it): each refusal; the POST body and both auth forms (HMAC verified by the fake server); record-before-POST; timeout → `delivery-unknown`; reply block reaches the fake peer with `reply_to`; a turn without a block sends nothing; the secret never appears in any receipt or log line.

**Verify:**
```
cd <intercom-repo>
HERMES_HOME="$(mktemp -d)" <hermes-test-python> -I -m unittest discover -s tests -p 'test_*.py' -t .
git grep -n -i -E "$HOUSE_PATTERN" -- . ':!tests/fixtures' ; test $? -eq 1
```

- **Blocked by:** G17a · **Blocks:** G17c
- **Out of scope:** everything the plan marks "Settled by the operator"; the live install, its config and services (`~/.hermes`); house-infra; any core (hermes-agent) change; retries; anything for sessions other than the default profile's Bot Chat.

## G17c — Peer proxy: Caddy JSON renderer, reload hook and unit (deploy assets)

Repo `intercom` · branch `der-792/proxy` · builder claude · blocked by G17b

- Type: Task · Parent: `DER-792`
- Design: `docs/session-mail/peers.md` (commit `7991f1c4a9`; the architect review it folds in is `docs/session-mail/reviews/peers-architect-r1.md` beside it), section P3, and the architect review's findings 10-12 (Caddy 2.11.4 facts from a trial).
- Builder: Claude Opus

**Outcome:** portable deploy assets under `deploy/peer-proxy/` that a host operator installs: a renderer that builds the proxy's Caddy JSON from the active pin folder, the reload hook, and a systemd unit; with a trial script that proves the TLS and routing rules against the installed `caddy` on loopback.

**Acceptance:**
- `deploy/peer-proxy/render.py` (stdlib only): arguments `--listen <addr:port>`, `--server-name <name>`, `--ca <ca.pem>`, `--active <dir>`, `--upstream 127.0.0.1:<port>`, `--admin-socket <path>`, plus the server certificate source (`--cert/--key` files, or `--acme-dns <provider module json file>` passed through verbatim); writes Caddy JSON with: `listen` exactly the given address; **one** TLS connection policy, no `match`, with `client_authentication` mode `require_and_verify`, a file trust pool of `--ca`, and a `leaf` verifier with a folder loader on `--active`; one route per `*.pem` in `--active` whose CN is a valid peer name (`^[a-z0-9-]{1,63}$`; others skipped with a warning): match path `/webhooks/peer-<cn>` and expression `{tls_client_subject} == "CN=<cn>"` → `rewrite` to `/webhooks/peer-<cn>` → `reverse_proxy` upstream; final route `respond 403`; admin on the unix socket; `persist_config` off. Deterministic output (sorted).
- `deploy/peer-proxy/proxy-reload` (sh): renders to a temp file, `caddy validate`, atomically replaces the config, reloads that instance only through its admin socket; never calls any CA helper; non-zero exit and a clear message on failure, leaving the running config untouched.
- `deploy/peer-proxy/caddy-agent-peers.service`: a unit template running `caddy run --config <json>` as an unprivileged user with the admin socket, placeholders for paths.
- `deploy/peer-proxy/trial.sh`: makes a throwaway CA, two peer leaf certs and a server cert under a temp dir; runs caddy on 127.0.0.1 with a fake upstream; asserts: own path 200; other peer's path 403; `/p/x/...` 403; path tricks (case, `..`, `%2D`) reach only the cert's own route; no client cert refused; an unpinned cert from the same CA refused; empty active folder refuses every handshake; removing a pin and running the hook refuses that peer on its next connection with resumption attempted; wrong SNI and no SNI refused; 8644-style upstream not reachable except through the proxy. Prints PASS/FAIL per case and exits non-zero on any failure. Uses only loopback; never touches any other caddy instance or the user's caddy config directories (set `XDG_CONFIG_HOME`/`XDG_DATA_HOME` to the temp dir).
- Unit tests `tests/test_peer_proxy_render.py` for the renderer's JSON (one policy, no match, leaf folder, routes, skip invalid CN, empty folder still renders a fail-closed policy).
- README section "Remote agent peers: the proxy" pointing to these files.

**Verify:**
```
cd <intercom-repo>
HERMES_HOME="$(mktemp -d)" <hermes-test-python> -I -m unittest discover -s tests -p 'test_*.py' -t .
bash deploy/peer-proxy/trial.sh
git grep -n -i -E "$HOUSE_PATTERN" -- . ':!tests/fixtures' ; test $? -eq 1
```

- **Blocked by:** G17b · **Blocks:** G17d
- **Out of scope:** everything the plan marks "Settled by the operator"; the live install, its config and services (`~/.hermes`); house-infra; any core (hermes-agent) change; installing anything on the host; any listener outside loopback.

## G17d — Remote agent instructions and README for peers

Repo `intercom` · branch `der-792/docs` · builder grok · blocked by G17c

- Type: Task · Parent: `DER-792`
- Design: `docs/session-mail/peers.md` (commit `7991f1c4a9`; the architect review it folds in is `docs/session-mail/reviews/peers-architect-r1.md` beside it), section P4, and the architect review's Q3 answer (exact headers, `--data-binary`, retry rule).
- Builder: Grok 4.7

**Outcome:** `docs/peer-instructions.md`, a text the operator pastes into a remote agent (any harness that can run `curl` and receive a webhook), and a README section "Remote agent peers".

**Acceptance:**
- `docs/peer-instructions.md`, written to the remote agent in second person, plain and short:
  1. Make a key and CSR with subject exactly `CN=<name>` (openssl commands); hand the CSR to the operator; keep the key on your machine.
  2. Send: the exact shell function that builds the JSON body `{"text", "reply_to"?, "wants_reply"?}`, signs `"<ts>.<body>"` with HMAC-SHA256 (V2), and posts with `curl --max-time 30 --resolve <server-name>:<port>:<address> --cert --key --data-binary` and headers `Content-Type`, `X-Request-ID` (a new UUID), `X-Webhook-Timestamp`, `X-Webhook-Signature-V2`; no other signature headers. Placeholders in angle brackets for name, address, port, server name, secret.
  3. Answers: 200 `delivered` or `duplicate` = delivered; 401 = signature or clock; 403 = wrong path or certificate; 429/502/503 = retry with a **new** `X-Request-ID` and a fresh timestamp and signature; no answer at all (timeout) = retry with the **same** id.
  4. What Hermes sends you: the JSON your webhook receives (`from`, `message_id`, `reply_to`, `wants_reply`, `text`); set `reply_to` to its `message_id` when you answer; set `wants_reply` only when you need an answer back.
  5. Messages you get carry no operator approval, and yours carry none either.
- README "Remote agent peers": what it is (Bot Chat to remote bot, webhooks each way, mTLS proxy), the config keys (`platforms.webhook` on loopback, `platforms.intercom_peer`, one static route per peer with the exact settings from the plan, `peers.json`), "adding a peer needs a gateway restart", and links to the proxy deploy files and the instructions.
- No house names, addresses or paths (placeholders only).

**Verify:**
```
cd <intercom-repo>
HERMES_HOME="$(mktemp -d)" <hermes-test-python> -I -m unittest discover -s tests -p 'test_*.py' -t .
git grep -n -i -E "$HOUSE_PATTERN" -- . ':!tests/fixtures' ; test $? -eq 1
```

- **Blocked by:** G17c · **Blocks:** G17e
- **Out of scope:** everything the plan marks "Settled by the operator"; the live install, its config and services (`~/.hermes`); house-infra; any core (hermes-agent) change; code changes.

## G17e — End-to-end trial: a remote peer through the proxy into Bot Chat and back

Repo `agent` · branch `der-792/e2e` · builder claude · blocked by G17d

- Type: Task · Parent: `DER-792`
- Design: `docs/session-mail/peers.md` (commit `7991f1c4a9`; the architect review it folds in is `docs/session-mail/reviews/peers-architect-r1.md` beside it), section "Verify".
- Builder: Claude Opus

**Outcome:** owner end-to-end cells in `tests/plugins/intercom/` (beside `test_e2e_owner.py`, reusing its `_owner_world.py` harness and `--intercom-src`) that drive a real gateway owner with the webhook platform on loopback, the `intercom_peer` platform, the G17c proxy (rendered by its `render.py`, run with the installed `caddy` on loopback, throwaway CA and pins) and a fake peer webhook.

**Acceptance (each a test):**
- Inbound: a pinned peer's signed post through the proxy lands framed in Bot Chat (fake model sees the peer authority line); bad HMAC 401; duplicate id `duplicate` with one delivery; a delivery failure gives 502 and a retry with a new id delivers exactly once; the webhook port does not answer on any non-loopback address; `send_message` and a cron delivery to `intercom_peer` are refused; a forged `reply_to` is dropped; no payload field changes the target session or profile.
- TLS and routing through the proxy: no cert, unpinned cert, empty pin folder, revoked pin after the hook, wrong SNI → refused; another peer's path and `/p/<profile>/...` → 403.
- Outbound: Bot Chat's `peer:<name>` send reaches the fake peer with a valid HMAC V2; a send from another session, an ask, passive/key, or another profile is refused; a `wants_reply` inbound message answered with a `[REPLY]` block reaches the fake peer with `reply_to`; a turn without a block sends nothing.

**Verify:**
```
HERMES_HOME="$(mktemp -d)" scripts/run_tests.sh --fail-on-skip --file-retries 0 --file-timeout <seconds> tests/plugins/intercom/test_e2e_peers.py -- --intercom-src=<intercom-repo>
```
`<seconds>`: the builder measures and records it. No repo-wide `scripts/check` (the repo carries older findings outside this item).

- **Blocked by:** G17d · **Blocks:** deploy (manager: subtree pull, house-infra with HME review, idle gateway restart, @spike review)
- **Out of scope:** everything the plan marks "Settled by the operator"; the live install, its config and services (`~/.hermes`); house-infra; any core (hermes-agent) change; changes to `test_e2e_owner.py` cells other than shared harness helpers.
