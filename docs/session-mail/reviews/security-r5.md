Commit: b8e1f2ed38
Verdict: changes needed

# Security gate, round 5: DER-701 session-mail, gateway-only shape (SM-Q20)

Read: `git diff 6e08c79398 HEAD -- docs/session-mail/hld.md docs/session-mail/lld.md`, the whole of
`lld.md` at `b8e1f2ed38`, and `docs/session-mail/poc/round3/`.

v0.23 code checked in `/var/tmp/hermes-session-mail/wt/v023`:

| Area | Files |
|---|---|
| Owner client | `hermes_cli/gateway_client.py:39-45,244-299,319-368`; `hermes_cli/gateway_runtime.py:318-346` |
| Owner authorisation | `gateway/session_authority.py:200-238,694-754`; `gateway/session_operator.py`; `gateway/session_controls.py:796-865`; `gateway/session_busy_controls.py:18-30,176-218` |
| Admission | `gateway/session_ingress.py:290-350`; `gateway/run_inbound.py:1215-1229`; `gateway/platforms/event.py:121,189-191` |
| Echo | `hermes_cli/plugin_messages.py`; `gateway/plugin_messages.py:86-146` |
| Profile scope | `tools/thread_context.py:38-70`; `hermes_constants.py:18` |
| Owner startup | `gateway/run_bootstrap.py:271-389,831,883`; `gateway/run_adapters.py:1088-1093` |

Same scope rules: Alex's settled decisions, now including SM-Q20 and SM-Q22, are not reopened, and
no fix below is a cap, hold, retry or approval gate.

Most replacements hold the same boundary, often more strongly, because the owner now authorises
every verb. One new part, the no-owner fallback, can re-open the round-1 "message lands in another
session" problem inside the owner. That is the blocker. Two replacements lose a check without
saying so.

## Replacements for removed fixes

| Fix | Replacement | Holds? |
|---|---|---|
| **TB-1 / F8 / F13 / F14 / F15** | Owner ticket over the same-UID control socket; no wake path | **Yes.** The ticket is minted on the profile's private control socket (`private_control_query`, peer is the same user only, `gateway_client.py:244-262`). It is checked against the discovered `profile_id` and `instance_id` (`:295-298`), and it travels as a WebSocket **subprotocol**, not in the URL (`gateway_ws_target`, `:39-45`). There is no key file, no URL setting and no TCP credential. The F13 analogue (fixed error text) is in B1. F14 is gone with the wake path. F15's analogue: operator input is stamped `local_operator_v1` with the socket principal (`session_authority.py:740-748`), so attribution is "operator", as with `act_as`, and the header carries `Not Alex`. One condition is in R5-5 |
| **F2** | Consent checked by intercom for messaging targets | **Partly.** See R5-2 (a check is lost) and R5-3 (narrower than the LLD says) |
| **F3** | The frame is built only by the sending process; the CLI is always a script | **Yes, as a decline.** In v0.23 any same-UID client holding a ticket can submit any text to any session of the profile, so a binding inside intercom could not stop a forger who bypasses intercom. The trust domain really is TB-1's. The LLD's sentence needs one correction (N1) |
| **F6** | No new RPC key | **Yes.** `prompt.submit` and `session.steer`/`session.redirect` refuse unknown parameters (`session_controls.py:855-859`, `session_busy_controls.py:177-180`). Intercom sends only `text`, `submission_id`, `queued`, `execution_generation` and `session_id` |
| **F9** | Owner authorisation per profile | **Yes, stronger.** `authorize` refuses `profile_mismatch` on both actor and reference (`session_authority.py:205-206`). The ticket is per profile home. `post_message` refuses another profile's chat (`gateway/plugin_messages.py:101-102`). The tool thread and `copy_context().run` carry the profile, because the home override is a ContextVar (`hermes_constants.py:18`) |
| **F11** | `discover_gateway_endpoint` over the control socket | **Yes.** Discovery and the ticket both come from the same-UID socket and are identity-checked. No registry role remains |
| **R2-5** | No URL | **Yes**, on one condition (R5-5) |
| **R2-6 / N4** | In-process waiter; `reply` accepted only from the target session's own `reply` call | **Yes, stronger.** The session id comes from the tool handler's keyword, not from a peer pid or an envelope |
| **F1 / R2-1 / R2-3 / N1 / N2** | The same rule in `scope.py`, reading `SessionDB(read_only=True)` and `ctx.get_config` fresh | **Yes.** Same rule, same fail-closed handling, raw fields only. Unknown sources are treated as messaging, so `shared` |
| **F12** | Escaping in `frame.py`, posted with `ctx.post_message` | **Yes for routing:** `post_message` posts only into the session bound to the calling context and refuses another profile (`gateway/plugin_messages.py:86-113`). For formatting see N3 |

