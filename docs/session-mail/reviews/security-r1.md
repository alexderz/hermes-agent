Commit: 643185083e
Verdict: changes needed

# Security gate, round 1: DER-701 session-mail (LLD trust boundaries)

Scope read: `docs/session-mail/lld.md` (whole, TB-1 to TB-9 closely), `docs/session-mail/hld.md`
§ Trust boundaries, `docs/session-mail/poc/` and `poc/round2/`. Code checked in this worktree
(`gateway/run_busy.py`, `gateway/run_plugin_injection.py`, `hermes_cli/plugins.py`,
`hermes_cli/dashboard_auth/agent_key.py`, `scripts/dashboard_dispatch.py`,
`hermes_cli/active_sessions.py`, `tui_gateway/plugin_inject.py`, `tui_gateway/methods_prompt.py`,
`agent/prompt_builder.py`, `gateway/hosted_room_discussion.py`, `hermes_state.py`,
`plugins/plugin_storage.py`, `hermes_cli/cli_tui_mixin.py`) and in the intercom clone at `ae90a2a`
(`inbox.py`, `__init__.py`).

Settled decisions (no caps, holds, retries or approval gates; delivery modes; the intercom base;
subtree deploy; SM-Q8's whole-answer fallback between local sessions) are not reopened. No fix
below adds a cap or a gate on delivery.

## What holds

- **TB-1 loopback key.** `verify_agent_key` takes the key only from a loopback peer with no
  forwarding header, compares with `hmac.compare_digest`, and reads the file owner-only with
  `O_NOFOLLOW` (`hermes_cli/dashboard_auth/agent_key.py:79-97,124-141`). Waking adds no privilege.
- **TB-2 socket.** The peer-UID check runs before any read (`intercom:inbox.py:563-568`). There is
  no TCP listener. Same-UID senders are the trust domain, and the LLD says so.
- **TB-4 gateway control.** `allow_gateway_control=False` is set on the injected event
  (`gateway/run_plugin_injection.py:148,236`). It also gates plaintext approval words
  (`gateway/run_busy.py:553`), the internal-event merge (`run_busy.py:389-390`) and control
  routing (`gateway/run_inbound.py:1223-1224`). An injected "yes" cannot answer an approval.
  Authorisation is rechecked against the restored route with adapter delegation off
  (`run_plugin_injection.py:111-139`).
- **Approvals on other hosts.** The classic CLI's approval prompt uses `_approval_state` and not
  `_pending_input` or `_interrupt_queue` (`hermes_cli/cli_modal_mixin.py:1082-1144`). The tui
  approvals travel on their own RPC. A framed message always starts with `📡`, so it is never a
  slash command or a bare approval word.
- **Steer wrapper break-out (Trial Q2).** `CONTROL_FRAME_OPENERS` includes
  `/?OUT-OF-BAND USER MESSAGE` (`agent/prompt_builder.py:571-574`), so the B6 relabel stops a body
  from closing the steer marker.
- **`poc/` contents.** No keys, tokens, hostnames or home paths are committed. The keys are
  `secrets.token_urlsafe(48)` per run, written `0600` into a throwaway home
  (`poc/round2/trial_r2.py:288-291`, `poc/trial_session_mail.py:291-293`). `api_key: probe-key`
  and `OPENAI_API_KEY=probe-key` are dummy values for a fake local model. Both evidence files use
  placeholders (`<temp-home>`, `<run-dir>`, `<port>`). Session ids in the evidence are throwaway.
  Nothing needs removing or rotating.

## Findings

### F1 — blocker: TB-5's chat rule covers only the echo, so private content still reaches shared chats through the body and the automatic reply

`lld.md:581` (TB-5), `lld.md:466-476` (B8 steps 4-6), `lld.md:580` (TB-4 data class).

TB-5 controls only the bot's echo post. Two other paths take Alex's private content into a group
chat, where every member can read it:

1. **Body into a group session.** A message sent to a gateway session in a group or forum chat
   goes into that chat's model context whether or not it is echoed. The answer the model posts
   there routinely quotes or summarises it. "Only its answer is posted, as it would be anyway" is
   the leak itself.
2. **Automatic reply into a group session.** A group-chat session sends to `Home` (or any operator
   session with a terminal). The B8 hook then delivers the reply back by steer. With no
   `[REPLY]` block, the reply is the **whole final answer** of that turn. If the message was
   steered into a turn where Alex was working (ux.md F9), that is Alex's own answer. The group
   model then has it and may post it.

   The text that starts this chain can be typed by any authorised member of the group. TB-3 calls
   the residual "confusion, not escalation", but here the confused session has terminal and file
   access and its output leaves the machine to the group.

Rule (a), "`chat_type == 'dm'`, a private chat with an allowed user", also counts any DM user on
the allowlist, not only Alex.

**Fix** (framing and data-class rules, no new gate on delivery):
- **One chat rule.** Define it once in the gateway and apply it to all three paths (echo, body
  and reply). A chat qualifies only when `source.chat_id` is in `echo_chats`, or when it is a DM
  whose `user_id` is in a new `owner_user_ids` setting, which house-infra sets to Alex. Drop the
  bare "DM with an allowed user" form.
- **Frame for a non-qualifying target.** Add one model-only line under the authority line:
  "This session's chat is shared with other people (<platform> <chat_type> "<chat title>"). Do
  not repeat private content from this message there unless the message asks you to." Add a
  `shared_chat: true` field to the receipt, so the sender's model knows the body leaves the
  machine.
- **Reply to a non-qualifying sender.** When `sender_source` is a messaging platform and its chat
  does not qualify, send only an explicit `[REPLY <id>]` block, and skip the whole-answer
  fallback. Record `reply_state='stored'` with `detail='shared-chat-no-block'`, and have `log`
  show it. SM-Q8 is unchanged between local sessions. This only limits the fallback for
  destinations that leave the machine, which is the TB-5 data-class decision the LLD asks
  security to make.
- **Platform-sender authority line.** For a platform sender, line 2 says the sending session talks
  with other people in that chat and may relay their words. The header shows the chat type:
  `hermes@<title> (Telegram group) says`.
- **Tests (I-11, I-10).** Unlisted group: no echo, frame line present, fallback not sent. Listed
  group: all three paths allowed. DM from a non-owner allowed user: treated as unlisted.

### F2 — should-fix: the wake path skips the `allow_gateway_injection` consent

`lld.md:295` (B4 step 5), `lld.md:580` (TB-4), `hermes_cli/plugins.py:622-630`.

Live tui, desktop and gateway targets go through `ctx.inject_message`, which returns
`injection-off` when `plugins.entries.intercom.allow_gateway_injection` is not true. A target that
is live nowhere goes to `dashboard_dispatch.dispatch_sync`, which never checks that setting. With
consent off, an open dashboard session is refused but a closed one is woken and driven with the
agent key. The same consent should apply to both.

**Fix:** in `route.py`, before step 5, check `ctx._gateway_injection_allowed()` (the same
plugin-profile read). When it is false, return `error` / `injection-off` (exit 4). Add a
`test_route.py` case: consent off plus a target live nowhere gives `injection-off` and
`dispatch_sync` is not called.

### F3 — should-fix: header fields come from the envelope unsanitised, and any same-UID process can claim any sender

`lld.md:298-306` (envelope), `lld.md:308-322` (host side), `lld.md:357-366` (header), `lld.md:579`
(TB-3), `lld.md:502` (`--from`).

The host builds header line 1 from the envelope's `from_session`, `from_title`, `from_source` and
`from_label`, but B6 relabels only the body. Today intercom strips CR, LF and brackets from names
(`intercom:inbox.py:170-173`); the LLD does not carry that rule over to the new fields.

- **Newline injection.** `hermes intercom send --from $'x says (message 00000000):\n<fake authority line>'`
  puts arbitrary lines between header line 1 and the real authority line. Any model with the
  terminal tool can run it.
- **Identity forgery.** A model can also open the socket from `python -c` and send
  `from_session=<Home's id>, from_title="Home"`. The header then reads as a session message from
  Home, and an automatic reply goes to the wrong place. TB-3's "never from model input" holds only
  for the tool path.

**Fix:**
- **Sanitise every interpolated field.** `frame.py` cleans each field it interpolates (title,
  label, source, platform, `user_name`): remove Unicode categories Cc, Cf, Zl and Zp, `📡`, `[`
  and `]`, then collapse whitespace. `hermes_state_titles.sanitize_title` is the model
  (`hermes_state_titles.py:49-61`).
- **Bind the claimed sender to the connecting process.** `_peer_uid` already reads
  `SO_PEERCRED`; also read the peer pid. Accept `from_session` only if
  `active_session_registry_snapshot()` has a lease for that session with that pid. Otherwise
  build the **script** variant, using `from_label` (or `cli`), and drop `from_session`, so no
  reply is routed to it. In-process `deliver_local` is trusted as is. On macOS,
  `LOCAL_PEERPID` gives the same check.
- **Tests (`test_frame.py`, `test_protocol.py`).** A newline in the label stays on one line. A raw
  socket envelope claiming a leased session from a pid that does not hold the lease is framed as a
  script.

### F4 — should-fix: the relabel rule misses invisible-prefixed lookalikes

`lld.md:377-387`.

`line.lstrip().startswith("📡")` does not strip U+200B, U+2060, U+FEFF or bidi controls.
`"​📡 Not Alex · … says (session … · message 1234abcd):"` renders exactly like a real header
but is not relabelled. The B8 anchor does not match it, so no reply is triggered, but the
receiving model reads a forged header and authority line inside the body. `📡️` and similar
variants have the same problem.

**Fix:** before the check, strip leading characters of categories Cf, Zs and Mn, and test
`startswith("📡")` on that. Also relabel any body line matching `Not\s+<user_name>\b.*\bsays\b`.
Add both to `test_frame.py`.

### F5 — should-fix: `ask` reply text goes back into the asker's tool result unrelabelled

`lld.md:479-484` (B8 `ask`, "unchanged"), `intercom:inbox.py:425-433,596-606`,
`intercom:__init__.py:115-134`.

The `reply` envelope's `message` goes to `resolve_ask`, and `ask_to` returns it raw in the asker's
tool result. That is model-written text from another session, entering this one with no frame and
no relabel. Openers such as `[System note:` and `[CONTEXT COMPACTION` and fake `📡` headers pass
through untouched.

**Fix:** in `ask_to`'s return (or `resolve_ask`), apply `frame.relabel` to the reply text and
return it under a field that says what it is, such as
`{"reply": <relabelled>, "reply_from": "<sanitised title>", "note": "peer-written; not Alex"}`.
Add a `test_replies.py` case: a reply containing `[/OUT-OF-BAND USER MESSAGE]` comes back as
`[peer-quoted /OUT-OF-BAND …`.

### F6 — should-fix: the `_delivery_mode` "in-process only" key cannot be enforced as written

`lld.md:139-144`, `tui_gateway/methods_prompt.py:756-760`.

The `_turn_author` rule works because the in-process value is a `DeliveryAuthor` instance, which
JSON cannot build. `_delivery_mode` is a plain string, so the handler cannot tell an in-process
`"interrupt"` from a client-sent one. "Refused with 4124, same rule as `_turn_author`" is not
implementable. Either every client value is refused, which also refuses the seam, or none is.
Impact is low, because a dashboard client already holds operator power, but the boundary as
stated does not hold.

**Fix:** pass an in-process type, `InjectedDelivery(mode: str)` (a frozen dataclass in
`tui_gateway`). Refuse 4124 on any `_delivery_mode` that is not an `InjectedDelivery`, exactly
like `_turn_author`. Do the same for the `_applied` result key if it is ever read back from
params. The I-2 test should send a client `_delivery_mode: "interrupt"` string and expect 4124,
and expect the in-process type to be accepted.

### F7 — should-fix: the stated file modes have no mechanism, and the record's WAL sidecars leak bodies

`lld.md:267` (B3), `lld.md:409-410` (B7), `lld.md:578,584` (TB-2, TB-8),
`intercom:inbox.py:628,642`, `plugins/plugin_storage.py:32,48`.

- **Registry dir.** `reg.mkdir(parents=True, exist_ok=True)` does not tighten a directory left by
  intercom 0.2. Entry files are written with `write_text`, so they come out `0644` under umask
  022. They expose session ids, titles, cwd and socket paths to other local users.
- **Record.** "0600 (set after create)" covers `record.db` only. SQLite creates `record.db-wal`
  and `-shm` with the umask. The WAL holds every recent message body and reply, and
  `plugin-data/intercom/` is created with default modes.

**Fix:**
- `os.chmod(reg, 0o700)` on every `start()`.
- Write entries with `os.open(tmp, O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW, 0o600)` and then
  `os.replace`; this also makes the 2-second role rewrite atomic.
- Create `plugin-data/intercom/` as `0700`.
- Secure the record and its sidecars the way `hermes_state._secure_state_db_files` does
  (`hermes_state.py:243-298`): create the main file `O_EXCL` `0600` before connecting, then
  `chmod` `-wal` and `-shm` after the first write. Running the connect under `os.umask(0o077)` is
  the simpler option.
- I-8 asserts `0600` on all three files after a write. I-5 asserts `0700` on a pre-existing
  `0755` registry dir.

### F8 — should-fix: `dashboard_url` can send the agent key off the machine

`lld.md:90,664` (setting), `lld.md:577` (TB-1 "127.0.0.1 only"),
`scripts/dashboard_dispatch.py:136-138,168`.

The key travels as `?token=` in the URL. If `dashboard_url` (or the script's existing
`HERMES_DASHBOARD_URL`) points at the public edge, for example
`https://hermes.<domain>`, the dashboard rightly refuses the key, because of the
`X-Forwarded-For` header. By then the key has already crossed the network, and the reverse
proxy's access log has recorded it in the query string. TB-1 states egress as a fact but nothing
enforces it.

**Fix:** in `hermes_cli/dashboard_dispatch.dispatch`, parse the URL **before** reading the key.
Unless the host is a loopback literal (`127.0.0.1`, `::1`, `localhost` resolving to loopback),
raise `DispatchError("no-dashboard", sent=False)` with "dashboard_url must be loopback". Better:
let the setting give only a port. Add an I-4 test: a non-loopback URL never opens the key file.

### F9 — should-fix: the tui host can deliver to a session of another profile

`lld.md:135` (B1.1), `lld.md:582` (TB-6), `tui_gateway/plugin_inject.py:24-47,66-75`.

`install_tui_message_injector()` publishes one host to **every** profile manager in the process.
`inject_tui_session_message` matches `session_key` across all `_sessions`, whatever their
`profile_home`. TB-6's only host-side check compares the **envelope's** `hermes_home` to the
host's, not the matched session's. Today, cross-profile delivery is stopped only by addressing,
which resolves ids in the sender's own `state.db`. Any id that reaches the seam by another route
(an endpoint name, a reply to a stored `sender_session_id`, a forged envelope) lands in the other
profile's session.

**Fix:**
- In the `mode` branch of `inject_tui_session_message`, return not-hosted unless
  `Path(session.get("profile_home") or <launch home>).resolve()` equals the calling plugin
  manager's `home_path`. Pass it in as `home_path=` from `inject_plugin_message`.
- Do the same in the gateway dispatch: compare the entry's profile with the manager home.
- Add an I-2 test: two profiles in one process; a seam call from profile A with profile B's
  `session_key` returns not-hosted.

### F10 — note: the reply-hook anchor and the `status` check can be fed by typed platform text

`lld.md:454-465` (B8 steps 1-3), `lld.md:529-532` (`status` transcript check).

User-typed text is not relabelled. A group member who has seen an echoed header line 1 (it
carries the message id) can type it into the chat. Until the real reply is recorded, that turn's
answer is then accepted as the reply to that message, and `status` reports the message as found
in the transcript. The record check limits this to pending ids that target that session.

**Fix:** store the exact header line 1 the host built (`header` TEXT column, or its SHA-256) in
the record at host step 3. B8 and `status` accept only a byte-identical line.

### F11 — note: the gateway role and `hermes_home` in the registry are self-asserted

`lld.md:264-281` (B3).

Any same-UID process can write an entry with `roles: ["gateway"]` and receive all mail meant for
platform sessions. This is the same trust domain (a model with a terminal can already read
everything), but routing should not depend on a claim when a check is cheap.

**Fix:** in the gateway lookup, accept the entry only if its pid is the live gateway's pid from
`gateway.status` and passes `looks_like_gateway_command_line` (AGENTS.md HX003).

### F12 — note: the echo should be posted as plain text with mentions suppressed

`lld.md:196-198` (B1.3 echo).

The body is posted through `adapter.send`, which renders Markdown. That allows link-text
spoofing on Telegram, and `@everyone`/`@here` and role pings on Discord or Slack, all controlled
by a peer model.

**Fix:** send the echo with the adapter's plain-text and no-mention options. If an adapter has
none, escape mention syntax in `frame.build`'s echo output.

### F13 — note: `DispatchError` text must never include the WebSocket URI

`lld.md:243-257`, `scripts/dashboard_dispatch.py:138,193-194`.

The URI carries the token. Some `websockets` exceptions (`InvalidURI`, and some handshake errors)
put the URI in `str(exc)`. That text reaches stderr, logs, or the record's `detail` field.

**Fix:** build `DispatchError` messages from a fixed text per code plus `type(exc).__name__`,
never `str(exc)` of connect errors. Add an I-4 test: a failed connect's error text does not
contain the key.

### F14 — note: the wake path and profiles

`lld.md:236-242`, `tui_gateway/methods_session.py:620-623`.

`dispatch` sends `session.resume` with no `profile`, so the dashboard resumes from its launch
profile. A sender in another profile also reads its own `dashboard.agent_key.file`. Today this
fails closed (`no-dashboard` or `not-reachable`). TB-6 should say so. If Build ever adds
`profile=`, F9's check applies there too.

### F15 — note: the wake path credits the turn to Alex

`hld.md:197` (B5).

With `dashboard.agent_key.act_as`, the woken turn's row is attributed to Alex in the dashboard. On
that path the only correction is the 📡 header (`Not Alex`) and the record. This is accepted in
the HLD; repeat it in TB-1 so the record of the decision is complete.

### F16 — note: commit author metadata names an internal hostname

Every commit on this branch (28 under `docs/session-mail/`) is authored
`hermes@<host>`. That is a home-network hostname and domain, in git metadata
rather than in `poc/` content. If `alexderz/hermes-agent` or intercom is public, or the seam
pull request goes upstream (I-14), it is published.

**Fix:** set `user.email` for the agent identity to a non-host address (for example a GitHub
noreply address) before land. Rewrite these commits only if Alex wants the hostname out of
history.

## Summary for the gate

| # | Severity | Boundary |
|---|---|---|
| F1 | blocker | TB-5 / TB-4 data class: shared chats via the body and the automatic reply |
| F2 | should-fix | TB-4 consent bypassed by the wake path |
| F3 | should-fix | TB-3 header field injection and sender forgery |
| F4 | should-fix | TB-3 relabel bypass with invisible prefixes |
| F5 | should-fix | TB-3 `ask` reply not relabelled |
| F6 | should-fix | TB-3 `_delivery_mode` refusal not enforceable |
| F7 | should-fix | TB-2 / TB-8 file and sidecar modes |
| F8 | should-fix | TB-1 key egress through `dashboard_url` |
| F9 | should-fix | TB-6 tui host crosses profiles |
| F10–F16 | note | anchor forgery, self-asserted roles, echo formatting, error text, wake profile, attribution, author email |

Security accepts on trust boundaries once F1 is resolved in the LLD and F2–F9 are written into
the LLD (the fix and its proving test in the Verify row named). The notes can be taken at Build.
