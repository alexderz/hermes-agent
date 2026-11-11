Commit: a37eb15b88
Verdict: changes needed

# Security gate, round 2: DER-701 session-mail (LLD round 2)

Read: `git diff 643185083e a37eb15b88 -- docs/session-mail/lld.md docs/session-mail/hld.md`, and
the full TB-1 to TB-9 table at `a37eb15b88`. Code checked for the new mechanisms:
- `gateway/status.py:2022` (`get_running_pid`);
- `gateway/session.py:1311` (`lookup_by_session_id`);
- `gateway/authz_mixin.py:380` (`_restored_source`);
- `hermes_state_common.py:509` and `hermes_state_gateway.py:296` (`gateway_routing`);
- `tui_gateway/methods_prompt.py:756-760`.

Same scope rules as round 1. No fix below adds a cap or a delivery gate.

One problem remains, and it is in the F1 fix itself. The chat scope **fails open** whenever no
live gateway in the same process can answer for it (R2-1). With that fixed, plus the two small
should-fix items, security accepts.

## Round-1 findings

| # | Status | Notes |
|---|---|---|
| F1 | **Partly fixed** | The chat rule is sound. `private` means only `echo_chats`, or a DM with a user in `owner_user_ids`; a DM with another allowed user is `shared`. It governs all three paths (echo, body, reply). The platform authority line, the shared-chat line, `shared_chat` in the receipt, and the reply fallback limited for shared senders are all as asked. But the scope is computed only by a live gateway in the same process, and `NULL` is read as "local sender". See R2-1 and R2-2 |
| F2 | Fixed | B4 step 5 checks `ctx.injection_allowed()` before `dispatch_sync`; tested in I-5 |
| F3 | Fixed | Fields are sanitised (Cc/Cf/Zl/Zp, `📡`, brackets). The sender is bound to the peer pid's lease, or to the verified gateway pid plus a `gateway_routing` row; otherwise the message is framed as a script with no reply. A child process of a session (a model's terminal) has its own pid and so falls to the script frame. Tested in I-5 and I-6. `reply` envelopes are not bound; see R2-6 |
| F4 | Fixed | The visible start skips Cf/Zs/Mn, and `Not <user_name> … says` lines are relabelled. `re.escape(user_name)` is used. Tested in I-6 |
| F5 | Fixed | `ask_to` returns `frame.relabel(text)` with `reply_from` and `note`. Tested in I-10 |
| F6 | Fixed | `InjectedDelivery` is a frozen dataclass and JSON cannot build it, the same mechanism as `DeliveryAuthor`. Any other `_delivery_mode` gets 4124. Tested in I-2 |
| F7 | Fixed | The registry dir is `chmod 0700` on every start; entries are `O_EXCL\|O_NOFOLLOW` `0600` plus `os.replace`; `plugin-data/intercom/` is `0700`; the record and its sidecars are created under `umask 077` and then `chmod`. Tested in I-5 and I-8 |
| F8 | Fixed | The setting is now a port (`dashboard_port`), and `dispatch` parses the URL before opening the key. Implementation detail in R2-5 |
| F9 | Fixed | The tui host compares `session["profile_home"]` with `home_path`, and the gateway compares the runner's home. Tested in I-2 and I-11 |
| F10 | Fixed in effect; rationale wrong | See R2-4 |
| F11 | Fixed | `get_running_pid()` is lock plus pid file, checked against the live process and the probed home (`gateway/status.py:2022-2033`). A strong anchor |
| F12 | Fixed | Echo goes out with `parse_mode: None` and `disable_mentions`, with an escaping fallback. Tested in I-11 and I-6 |
| F13 | Fixed | Fixed text per code plus the exception type name. Tested in I-4 |
| F14 | Fixed (stated) | TB-6 and B2 |
| F15 | Fixed (stated) | TB-1 |
| F16 | Fixed going forward | `a37eb15b88` is authored `hermius-maximus@users.noreply.github.com`. Earlier commits still carry the hostname; rewriting them is Alex's call |

New mechanisms checked: `echo_chats`, `owner_user_ids`, `dashboard_port`, `header_sha`, the
peer-pid lease check, `InjectedDelivery`, `ctx.injection_allowed()` and
`ctx.session_chat_scope()`. Apart from the items below they add no trust-boundary problem:
- `injection_allowed()` and `session_chat_scope()` are read-only and reveal only the plugin's own
  consent and a private/shared bit;
- the new config keys are written by house-infra only, in the same trust domain as
  `allow_gateway_injection`;
- `header_sha` is written by the host serve thread, into a row the sender already created.

## Findings

### R2-1 — blocker: the chat scope fails open for messaging-platform sessions not served by a live gateway in the same process

`lld.md:173-175` (`session_chat_scope` returns `None` when no live gateway in this process knows
the session), `lld.md:425-426` (host step 4: "Not `None` only in the gateway process"),
`lld.md:591` (`sender_chat_scope` "NULL (local sender)"), `lld.md:634-639` (B8 step 4),
`lld.md:806` (I-1 tests that it is `None` outside the gateway).

Scope belongs to the **session's origin chat**, not to the process that happens to host the
session now. Two gaps follow:

1. **Platform session hosted elsewhere.** A Telegram group session can be opened, resumed or
   woken in the dashboard. It then has a dashboard lease, so B4 step 3 routes to the tui host,
   whose `session_chat_scope` is `None`. The body arrives with no shared-chat line and no
   `shared_chat` in the receipt. The message and any reply stay in that session's transcript,
   and the next time a group member speaks, the gateway's turn has them in context and may post
   them to the group.
