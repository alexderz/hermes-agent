Commit: 6ccea9121f
Verdict: accept on trust boundaries

# Security gate, round 6: DER-701 session-mail, gateway-only shape

Read: `git diff 031b25c450 6ccea9121f -- docs/session-mail/lld.md docs/session-mail/hld.md`.
Checked against code:
- `tui_gateway/contracts/canonical_sessions.py:81,156` (`omit_messages`);
- `gateway/session_controls.py:123,693-695` (the owner honours `omit_messages`);
- HLD O23 (`hld.md:157,229`).

Same scope rules as before.

## Round-5 findings

| # | Status | Notes |
|---|---|---|
| R5-1 (blocker) | **Fixed** | B12 chooses the legacy path by **capability**: the owner-client names are importable or not. Liveness never decides it; `None`, `starting` and `draining` are all `no-owner` / `owner-restarting` (exit 5). On an old build the inbox starts lazily, only in a process where `_find_cli_instance` finds a classic `HermesCLI`, never in a `tui_gateway`, dashboard or gateway process, and without reading argv. The legacy drain hook is registered only with the inbox, and B6's echo hook is separate. Tested in G-10 (discovery `None`/`starting`/`draining` → no inbox, no drain) and G-2 E2E (no socket after an owner restart) |
| R5-2 | **Stated for Alex (option b)** | The B2 paragraph, the TB-4 row, the "Removed fixes" row and HLD O23 / SM-Q18 all say it. The reasoning is sound: v0.23 publishes no predicate, and a new core function would break "listings only". Mitigations are named: such a chat is `shared` and gets no echo. G-3 pins the behaviour. The fallback (a thin read-only predicate plus its listing) is stated if Alex declines. Security accepts this as a decision for Alex, not a defect; see "Condition" |
| R5-3 | **Fixed** | The consent is required for **every** delivery. With no source test, a failed read cannot open it. G-3 covers every target kind. The F2 row is corrected |
| R5-4 | **Fixed** | `session.resume{omit_messages: true}`. The contract has the field (`canonical_sessions.py:81`), and the owner returns no rows when it is set (`session_controls.py:693-695`). Only `running` and `execution_generation` are read, and no handle field reaches a receipt, log or error. Asserted in G-2 |
| R5-5 | **Fixed** | Invariant: always the discovered endpoint, and `HERMES_TUI_GATEWAY_URL` is never read. Asserted in G-2 |
| N1 | Fixed | The F3 row now adds "which only the Hermes user can write; that stays inside TB-1's domain" |
| N2 | Fixed | Invariant that every submitted `text` starts with `📡` after sanitising, for every variant. Asserted in G-7 and G-3, with the reason (command, approval and clarify parsing) |
| N3 | Fixed | Escaping per target renderer (Telegram HTML or MarkdownV2 as configured, Discord and Slack mentions, ntfy plain). **A platform with no escaper gets no echo**, which fails closed. G-6 runs the real ntfy adapter plus per-platform escapers |
| N4 | Fixed | G-6 E2E: after a delivery into an unlisted group, the fake server received only the turn's answer |

## Nothing new crosses a boundary

The delta only tightens:
- consent widens to every delivery;
- the legacy path narrows;
- resume omits the transcript;
- the echo is dropped when a platform has no escaper.

The one new behavioural fact, operator power into de-authorised chats, is not new code. It is
v0.23's existing operator semantics, now written down for Alex. No new key, setting, verb, writer
or egress is added.

## Notes (for Build; none blocks the gate)

### N6-1 — the capability check fails safe on an in-between build

`hermes_cli/gateway_client.py` already exists at the branch base (`031b25c450`). A build that has
the module but no working owner would select the owner path and answer `no-owner` rather than
fall back to the legacy path. That is the safe direction, losing availability rather than
isolation. G-10's "simulated old build" should simulate the names being **absent**, which is
the only legacy trigger.

### N6-2 — keep the "no escaper, no echo" table next to the escapers

N3's rule is only as good as the list of platforms that have an escaper. Keep that list in
`frame.py`, beside the escapers. A new entry in `echo_chats` for a platform without one then
produces no echo plus one warning, never an unescaped post. Add that warning case to G-6.

## Condition

Security's accept covers trust boundaries. R5-2 / O23 is now a **decision for Alex**, made with the
LLD (SM-Q18).
- **If he accepts it:** nothing more is needed.
- **If he declines it:** the stated fallback (a thin read-only core predicate plus its listing,
  wired in as B2's step 3 before consent) needs a short security re-check of that predicate only.