**Kept fixes, still applied:**
- **F4:** B5, unchanged.
- **F5:** B8 `ask`.
- **F7:** B7 for the record. The registry part applies only on the legacy path, and that path is
  the subject of R5-1.
- **F10 / R2-4:** span hash, now written by the sender. Correct, because the sender now builds the
  frame.
- **R2-2:** B5.
- **Shared-chat line and platform authority line:** B5.

**New parts:**

| Part | Result |
|---|---|
| Owner client and ticket | Sound (above), with R5-5 |
| Consent for messaging targets | R5-2, R5-3 |
| Chat rule and echo via `ctx.post_message` | Sound. Echo goes only to private chats, posted from the target's own turn, and never on a lookalike (hash match). O21 is a functionality question; dropping the echo if the hooks do not bind is the safe outcome |
| In-process `ask` | Sound (R2-6 row) |
| No-owner fallback | R5-1 (blocker) |

**Approval, clarify and slash laundering on the new path.** I checked this because the old
`allow_gateway_control=False` no longer travels with the message.
- A viewer's `prompt.submit` onto a chat route becomes a `MessageEvent` with the default
  `allow_gateway_control=True` (`session_ingress.py:302`).
- But reply intercepts (clarify, slash-confirm, update prompt) are refused for any admitted turn
  (`run_inbound.py:1222`, `executing_admission`).
- Plaintext approval needs a bare word (`run_busy.py:683`), and command parsing needs a leading `/`
  (`event.py:191`). The frame always starts with `📡`.
- Steer and redirect go to `agent.steer`/`agent.redirect` only (`session_busy_controls.py:212-215`).
- The typed voice-stop check needs a bare stop phrase (`session_controls.py:832-850`).

So "inert by construction" holds, but it now rests **only** on the frame's first character; see N2.

## Findings

### R5-1 — blocker: the legacy inbox is chosen by owner discovery at plugin load, so it can start inside the owner or the admin dashboard

