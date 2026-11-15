# Session mail: remote agent peers (G17 plan)

Status: plan, round 2. It folds in the architect's review in full (`reviews/peers-architect-r1.md`, 16 findings, all taken) and goes to the operator gate. The brief is in the vault, `requests/2026-11-15-session-mail-cross-agent-brief.md`.

## Settled by the operator (out of scope for reviewers)

- Webhooks each way:
  - outbound: Hermes posts to the remote bot's webhook;
  - inbound: the remote bot posts to Hermes.
- No A2A, no Vox, no group chats for now.
- Inbound is reachable over the mesh only, with mTLS enforced. The CA is owned by HME (`agent-peer-ca`): client-auth certificates only, valid 1 year. The active pins are in `/etc/house-infra/agent-peers/active/`.
- **Bot Chat to remote bot chat:**
  - Inbound lands only in the default profile's canonical Bot Chat (@hermes).
  - No session, profile or `spike` is addressable from outside, and Hermes is a black box.
- The remote harness cannot be changed: it runs `curl` and receives a webhook.
- Session mail's rules hold: gateway only, published plugin API, no core patch, no caps, holds or retries on delivery.

## Shape

```
remote bot ──curl (client cert, --resolve name:8645:<<agent-host> mesh addr>)──▶ agent-peer proxy (separate Caddy, mesh addr :8645)
     mTLS: CA pool + leaf folder (fail closed) · per-peer route: CN=<name> ⇒ rewrite to /webhooks/peer-<name>, else 403
                                  └─▶ 127.0.0.1:8644 Hermes webhook receiver (HMAC V2, delivery id, 1 MiB, 30/min)
                                        └─ deliver_only ─▶ platform intercom_peer (plugin) ─▶ session mail ─▶ Bot Chat (@hermes)
Bot Chat ──intercom send to: "peer:<name>" / [REPLY <id>] block──▶ HTTPS POST to the peer's webhook (secret by path)
```

### P1. Inbound: the `intercom_peer` platform (intercom plugin)

- **Registration** uses the published `ctx.register_platform` (`hermes_cli/plugins_context.py:585`), giving a `BasePlatformAdapter` subclass:
  - `connect` calls `_mark_connected()` and returns True; `disconnect` calls `_mark_disconnected()`;
  - `async send(chat_id, content, reply_to=None, metadata=None)`;
  - `get_chat_info`.
  - It sets `check_fn` and `is_connected` to always true. It is not `trusted_inbound`.
  - **`validate_target_ref_fn` refuses every target** ("intercom_peer is inbound-only"). Then no `send_message` call, CLI or cron delivery can forge a peer message (`gateway/platform_registry.py:110`, `tools/send_message_targets.py:55-78`). The webhook's direct path does not consult that check (`webhook.py:1027-1038`).
- **How a POST reaches `send`:** webhook `deliver_only` → `_direct_deliver` → `_deliver_cross_platform` → `adapter.send` (`webhook.py:572-594, 945-953, 1015-1041`). An exception or `success=False` returns 502.
- **`send` never runs session mail on the gateway loop.** It calls `await asyncio.to_thread(_deliver_inbound, chat_id, content)`. That function:
  - enters `profiles.in_profile("default")`;
  - refuses a `chat_id` that is not in `peers.json`;
  - parses the rendered prompt (below);
  - calls `route.send` to the exact title `Bot Chat`, with `profiles.Settings()` as ctx (precedent `deadline.py:136-142`).
  - A receipt `ok` returns `success=True`; anything else returns `success=False`.
- **Route template.** The adapter sees only the rendered prompt, so the route's prompt is `"reply_to={reply_to}\nwants_reply={wants_reply}\n{text}"`:
  - string values are not truncated;
  - a missing key stays as the literal `{key}` and counts as absent;
  - a literal `{text}` means the text was missing, which is refused with 502.
