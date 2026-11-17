Commit: 9c139c332c
Verdict: changes

Architect review of `docs/session-mail/peers.md` (G17). I checked it against the code at 9c139c332c. The Caddy findings come from Caddy v2.11.4 source (`modules/caddytls/connpolicy.go`, `leaffolderloader.go`) and from a loopback-only trial: `bind 127.0.0.1`, throwaway CA under `<trial dir>`. `the existing edge proxy`  and the live install were not touched.

The shape holds. P1 works through `ctx.register_platform`, with no core patch. Four changes are blocking:
- F1: a retry after a 502 is lost as a duplicate.
- F2: the adapter's `send` would deadlock the gateway loop.
- F3: a registered platform lets any session forge peer messages.
- F4: a peer would receive Bot Chat's whole answer.

The Caddy design also needs fixes (F10–F12).

## Answers to the five questions

**Q1. P1 via `ctx.register_platform`: yes, and it is the lightest correct way.**
- How the dispatch reaches the adapter:
  - `_is_known_platform` accepts registered names (`gateway/platforms/webhook.py:155-162`), but `deliver_only` never consults it.
  - `_handle_deliver_only` (`webhook.py:572-594`) → `_direct_deliver` (`webhook.py:945-953`) → `_deliver_cross_platform` (`webhook.py:1015-1041`).
  - There, `Platform(name)` resolves through `_missing_` for registry names (`gateway/config.py:244-266`).
  - `_find_adapter` → `_authorization_adapter(platform, None)` (`webhook.py:1009-1013`, `gateway/authz_mixin.py:205-226`) returns `runner.adapters[platform]` for a bare route. The adapter therefore only exists if the default profile's config enables the platform (`gateway/config.py:672-693`, `gateway/run_adapters.py:1771-1781`).
  - The result: `send(chat_id, content, metadata=…)` (`webhook.py:1038`). An exception or `success=False` gives 502 (`webhook.py:583-594`).
- Why the alternatives are worse:
  - A `post_gateway_admission` consumer answers 202 whatever happens and sees every inbound message (`webhook.py:822-830`).
  - `cron_job` is asynchronous 202 (`webhook.py:596-626`).
- What the adapter must be: a `BasePlatformAdapter` subclass with these four methods (`gateway/platforms/base.py:2621-2631, 4746`):
  - `connect` → `_mark_connected()`, return True;
  - `disconnect` → `_mark_disconnected()`;
  - `async send(chat_id, content, reply_to=None, metadata=None)`;
  - `get_chat_info`.
- Registration: `check_fn=lambda: True`, `is_connected=lambda cfg: True`, `validate_target_ref_fn=<refuse all>` (F3), not `trusted_inbound`.
- Config: `platforms.intercom_peer.enabled: true`, in the default profile only.
- Scoping: in `send`, run the whole delivery off the loop (F2) inside `profiles.in_profile("default")` (`plugins/intercom/profiles.py:57-68`).
- Synchronous delivery and 502: yes. Inside that thread, `route.send(...)` to the exact title `Bot Chat` returns the receipt. `ok` means `SendResult(success=True)`; anything else means `success=False`, which the webhook turns into 502.

**Q2. Record, frame and replies.**
- Record:
  - There is no `sender_kind` column (`plugins/intercom/record.py:84-125`).
  - Use `sender_source='peer'`, `sender_label=<name>` and `sender_session_id=NULL` inbound.
  - Outbound rows use `address='peer:<name>'` and `delivery_path='peer'`.
  - No migration is needed.
- Frame: a new sender kind `peer` in `frame.py` (F5).
- Reply routing:
  - Branch in `replies._answer` / `_deliver` (`plugins/intercom/replies.py:216-246`) before `_unwakeable` (`replies.py:212-213`), which would otherwise mark the row `stored`.
  - For `sender_source == 'peer'`, call `peers.post(name, text, reply_to=row["id"])` on the existing daemon thread and record `reply_message_id`.
  - The peer gets only the `[REPLY]` block (F4).
