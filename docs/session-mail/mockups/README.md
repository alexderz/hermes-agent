# Mockups — session-mail (DER-701): how a message looks on existing screens

LLD grain. Pictures for screens people will see. **designer.**
Human gate: operator accepts, or writes `UX verification not required`.

- Slug: `session-mail`
- UX / stories: [`../ux.md`](../ux.md), [`../stories/`](../stories/) (Plan and UX accepted by Alex on 2026-11-10, with all recommended answers)
- LLD: `docs/session-mail/lld.md` (Spec, in progress)
- Date: `2026-11-10`
- Operator: pending

## Required

- **Medium:** one self-contained HTML file per variant, with no external assets, scripts or images. Open it in any browser. Neutral greys only, and every status chip is a word (`steered`, `interrupted · redirect`, `silent`, `refused · ambiguous`).
- **Variants:** three, which differ only in **header line 1**: its information order and whether it is one line or two. Everything `ux.md` fixes is the same in all three: the authority line, the interrupt line, the footer, the closing line `📡 End of message <id>`, and the relabelling of body lines that start with 📡.

  | Variant | File | Header line 1 for the example mail |
  |---|---|---|
  | **A — "Not Alex" first** (as in `ux.md` today) | [`variant-a-not-alex-first.html`](variant-a-not-alex-first.html) | `📡 Not Alex · reply expected · hermes@Hermes Improvement — Orchestrator says (session 20261109_071203_a1b2 · message 3f2a9c):` |
  | **B — sender first** (intercom's order; the HLD's D2 example) | [`variant-b-sender-first.html`](variant-b-sender-first.html) | `📡 hermes@Hermes Improvement — Orchestrator (session 20261109_071203_a1b2, not Alex) says · reply expected · message 3f2a9c:` |
  | **C — two-line card** | [`variant-c-two-line-card.html`](variant-c-two-line-card.html) | `📡 Not Alex · hermes@Hermes Improvement — Orchestrator says:` then `reply expected · message 3f2a9c · session 20261109_071203_a1b2` |

- **Surfaces** (each file shows all of them, in this order):
  - Hermes Mobile: the target chat and the sender chat side by side;
  - the desktop app;
  - the web dashboard chat and the Ink TUI (one renderer);
  - the classic CLI, with Budgeting open in `hermes chat`;
  - a Telegram topic (SM-Q15 b: only the header and the body are posted);
  - states.
- **The exchange shown everywhere**, with the real wording from `ux.md`:
  1. "Hermes Improvement — Orchestrator" steers mail 3f2a9c into Alex's running turn with "Budgeting — Orchestrator".
  2. Budgeting's answer carries a `[REPLY 3f2a9c]` block.
  3. The block arrives back as mail 8e41b0, labelled "reply optional".
  4. A later `delivery="interrupt"` mail (5b77e1) gets the receipt `interrupted` (redirect).
  5. Hermes Improvement ends with `[REPLY 8e41b0][SILENT][/REPLY]`, so nothing is sent.
- **Files or links:** the three HTML files above, in git.
- **Map to stories:**

  | Picture | Stories |
  |---|---|
  | Mobile steps 1 and 4, and the sender's tool rows | sm-01, sm-04, sm-05, sm-08, sm-17, sm-18 |
  | Mobile steps 2, 3 and 5 | sm-06, sm-07 |
  | Desktop, dashboard chat and Ink TUI | sm-09, sm-19 |
  | Classic CLI | sm-18, sm-19 |
  | Telegram | sm-20 |
  | States | sm-03, sm-04 (waking), sm-15, O17 |

  Each file also has this table.
- **Empty / error / loading:**
  - *Empty:* there is no new screen, so nothing changes when there is no mail.
  - *Error:* the sender's tool row for a `refused` (ambiguous) address, listing the candidates.
  - *Loading:* the sender's tool row while a session that is live nowhere is woken (`running…`, then `started`).
  - *Known bug:* until the O17 fix, a queued mail shows twice on the phone (two identical bubbles, one reply).
