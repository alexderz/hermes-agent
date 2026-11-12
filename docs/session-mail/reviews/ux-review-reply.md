# UX review, delta: reply modes and `list` (DER-701)

Reviewer: UX reviewer (designer role, review loop only). Date: 2026-11-11.

Under review: `git diff 97367027f1 HEAD -- docs/session-mail/ux.md docs/session-mail/stories
docs/session-mail/mockups`. HEAD is `7fa53f3d90`, and the working tree has no changes to these
files.

Requirements:
- the change spec `prompts/reply-modes-spec.md` (Alex's request, decided by the manager);
- the LLD at HEAD (`83fe88e69b`, B5 labels and footers, B9 / G-3 / G-10);
- the stated taste: the tool description, header and footer short and unambiguous; the
  no-empty-replies rule and `[SILENT]` in the description and every footer; Alex's glance; no
  caps, holds or gates.

**How I checked:**
- I read the full diff (`ux.md`, 11 stories, the README).
- I extracted mockup A's text, including the reply footer and the new `none` state.
- I compared the labels and footers with LLD B5's table.
- I searched for `send` examples without `reply`.

## What holds

- **`none` sends nothing back.**
  - The "What sends nothing" and "Several messages in one turn" sections, the receipts row ("No
    answer was asked for, and none will come back."), J3, sm-06 and sm-13 all say no block is
    captured and there is no whole-answer fallback, even for a note steered into a busy turn. This
    closes the B8 gap the spec names.
  - The `none` footer is the spec's sentence word for word, and it has no `[SILENT]`, as the spec
    and LLD B5 allow.
  - sm-07 records the exception.
- **Replies go back only from an explicit block.** The "What sends nothing" section, "Several
  messages in one turn", J1 step 6, J2, sm-06 and sm-07 all say so. The SM-Q8 line now limits the
  fallback to `requested` / `waiting`.
- **`reply` is required on `send` with no default.** This is in the parameters table, the
  description, sm-01 and sm-13. The CLI defaults to `--reply none` and `--no-reply` is gone (J3,
  sm-11, and exit 2 for a bad `--reply`). `waiting`'s footer line is the spec's sentence, and the
  sender's call does not block.
- **`list` gives ids:**
  - id, title, project, last active and state; newest 30 first;
  - runs only with `include_runs`, plus `query` and `limit`, stated as output size, not a delivery
    cap (tool, CLI with a sample, sm-12);
  - every receipt carries `target_session`;
  - the description's `to:` line says to use ids for follow-ups, and that they survive compaction.
- **The description** is shorter (273 words). The catalog sentence and Alex's interrupt sentence
  are word for word.
- **No settled decision is reopened.** SM-Q16 (a) keeps `ask`. No cap, hold or gate is added.
  Changing the reply fallback for `none` and replies is the spec's own decision.

## Findings

### RM-1. The reply footer still says the whole answer goes back, then says it doesn't (blocking)

- **Where:** `ux.md` § "Footer", variants, the row "A reply (`reply optional`) | 2, 5". It replaces
  only lines 2 and 5, so line 1 stays: "Your final answer goes back to session "…" by itself; do not
  call intercom send to answer." Mockup A draws exactly that: the 8e41b0 and c41d77 footers read
  "Your final answer goes back … by itself", then "Only text between [REPLY 8e41b0] and [/REPLY] is
  sent back; with no block, nothing is sent."
- **Requirement broken:**
  - The spec: replies are sent back "only from an explicit `[REPLY <id>]` block, **never** from the
    whole-answer fallback".
  - The stated taste: the footer must be unambiguous.
  - LLD B5: for `optional`, "Only a `[REPLY <id>] … [/REPLY]` block is sent back; nothing else is."
- **What happens:** the two lines contradict each other, one line apart. A model that trusts line 1
  writes no block and expects its answer to arrive, and the exchange silently drops. That is the
  opposite of what the debate journey (J2) needs.
- **Fix:**
  - Replace line 1 for replies too, for example: `Only a [REPLY 8e41b0] … [/REPLY] block goes back
    to session "Budgeting — Orchestrator"; nothing else does. Write one only if you have more to
    say. Do not call intercom send to answer. (intercom is the tool for new messages; …)`.
  - Fold line 2 into it, keeping LLD B5's wording.
  - Update the variants row ("1–2, 5"), the mockup's reply footers, and sm-05 / sm-06 so they
    check it.

### RM-2. `ask` and `waiting` are not clearly different, in the labels or in the description (blocking)

- **Labels:**
  - `send` + `waiting` reads `waiting on your reply`, and an `ask` reads `waiting on your reply
    (ask)` (`ux.md` § "Header" bullet, J12, sm-05, sm-21). They differ only in a trailing
    "(ask)".
  - With interrupt, `📡 Not Alex · interrupt asked · waiting on your reply (ask)` is 61 characters
    (`ux.md` says so). On a phone row "(ask)" falls onto line 2 and into the clamp's fade.
  - But the two need **different answering methods**: a block in the turn's answer for `waiting`,
    or the `reply` tool for `ask`. The architect raised exactly this risk.
- **Description:**
  - `ask` is "use it only when this turn cannot go on without the answer".
  - `waiting` is "if you need it before you can go on".
  - These are the same test in different words. The spec draws the line differently: `ask` only
    when this turn cannot continue; **otherwise** `send` with `reply: waiting`.
- **Requirement broken:** the stated taste (unambiguous), and the spec's distinction.
- **Fix:**
  - **Labels:** put the difference first, in words that also say how to answer. For example,
    keep `waiting on your reply` for `send` + `waiting`, and make `ask` read `ask: answer with
    intercom reply`. LLD B5 leaves the `ask` label to `ux.md`, so this needs no LLD change.
  - **Description:** "waiting if they should answer first but your turn can go on (your call
    returns at once; the answer arrives as a new message)", and on `ask`: "… use it only when this
    turn cannot go on without the answer; otherwise send with reply: waiting".
  - Update J12, sm-05, sm-21, the glance-length bullet and § "Accessibility".

### RM-3. Two `send` examples lack the now-required `reply` (minor)

- **Where:**
  - J8 step 1: `intercom(action="send", to="@budgeting", delivery="interrupt", message=…)`;
  - the relay-skill line (`action="send", to = …, message = your text`), which the manager pastes
    into the live skills.
- **What happens:** both would be refused, because `reply` is required. A session following the
  relay skill would fail on its first send.
- **Fix:** J8 should add `reply="requested"`. The relay-skill line should add "reply = none (a
  note), requested or waiting (required)".

