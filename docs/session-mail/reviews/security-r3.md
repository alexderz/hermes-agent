Commit: 5119747616
Verdict: accept on trust boundaries

# Security gate, round 3: DER-701 session-mail (LLD round 3)

Read: `git diff b2eea4af9b HEAD -- docs/session-mail/lld.md docs/session-mail/hld.md`. Changes
are in `3a1d8934ac`; HEAD `5119747616` only adds the mockup review record.

Code checked for the new mechanisms:
- `hermes_state_gateway.py:250-280`: the `sessions` origin columns, kept along the compression
  lineage;
- `gateway/session_identity.py:151-176` (`restore_identity`);
- `hermes_cli/input_sanitize.py:50-54` (`sanitize_user_prompt_text`).

Same scope rules as before. Nothing below adds a cap or a gate.

## Round-2 findings

| # | Status | Notes |
|---|---|---|
| R2-1 | **Fixed** | `gateway/chat_scope.py` works in any process. It takes the live entry when there is one, otherwise the stored origin read from `state.db` with `read_only=True`, falling back to `gateway_routing`. It fails closed: a platform source with no origin is `shared`, and `None` is returned only for local sources. It is used at insert (`sender_chat_scope`) and at host step 4. B8 treats `NULL` plus a platform source as `shared`. Tested in I-1, I-10 and E2E (a group session opened in the dashboard). The columns it needs (`source, user_id, chat_id, chat_type, thread_id, origin_json`) exist and follow the lineage (`hermes_state_gateway.py:258-266`) |
| R2-2 | Fixed | A footer line for shared-chat senders, on both the `send` and `ask` footers. Tested in I-6 |
| R2-3 | Fixed | `"<platform>:<id>"` strings. Non-string or unprefixed entries are ignored with a warning, which fails closed. Config is read fresh under `_plugin_home_scope(home_path)`. Tested in I-11 |
| R2-4 | Fixed | The hash now covers the whole framed span, and the round-2 rationale is corrected. `sanitize_user_prompt_text` only strips bracketed-paste debris (`input_sanitize.py:19-54`), so hashing after it is safe. A mismatch only means no reply, which is the safe direction. Residual in N3 |
| R2-5 | Fixed | `urlsplit().hostname` plus `ip_address().is_loopback`. No names are resolved, and `localhost` is refused. Tested in I-4 with the userinfo, suffix and fragment cases |
| R2-6 | Fixed | The ask waiter stores the target host's pid, and `reply` is accepted only from that peer pid. Tested in I-5. One availability gap is in N4 |

The new pieces add no trust-boundary problem:
- `gateway/chat_scope.py` and `session_chat_scope` only read: `state.db` read-only and the
  plugin's own config. They return a private/shared bit.
- The wake receipt wording (R7-1) is text only.

## Notes (for Build; none blocks the gate)

### N1 — the scope must not depend on `restore_identity`

`lld.md` B1, step 1 of `session_chat_scope`.

`restore_identity(source, *, runner, transport_profile)` returns `None` and pins nothing when
there is no runner or no `multiplex_profiles` (`gateway/session_identity.py:163-167`). That is
harmless, because the scope needs only `platform`, `chat_id`, `chat_type` and `user_id`. Build
should take those raw origin fields and treat the re-pin as optional, so a `None` from it never
becomes "no origin" and flips a resolvable session to the fail-closed path or the reverse.

I-1 should call `session_chat_scope` with no runner and assert `shared` for a group row and
`private` for an owner DM row.

### N2 — fail closed on errors too

Any exception while reading the stored origin (database locked or missing, bad `origin_json`)
should yield `shared` unless `sessions.source` was positively read as local. A missing
`sessions` row counts as unknown, so it is `shared`.

The LLD's wording ("`None` only for local sources") implies this. Add one I-1 case with a
corrupt `origin_json` and one with a missing row.

### N3 — the span hash raises the bar but is not a secret

Lines 2–3 and the footer are deterministic, built from public `ux.md` wording plus fields that
header line 1 already shows. So someone who has seen an echo and reads the public repo could
rebuild the whole span. That is acceptable, because echoes go only to `private` chats (Alex's DM
and the chats he lists). Keep the LLD's claim at "cannot be reproduced from the echo alone",
not "cannot be forged".

### N4 — an `ask` that wakes its target needs the dashboard pid

The R2-6 binding stores "the target lease's pid, or the verified gateway pid". When the `ask` goes
through the wake path (B4 step 5), the reply comes from the dashboard process. The waiter should
store the dashboard's pid: the owner of the loopback port, or the dashboard's lease once the
turn starts. Otherwise the reply is refused and the ask times out. This affects availability
only, not trust; add it to the I-5 wake case.

### N5 — F16 regressed

`3a1d8934ac` uses the noreply address. `b2eea4af9b` and HEAD `5119747616` are authored
`hermes@saturn.home.derzhi.com` again. The manager should pin `user.email` in the worktree's git
config, so every agent role commits under the noreply identity, before land. Whether to rewrite
history is still Alex's call.

## Acceptance

Security accepts the LLD on trust boundaries at `5119747616`. N1–N4 go to the Build items they
name (I-1, I-5). N5 is for the manager.
