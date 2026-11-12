# Mockup review, round 2: session-mail (DER-701), Spec step

Reviewer: UX reviewer (designer role, review loop only). Date: 2026-11-10.

Under review: `git diff 643185083e b2eea4af9b -- docs/session-mail/mockups`. The working tree has
no changes to these files.

Requirements:
- `ux.md` as accepted on 2026-11-10 (`d0034fd9`, unchanged);
- the brief;
- **LLD round 2** (`a37eb15b88`, as in `b2eea4af9b`) and the HLD at that commit;
- the stated taste: Alex sees at a glance that a row is not him, from which session, and whether a
  reply is expected; status colour always with a label; the existing look on each surface.

**How I checked:** I re-rendered the changed sections of variant A with headless Chromium (phone
steps 4 and 5, the c41d77 reply, the desktop, the states and Telegram). I extracted the visible
text of all three files and searched it for each fixed and new string. I checked the README and
the files against the LLD's "Final header shape", B6 (framing), TB-5 and B1.3 (the chat rule), and
its O17 note.

## Round-1 findings

| # | Round-1 finding | Status |
|---|---|---|
| M-1 | The LLD's interrupt-header change was not shown or resolved | **Fixed in substance.** The designer accepts the LLD's wording and makes it truthful: `interrupt asked ·` appears only when interrupt was requested, and line 3 is conditional. This matches LLD "Final header shape" and B6 word for word. All three files use it (12–13 occurrences each). The applied mode is stated only in the receipt, the record and the CLI. The README lists every accepted `ux.md` and story line it changes, for the manager to show Alex. A fallback state is drawn, but its reason is wrong: see N-2. |
| M-2 | The Telegram post was drawn as unconditional | **Fixed**, apart from the config path (N-3). The topic is now drawn as listed, and "States" has an unlisted shared topic where only the answer appears. |
| M-3 | "Neutral colours only" was not true | **Fixed.** The text now says "lightly tinted, and every chip is a word". The old claim is gone from all files. |
| M-4 | The sample answer said "as asked" | **Fixed.** It now reads "Hermes Improvement asked me to stop (message 5b77e1): … Your November import is on hold …", the same on every surface. The only remaining "as asked" match is inside "what was asked" in an explanatory note. |
| M-5 | Exchange order and completeness | **Fixed.** Steps are renumbered (silent is 4, interrupt is 5), and the c41d77 reply is drawn arriving on the sender's phone. |
| M-6 | README comparison accuracy | **Fixed.** C's CLI row now says both glance words show, across two lines. A new row and a bold paragraph say that B and C reopen the accepted `ux.md`. |

Unchanged and still correct: the fixed wording matches `ux.md` word for word, the three files
differ only in header line 1, the CLI 80-character previews are exact, and the recommendation of
**A** stands.

## New findings

### N-1. The O17 double bubble is still drawn, but LLD round 2 retracts O17 (blocking)

- **Where:**
  - the README: "*Known bug:* until the O17 fix, a queued mail shows twice", and O17 in the
    story map;
  - every file's "States": "Known bug until the O17 fix: a queued mail shows twice", drawn as two
    identical bubbles.
- **Requirement broken:**
  - The mockups must match the LLD they claim to follow (the README says "aligned with LLD round
    2").
  - LLD round 2, opening note: "O17 is retracted and has **no fix item** … a queued message shows
    **once** … `ux.md` § "Hermes Mobile" / "Web dashboard" needs the designer to drop the "shows
    twice until the O17 fix" lines".
  - HLD O17: "**Retracted** … a queued message shows once".
  - As drawn, the mockups show Alex a bug that does not exist, and invite a fix nobody will make.
- **Fix:**
  - Remove the O17 state and its README line.
  - Change the story-map cell to drop O17.
  - Add the `ux.md` lines the LLD asks to drop to the README's "for Alex" table: J5's "appears
    **twice**" sentence, § "Hermes Mobile" "Until the O17 fix …", § "Web dashboard and desktop app"
    "Until the O17 fix …", the sm-08 and sm-09 Done-when lines, and the HLD O17 row in "Open
    questions".

### N-2. The J9 fallback state shows the wrong applied mode for a compacting target

- **Where:** "States", "Fallback (J9): interrupt asked, steer applied (target compacting)", and
  the README's matching bullet ("steer applied, because the target is compacting"). The receipt
  reads `steered · asked: interrupt`, and the note says "the turn keeps going, the mail sits
  mid-turn".
- **Requirement broken:**
  - `ux.md` J9: compacting "demotes interrupt **and steer** to queue on the dashboard, desktop and
    Ink TUI".
  - HLD D1 / LLD, `tui_gateway` row: "Compression keeps demoting to queue, reported as applied
    `queue`".
  - So a compacting target gives `queued (asked: interrupt; …)`, not `steered`. In practice no
    host takes interrupt down to steer for compaction. Steer appears only for a classic CLI on a
    build without the seam, which J9 names as the second case.
- **Fix:** do one of these, and make the README bullet match.
  - Keep "target compacting" and draw the queue fallback: chip `queued · asked: interrupt`;
    receipt `"Budgeting — Orchestrator" is busy. Message 5b77e1 is queued and runs after its
    current turn. … You asked for interrupt; this session could not take it now, so queue was
    used.`; the message shown as the next turn.
  - Or keep `steered · asked: interrupt` and change the reason to "a classic CLI on a Hermes
    build without the seam".

  Either one still shows the conditional line 3 being true.

### N-3. The `echo_chats` config path does not match the LLD (minor)

- **Where:** the README's Telegram note ("a chat whose id is in
  `plugins.entries.intercom.settings.echo_chats`"), and the same text in each file's Telegram
  note.
- **Requirement:** LLD round 2, configuration: `plugins.entries.intercom.echo_chats` and
  `owner_user_ids` "sit at the entry level, next to `allow_gateway_injection`", not under
  `settings`. A DM counts as private only when the user is in `owner_user_ids`.
- **Fix:** write `plugins.entries.intercom.echo_chats`, and "an owner DM (a user listed in
  `owner_user_ids`)". House-infra will copy this path.

### N-4. The README's list of `ux.md` changes for Alex covers only M-1 (minor, before the operator gate)

- **Where:** the README, § "M-1: the interrupt wording changes, for Alex to see".
- **What happens:** LLD round 2 also changes text that Alex or a session reads, and that the
  accepted `ux.md` states differently. None of it is in the table:
  - **The messaging-platform sender label.** It is now `hermes@<title> (Telegram group)` or
    `(Telegram DM)`; `ux.md` and sm-20 say `(Telegram)`.
  - **A third authority-line variant** for messaging-platform senders ("… may be relaying their
    words …").
  - **The model-only shared-chat line** for targets in shared chats.
  - **The reply rule for shared-chat senders.** Only an explicit `[REPLY]` block is sent, and
    `status` / `log` show `stored (shared chat, no [REPLY] block)`.
  - **The Telegram echo is conditional** (TB-5), where `ux.md` § "Messaging-gateway sessions" and
    sm-20 say it is posted before every turn.
  - **The O17 lines** (N-1).
- **Fix:** widen the table to "all `ux.md` changes from LLD round 2", so Alex accepts one complete
  list instead of finding these later. R7-1's "started a turn in the dashboard" can go in the
  same table, as the README already suggests.

Verdict: changes needed
Reviewed: ae191f4dc3f7313d79554b034c63145a0f47dcdb37bba748b04fda46b59fc89c
