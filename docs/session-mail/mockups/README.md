# Mockups — session-mail (DER-701): how a message looks on existing screens

LLD grain. Pictures for screens people will see. **designer.**
Human gate: operator accepts, or writes `UX verification not required`.

- Slug: `session-mail`
- UX / stories: [`../ux.md`](../ux.md), [`../stories/`](../stories/) (Plan and UX accepted by Alex on 2026-11-10, with all recommended answers)
- LLD: [`../lld.md`](../lld.md) (round 2, `a37eb15b88`: security review round 1 and mockup review M-1 folded in)
- Date: `2026-11-10` (round 2: aligned with LLD round 2; mockup review round 1, M-1 to M-6, fixed)
- Operator: pending

## Required

- **Medium:** one self-contained HTML file per variant, with no external assets, scripts or images. Open it in any browser. The palette is neutral greys. Status chips are lightly tinted, and every chip is a word (`steered`, `steered · asked: interrupt`, `interrupted · redirect`, `silent`, `refused · ambiguous`), so colour is never the only signal.
- **Variants:** three, which differ only in **header line 1**: its information order and whether it is one line or two. Everything else is the same in all three:
  - from the LLD's final shape (B6): `interrupt asked ·` appears only when interrupt was requested, and line 3 is conditional;
  - from `ux.md`: the authority line, the footer, the closing line `📡 End of message <id>`, and the relabelling of body lines.

  | Variant | File | Header line 1 for the example mail |
  |---|---|---|
  | **A — "Not Alex" first** (`ux.md`'s order and the LLD's final shape) | [`variant-a-not-alex-first.html`](variant-a-not-alex-first.html) | `📡 Not Alex · reply expected · hermes@Hermes Improvement — Orchestrator says (session 20261109_071203_a1b2 · message 3f2a9c):` |
  | **B — sender first** (intercom's own order) | [`variant-b-sender-first.html`](variant-b-sender-first.html) | `📡 hermes@Hermes Improvement — Orchestrator (session 20261109_071203_a1b2, not Alex) says · reply expected · message 3f2a9c:` |
  | **C — two-line card** | [`variant-c-two-line-card.html`](variant-c-two-line-card.html) | `📡 Not Alex · hermes@Hermes Improvement — Orchestrator says:` then `reply expected · message 3f2a9c · session 20261109_071203_a1b2` |

  **B and C reopen the accepted `ux.md`.** Choosing either changes header line 1 in `ux.md` (§ "Header", F10, the `status` transcript anchor) and sm-05, so Alex would have to accept the UX again. A needs no change to `ux.md`'s order. M-1's wording change, below, applies to all three.
- **Surfaces** (each file shows all of them, in this order):
  - Hermes Mobile: the target chat and the sender chat side by side;
  - the desktop app;
  - the web dashboard chat and the Ink TUI (one renderer);
  - the classic CLI, with Budgeting open in `hermes chat`;
  - a Telegram topic, drawn as listed in `echo_chats`, with the unlisted case in "States";
  - states.
- **The exchange shown everywhere**, with the real wording from `ux.md` and the LLD:
  1. "Hermes Improvement — Orchestrator" steers mail 3f2a9c into Alex's running turn with "Budgeting — Orchestrator".
  2. Budgeting's answer to Alex carries a `[REPLY 3f2a9c]` block.
  3. The block arrives back in Hermes Improvement as mail 8e41b0, labelled "reply optional".
  4. Hermes Improvement's answer ends `[REPLY 8e41b0][SILENT][/REPLY]`, so nothing is sent.
  5. Later, Hermes Improvement sends with `delivery="interrupt"` (5b77e1):
     - the header says `interrupt asked`;
     - the receipt says `interrupted` (redirect);
     - Budgeting's answer names who asked, and tells Alex his November import is on hold;
     - its `[REPLY 5b77e1]` block arrives back as mail c41d77.
- **Files or links:** the three HTML files above, in git.
- **Map to stories:**

  | Picture | Stories |
  |---|---|
  | Mobile steps 1 and 5, and the sender's tool rows | sm-01, sm-04, sm-05, sm-08, sm-17, sm-18 |
  | Mobile steps 2–4, and the c41d77 reply | sm-06, sm-07 |
  | Desktop, dashboard chat and Ink TUI | sm-09, sm-19 |
  | Classic CLI | sm-18, sm-19 |
  | Telegram | sm-20 |
  | States | sm-03, sm-04 (waking), sm-15, sm-18 (fallback), sm-20 (unlisted chat), O17 |

  Each file also has this table.
- **Empty / error / loading:**
  - *Empty:* there is no new screen, so nothing changes when there is no mail.
  - *Error:* the sender's tool row for a `refused` (ambiguous) address, listing the candidates.
  - *Loading:* the sender's tool row while a session that is live nowhere is woken (`running…`, then `started`).
  - *Fallback (J9):* interrupt asked, steer applied, because the target is compacting. The receipt is `steered · asked: interrupt` and ends "You asked for interrupt; this session could not take it now, so steer was used." The header still says `interrupt asked`, and the conditional line 3 is true either way.
  - *Telegram, unlisted chat:* a group or topic that is not in `echo_chats` is shared. Nothing is posted there, so only the answer appears.
  - *Known bug:* until the O17 fix, a queued mail shows twice (two identical bubbles, one reply).
- **Agent review:** round 1 (`../reviews/mockup-review-r1.md`, changes needed) fixed here; round 2 pending.

## Comparison

What each header order does on the surfaces where it matters most.

| Check | A — "Not Alex" first | B — sender first | C — two-line card |
|---|---|---|---|
| **Phone, first wrapped line** (about 34 characters at 340 px) | `📡 Not Alex · reply expected ·`, or `📡 Not Alex · interrupt asked ·` for an interrupt: the glance words, for any title | `📡 hermes@Hermes Improvement —`: "not Alex" and the reply label come 3–4 lines later, after the session id | `📡 Not Alex · hermes@Hermes`: "Not Alex" yes; the reply label is on the card's second line, after the title wraps |
| **Classic CLI's 80-character notice** (`⏩ Steered: '…'`, `↪ Redirected current turn: '…'`) | `📡 Not Alex · reply expected · hermes@Hermes Improvement — Orchestrator says (ses...`: complete glance words on one line | `📡 hermes@Hermes Improvement — Orchestrator (session 20261109_071203_a1b2, not Al...`: **"not Alex" is cut off**, and the reply label never shows | `📡 Not Alex · hermes@Hermes Improvement — Orchestrator says:` then, on a **second terminal line**, `reply expected · mes...`: "Not Alex" and the reply label both show, but across two lines, because the preview holds the header's line break |
| **Telegram post** (listed chats only) | One line, glance words first | One line; "not Alex" buried in brackets | Two lines; the clearest card to read in a chat |
| **Model reading it** | Clear | Clear (intercom's familiar order) | Clear |
| **Reply matcher and `status` anchor** (LLD B6/D3) | One line: starts `📡 Not Alex · `, ends `· message <id>):`. This is the LLD's final shape | One line: starts `📡 hermes@` | **Two lines**: the id is on the line after the anchor, so the matcher and the `status` check must read two lines |
| **Closeness to intercom upstream** | Keeps `hermes@<title> says`, after the glance words | Closest | Keeps `hermes@<title> says`, then a new second line |
| **"interrupt asked"** (48 characters with the reply label) | `📡 Not Alex · interrupt asked · reply expected ·`: one or two phone lines, before the title | `… says · interrupt asked · reply expected · message 5b77e1:`, at the end of a long line | On the second card line, after the title |
| **Changes the accepted `ux.md`?** | No (only M-1's wording, which applies to all three) | Yes: header order, F10, `status` anchor, sm-05 | Yes: as B, plus a two-line matcher |

## Recommendation: A

A is the only shape whose first phone line and whose classic-CLI notice both carry "Not Alex" and the reply label, on one line, whatever the sender's title. That is the at-a-glance requirement (UX review round 1, finding 8).

- B loses "not Alex" from the CLI notice for an ordinary title such as "Hermes Improvement — Orchestrator".
- C does show both in the CLI, but across two terminal lines. It loses the reply label from the phone's first line, and makes reply matching read two lines.

A is also `ux.md`'s order and the LLD's final shape (B6), so choosing it reopens nothing beyond M-1's wording change.

## M-1: the interrupt wording changes, for Alex to see

The frame is built before the host reports which mode it applied (LLD, "Final header shape"). So the header can only say what was **asked**. The designer accepts the LLD's wording, and the mockups show it:

- line 1: `📡 Not Alex · interrupt asked · <reply label> · …`, only when the sender asked for interrupt;
- line 3: "The sender asked to interrupt. If your previous work in this session was stopped for this message, decide yourself whether to go back to it.";
- what was **applied** is stated only in the receipt, the record and the CLI (`interrupted · redirect`, or `steered (asked: interrupt; …)`).

This is truthful in both cases: a redirect (step 5) and the J9 fallback (States).

It contradicts these accepted lines, which the manager should change when Alex sees the mockups. They are listed here, not edited:

| Where | Today | Becomes |
|---|---|---|
| `ux.md` J8 step 4 | "its first line: `📡 Not Alex · interrupt · reply expected · …`, followed by a line telling it that its previous work was stopped" | `📡 Not Alex · interrupt asked · reply expected · …`, then the conditional line 3 |
| `ux.md` J9 | "The header carries no "interrupt" label, because nothing was interrupted." | "The header still says `interrupt asked` (what was requested), and its line 3 is conditional, so it stays true. The receipt says what was applied." |
| `ux.md` § "Header", the interrupt example | heading "only when the applied mode is interrupt"; line 1 `… · interrupt · …`; line 3 "The sender asked to interrupt: your previous work in this session was stopped for this message. Decide yourself whether to go back to it." | "only when the sender asked for interrupt"; `… · interrupt asked · …`; the LLD's conditional line 3 |
| `ux.md` § "Header", glance bullet, and § "Accessibility" | "30–42 characters; 50 for an `ask` sent with interrupt" | "30–48 characters; 56 for an `ask` sent with interrupt, which on a narrow phone may wrap after "interrupt asked ·"" |
| `ux.md` § "Hermes Mobile" | "its first line says "interrupt"" | "its first line says "interrupt asked"" |
| `ux.md` § "Terminal sessions", the `interrupted` row | `'📡 Not Alex · interrupt · reply expected · …'` | `'📡 Not Alex · interrupt asked · reply expected · …'` |
| sm-05 | "Line 1 says `interrupt` and line 3 is present only when the applied mode was interrupt." | "Line 1 says `interrupt asked` and line 3 (conditional) is present only when the sender asked for interrupt." |
| sm-08 | "first line reads `📡 Not Alex · interrupt · …`" | "first line reads `📡 Not Alex · interrupt asked · …`" |
| sm-18 | "line 1 says `interrupt`, and line 3 tells the target its previous work was stopped…"; on a fallback "the header has no `interrupt` label" | "line 1 says `interrupt asked`, and line 3 says that if its previous work was stopped, it decides whether to go back to it"; on a fallback "the header still says `interrupt asked`, and the receipt says `asked: interrupt`" |

## Notes for the builder

- **The footer makes every mail long on the phone.** The footer is about 10 lines and Alex sees all of it, because the app shows plain text. The mockups show it in full on purpose. It is the accepted design (the footer is how the model learns the reply rules; SM-Q11 accepted the phone look), but it is the first thing Alex will notice. A Hermes Mobile change that folds everything after the header is the natural follow-up. It is out of scope for this chunk.
- **Telegram (LLD TB-5).** The echo is posted only to a private chat: a DM from an owner, or a chat whose id is in `plugins.entries.intercom.settings.echo_chats`. It is header line 1 and the body, as plain text with mentions suppressed. Shared chats still get the mail, plus a model-only shared-chat line. A reply to a shared-chat sender carries only an explicit `[REPLY]` block. The mockups draw the shared case's visible part, "only the answer".
- **Budgeting's answer after the interrupt** shows the intended behaviour (mockup review M-4). It says who asked ("Hermes Improvement asked me to stop (message 5b77e1)"), never "as asked", and it tells Alex what happened to his own request ("Your November import is on hold…").
- **The 📡 emoji** shows as a box in the headless browser used for the check screenshots, which has no emoji font. Phones, desktops, terminals and Telegram render it. Nothing depends on it, because every meaning is in words.
- **Row chrome is approximate** for the dashboard chat, the Ink TUI and the classic CLI (gutters, tool-row glyphs). **The text is exact**, and so are the CLI notices and their 80-character previews, which come from the CLI's own rule (`text[:80] + "..."`).
- **The Telegram stopped answer** after an interrupt is drawn as a note only. What the topic shows for it is checked when the echo is built (`ux.md`, "Still to check").
- **Carried forward, not changed here:** UX review R7-1. The wake receipt reads `"Home" was idle. Message 7c1d02 started a turn there.`, which is exactly `ux.md`'s wording. "there" means the dashboard for a session that is live nowhere. If Alex sees `ux.md` again for M-1, "… started a turn in the dashboard" can be taken in the same pass.