### RM-4. The missing-`reply` refusal has no wording (minor)

- **Where:** sm-01 and sm-13 say a `send` without `reply` is "refused as a usage error". LLD G-3
  names it `reply-missing`, recorded as nothing. `ux.md` § "Receipts" has no row for it.
- **Fix:** add a row: `refused` (`reply-missing`): `Nothing was sent: choose reply: none, requested
  or waiting.` State that nothing is recorded, to match the LLD.

### RM-5. Small wording points (minor)

- **The `none` variant's text drops line 1's tool hint.** The variant row's text omits "(if
  intercom is not in your tool list, tool_describe it, then tool_call it.)". Mockup A includes it,
  and sm-05 requires it in every footer's line 1. A pre-deploy session learns the tool from
  footers (sm-16), and the CLI default is `none`, so many notes carry this footer. Add the hint to
  the `ux.md` row.
- **The reply footer drops `[SILENT]`.** Line 5 reads "If you have nothing new, write no block."
  But sm-07's Done-when keeps `[SILENT]` in every footer variant except `none`. Either write
  "write no block (or a `[SILENT]` one)", or add the reply footer to sm-07's exception.
- **The `waiting` receipt is unclear.** "It was marked as blocking you; your call does not wait"
  is easy to misread. A clearer version: `You marked it as waiting: your call returns now, and the
  answer will come back as a new message.`
- **The id formats differ.** The examples show headers with `session 20261109_071203_a1b2` (the
  v0.22 shape), while `list` shows `local-7f3a91c2`. The spec makes ids the follow-up address,
  taken from `list`, receipts and headers, so use one id shape in the examples.

Verdict: changes needed
Reviewed: d5fda12d70be5cbcd28f43f564d559e73e1257ab42d08730118bb818e3be5822
