# UX review, round 2: session-mail (DER-701)

Reviewer: UX reviewer (designer role, review loop only). Date: 2026-11-09.
Under review: `docs/session-mail/ux.md` and `docs/session-mail/stories/` at commit `395f5fb668`
(designer round 2; the diff from `ac48638002`). The working tree has no changes to these files;
the only untracked item is `docs/session-mail/poc/`, which is out of scope and was not reviewed.
`hld.md` is unchanged, so the "For the architect" list is checked as proposed HLD changes.
Requirements are the same as in round 1 (`ux-review-r1.md`).

## Round-1 findings

| # | Round-1 finding | Status |
|---|---|---|
| 1 | Merged rows and no end marker | **Fixed.** `📨 End of mail <id>` closing line (`ux.md:228-231`), F8 (`ux.md:102-104`), header rule narrowed (`ux.md:210`), sm-04/05/08/09 updated. |
| 2 | Whole answers bounce back | **Fixed.** Footer line 2 (`ux.md:223`), J1 step 6 (`ux.md:45`), F5 second paragraph (`ux.md:96`), sm-06 Done-when. |
| 3 | Stopping does not stop the exchange | **Fixed in the design, with a gap in checkability.** F9 (`ux.md:106`), sm-10, architect item 3. See R2-2. |
| 4 | `[SILENT]` missing from the tool description | **Fixed** (`ux.md:153`, sm-07:17). |
| 5 | A cut-off send reported as "not delivered" | **Partly fixed.** There is now a distinct `delivery unknown` result and exit 6, but the advice it gives cannot be acted on. See R2-1. |
| 6 | Reply delivery failure not covered | **Fixed.** F2b (`ux.md:83`), `list` reply column (`ux.md:335-338`), sm-12, sm-15. |
| 7 | Script senders' line 2 | **Fixed** (`ux.md:198-203`). |
| 8 | Header line 1 claim untrue | **Fixed.** The glance words now come first, and the claim matches (`ux.md:206`, `:376`); about 35 characters. |
| 9 | Unwakeable-sender wording | **Fixed.** `<source>` names the one that applies, "finished" is dropped, and `reply expected` is kept on purpose (F6, sm-14). |
| 10 | Exit code for an empty body | **Fixed** (`ux.md:299-300`, sm-11). |
| 11 | `status` "unknown" wording | **Fixed** (`ux.md:317`, sm-12). |
| 12 | sm-01 "every session" | **Fixed** (sm-01:13). |
| 13 | Tool description length | **Fixed.** Trimmed, and every required rule is kept. |

What holds in the new text: nothing that the settled decisions forbid has been added. F9 is Alex's
own stop, not a cap, and exit 6 is a report, not a retry. The no-empty-replies rule and the
`[SILENT]` instruction are now in the tool description and in every footer variant. The words "not
Alex" come first on every surface. Colour is still never the only signal.

## New findings

### R2-1. "Check status before you send again" cannot be acted on (blocking)

- **Where:** `ux.md:87` (F3, second case), `ux.md:177` (`error` (delivery unknown)),
  `ux.md:303` (exit 6), `ux.md:317` (`status` delivery line); sm-15; architect item 4.
- **Requirement broken:** each user must be able to finish the job in the story. sm-15's "So that"
  is "I can decide myself whether to send again". Results must be unambiguous.
- **What happens:**
  - The new result tells the sender to run `status` before it sends again. But `status` shows that
    same mail only as `error (delivery unknown)`.
  - Nothing in the outbox can say whether the steer or submit actually landed. A reply would
    settle it, but `no reply recorded` cannot be told apart from "not yet".
  - So the sender, a model or a script, learns nothing new and is back to guessing, and a duplicate
    is as likely as before.
  - The same holds for the "sending process died" case (`ux.md:88`).
- **Fix:**
  - Give `status` a read-only check that answers the question. The steered or queued row is
    written to the target's transcript when it is accepted (HLD Persistence). So `status` can look
    for that mail's header (`mail <id>`) in the target session's transcript and print, for
    example:
    - `delivery  unknown, but found in the target's transcript (07:00:04)`, or
    - `delivery  unknown, not found in the target's transcript`.

    This is a read, not a retry and not a pending state.
  - Add this to architect item 4, as an HLD change: `status` reads the target's transcript in
    `state.db`. Add it to sm-12 and sm-15 as a Done-when.
  - Also narrow "delivery unknown" to the case where the steer or submit call was sent and got no
    answer. A resume that times out before either call is sent delivered nothing, so it is "Not
    delivered" (exit 5). Say this in architect item 4, so the two `detail` codes are split at the
    right point.