`lld.md:428-431` (B12: "`inbox.start()` runs only when `discover_gateway_endpoint` finds no owner
at plugin load"), `lld.md:86-87` (`pre_llm_call` hook), `intercom:__init__.py:137-147,164-175`
(the legacy `_on_pre_llm_call` drain and `inbox.start()`).

Whether the legacy path starts is decided from **liveness at load time**, and both multi-session
processes can get it wrong.

**1. The owner itself.** The owner constructs its runner (`gateway/run_bootstrap.py:831`), and
plugins are discovered (`run_adapters.py:1091-1092`, and on any `model_tools` import) before or
around the start of its control socket (`run_bootstrap.py:883`). Even once the socket exists,
`identify` answers `starting` until the listener settles (`run_bootstrap.py:374-378`). If
intercom's check reads any non-ready verdict as "no owner", then after every gateway restart:
- `inbox.start()` runs **in the owner**;
- its socket listens;
- the legacy process-wide `pre_llm_call` drain is registered.

That drain injects parked messages as `context` into **whichever session's next LLM call comes
first**, for every chat the owner hosts, Telegram groups included. This is the exact problem the
round-1 design ruled out ("the process-wide drain runs only when the seam is absent").

**2. The admin dashboard.** It loads intercom too (`lld.md:534-536`). If it starts while the owner
is down (a shared restart window), it takes the legacy path. Its sessions' `send` then goes over
the legacy registry to whichever process also took the legacy path, the owner in case 1, and
lands in that process's drain.

**3. The decision is never revisited.** A process that guessed wrong at load keeps the legacy
path for its whole life.

This is cross-session delivery, and cross-chat delivery into `shared` chats, with no frame check
on the receiving side. The legacy `_deliver_local` uses intercom's old frame, not B5.

**Fix (no gate; it only selects the implementation):**
- **Decide by capability, not liveness.** The legacy inbox, socket, registry and drain hook are
  used only when this Hermes build **cannot** host an owner client at all:
  `hermes_cli.gateway_client.connect_gateway` / `discover_gateway_endpoint` are absent from
  `plugin_api.json`, or not importable. On any v0.23 build the legacy path never starts. "Owner
  not reachable right now" is `no-owner` / `owner-restarting` (exit 5), never a fallback.
- **Never in a multi-session host.** As a second guard, the legacy inbox never starts in a gateway
  owner, `tui_gateway` or dashboard process. Detect this with a published host fact or the
  plugin's own host kind, never argv (HX003).
- **Separate the hooks.** Register the legacy `pre_llm_call` drain only together with
  `inbox.start()`. B6's echo `pre_llm_call` is a separate hook.
- **Tests.**
  - G-10: on a build that publishes the owner names, with discovery returning `None`, `starting`
    or `draining`, `inbox.start()` is not called and no drain hook is registered.
  - G-2 E2E: after an owner restart, no intercom socket exists under
    `$HERMES_HOME/intercom/sessions/`.

### R5-2 — should-fix: the gateway's current-authorisation recheck for chat targets is gone, and the LLD does not say so

`lld.md:437-446` ("Removed security fixes": TB-4 is not listed), `lld.md:463` (TB-4); old LLD TB-4
("Authorisation is rechecked at dispatch, `_plugin_injection_authorized`"),
`gateway/run_plugin_injection.py:111-139`.

The v0.22 seam re-checked the chat route against today's allowlists, pairing and allow-all
before a plugin event could start a turn, with adapter delegation off. Intercom now submits as
an **operator** client. For a non-local route, `SessionAuthority.authorize` checks only the
capability and profile (`session_authority.py:200-238`); `_submit` stamps `local_operator_v1`
(`:740-748`). Nothing re-checks whether that chat's user is still authorised. Native ingress does
re-check (`session_envelope.py:165`), but operator input deliberately does not
(`session_operator.py:1-7`: "already-authorized operator input").

Consequence: a model in any session can address a chat whose user Alex has since removed from the
allowlist, or whose pairing was revoked. The turn runs, and its answer is posted to that person.
The chat rule makes it `shared`, so the body arrives with the shared-chat line, but the boundary
the seam enforced, "only currently authorised chats", is no longer enforced by anyone.

**Fix.** Either option is acceptable; neither is a delivery gate. Both keep an authorisation
check that existed.
- **(a) Restore the check through a listing.** A read-only predicate goes into L-1, for example a
  module-level `gateway.authz:route_is_authorized(profile_home, session_id)` wrapping
  `_is_user_authorized_for_source(..., allow_adapter_delegation=False)` on the stored origin. If
  only a runner method exists today, that needs a thin core function, which is a small core
  addition; the LLD should then say so. B2 step 3 then returns `refused-by-owner` /
  `not-authorized` (exit 4) for a chat that fails it.
- **(b) Accept it explicitly.** Add a TB-4 row: "Operator power: intercom can start a turn in any
  stored chat of the profile, including one whose user is no longer authorised, as Alex can from
  the Webapp." Add a G-3 test that pins the behaviour. Alex then accepts it with the LLD.

Recommended: (a) if a predicate can be listed without new behaviour, else (b).

### R5-3 — should-fix: the consent now covers fewer targets than before, and the LLD calls that "as before"

`lld.md:175` (B2 step 3), `lld.md:438` (F2 row: "Local sessions need none, as before (the old CLI
branch needed none)").

In v0.22, `allow_gateway_injection` was required for **every non-CLI host**: tui, desktop,
dashboard and gateway. Only classic CLI targets were exempt. Now it is required only for
messaging targets, so Webapp, desktop and Ink sessions receive steer and interrupt with the key
off. The key is `true` on Alex's install, so nothing changes there. But the replacement table
misstates the old boundary, and a profile with the key off now gets more than it consented to.

There is also an edge case: B2 step 3 decides "messaging" from `sessions.source`, and it does not
say what happens when that read fails.

**Fix:**
- Check the consent for **every** delivery (one rule, matching every v0.22 host except classic
  CLI, which no longer exists as a host).
- Or keep messaging-only and correct the F2 row so it states the narrowing for Alex to accept.
- Either way, a target whose source cannot be read positively as local needs the consent
  (fail closed, the same reading as B4).
- Add a G-3 case.

### R5-4 — note: drop the `session.resume` history; never log it or return it

`lld.md:128-131` (B1). `session.resume` returns the target's **whole transcript**
(`connect_gateway`'s 8 MB frame limit exists for it, `gateway_client.py:323`). It arrives in the
sending process: the tool thread in the owner, or the CLI.

Intercom must read only `running` and `execution_generation`, and drop the rest. If the history
reached the receipt, a log line or an exception text, the sending model would read another
session's history through a tool result. That is a data-class leak even though same-UID code
could read `state.db` anyway.

G-2 should assert that the receipt and the log hold no transcript text. If the owner offers a
lighter attach (a resume without history), use it.

### R5-5 — note: always pass the discovered endpoint to `connect_gateway`

`gateway_client.py:332-368`. With `endpoint=None`, `connect_gateway`:
- **ensures** an owner, starting one;
- honours `HERMES_TUI_GATEWAY_URL` as a remote target.

That would start a gateway from a tool call, or send the frame to a remote URL. B1 passes the
endpoint, which is correct. Make it an invariant, and test in G-2 that `client.py` never calls
`connect_gateway` without an endpoint and does not read `HERMES_TUI_GATEWAY_URL`.

### N1 — note: F3's decline needs one more clause

`lld.md:439`: "A forged frame gets no reply unless its exact span is in the record." Anyone who can
submit through the owner (same UID) can also write `record.db` (`0600`, same UID). So a forger can
insert a matching row, and an automatic reply then goes to a session of their choosing.

That stays inside the TB-1 domain and is acceptable, but say it: "…unless its exact span is in the
record, which only the Hermes user can write."

### N2 — note: inertness now rests only on the leading `📡`

With no `allow_gateway_control=False`, a frame that did not start with `📡` would be
command-parsed, approval-routed and clarify-routed like typed text on chat routes. B5 guarantees
the prefix. Add a G-7 or G-3 assertion that the submitted `text` always starts with `📡`, after
`sanitize_user_prompt_text`, for every variant (send, reply, script, ask).

### N3 — note: echo escaping must match each adapter's rendering

`post_message` calls `adapter.send` with the adapter's default formatting
(`gateway/plugin_messages.py:124-131`). There is no plain-text or no-mentions option, unlike
round 4's `parse_mode: None`. "Markdown-escaped" must therefore match what each adapter renders.
Telegram may render HTML or MarkdownV2, and Discord and Slack have their own mention syntaxes.

G-6 should run the escaping cases (link text, `@everyone`, `<@…>`) through the real ntfy adapter
in the E2E, and per-platform unit tests should cover the platforms Alex has in `echo_chats`.

### N4 — note: check that the owner never posts operator input into the chat itself

TB-5's guarantee is that a shared chat receives the **answer**, not the body. I found no path that
mirrors a viewer's submitted text to the platform (`run_turn_runner.py:270-333` and
`local_viewer_events.py` are local-viewer only). G-6's E2E should still assert it: after a delivery
into an unlisted group, the fake ntfy server received only the turn's answer.

## Commit metadata

`b8e1f2ed38` is authored `hermius-maximus@users.noreply.github.com` (F16 holds).

## Acceptance

R5-1 must change in the LLD: the legacy path selected by capability, never by load-time liveness,
and never started in a multi-session host, with its tests. R5-2 and R5-3 must each be either fixed
or stated for Alex. With those, security accepts on trust boundaries. R5-4, R5-5 and N1–N4 can be
taken at Build (G-2, G-3, G-6, G-7).
