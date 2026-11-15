# Session mail: remote agent peers (G17 plan)

Status: plan, for architect review and then the operator gate. The brief is in the vault, `requests/2026-11-15-session-mail-cross-agent-brief.md` (Follow-ups 1–7 and the CA interface section).

## Settled by the operator (out of scope for reviewers)

- Webhooks each way:
  - outbound: Hermes posts to the remote bot's webhook;
  - inbound: the remote bot posts to Hermes.
- No A2A, no Vox, no group chats for now.
- Inbound is reachable over the mesh only, and mTLS is enforced. The CA is owned by HME (`agent-peer-ca`, runbook `hosts/<agent-host>/AGENT-PEER-CA.md`). Certificates last 1 year.
- **Bot Chat to remote bot chat:**
  - Inbound lands only in the default profile's canonical Bot Chat (@hermes).
  - No session, profile or `spike` is addressable from outside, and Hermes is a black box.
  - Internal routing from Bot Chat uses the existing tools.
- We cannot change the remote harness. All it can do is run `curl` (with a client certificate) and receive a webhook.
- Gateway-only session mail, the published plugin API, no core patch, no caps, holds or retries on delivery (session mail's settled rules).

## Shape

```
remote bot ──curl --cert──▶ <mesh-addr>:8645 (agent-peer proxy, mTLS, pinned leaves)
                              └─▶ 127.0.0.1:8644/webhooks/peer-<name> (Hermes webhook receiver: HMAC, idempotency)
                                    └─ deliver: intercom-peer, deliver_only ─▶ session mail ─▶ Bot Chat (@hermes)
Bot Chat ──intercom send to: "peer:<name>"──▶ HTTPS POST to the peer's webhook URL (secret by path)
```

### P1. Inbound delivery target (intercom plugin)

- The intercom plugin registers a gateway platform `intercom-peer` with the published `ctx.register_platform`. `gateway/platforms/webhook.py:157-161` accepts any registered platform as `deliver`, and `deliver_only` delivers the rendered prompt synchronously. It returns 200 on success and 502 on failure (docs `user-guide/messaging/webhooks.md` "Response codes"), so the peer retries a failed post itself. Idempotency by `X-Request-ID` (1 hour) stops a retried post from delivering twice.
- The platform's send runs session mail's own path into the default profile's canonical Bot Chat. The `chat_id` comes from `deliver_extra` and is fixed per route to the peer name, never taken from the payload.
- **The frame** is the existing script/messaging frame:
  - sender label `peer <name>`;
  - authority line: "a message from a remote agent, <name>; not from <user>, carries none of their approval";
  - reply mode `requested` when the payload sets `reply_to` or `wants_reply`, else `none`;
  - delivery: steer, falling back to queue as usual.
- **Answers.** A `[REPLY <id>]` block written in Bot Chat goes back through P2 (`replies.py`, keyed on the record's `sender_kind = "peer"`). This gives the peer a thread without seeing any session.
- **Payload** (the peer's JSON): `{"text": "...", "reply_to": "<our message id>"?, "wants_reply": bool?}`. Unknown fields are ignored and the size limit is the receiver's. Text is untrusted and is framed and sanitised like any session-mail body (the control-frame openers are relabelled).
- **Route config:** in the default profile's `platforms.webhook.extra.routes`, written through house-infra: `peer-<name>` with `secret` from the peer's HMAC secret, `deliver: intercom-peer`, `deliver_only: true` and `deliver_extra.chat_id: <name>`. The webhook adapter binds `127.0.0.1` only (`platforms.webhook.extra.host`).

### P2. Outbound (intercom plugin)

- `intercom send to: "peer:<name>"` is allowed only from the default profile's Bot Chat. From anywhere else it is refused with a reason ("only Bot Chat talks to remote agents; message Bot Chat").
- **Peer list:** `plugin-data/intercom/peers.json` (name, webhook URL, path of the outbound secret file, `insecure: false`), written by house-infra.
- **The POST** carries `{"from": "hermes", "message_id", "reply_to"?, "wants_reply", "text"}` with an HMAC header, if the peer's webhook takes one, from the secret file. The secret is never shown to the model.
- **Receipt:** `delivered (HTTP 2xx)` or the refusal or error. No retry, as session mail does everywhere.
- **Replies** to a peer's message (P1) use the same POST with `reply_to`.
- `list` shows the configured peers to Bot Chat only, as `peer:<name>`.

### P3. Agent-peer proxy and reload hook (house-infra, the agent host)

- **A separate Caddy instance** (`caddy-agent-peers.service`), so that the TLS settings below do not touch `caddy-edge`:
  - It binds `<mesh-addr>:8645` only.
  - TLS client auth is `require_and_verify` with trusted CA `ca.pem` and `trusted_leaf_cert_file` for every file in `/etc/house-infra/agent-peers/active/`.
  - Session tickets are disabled (`apps.tls.session_tickets.disabled`), so a revoked peer cannot resume. HTTP keep-alive is off.
  - The upstream `127.0.0.1:8644` path is limited to `/webhooks/peer-<cert CN>`, so each certificate reaches only its own route.
- **Hook** `/etc/house-infra/agent-peer-ca/proxy-reload` (root, called by `agent-peer-ca sign|revoke`):
  - it renders the config from `active/`, runs `caddy validate` and reloads that instance only;
  - it never calls the CA helper;
  - **with an empty `active/` it stops the listener (deny all).**
- **Firewall:** the mesh zone already accepts the mesh range; nothing is widened.

### P4. Remote agent instructions

`docs/peer-instructions.md`: a short text Alex pastes into the remote bot. It covers:
- making a key and CSR;
- the exact `curl --cert --key --cacert ... -H 'X-Request-ID: <uuid>'` command, signed with HMAC;
- retrying on a non-2xx answer with the same request id;
- what a reply looks like.

No code runs on the remote side.

## Verify (trial, before the gate to deploy)

- **Trial setup:** a temporary `HERMES_HOME` gateway with a fake model, a throwaway CA and pins under `/var/tmp`, and a trial Caddy on a loopback alias.
- **Inbound:**
  - a pinned cert posts and Bot Chat gets the framed message;
  - a wrong HMAC gives 401;
  - an unpinned cert from the same CA, and no cert, are refused at TLS;
  - a revoked pin is refused on its next connection, with ticket resumption tried;
  - an empty `active/` means nothing listens;
  - a repeated request id is a duplicate with no second delivery;
  - a failed delivery returns 502.
- **Outbound:** a fake peer webhook records the POST and its HMAC; a send from a non-Bot-Chat session is refused.
- **Answers:** a `[REPLY]` block in Bot Chat reaches the fake peer with `reply_to`.
- **Black box:** no payload field can choose a session, profile or route.
- **Before live:** @spike reviews P3 and P1's exposure.

## Items (build order)

G17a P1 inbound target and frame · G17b P2 outbound and replies · G17c P3 proxy and hook (house-infra; HME applies or reviews) · G17d P4 instructions and README · G17e trial E2E. Builders: Claude Opus for G17a/b/c and Grok for G17d. Each item gets a verifier and a fresh reviewer.

## Open for the architect

1. Does `ctx.register_platform` give a send path that the webhook's `deliver_only` dispatch reaches (`webhook.py:946-1040`, `_find_adapter`), with the adapter's `send` able to call session mail synchronously? Or is a lighter registration enough?
2. The record: a new `sender_kind = "peer"` in the record and frame, and the reply routing in `replies.py`.
3. Does Caddy 2.11's `trusted_leaf_cert_file` fully replace CA-only trust (no fallback when the list is empty)? Do disabled session tickets also stop TLS 1.3 PSK resumption?