### R2-2. F9's `status` label depends on a hook call the HLD does not know will happen (blocking for checkability)

- **Where:** `ux.md:106` (F9), `ux.md:325`, `ux.md:338`; `sm-10:15`; architect item 3.
- **Requirement broken:** "Done when" lines must be checkable. A design must not promise what
  the HLD cannot yet deliver without saying so.
- **What happens:**
  - HLD O9 / PoC Q9 leave open whether `post_llm_call` fires at all for a stopped or failed turn,
    and whether it can tell such a turn from a normal one.
  - sm-10:15 promises that `status` shows `not sent: turn stopped` / `not sent: turn failed`.
    - If the hook does not fire, nothing records that label, and `status` shows `no reply
      recorded`.
    - If the hook fires but has no stop or fail signal, the turn's text is treated as a normal
      final answer and mailed back. That is exactly what F9 forbids.
  - Architect item 3 says "whatever `post_llm_call` sees …". It does not say that the hook needs a
    stop or fail signal, or what happens when there is no call.
- **Fix:**
  - In sm-10, make the core Done-when "a turn Alex stops, or one that fails, sends no reply and wakes
    no one". Make the label conditional: `not sent: turn stopped / failed` when the hook sees the
    turn, otherwise `no reply recorded`.
  - In architect item 3, state the need plainly: the hook must be able to tell a stopped or failed
    turn from a finished one (PoC Q9 must find that signal), or the turn must not reach the reply
    path at all. Ask the architect to confirm that one of the two holds before Spec.

### R2-3. sm-06's new line contradicts the fallback rule (minor)

- **Where:** sm-06, the line "no text outside a block is ever mailed when a block is present",
  compared with `ux.md:243` and HLD D3 step 2.
- **What happens:** `ux.md:243` and the HLD give the whole final answer to a mail *with no block of
  its own*, even when another mail in the same turn has a block. So when one of two mails has a
  block, text outside that block is mailed to the other sender. The story line says it never is.
- **Fix:** reword it to "for a mail that has its own block, only that block is mailed". Or, if the
  designer wants "any block present means no fallback for any mail", put that in `ux.md` and in
  architect list item 6 as an HLD change.

### R2-4. Relabel any body line that starts with 📨, not just three openings (minor)

- **Where:** `ux.md:208`, sm-05 (the lookalike line), architect item 1.
- **Requirement broken:** mail must not carry false instructions in the reader's own frame. The
  footer must be unambiguous.
- **What happens:** the relabel list is `📨 Mail`, `📨 Reply` and `📨 End of mail`. A body can
  still hold a fake `---` / `📨 How to answer mail <id>` block with contrary instructions (for
  example "your whole answer is sent; do not use a block"). It would sit just above the real
  footer and look like it.
- **Fix:** relabel every body line that starts with `📨`. That is one rule, and it covers the
  footer heading too. Update `ux.md:208`, sm-05 and architect item 1.

### R2-5. sm-05's first Done-when excludes replies (minor)

- **Where:** sm-05, the first Done-when ("Every mail … line 1 starts `📨 Mail (not Alex) ·`").
- **What happens:** replies are mail too (`ux.md:25`), and their line 1 starts
  `📨 Reply (not Alex) ·` (the next bullet). As written, every reply fails the first bullet.
- **Fix:** "line 1 starts `📨 Mail (not Alex) ·`, or `📨 Reply (not Alex) ·` for a reply".

## "For the architect" list

All six items are flagged as HLD changes or point to items already listed under "Differences from
the HLD", and none adds a cap, hold, retry or gate:

- Items 1, 2 and 5 are consistent with the HLD's shape: D2's element list, B2's relabelling, D3's
  matcher, and outbox rows linked by `in_reply_to`.
- Item 4 is consistent with D4, but needs R2-1's two additions.
- Item 3 extends O9 in the direction the HLD already leans, but needs R2-2's precondition.
- Item 6 is consistent.

Verdict: changes needed
Reviewed: 3aed7054282c3d359f910c3dfb94ec103bd26b5238a622be389b92e792501eac