2. **Reply rows with a NULL scope.** When such a session sends, or when any sender path does
   not fill `sender_chat_scope`, the row has `NULL`. B8 reads `NULL` as local and uses the
   whole-answer fallback. That is the exact leak F1 closed.

**Fix:**
- **Compute scope from the stored origin, in any process.** Make `_chat_scope` work on a
  `SessionSource` restored from durable state: the `gateway_routing` row's `entry_json` in
  `state.db` (`hermes_state_gateway.py:296-320`), read read-only, re-pinned like
  `_restored_source` (`gateway/authz_mixin.py:380-391`). `ctx.session_chat_scope(session_id)`
  uses the live gateway entry when there is one, and otherwise this stored route.
- **Fail closed.** If `sessions.source` is a messaging platform (not in
  `cli, tui, desktop, cron, oneshot, subagent`) and no origin resolves, the scope is `shared`.
  `NULL` is allowed only for local sources.
- **Apply it on both sides.** Host step 4 and the sender's row (`sender_chat_scope`) both use
  this function, wherever they run.
- **B8 reads the source too.** When `sender_chat_scope` is `NULL` and `sender_source` is a
  messaging platform, treat it as `shared`.
- **Tests:**
  - I-1: `session_chat_scope` for a Telegram group session with **no live gateway** returns
    `shared` (from the stored route), and a platform session with no route returns `shared`.
  - I-10: a row with `sender_source='telegram'` and `sender_chat_scope=NULL` and no block sends
    nothing (`shared-chat-no-block`).
  - E2E: a group session opened in the dashboard gets the shared-chat line.

### R2-2 — should-fix: the model writing a reply is not told that it goes into a shared chat

`lld.md` B6 (the platform authority line), B8 step 4, B8 `ask`.

For a shared-chat sender, an explicit `[REPLY]` block, or an `ask` reply, is still delivered,
which is correct: the model chose it. But the shared-chat line goes only to a **shared target**.
A local session answering a shared **sender** sees only "talks with other people … may be
relaying their words". That warns about the request, not about where the answer will be read.

**Fix:** when the sender's scope is `shared` (after R2-1), the footer's "How to answer" adds one
model-only line: "Your reply goes into a {Platform} {chat_type} that other people read." Use it
for the send footer and the `ask` footer. Test it in I-6.

### R2-3 — should-fix: `echo_chats` and `owner_user_ids` are not tied to a platform, and types are unstated

`lld.md:126-136`, `lld.md:178-184`, `lld.md:847-851`.

Chat and user ids are compared without the platform, and their type is not specified.
- **Ids are per platform.** Telegram, Discord, Slack, Signal and WhatsApp each have their own id
  space, and a numeric id listed for one platform can match on another.
- **Types.** YAML gives `-1001234` as an int, while `SessionSource.chat_id` and `user_id` are
  strings (`gateway/session.py:73,126`). A mismatch fails closed, which is safe but silent.

`_chat_scope` should also read the plugin's own profile config fresh on each call, like
`_gateway_injection_allowed` (`hermes_cli/plugins.py:622-630`), so removing a chat takes effect
without a restart. That needs to be stated.

**Fix:**
- Entries become `"<platform>:<id>"` strings, for example `telegram:-1001234567890` and
  `telegram:123456789`.
- Compare against `f"{source.platform.value}:{source.chat_id}"` and the same for `user_id`.
- Read under `_plugin_home_scope(manager.home_path)` with `load_config_readonly()`, with no cache.
- Test in I-11: the same number under another platform is `shared`, and an int YAML value is
  normalised or rejected with a warning.

### R2-4 — note: F10's rationale is wrong, but the outcome holds

`lld.md` B8 step 2 says a typed copy "lacks the host's exact fields". It does not: the echo **is**
header line 1, byte for byte when sent as plain text, so a copy-paste reproduces `header_sha`.
After F1 that is acceptable, because echoes go only to `private` chats (Alex's DM and the chats he
lists), so nobody untrusted sees an echo.

If you want the check to hold without leaning on that, hash the whole framed span: header line 1
through `📡 End of message <id>`, including lines 2–3 and the footer, which are model-only and
never echoed. Either way, correct the sentence.

### R2-5 — note: the loopback check must parse, not match strings

`lld.md` B2 step 0.
- Use `urllib.parse.urlsplit(url).hostname` with `ipaddress.ip_address(...).is_loopback`.
- Refuse hostnames outright rather than resolving `localhost`; intercom always builds
  `127.0.0.1` anyway.
- Add I-4 cases: `http://127.0.0.1.evil.example`, `http://127.0.0.1@evil.example`,
  `http://evil.example#@127.0.0.1` and `http://[::1]:9119` (the last one allowed).

### R2-6 — note: `reply` envelopes (answers to an `ask`) are not bound to a process

`intercom:inbox.py:425-433,596-606`.

`resolve_ask` trusts the envelope's `from_name`. F3's peer-pid binding covers `send` and `ask`
only. Any process running as the Hermes user that learns a `request_id` can answer someone else's
ask. The `request_id` is in the target's transcript and footer, and could be posted by a model.
This is the same trust domain and cheap to close.

**Fix:** store the target lease's pid with the waiter when the ask is sent. Accept a `reply` only
from that peer pid, or from the verified gateway pid for a gateway target. Test in I-5.

## Acceptance

R2-1 must be written into the LLD: the scope comes from the stored origin, unknown platform
sessions fail closed to `shared`, and the I-1, I-10 and E2E checks are added. R2-2 and R2-3 should
go in with it. With those, security accepts on trust boundaries. R2-4 to R2-6 can be taken at
Build.