- The Bot Chat check: in one place, at the entry of a new `peers.send` that `route.send` delegates to when `to` starts with `peer:` (`route.py:138`) (F9).

**Q3. Receiver.**
- Bind: `platforms.webhook.extra.host: 127.0.0.1` (`webhook.py:218`) is mandatory. The default `None` binds every interface (`webhook.py:60-63`), and the mesh zone accepts the mesh range (plan line 61), so 8644 would bypass mTLS.
- Idempotency:
  - It keys on (profile, route, delivery id), held in memory for 1 h (`webhook.py:233-236, 382-391`), and does not survive a gateway restart.
  - `X-Request-ID` is used only when none of `X-GitHub-Delivery`, `svix-id` or `webhook-id` is present (`webhook.py:77-80`).
- Body limit: 1 MiB (`max_body_bytes`), checked before the read and on chunked bodies (`webhook.py:240, 284, 537-547`).
- Rate limit: 30/min per route (`webhook.py:239, 370-380`).
- Signing: use V2, never V1. V1 signs the body only, so a captured request replays forever (`webhook.py:902-910`). V2 is `hex(HMAC-SHA256(secret, "<ts>.<body>"))` with ts within ±300 s (`webhook.py:70, 887-901`). The V2 header commits to V2 (`webhook.py:891-897`).
- Send no `svix-*`, `webhook-signature`, `X-Hub-Signature-256`, `linear-signature` or `X-Gitlab-Token` header: those take precedence (`webhook.py:874-885`).
- The exact command:
  ```
  TS=$(date +%s); BODY='{"text":"…"}'
  SIG=$(printf '%s.%s' "$TS" "$BODY" | openssl dgst -sha256 -hmac "$SECRET" -r | cut -d' ' -f1)
  curl --max-time 30 --resolve <proxy-name>:8645:<agent host mesh addr> --cacert <server-ca>.pem \
       --cert peer.pem --key peer.key \
       -H 'Content-Type: application/json' -H "X-Request-ID: $(uuidgen)" \
       -H "X-Webhook-Timestamp: $TS" -H "X-Webhook-Signature-V2: $SIG" \
       --data-binary "$BODY" https://<proxy-name>:8645/webhooks/peer-<name>
  ```
  - Use `--data-binary`, not `-d`: `-d` strips newlines, so the signed bytes would differ from the bytes sent.
  - Answers: 200 `delivered`, 200 `duplicate` (treat it as delivered), 401, 404, 413, 429, 502 (`website/docs/user-guide/messaging/webhooks.md:425-436`).

**Q4. Caddy 2.11.4** (F10–F12).
- `trusted_leaf_cert_file`:
  - It is the deprecated `trusted_leaf_certs`.
  - Where leaf certs are given, the leaf check is in addition to the CA chain: all verifiers must pass in `verifyConnection`, which also runs on resumed sessions.
  - **With zero files no leaf verifier is created and trust falls back to the CA alone**, so any agent-peer-ca certificate is accepted, including a revoked one.
  - The non-deprecated `verifier leaf { folder <dir> }` fails closed. With an empty folder the listener came up and refused every handshake in the trial.
- Session tickets:
  - Caddy sets `SessionTicketsDisabled=true` on every connection policy that has `client_authentication`. In Go that also disables TLS 1.3 PSK tickets.
  - In the trial the pinned policy issued no NewSessionTicket. The Caddyfile's catch-all `{}` policy, which has no client auth, did issue one.
  - `apps.tls.session_tickets.disabled` is therefore redundant for the mTLS policy, but harmless.
- Per-certificate path: one route per pinned peer, `@p { path /webhooks/peer-<cn>; expression {tls_client_subject} == "CN=<cn>" }`, then `rewrite * /webhooks/peer-<cn>` and `reverse_proxy 127.0.0.1:8644`; everything else gets `respond 403`.
  - Trial results: own path 200; other peer's path 403; `/p/spike/…` 403; trailing slash 403.
  - The path matcher is case-insensitive and matches the cleaned, decoded path: `/WEBHOOKS/PEER-ALPHA`, `…/peer-beta/../peer-alpha` and `peer%2Dalpha` were all forwarded. Hence the `rewrite`, which pins the upstream URI to the canonical path.

