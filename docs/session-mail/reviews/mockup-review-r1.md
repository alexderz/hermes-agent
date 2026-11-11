# Mockup review, round 1: session-mail (DER-701), Spec step

Reviewer: UX reviewer (designer role, review loop only). Date: 2026-11-10.

Under review, at commit `643185083e`:
- `docs/session-mail/mockups/README.md`;
- `variant-a-not-alex-first.html`;
- `variant-b-sender-first.html`;
- `variant-c-two-line-card.html`.

Requirements:
- `ux.md` as accepted by Alex on 2026-11-10 (unchanged since `d0034fd9`);
- the brief;
- `lld.md` (`49d7be2e20`);
- the stated taste: Alex sees at a glance that a row is not him, from which session, and whether a
  reply is expected; status colour always with a label; the existing look on each surface.

**How I checked:**
- **Rendering.** All three files were rendered with headless Chromium, at 1400 px, page by page.
  Every section was checked: phone, desktop, dashboard / Ink TUI, classic CLI, Telegram, states
  and the story map.
- **Wording.** The visible text was extracted and compared against `ux.md` (the authority line,
  interrupt line, footer lines, tool-describe clause, closing line and receipt sentences), and the
  three files were diffed against each other.
- **CLI previews.** These were recomputed with the CLI's rule `text[:80] + "..."`.

## What holds

- **Wording is exact.** Every fixed string in the mockups matches `ux.md` word for word:
  - the authority line, the interrupt line and every footer line;
  - the closing line;
  - the steer and redirect receipts, and the refused and wake receipts (instances of `ux.md`'s
    templates).

  The three files differ **only** in header line 1 and in the notes that describe it.
- **The CLI previews are exact:**
  - A: `📡 Not Alex · reply expected · hermes@Hermes Improvement — Orchestrator says (ses...`;
  - A, interrupt: `… Orchestrat...`;
  - B: `… (session 20261109_071203_a1b2, not Al...`.

  So the README is right that B cuts off "not Alex" and never shows the reply label.
- **Glance requirement and existing look.**
  - On the phone, every message is a user bubble in Alex's colour (SM-Q11). In A its first wrapped
    line is `📡 Not Alex · reply expected ·`, as the render confirms.
  - The desktop never opens with `Message from`.
  - The dashboard and Ink TUI show no steer wrapper.
  - The classic CLI uses its existing notices.
  - No new screen is drawn.
- **States.** The error state (refused, with candidates), the loading state (waking, `running…`
  then `started`), the O17 double bubble and the empty state are all drawn or stated. Every
  status chip carries a word.
- **The variants are as different as the requirements allow.** The accepted `ux.md` fixes the
  look of every surface and every line except the header's order. So header line 1 (its order, and
  one line or two) is the only free axis, and the README says so plainly. On that axis the three
  are really different: they lead with different words, and they imply different reply-matcher
  anchors.
- **The README's comparison matches the renders:**
  - phone first lines: A `📡 Not Alex · reply expected ·`; B `📡 hermes@Hermes Improvement —`,
    with "not Alex" on line 3; C `📡 Not Alex · hermes@Hermes`;
  - the CLI notices;
  - the two-line matcher that C would need.

  The recommendation of **A** follows from the written requirement (UX review round 1, finding 8),
  and A is what `ux.md` specifies.

## Findings

### M-1. The LLD changes the interrupt header, but the mockups and README don't show or resolve it (blocking)

- **Where:**
  - `lld.md` B4, host step 3, and B6: "header line 1 carries `interrupt ·` when the **requested**
    mode is `interrupt`". Line 3 becomes conditional ("If your previous work in this session was
    stopped for this message, …"), offered as "a small wording delta from `ux.md` … for the
    designer to accept".
  - README "Notes for the builder": "No contradiction with `ux.md` was found".
  - Every file: the interrupt bubble uses `ux.md`'s unconditional line 3, and no fallback state is
    drawn.
- **Requirement broken:**
  - Accepted `ux.md` J9: "The header carries no "interrupt" label, because nothing was
    interrupted".
  - sm-18: "the header has no `interrupt` label" on a fallback.
  - Alex's need to "know when a message interrupted work".
  - Under the LLD, a message sent with `interrupt` that the host could only **steer** (for example
    while compacting) would still open `📡 Not Alex · interrupt · …`. That tells Alex, and the
    model, that work was stopped when it was not.
