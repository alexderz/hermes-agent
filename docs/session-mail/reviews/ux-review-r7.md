# UX review, round 7 (delta re-review): session-mail (DER-701)

Reviewer: UX reviewer (designer role, review loop only). Date: 2026-11-09.

Scope: only the delta `git diff 9f7fe41d13 -- docs/session-mail/ux.md docs/session-mail/stories`,
committed as `d352e9c4ac`. The working tree has no changes to these files. The delta covers:
- the round-6 notes;
- the alignment with Trial round 2 (`poc/round2/poc.md`);
- the HLD at `2f74663bcc`.

Requirements are the same as in rounds 5 and 6.

## Round-6 notes

| # | Note | Status |
|---|---|---|
| R6-1 | For gateway targets, "busy" must be per chat | **Applied** (`ux.md` § `status`, sm-12, architect item 7). A classic CLI uses its process flag; a gateway target uses that chat's own lease, and the text says why the process flag is not used. |
| R6-2 | `[SILENT]` for `ask` in the tool description and the receipt | **Applied.** The description adds "(for an ask, reply with [SILENT])", the `ask` receipt row has `"<title>" replied that it has nothing to add.`, and sm-21 checks that exact sentence. |

## Trial round 2 alignment (checked against `poc/round2/poc.md` and HLD `2f74663bcc`)

- **Redirect is the normal interrupt.** J8, the classic-CLI table, sm-18 and the Telegram section
  match R1 (12 of 12 cells; every v0.22 agent reports `_supports_active_turn_redirect`) and HLD
  D1. The hard interrupt is now named only as the fallback for media payloads or older agents.
- **Gateway silence is settled.** The Telegram section and sm-20 match R4 and HLD D6: injected
  turns are stored as `internal_notification`, so a bare `[SILENT]` is not posted. It is correctly
  removed from "Still to check". The SM-Q15 post itself and what an interrupt shows in the topic
  stay under "Still to check", as R4 did not run them.
- **O17 (queued rows written twice).** J5, the Mobile and dashboard sections, sm-08, sm-09 and a
  new open-question row match HLD O17 and R1-extra:
  - the bug is in Hermes and affects every queued prompt, Alex's own included;
  - only the dashboard writes the row twice, not the gateway or the CLI;
  - only one reply is sent.

  This is said plainly and in words, with no colour, and the Done-when lines can be checked
  either way.
- **O18 (no lease before a terminal's first turn).** F13, J10, sm-19 and an open-question row match
  HLD O18 and R2/R3. They state the effect honestly: the turn runs in the dashboard, the terminal
  sees nothing, and a later typed turn may get 4090. Accepting this for v1 is put to Alex as an
  open question, not decided quietly.
- **The Ink TUI was not run**, and this is listed under "Still to check".
- **"For the architect"** now cites `2f74663bcc`. Items 1–9 are unchanged except item 7 (R6-1),
  and nothing new contradicts the HLD.

Nothing in the delta adds a cap, hold, retry or gate. The interrupt sentence, the footer rules and
the authority text are unchanged.

## New findings (minor, not blocking)

### R7-1. F13 should say what happens to Alex's typed text, and the receipt should say where the turn ran

- **Where:** `ux.md` F13 and J10; sm-19 (new Done-when); the `started` receipt row; the O18 row in
  "Open questions".
- **Requirement:** Alex keeps control, and he will not tolerate "losing his own draft". The
  receipts must be unambiguous.
- **What happens:**
  - F13 says that when Alex types in that terminal after the message, "their turn may be refused
    with 4090". It does not say whether his typed text is kept, shown back to him, or lost. The
    O18 question Alex is asked should include that cost.
  - The sender's receipt in this case is the ordinary `started` sentence, "… was idle. Message
    3f2a9c started a turn there". A sender (or Alex, reading the tool row) who knows the session is
    open in a terminal will read "there" as the terminal.
- **Fix:**
  - In F13 and the O18 row, state what the terminal does with the refused input. If that is not
    known, add it to "Still to check", for example: "after an F13 wake, the terminal's next typed
    turn: is the text kept, and what does the person see?"
  - Make the wake-path receipt name the dashboard, for example: `… was not open anywhere that could
    take it, so message 3f2a9c started a turn in the dashboard.`

  This adds wording only, not a hold or a gate.

### R7-2. sm-18 no longer checks the hard-interrupt receipt sentence

- **Where:** sm-18, first Done-when.
- **What happens:** round 6 added a check that the `interrupted` receipt says "redirected … runs
  now" or "stopped … runs as that session's next turn". The rewritten line drops it, but
  `ux.md:209-210` still has both sentences, and the fallback still exists for media payloads and
  older agents.
- **Fix:** add back "Receipt: `interrupted`, with the redirect or the hard-interrupt sentence from
  `ux.md` § Receipts."

Verdict: meets requirements
Reviewed: d0034fd93ec04c9e8e59c84cc904cd1303e6a0030226bcfb200e4a25315d6194
