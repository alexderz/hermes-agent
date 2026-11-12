Commit: fdbd1b69c2

Verdict: pass

Round 2. I reviewed `docs/session-mail/groom.md` at `fdbd1b69c2` (diff from `fbb00076f4`)
against `lld.md` round 9, following groom-step § 2.

## Round-1 findings

| # | Finding | Status |
|---|---|---|
| 1 | G14 Verify rejected `--intercom-src`; a skip passed green | **Fixed.** G14 now uses `--fail-on-skip … -- --intercom-src=<intercom-repo>`. `run_tests_parallel.py` forwards everything after `--` as-is, so the conftest option reaches pytest. G12 adds `--fail-on-skip`. `tests/plugins/intercom/` is not under the runner's skipped `integration/` / `e2e/` directories, so discovery finds it |
| 2 | A failing G14 did not hold back G12 | **Fixed.** G12 needs a **passing** verdict. Every fix item is blocked by G14, blocks G12, and ends with a G14 re-run. The O21 fallback is a G6 change that also blocks G12. The Graph says the same. No cycle: fix items sit between G14 and G12 |
| 3 | G13's scrub grep could never pass | **Fixed.** It now uses `-r`. `HOUSE_PATTERN` is supplied by the manager and never written in the ticket. The generic path and IP check runs alone. If `HOUSE_PATTERN` is unset or empty, grep matches everything and the check fails, so it fails closed |
| 4 | B9 receipt wording had no owner | **Fixed** in G3: `reply`, candidates' ids, the `(session <id>)` line ending, and the cold-start and `not-addressable` sentences, word for word as in LLD B9 |
| 5 | G2 return shape and `prompt.receipt` | **Fixed.** `deliver_sync` returns `applied` / `applied_detail` / `admission_id`. `receipt(admission_id)` is added. Both are recorded under "For the manager" 4. See minor 1 |
| 6 | Late-steer echo and escaper tests had no single owner | **Fixed.** The late steer is in G14 (GW-4 list), and G6 Verify points there. The per-platform escaper tests are G7's alone, and G6 keeps the missing-escaper warning and the post decision |
| 7 | G14 temp-home config | **Fixed.** The config lists `plugins.enabled`, `allow_gateway_injection`, `user_name`, `echo_chats` (the fake ntfy chat) and one unlisted group. `.env` holds only fake ntfy values |
| 8 | G1 needs a fake model | **Fixed** |
| 9 | Missing LLD test-row assertions | **Fixed.** G3: consent for every target kind, and `reply_mode` stored as passed. G8: two writers on one file. G10: `@<project>` when true, `--to @x` exits 3, and with discovery `None` / `starting` / `draining`, `inbox.start()` is never called |
| 10 | G11's diff line was not a check | **Fixed.** The AST comparison (module docstring removed) exits non-zero on any code change. "For the manager" 2 now records the docstring-only note as settled. See minor 3 |
| 11 | G12 did not run the vendored unit suite | **Fixed.** `unittest discover` runs in `plugins/intercom`, the same layout as the intercom item commands |
| 12 | Graph prose on G14 | **Fixed** |

## New-change checks

The round-2 edits break none of the review checks:
- **Coverage:** every LLD build item and test row still maps to exactly one item.
- **Graph:** no blocker link was added or removed apart from the G14 fix items, and there are no
  cycles. "Blocked by" and "Blocks" still agree.
- **Gates:** G14 and the operator's restart window are both still needed.
- **Hygiene:** the new text (the lefthook rule moved under "Common", the `.env` line, the scrub
  patterns) has no secrets, house host names or local absolute paths. The generic scrub pattern
  writes `/ho[m]e/` and the like, so even the pattern text contains no literal path.

## Minor (non-blocking; fold in at freeze if convenient)

1. **G2's `admission_id` wording.** "`None` for steer and redirect" can be read as "by the
   requested mode". But a rejected steer and a hard interrupt both end in
   `prompt.submit{queued: true}`, which does return an admission id, and G10's `status` needs it
   then.
   **Fix:** "`admission_id` is `prompt.submit`'s id whenever the sequence ends in a submit (start,
   queue, steer → queue, hard interrupt); `None` when `session.steer` or `session.redirect` took
   it."

2. **G14's runner defaults weaken the gate.**
   - The runner retries a failing file once by default (`_DEFAULT_FILE_RETRIES = 1`) and counts
     a pass on retry as passed (reported FLAKY).
   - Each file has a 300 s timeout, which an E2E with 24+ cells, an owner restart and a pty CLI
     may exceed.

   **Fix:** add `--file-retries 0` to G14's and G12's E2E lines, plus an explicit
   `--file-timeout` sized by the builder. Alternatively, state that a FLAKY result is a failing
   verdict.

3. **G11's AST check needs bash.** The `<(git show …)` process substitution fails under `sh`.
   **Fix:** precede it with `bash -c '…'`, or write the base file to a `mktemp` path first.