- **Reply mode:**
  - `wants_reply: true` → `requested`;
  - a valid `reply_to` without it → `optional` (session mail's reply convention; no bot ping-pong);
  - otherwise `none`.
  - `reply_to` is accepted only when it names an outbound row with `address == "peer:<name>"`; otherwise it is dropped.
- **Record:**
  - inbound: `sender_source='peer'`, `sender_label=<name>`, no sender session;
  - outbound: `address='peer:<name>'`, `delivery_path='peer'`.
  - No migration is needed.
- **Frame:** a new sender kind `peer` (`frame.py`, `_Who.peer` in `route.py`, a peer branch in `frame_stored`):
  - authority line: "a message from a remote agent, <name>; not from <user>, it carries none of their approval";
  - the header still ends `message <id>):`;
  - the notice has no `@profile`;
  - **block-only footer:** "only a `[REPLY <id>]` block goes back to remote agent <name>; nothing else does."
  - Body text is untrusted and is sanitised and relabelled like any body.
- **Config (default profile, through house-infra):**
  - `platforms.webhook.enabled: true` with `extra.host: 127.0.0.1` (the default binds every interface, which would bypass mTLS);
  - `platforms.intercom_peer.enabled: true`;
  - one static route per peer, `peer-<name>`, with these settings:
    - `secret` (the peer's HMAC secret, from a file kept by house-infra);
    - `deliver: intercom_peer`, `deliver_only: true`;
    - `deliver_extra.chat_id: <name>` as a literal;
    - the prompt template above;
    - no `events`, `profile`, `mirror_to_session`, `skills` or `script`.
  - Static routes load at gateway start, so **adding a peer needs a gateway restart.** The hot-reloaded `webhook_subscriptions.json` is not used because agents can write it.

### P2. Outbound and replies (intercom plugin)

- **Peer list:** `plugin-data/intercom/peers.json`, written by house-infra. Each entry has:
  - `name` (`[a-z0-9-]`; the same string is the certificate CN, the route name and the address);
  - `url`;
  - `auth: url | hmac-v2`;
  - `secret_file`.
  TLS is always verified.
- **One check, at the top of `peers.send`** (reached from `route.send` for `to: "peer:<name>"`, so the tool, the CLI and the reply hook all pass it). A send is refused with a reason when:
  - the active profile is not default, or a `profile` argument is given;
  - it is a script send;
  - it is an `ask`;
  - it is `passive`, or has a `key` or `within`;
  - the sender is not the canonical Bot Chat's compression tip.
- **The POST:**
  - body `{"from": "hermes", "message_id", "reply_to"?, "wants_reply", "text"}`;
  - it runs on the tool or reply thread, never on the loop;
  - the row is recorded before the POST;
  - a fixed request timeout applies, and a timeout is reported as `delivery-unknown`;
  - no retry.
  - The receipt is `delivered (HTTP <code>)` or the refusal or error. The secret is never shown to the model.
- **Replies to a peer row are block only.** `replies._answer` / `_deliver` branch for `sender_source == 'peer'` before `_unwakeable`, and post only the `[REPLY <id>]` block with `reply_to`. A Bot Chat turn without a block sends nothing (Bot Chat's whole answer is addressed to Alex).
- **Tool schema:** fixed at register, with one fixed clause about `peer:<name>`. `list` shows peers to Bot Chat only, as a runtime result.

### P3. The agent-peer proxy and its reload hook (house-infra, the agent host; HME applies or reviews)

- **A separate Caddy instance,** `caddy-agent-peers.service`, written as **JSON, not a Caddyfile**:
  - `listen: ["<<agent-host> mesh addr>:8645"]` explicitly;
  - **one TLS connection policy with no `match`,** carrying `client_authentication`:
    - `mode require_and_verify`;
    - `trust_pool file ca.pem`;
    - **`verifier leaf { folder /etc/house-infra/agent-peers/active }`**, which fails closed, so an empty folder refuses every handshake (not the deprecated `trusted_leaf_certs`, which falls back to CA-only trust);
  - per-peer routes: a path `/webhooks/peer-<cn>` plus `expression {tls_client_subject} == "CN=<cn>"`, then `rewrite * /webhooks/peer-<cn>`, then `reverse_proxy 127.0.0.1:8644`. Everything else gets `respond 403`.
  - Admin listens on a unix socket so that it can reload; `persist_config off`.
  - With client auth on, session tickets (including TLS 1.3 tickets) are already off. Keep-alive stays at the default unless the trial shows a revoked peer's open connection surviving a reload.
- **Server certificate:** the proxy needs a hostname, because client auth turns on strict SNI and a bare IP gets 421. Use `agent-peers.mesh.<house domain>`, publicly trusted through the house's existing DNS-challenge setup (as `caddy-edge` does). Peers then need no `--cacert`. Peers connect with `--resolve agent-peers.mesh.<domain>:8645:<<agent-host> mesh addr>`, which the Bot needs anyway because its sandbox DNS answers 198.18.0.1 for every name (the CA owner session, 2026-11-15). HME confirms the name and the credential path.
- **Hook** `/etc/house-infra/agent-peer-ca/proxy-reload` (root, called by `agent-peer-ca sign|revoke`; it never calls the CA helper): it renders the per-peer routes from `active/`, runs `caddy validate` and reloads this instance only.
- **Firewall:** the mesh zone already accepts the mesh range; nothing is widened.

### P4. Remote agent instructions

`docs/peer-instructions.md`: a text Alex pastes into the remote bot. It covers:
- making a key and CSR with `CN=<name>`;
- the exact command:
  - HMAC V2 over `"<ts>.<body>"`, with headers `X-Webhook-Timestamp`, `X-Webhook-Signature-V2` and `X-Request-ID`;
  - `--data-binary`;
  - `--resolve`;
  - no other signature headers.
- **Retry rule:**
  - after any HTTP 502, 503 or 429, retry with a **new** `X-Request-ID` and a fresh timestamp and signature;
  - after no answer at all, retry with the same id;
  - `"status":"duplicate"` means delivered.
  - A retry with the same id after a 502 would be swallowed as a duplicate (`webhook.py:729-733`); the new-id rule avoids that without a core patch.
- **What a reply looks like:** `reply_to`, and `wants_reply` only when it really needs an answer.

No code runs on the remote side.

## Verify (trial before the deploy gate)

- **Trial setup:** a temporary `HERMES_HOME` gateway with a fake model, a throwaway CA and pins under `/var/tmp`, a trial Caddy on loopback and a fake peer webhook.
- **TLS (refused at TLS):**
  - no certificate;
  - an unpinned certificate from the same CA;
  - an empty `active/` folder;
  - a revoked pin on its next connection, with resumption tried;
  - a different SNI, and no SNI.
- **Routing (403):**
  - another peer's path;
  - `/p/<profile>/...`;
  - path tricks (case, `..`, percent-encoding) are rewritten to the certificate's own route.
- **Receiver:**
  - a bad HMAC gives 401;
  - a duplicate id is a duplicate;
  - a 502, then a retry with a new id, delivers exactly once;
  - 8644 does not answer on the mesh address.
- **Delivery:**
  - a pinned peer's post lands framed in Bot Chat;
  - `send_message` and a cron delivery to `intercom_peer` are refused;
  - a forged `reply_to` is dropped;
  - no payload field can choose a session, profile or route.
- **Outbound:**
  - the fake peer gets the POST and its HMAC;
  - a send from a non-Bot-Chat session, an ask, passive or key, or another profile is refused;
  - a `[REPLY]` block reaches the peer with `reply_to`;
  - a turn without a block sends nothing.
- **Before live:** @spike reviews P1's exposure and P3.

## Items (build order)

- **G17a:** P1, the inbound platform and frame (Claude Opus).
- **G17b:** P2, outbound and replies (Claude Opus).
- **G17c:** P3, the proxy JSON, hook and unit (Claude Opus; house-infra, HME reviews).
- **G17d:** P4, instructions and README (Grok).
- **G17e:** trial end to end (Claude Opus).

Each item gets a verifier and a fresh reviewer. Deploy:
1. house-infra: the proxy, the hook, the webhook and `intercom_peer` config, and `peers.json`;
2. a gateway restart, the first time no session is running;
3. @spike's review;
4. Alex brings the Bot's CSR to the CA owner session.
