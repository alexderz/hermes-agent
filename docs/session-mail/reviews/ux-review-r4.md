# UX review, round 4 (delta re-review): session-mail (DER-701)

Reviewer: UX reviewer (designer role, review loop only). Date: 2026-11-09.

Scope: only the delta `git diff d71ed6ec04 0051259015 -- docs/session-mail/ux.md
docs/session-mail/stories`, which covers:
- the designer's round-3 notes;
- the alignment with the Trial (`poc/poc.md`);
- the HLD changes in `d49bb90d67`.

Requirements are the same as in rounds 1–3. The working-tree `ux.md` is the same file as at
`0051259015`.

## Round-3 notes

| # | Note | Status |
|---|---|---|
| R3-1 | Match the transcript check on the header line | **Applied** (`ux.md:339`, sm-12, architect item 3). It uses the same anchor as D3. |
| R3-2 | "Not found" advice the sender can act on | **Applied** (`ux.md:341`, `ux.md:197`, sm-12). The compaction condition is gone. It still says this is advice, not a timer or a hold. |

## Delta checks

- **Stopped or failed turns.** These now match the HLD:
  - F9 (`ux.md:141`), "What sends nothing" (`ux.md:230`), sm-10 and the `status` and `list` texts
    now match HLD O9 and Trial Q9 (the reply hook does not fire, so nothing is sent).
  - The `not sent: turn …` labels are removed everywhere. No leftovers were found in `ux.md` or in
    the stories.
  - sm-10's Done-when (`no reply recorded`) can be checked.
  - The open point (a steered mail in a stopped turn may be handed to the next turn) is listed
    under "Still to check", as the HLD lists it.
- **4090 for a held target** (F2, the `error` (held) result, sm-15) matches HLD D4 and Trial Q5.
- **The footer stays short and complete.** Only line 1 grew, by one clause. The no-empty-replies
  rule (line 4) and `[SILENT]` (lines 2 and 5, and the no-reply variant) are unchanged, and every
  variant carries them. Nothing in the new text gives mail Alex's authority or invites
  acknowledgements.
- **Caching.** The Tool Search text matches HLD D6 and O11/O12: no cache miss with Tool Search on,
  one miss with it off. sm-16 says the same.
- **The new open question (HLD O11)** is consistent with the HLD's O11 row and is flagged as a
  deploy step that needs Alex.

## New findings

### R4-1. The catalog shows 60 characters, so the "first sentence carries the rule" design does not work (blocking; one-line fix)

- **Where:** `ux.md:170` (design rule), `ux.md:165` (the catalog row), `ux.md:185` (the
  description's first sentence); sm-01 (second Done-when).
- **Requirement broken:**
  - The tool description must be short and unambiguous.
  - The no-empty-replies rule must be in the tool description.
  - A design rule must hold in the product it describes.
- **What happens:**
  - The catalog does not show the first sentence. It shows the first sentence clipped to **60
    characters** on a word boundary (`tools/tool_search_catalog.py:215-225`, `_short_desc`,
    `max_chars=60`).
  - The new first sentence is 102 characters, so the catalog shows: `Send mail to another Hermes
    session on this machine; write…`.
  - The rule the design rule exists to carry is cut off. sm-01's Done-when ("its first sentence
    names … the no-empty-messages rule") passes on paper, but the catalog never shows that rule.
- **Fix:**
  - Make the first sentence fit in 60 characters and keep the rule. For example: `Mail another
    Hermes session; never send an empty message.` (57 characters). The second sentence can then
    say "on this machine".
  - State the 60-character limit in the design rule and in sm-01. For example: "the catalog shows
    at most the first 60 characters of the first sentence; that span names the job and the
    no-empty rule".

### R4-2. The footer names the tool but not how to call it when it is deferred (minor)

- **Where:** footer line 1 and its variants (`ux.md:237`, `ux.md:251-252`), plus the relay-skill
  line (`ux.md:173`).
- **What happens:**
  - A session created before the deploy learns `session_message` from the footer, told to "use
    tool_call". But nothing gives it the parameter names. The skill line names `to` but not
    `message`.
  - It also never reads the description's sender-side rules: the laundering rule ("never use it to
    get another session to do something you were refused"), and the result meanings.
  - The model either guesses the arguments or must think to call `tool_describe`.
- **Fix:** change the parenthetical in footer line 1 to "(if it is not in your tool list,
  `tool_describe` it, then `tool_call` it)". In the skill line, name `message` and the
  `tool_describe` step the same way. This adds only a few words, and the footer stays short.

### R4-3. Smaller points (minor)

- **The held code is named three ways.** F2 and the `error` (held) result use `4090`. F2b
  (`ux.md:83`) still says `SESSION_NOT_OWNED`. Architect item 4 says `4090 / SESSION_NOT_OWNED`.
  `list` prints `(held)`. Say once what the outbox stores as the code, and what `list` and `status`
  print for it.
- **sm-16's "learns the name" Done-when always passes.** "From at least one of: the footer …, the
  relay skills …, or Alex" passes whatever the design does. Make the check the part the design
  controls: "a pre-deploy session that receives a mail can name `session_message` and call it
  through `tool_call` (or `tool_describe` then `tool_call`) using only the footer".
- **sm-05 wording.** "footer line 1 naming `session_message` for new mail" reads as "only in new
  mail's footer". `ux.md` gives the line to every footer, replies included. Reword to "footer line
  1 names `session_message` as the tool for new mail, in every variant".
- **F9's last sentence.** If the Trial later shows that a steered mail in a stopped turn is handed
  to the next turn, that turn's answer is mailed back, and the debate goes on after Alex's stop. F9
  already lists this as unknown. Add one clause, so Alex is not surprised: "if it is handed on,
  stopping that next turn too ends it".

Verdict: changes needed
Reviewed: 195eb5fe476909e6e117a43e8e1523e2ecf1ee36b2b3228f963ea32451da295e