**Q5.** F13–F16.

## Findings

1. **High: a retry after 502 is swallowed as a duplicate.** Plan lines 30 and 68 vs `gateway/platforms/webhook.py:729-733` and `572-594`.
   - The delivery id is recorded before `_handle_deliver_only` runs, and a failed delivery never releases it. The coalesced path does release it (`webhook.py:772-773`); the deliver_only path does not.
   - So "retry with the same request id" after a 502 gets `200 duplicate` and the message is silently lost. The plan's P1 text ("the peer retries… idempotency stops double delivery") contradicts the code.
   - Change P4 to:
     - after any HTTP answer of 502, 503 or 429, retry with a **new** `X-Request-ID` and a fresh timestamp and signature;
     - reuse the same id only when no HTTP answer arrived (timeout or connection drop), and treat `"status":"duplicate"` as delivered.
   - Add a Verify case: after a 502, a retry with a new id delivers exactly once.
   - Without a core patch there is no other fix.

2. **High: the adapter's `send` must not run session mail on the gateway loop.**
   - `client._run` starts a thread and `join()`s it (`plugins/intercom/client.py:104-119`).
   - The owner RPC server is a task on the same loop (`gateway/run_api.py:278-292`), and `_deliver_cross_platform` awaits `adapter.send` on that loop (`webhook.py:1038`). Calling `route.send` directly deadlocks the owner until its timeouts.
   - P1 must say: `send` does `await asyncio.to_thread(_deliver_inbound, name, content)`. `to_thread` copies contextvars. `_deliver_inbound` enters `profiles.in_profile("default")` and calls `route.send` with `profiles.Settings()` as ctx, the precedent being `deadline.py:136-142`.

3. **High: a live platform makes peer messages forgeable by any session.**
   - An enabled plugin platform with a live adapter is a target for `send_message` (`tools/send_message_tool.py:312-327, 740-742`) and for cron delivery (`cron/scheduler_delivery.py:1159-1213`).
   - Any session's model (or a prompt injection) could send to `intercom_peer:alpha` and land a "remote agent alpha" frame in Bot Chat. Bot Chat's answer would then go to the real peer.
   - Fix with the published API: register `validate_target_ref_fn=lambda _ref: "intercom_peer is inbound-only (webhook routes)"` (`gateway/platform_registry.py:110`). It has the final say for every caller: model tool, CLI and cron (`tools/send_message_targets.py:55-78`). The webhook's direct path does not consult it (`webhook.py:1027-1038`).
   - The adapter also refuses any `chat_id` not in `peers.json`.
   - Add Verify cases: a `send_message` to that platform, and a cron delivery to it, are refused.

4. **High: a peer would receive Bot Chat's whole answer.**
   - For `requested` mode with no block, the whole final answer is sent (`replies.py:185-193`, footer text `frame.py:465-471`).
   - Bot Chat's answer is addressed to Alex, so this breaks the black box.
   - Rule for peer rows: block only. Take the `no-block` branch in `reply_for` (`replies.py:185-187`), and make the peer footer say that only the `[REPLY <id>]` block goes to remote agent `<name>`.
   - Add a Verify case: a Bot Chat turn without a block sends nothing to the peer.

5. **Medium: the frame is not "the existing script/messaging frame".**
   - `_sender_kind` accepts only session, script and messaging (`frame.py:316-323`).
   - The script authority line says "a script on this machine" (`frame.py:377-381`), and the script footers say "stored… hermes intercom status" (`frame.py:481-497`). Both are wrong for a peer.
   - Add a `peer` kind with:
     - the plan's authority line in `_authority`;
     - a `_header` branch that still ends `message <id>):`, so `_HEADER_RE` matches (`replies.py:63`);
     - a block-only `_footer_bullets` branch;
     - no `@profile` handle in `_notice`.
   - Add `_Who.peer(name)` in `route.py:549-597`.
   - `frame_stored` would re-frame a sessionless row as a script (`route.py:305-306`). Add a peer branch there too, although peer rows are never passive or keyed.