- **Agent review:** pending (requirements only).

## Comparison

What each header order does on the surfaces where it matters most.

| Check | A — "Not Alex" first | B — sender first | C — two-line card |
|---|---|---|---|
| **Phone, first wrapped line** (about 34 characters at 340 px) | `📡 Not Alex · reply expected ·`: both glance words, for any title | `📡 hermes@Hermes Improvement —`: "not Alex" and the reply label come 3–4 lines later, after the session id | `📡 Not Alex · hermes@Hermes`: "Not Alex" yes; the reply label is on the card's second line, after the title wraps |
| **Classic CLI's 80-character notice** (`⏩ Steered: '…'`, `↪ Redirected current turn: '…'`) | `📡 Not Alex · reply expected · hermes@Hermes Improvement — Orchestrator says (ses...`: complete glance words | `📡 hermes@Hermes Improvement — Orchestrator (session 20261109_071203_a1b2, not Al...`: **"not Alex" is cut off**, and the reply label never shows | The preview holds the header's line break, so the notice spills onto a second terminal line |
| **Telegram post** | One line, glance words first | One line; "not Alex" buried in brackets | Two lines; the clearest card to read in a chat |
| **Model reading it** | Clear | Clear (intercom's familiar order) | Clear |
| **Reply matcher (HLD D3)** | One line: starts `📡 Not Alex · `, ends `· message <id>):` | One line: starts `📡 hermes@`, ends `· message <id>:` (the HLD's current anchor) | **Two lines**: the id is on the line after the anchor, so the matcher and the `status` transcript check must read two lines |
| **Closeness to intercom upstream** | Keeps `hermes@<title> says`, after the glance words | Closest | Keeps `hermes@<title> says`, then a new second line |
| **Interrupt label** | `📡 Not Alex · interrupt · reply expected ·` stays on the first line or two | `… says · interrupt · reply expected · message 5b77e1:` sits at the end of a long line | It goes on the second line, `interrupt · reply expected · …`, after the title |

## Recommendation: A

A is the only shape whose first phone line and whose classic-CLI notice both carry "Not Alex" and the reply label, whatever the sender's title. That is the at-a-glance requirement (UX review round 1, finding 8). B loses "not Alex" from the CLI's 80-character notice for an ordinary title such as "Hermes Improvement — Orchestrator". C reads well as a card, but it pushes the reply label off the first line, breaks the CLI notice across two lines, and makes reply matching read two lines. A is also what `ux.md` already specifies, so choosing it changes nothing in the accepted UX. It needs only the HLD alignment already listed as item 1 under `ux.md` § "For the architect" (the D2 example and the D3 anchor).

## Notes for the builder

- **The footer makes every mail long on the phone.** The footer is about 10 lines and Alex sees all of it, because the app shows plain text. The mockups show it in full on purpose. It is the accepted design (the footer is how the model learns the reply rules; SM-Q11 accepted the phone look), but it is the first thing Alex will notice. A Hermes Mobile change that folds everything after the header is the natural follow-up. It is out of scope for this chunk.
- **The 📡 emoji** shows as a box in the headless browser used for the check screenshots, which has no emoji font. Phones, desktops, terminals and Telegram render it. Nothing depends on it, because every meaning is in words.
- **Row chrome is approximate** for the dashboard chat, the Ink TUI and the classic CLI (gutters, tool-row glyphs). **The text is exact**, and so are the CLI notices and their 80-character previews, which come from the CLI's own rule (`text[:80] + "..."`).
- **The Telegram stopped answer** after an interrupt is drawn as a note only. What the topic shows for it is checked when the SM-Q15 post is built (`ux.md`, "Still to check").
- **No contradiction with `ux.md`** was found, so `ux.md` is unchanged. One small wording point: at 340 px, A's first wrapped line ends at "reply expected ·", and `hermes@` starts line 2. `ux.md` § "Hermes Mobile" says the first wrapped line is `📡 Not Alex · reply expected · hermes@…`. The glance words it promises are all on line 1, so the claim holds.
