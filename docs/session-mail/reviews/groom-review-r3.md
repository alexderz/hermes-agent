Commit: 73a5524315

Verdict: pass

Round 3. I reviewed `docs/session-mail/groom.md` at `73a5524315` (diff from `fdbd1b69c2`; only
`groom.md` changed) against `lld.md` round 9, following groom-step § 2.

## Round-2 minor notes

| # | Note | Status |
|---|---|---|
| 1 | G2: the `admission_id` wording | **Fixed.** `admission_id` is `prompt.submit`'s id whenever the sequence ends in a submit (start, queue, steer → queue, hard interrupt). It is `None` only when `session.steer` or `session.redirect` took the message. This matches the B1 mode table and gives G10's `status` an id on every fallback path |
| 2 | G14 / G12: runner retries and timeout | **Fixed.** Both E2E lines have `--fail-on-skip --file-retries 0 --file-timeout <seconds>`. The runner accepts `0` ("0 disables") and a float timeout. The notes say a FLAKY E2E is a failing verdict, that the builder sizes the timeout above the 300 s default and records it in the item, and that G12 uses the same value. `<seconds>` is a builder-filled placeholder, which is acceptable here |
| 3 | G11: the AST check needs bash | **Fixed.** It is wrapped in `bash -c '…'`, and the inner Python has no single quotes, so the quoting holds. I ran it at this commit: it exits 0 on the unchanged `scripts/dashboard_dispatch.py` and 1 when a code line is appended |

## Re-check

Round 3 changed only these three text spots, and none of the review checks moved:
- **Coverage:** every LLD build item and test row still maps to exactly one item, with nothing
  invented.
- **Graph:** there are no blocker-link changes and no cycles.
- **Gates:** both are still needed (G14, and the operator's restart window on G12).
- **Hygiene:** no secrets, house host names or local absolute paths appear in any body.

## Findings

None.