6. **Medium: inbound `reply_to` is untrusted, and the plan's reply mode loops bots.**
   - Accept `reply_to` only when `record.get(reply_to)` is an outbound row with `address == "peer:<name>"`; otherwise drop it.
   - Reply mode should be:
     - `wants_reply: true` → `requested`;
     - a valid `reply_to` without `wants_reply` → `optional` (session mail's reply convention, `replies.py:24-25`; `route.py:159` allows `optional` only with `reply_to`);
     - else `none`.
   - The plan's "requested when reply_to is set" makes every reply ask for another. With no caps (settled), that ping-pongs two bots forever.

7. **Medium: the payload does not reach `send`; only the rendered prompt does.**
   - The adapter receives `content` (the route's rendered `prompt`) and `deliver_extra.chat_id` only (`webhook.py:576-578, 1027-1038`).
   - `{__raw__}` and the empty template truncate at 4000 characters (`webhook.py:919-926`), which breaks the JSON.
   - Specify the template `prompt: "reply_to={reply_to}\nwants_reply={wants_reply}\n{text}"`:
     - string values are not truncated (`webhook.py:934`);
     - a missing key stays as the literal `{key}` (`webhook.py:930-933`), which the adapter reads as absent;
     - a literal `{text}` means `text` was missing, so refuse (502).
   - `chat_id` must be a literal, with no braces (`deliver_extra` is rendered from the payload, `webhook.py:938-941`).
   - Do not set `events`, `profile` (an absent `profile` binds the route to default, `webhook.py:518-523`; this matters with `multiplex_profiles: true` live), `mirror_to_session`, `skills` or `script`.

8. **Medium: P1 config is incomplete.**
   - State `platforms.webhook.enabled: true` with `extra.host: 127.0.0.1`. Webhook is not enabled live today: no `platforms:` key in the live `config.yaml`, nothing listening on 8644.
   - State `platforms.intercom_peer.enabled: true`.
   - Static routes are read at construction (`webhook.py:221`), so adding a peer means a gateway restart. Say so, or say why not to use the hot-reloaded `webhook_subscriptions.json` (`webhook.py:438-484`). Don't use it: it is agent-writable.
   - Name the platform `intercom_peer`, not `intercom-peer`. Platform values use underscores (`config.py:217-241`).
   - Add a Verify case: 8644 does not answer on <agent host mesh addr>.

9. **Medium: where "only Bot Chat may send to peers" lives.**
   - One check, at the top of `peers.send`, reached from `route.send` (`route.py:138`), so the tool (`plugins/intercom/__init__.py:256-272`), CLI script sends and the reply hook all pass it.
   - Refuse when any of these holds:
     - the active profile is not default, or a `profile` argument is given;
     - `script=True`;
     - `kind == "ask"`: the in-process waiter needs a `reply` tool call the peer cannot make (`replies.py:260+`);
     - the delivery is `passive`, or the call has a key or `within`;
     - the sender's compression tip is not the tip of `get_session_by_title(CANONICAL_BOT_CHAT_TITLE)` (`hermes_state.py:1629`, `address.py:452-476`).
   - The tool schema is fixed at register (`__init__.py:446-462`). Never vary it per session (prompt caching); at most add one fixed clause. Listing peers in `list` for Bot Chat only is fine, because it is a runtime result.

10. **High (P3): zero leaf files fall back to CA-only trust; use the leaf verifier.**
    - Replace `trusted_leaf_cert_file` per file (plan line 54) with `client_auth { mode require_and_verify; trust_pool file ca.pem; verifier leaf { folder /etc/house-infra/agent-peers/active } }`.
    - The folder loader reads `*.pem` recursively at provision. In the trial, an empty folder refused every handshake.
    - Drop "with an empty `active/` it stops the listener" (plan line 60); the verifier fails closed by construction. The hook still renders the per-peer path routes, validates and reloads.
    - Reload needs an admin endpoint: use a unix-socket `admin`, or a `systemctl reload` that has one. `admin off` cannot reload.
    - Set `persist_config off`.

11. **High (P3): the Caddyfile emits a catch-all TLS policy with no client auth, and IP-only clients get 421.**
    - Catch-all policy: adapting the Caddyfile produced an SNI-matched mTLS policy plus an unmatched `{}` policy.
      - Trial: with a different SNI, the `{}` policy served the certificate without asking for one and issued a TLS 1.3 ticket; only the Host matcher (an empty 200) kept the request from the upstream.
      - Fix: write the proxy as JSON with **one** connection policy, no `match`, carrying `client_authentication`.
      - Keep the per-peer `tls_client_subject` expression matcher as the second gate.
    - IP-only clients: client auth turns on strict SNI/Host enforcement, so `https://<agent host mesh addr>:8645` gets **421** (trial).
      - The proxy needs a hostname, and peers use `--resolve <name>:8645:<agent host mesh addr>`.
      - **Missing from the plan:** who issues the proxy's server certificate (SAN = that name) and which CA file peers pass as `--cacert`. P3 and P4 must state both.
    - Binding: a site address does not bind. Without `bind`, adapt produced `listen: [":18645"]` (all interfaces). State `listen: ["<agent host mesh addr>:8645"]` explicitly.

12. **Medium (P3): limiting each certificate to its own path.**
    - Use per-peer routes as in Q4, with `rewrite * /webhooks/peer-<cn>` before `reverse_proxy`, because the path matcher is case-insensitive and normalises (trial).
    - Default: `respond 403`.
    - Constrain peer names to `[a-z0-9-]` so the CN, file name and route name are the same string.
    - Issue subjects exactly `CN=<name>`: the placeholder is the full DN.

13. **Low: overbuilt or unneeded.**
    - `insecure: false` in `peers.json` (plan line 44): a flag nobody sets. Always verify TLS, and drop it.
    - "HTTP keep-alive is off" (plan line 55): unproven need; drop it unless the trial shows a reload leaves a revoked peer's connection open.
    - `apps.tls.session_tickets.disabled`: redundant with client auth. Keep it only as a belt for the catch-all policy, and F11 removes that policy.
    - "HMAC header, if the peer's webhook takes one" (plan line 45) against "secret by path" (line 25): pick one form per peer in `peers.json` (`auth: url | hmac-v2`). Don't build a generic header scheme.

14. **Low: outbound POST.**
    - It runs on the tool handler thread or the reply daemon thread, never on the loop. Good: keep it there.
    - Give it a fixed request timeout; that is not a retry or a cap. Report a timeout as `delivery-unknown`.
    - Record the outbound row before the POST, as `route.py:269-279` does for sessions.

15. **Low: Verify list.**
    - Replace "an empty `active/` means nothing listens" with "an empty `active/` refuses every handshake".
    - Add:
      - a different SNI and no SNI are refused;
      - `/p/<profile>/…` gets 403;
      - a forged `reply_to` is dropped;
      - a reply without a block sends nothing to the peer;
      - plus the F1, F3 and F8 cases.
    - "With ticket resumption tried" is cheap; keep it.

16. **Note: trial side effects (mine, not the plan's).**
    - The first trial run wrote `~/.config/caddy/autosave.json` and created `~/.local/share/caddy/`. Both are owned by hermes, created 2026-11-15 13:13; neither is `the existing edge proxy`'s, which runs as user `caddy`.
    - The trial files are in `<trial dir>`.
    - All trial listeners (127.0.0.1:18645-18648) are stopped.
    - All of these are safe to delete.
