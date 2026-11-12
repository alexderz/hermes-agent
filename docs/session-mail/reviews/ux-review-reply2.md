# UX review, delta round 2: reply modes and `list` (DER-701)

Reviewer: UX reviewer (designer role, review loop only). Date: 2026-11-11.

Under review: `git diff HEAD~1 -- docs/session-mail/ux.md docs/session-mail/stories
docs/session-mail/mockups`, with HEAD at `e91eb8487e`. The working tree has no changes to these
files.

Requirements are the same as in `ux-review-reply.md`: `prompts/reply-modes-spec.md`, the LLD at
`83fe88e69b`, and the stated taste.

**How I checked:**
- I read every changed line in `ux.md` and the stories.
- I extracted every footer's first line from mockup A.
- I searched for leftovers: the old `ask` label, "blocking you", v0.22-style ids, and `send`
  examples without `reply`.

## Round-1 findings

| # | Finding | Status |
|---|---|---|
| RM-1 | The reply footer said the final answer goes back, then said it doesn't | **Fixed.** The reply variant now replaces lines 1–2 with one line: "Only a [REPLY <id>] … [/REPLY] block is sent back to session "<title>"; nothing else is. Write one only if you have more to say. Do not call intercom send to answer. (… tool_describe …)". It matches LLD B5. In mockup A, the 8e41b0 and c41d77 footers now open with it, and no reply footer says "by itself" (checked line by line). sm-05 and sm-06 have Done-when lines for it. |
| RM-2 | `ask` and `waiting` were not clearly different | **Fixed.** The `ask` label is now `sender paused: use intercom reply`. It starts with different words from `waiting on your reply` and says how to answer. The `ask` footer opens "The sender's turn is paused until you answer". The description now separates the two by the spec's test: `ask` "only when this turn cannot go on without the answer, otherwise send with reply: waiting"; `waiting` "if they should answer first but your turn can go on". J12, sm-05, sm-13, sm-21, the glance-length bullets (30–55, 67 with interrupt; "Not Alex" always on line 1), SM-Q16 and "Differences" are all updated. The old label appears nowhere. "For the architect" item 3 asks the LLD to point to the new wording. |
| RM-3 | Two `send` examples lacked `reply` | **Fixed.** J8 has `reply="requested"`. The relay-skill line has "reply = none (a note), requested or waiting (required)", and it now leads with the session id. |
| RM-4 | The missing-`reply` refusal had no wording | **Fixed.** A receipts row reads `refused` (`reply-missing`): `Nothing was sent: choose reply: none, requested or waiting.` and nothing is recorded. sm-01 and sm-13 match, and "For the architect" item 2 asks LLD B2 to quote it. |
| RM-5 | Small wording points | **Fixed:** the `none` footer keeps the tool hint (`ux.md`, sm-13, mockup); the reply footer's line 5 says "write no block (or a [SILENT] one)", which is consistent with sm-07; the `waiting` receipt reads "You marked it as waiting: your call returns now, and the answer will come back as a new message."; and every example uses `local-…` ids, the same shape as `list` (no v0.22-style id is left in `ux.md` or mockup A). |

The changes add no cap, hold or gate, and reopen no settled decision.

## New finding (minor, not blocking)

### RP2-1. A sender in a shared chat gets the same line-1 contradiction RM-1 fixed for replies

- **Where:** `ux.md` § "Footer". For a `requested` message from a sender in a shared chat (the 4b0e21
  example from "Family planning (Telegram group)"), the footer keeps line 1: "Your final answer goes
  back to session "Family planning" by itself". Mockup A draws exactly that line in the 4b0e21
  footer.
- **What happens:**
  - For such a sender, "A sender in a shared chat" (LLD B8, TB-5) says only an explicit block is
    sent back, and the whole-answer fallback is not used. The footer adds only the
    reply-destination line.
  - So line 1 again promises something the hook will not do. A model that writes no block expects
    its answer to arrive, and nothing goes back.
  - This predates the reply-modes change, but it is the same kind of contradiction RM-1 fixed.
- **Fix:** for a shared-chat sender, use the reply variant's line 1 ("Only a [REPLY <id>] …
  [/REPLY] block is sent back to session "<title>"; nothing else is. …"), followed by the
  reply-destination line. Update the 4b0e21 footer in mockup A, and sm-05 / sm-20 to match.

Verdict: meets requirements
Reviewed: f39da8728f654bb2dc48378623d95a3e5780802f2acc10b51b711ec84c1befb1