- **Fix:** the designer has to answer the LLD's request in writing at this step, and the mockups
  have to show the answer.
  - **Reject the delta.** The host would then build the frame after the seam returns the applied
    mode, or the seam returns it before the text is committed. That is an LLD change for the
    architect.
  - **Or accept it with truthful words.** For example: line 1 `📡 Not Alex · interrupt asked ·
    reply expected · …`, line 3 as the LLD words it, and `ux.md` J9 and sm-18 updated to match.
    Since `ux.md` is accepted, this is a wording change that Alex should see.

  Either way, add the J9 fallback to "States": interrupt asked, steer applied, with the receipt
  `steered (asked: interrupt; …)` and the header as decided. Then correct the README's "No
  contradiction" note.

### M-2. The Telegram post is drawn as unconditional; the LLD now posts only to DMs or listed chats (minor)

- **Where:** the Telegram section in each file, and the README's "Surfaces" list ("only the
  header and the body are posted"). Compare `lld.md` TB-5: the gateway posts the echo only when the
  chat is a DM, or when its `chat_id` is in `plugins.entries.intercom.settings.echo_chats`;
  otherwise only the answer appears.
- **What happens:** "# Budgeting · topic" is a forum topic, so under the LLD it gets the post only
  if Alex lists it. The mockup gives no hint of that, and a topic that is not listed would show an
  answer "out of nowhere" (the SM-Q15 (a) look).
- **Fix:** add a one-line note to the Telegram section ("posted because this chat is listed in
  `echo_chats`; an unlisted group or topic shows only the answer"). Optionally, draw the unlisted
  case in "States".

### M-3. "Neutral colours only" is not true of the chips (minor)

- **Where:** the README ("Neutral greys only") and each file's exchange box ("Neutral colours
  only"). Compare the CSS (`.tag.ok` green, `.tag.warn` amber, `.tag.err` red tints): `started`,
  `steered`, `interrupted · redirect` and `refused · ambiguous` are tinted.
- **What happens:** the requirement itself is met, because every tinted chip carries its word. The
  claim about it is false.
- **Fix:** say "status chips are lightly tinted, and every chip is a word", or make them grey.

### M-4. Sample answer text models the confusion the design guards against (minor)

- **Where:** Budgeting's answer after the interrupt (every surface): "Stopped the import **as
  asked**. I will re-run it …".
- **Requirement:** a message must never read as Alex's instruction. The HLD names a model saying
  "as you asked" about mail as the trigger for reopening SM-Q7 C.
- **What happens:**
  - In Alex's own chat, "as asked" reads as if Alex asked. It was the peer who asked.
  - The answer also drops Alex's own request ("Now import November too.") without a word, though
    line 3 tells the model to decide whether to go back to it.
- **Fix:** model the intended behaviour. For example: "Hermes Improvement asked me to stop (message
  5b77e1): the March export changed column order. I stopped the import. Your November import is on
  hold until I re-run from the raw files with the new mapping." The `[REPLY 5b77e1]` block stays as
  it is.

### M-5. Exchange order and completeness (minor)

- **Where:** the exchange list (step 4 is "Later, …", yet it comes before step 5), and the sender's
  phone, which draws step 5 (silent) above step 4 (interrupt).
- **What happens:**
  - The numbers do not follow the timeline shown.
  - Budgeting's `[REPLY 5b77e1]` block is never shown arriving back in Hermes Improvement as a 📡
    bubble.
- **Fix:** swap the numbers of steps 4 and 5, or reorder the list. Either show the 5b77e1 reply
  arriving, or note that it arrives like step 3.

### M-6. README comparison: two accuracy points (minor)

- **C's CLI notice.** The README row says only that C's notice "spills onto a second terminal
  line". C's own file says that line "shows the reply label", so in C the CLI does carry "Not
  Alex" and the reply label, across two lines. The recommendation still holds, because C fails on
  the phone's first line, but the row should say so.
- **B and C reopen the accepted `ux.md`.** The README presents B and C as options but doesn't say
  plainly that choosing either would reopen the accepted `ux.md` (the header, F10, the
  `status` anchor, sm-05) and need Alex again. Add one sentence.

## Carried forward (not a mockup defect)

**UX review R7-1, the wake receipt.** The loading state shows `"Home" was idle. Message 7c1d02
started a turn there.`. That is exactly `ux.md`'s wording, so the mockup is correct. But for a
session that is live nowhere, the turn starts in the dashboard, and "there" is ambiguous. R7-1's
wording ("… started a turn in the dashboard") is still open in the accepted `ux.md`. It can be
taken in the same pass as M-1, if Alex sees `ux.md` again.

Verdict: changes needed
Reviewed: 642ac519cabdfa25fe2ad305f53dc9ad9bd86934ca9180b9d9d773365fdce47f
