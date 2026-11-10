# UX review, round 6: session-mail (DER-701)

Reviewer: UX reviewer (designer role, review loop only). Date: 2026-11-09.

Under review: the diff `git diff 9cba7fa6fd -- docs/session-mail/ux.md docs/session-mail/stories`,
committed as `9f7fe41d13`. The working tree has no changes to these files. The untracked
`poc/round2/` (Trial round 2, in progress) is out of scope.

`hld.md` has had no commits since `923a6ff272`, so the consistency check below is against that
version.

Requirements are the same as in round 5.

## Round-5 findings

| # | Round-5 finding | Status |
|---|---|---|
| R5-1 | `status` "not found" could invite a duplicate on a classic CLI or gateway host | **Fixed.** `ux.md` § `status` now words the advice by host and by live state: busy, idle or gone. "Sending again will not duplicate it" is printed only when that is true. The delivery-unknown receipt now defers to what `status` says. sm-12 and sm-15 have matching Done-when lines. Architect item 7 is corrected as an HLD change. |
| R5-2 | The `ask` footer dropped `[SILENT]` | **Fixed.** Line 5 of the `ask` footer is `reply once with message="[SILENT]"`, and the asker gets "nothing to add" at once. sm-21 has a Done-when for it. sm-07 is back to "every footer variant, the `ask` footer included". Architect item 8 carries the asker-side mapping. |
| R5-3 | sm-01 forbade `held` | **Fixed.** |
| R5-4 | Hard-interrupt receipt wording | **Fixed.** There are now separate `redirect` and `hard-interrupt` sentences (`ux.md:209-210`), and sm-18 follows them. |
| R5-5 | An idle classic CLI with half-typed input | **Fixed.** It is under "Still to check" and in sm-19, backed by the Trial. |
| R5-6 | Gateway injection switched off | **Fixed.** The new `injection-off` case is in F3, the receipts, exit 4, sm-15 and architect item 9. The claim matches the code: `inject_plugin_message` returns False for every non-CLI path without the setting (`hermes_cli/plugins_injection.py:34-38`), so "nothing is queued either" and "a classic CLI target is not affected" are both true. |
| R5-7 | Character claim and CLI help text | **Fixed.** The text now says "50 for an interrupting `ask`". The `--delivery` help carries Alex's sentence word for word (sm-11). |

## Consistency with the HLD

Items 1–9 of "For the architect" are all marked as changes still needed in `hld.md` (`923a6ff272`):
- header order and anchor;
- "message" instead of "mail";
- the script header form;
- the CLI verbs;
- the first sentence;
- `user_name`;
- the `status` live-state read;
- `[SILENT]` on `ask`;
- `injection-off`.

Nothing in the new text contradicts the HLD without being listed there. None of these items adds a
cap, hold, retry or gate. The live-state read and the help text are reads and words, not timers.

## New findings (minor, not blocking)

### R6-1. For gateway targets, "busy" must be per chat, not per process

- **Where:** `ux.md` § `status` ("its lease, and intercom's busy or idle flag"), architect item 7.
- **What happens:** intercom's registry has one entry per process, so its busy or idle flag
  describes the whole gateway, not one Telegram topic. With many chats in one gateway, the flag can
  read "busy" because another chat is running, and the sender is told to wait for nothing. It can
  also read "idle" between other chats' turns.
- **Fix:** say that for a gateway host the test is the target chat's lease. HLD § Data says the
  gateway keys the lease by its session key, and only while a turn runs. So "lease present" means
  that chat is busy. Keep the process flag only for a classic CLI, which has one session per
  process.

### R6-2. The `[SILENT]` sentence in the tool description and the `ask` receipt row should cover `ask`

- **Where:** the tool description (`ux.md:194`, "When you receive a message and have nothing new,
  answer [SILENT]"), and the receipt row "any, `ask`" (`ux.md:216`).
- **What happens:**
  - For an `ask`, a final answer of `[SILENT]` is never sent. A model that follows the tool
    description rather than the footer leaves the asker waiting until its timeout. The footer gets
    it right; the description does not.
  - The asker's receipt for a `[SILENT]` reply ("nothing to add", architect item 8) has no wording
    in the receipt table.
- **Fix:**
  - Add a few words to the description: "… answer [SILENT] (for an ask, reply with [SILENT])".
  - Add the asker's sentence to the receipt table, for example: `"<title>" replied that it has
    nothing to add.`

Verdict: meets requirements
Reviewed: 6d3564079c05d5e4ad564c58942eccc2fb9dcabeccab4fae10ce29c94e992749
