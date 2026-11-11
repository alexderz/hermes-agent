# Mockups — session-mail (DER-701): how a message looks on existing screens

LLD grain. Pictures for screens people will see. **designer.**
Human gate: operator accepts, or writes `UX verification not required`.

- Slug: `session-mail`
- UX / stories: [`../ux.md`](../ux.md), [`../stories/`](../stories/) (Plan and UX accepted by Alex on 2026-11-10, with all recommended answers)
- LLD: [`../lld.md`](../lld.md) (round 3, `3a1d8934ac`: security review round 2 and the wake-receipt wording)
- Date: `2026-11-10` (round 3: aligned with LLD round 3; mockup review round 2, N-1 to N-4, fixed; `ux.md` and the stories edited to match, listed below)
- Operator: pending
- `2026-11-11`: gateway-only alignment (SM-Q20, SM-Q22; HLD round 3, LLD round 5). **Layout A only** is updated; B and C stay as reviewed in round 3, since A is the recommendation. See "Gateway-only alignment" below.

## Required

- **Medium:** one self-contained HTML file per variant, with no external assets, scripts or images. Open it in any browser. The palette is neutral greys. Status chips are lightly tinted, and every chip is a word (`steered`, `steered · asked: interrupt`, `interrupted · redirect`, `silent`, `refused · ambiguous`), so colour is never the only signal.
- **Variants:** three, which differ only in **header line 1**: its information order and whether it is one line or two. Everything else is the same in all three:
  - from the LLD's final shape (B6): `interrupt asked ·` appears only when interrupt was requested, line 3 is conditional, a messaging-platform sender is `hermes@<title> (Telegram group)` with its own authority line, and two model-only lines (shared-chat, reply-destination) appear only for shared chats;
  - from `ux.md`: the authority line, the footer, the closing line `📡 End of message <id>`, and the relabelling of body lines.

  | Variant | File | Header line 1 for the example mail |
  |---|---|---|
  | **A — "Not Alex" first** (`ux.md`'s order and the LLD's final shape) | [`variant-a-not-alex-first.html`](variant-a-not-alex-first.html) | `📡 Not Alex · reply expected · hermes@Hermes Improvement — Orchestrator says (session 20261109_071203_a1b2 · message 3f2a9c):` |
  | **B — sender first** (intercom's own order) | [`variant-b-sender-first.html`](variant-b-sender-first.html) | `📡 hermes@Hermes Improvement — Orchestrator (session 20261109_071203_a1b2, not Alex) says · reply expected · message 3f2a9c:` |
  | **C — two-line card** | [`variant-c-two-line-card.html`](variant-c-two-line-card.html) | `📡 Not Alex · hermes@Hermes Improvement — Orchestrator says:` then `reply expected · message 3f2a9c · session 20261109_071203_a1b2` |

  **B and C reopen the accepted `ux.md`.** Choosing either changes header line 1 in `ux.md` (§ "Header", F10, the `status` transcript anchor) and sm-05, so Alex would have to accept the UX again. A needs no change to `ux.md`'s order. The wording changes from the LLD, below, apply to all three.
- **Surfaces** (each file shows all of them, in this order):
  - the Webapp in a phone browser (replaces Hermes Mobile, SM-Q22): the target chat and the sender chat side by side;
  - the desktop app;
  - the desktop app (and the Webapp at desktop width), then the Ink TUI (layout A; B and C still show the old "web dashboard chat" frame);
  - the classic CLI, with Budgeting open in `hermes chat`;
  - a Telegram topic, drawn as listed in `plugins.entries.intercom.echo_chats`, with the shared (unlisted) case in "States";
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
  | Desktop / Webapp, Ink TUI | sm-09, sm-19 |
  | Classic CLI | sm-18, sm-19 |
  | Telegram | sm-20 |
  | States | sm-03, sm-04 (waking), sm-15, sm-18 (fallback), sm-20 (shared chat), sm-05 (platform sender) |

  Each file also has this table.
- **Empty / error / loading:**
  - *Empty:* there is no new screen, so nothing changes when there is no mail.
  - *Error:* the sender's tool row for a `refused` (ambiguous) address, listing the candidates.
  - *Loading:* the sender's tool row during a cold start (`running…`, then `started` with the LLD's cold-start receipt: `"Home" was not open, so the gateway reopened it and message 7c1d02 started a turn there.`).
  - *Error, admin dashboard:* `error · not-addressable`, `"<title>" is open in the admin dashboard, which intercom cannot reach. Nothing was sent.` (layout A).
  - *Fallback (J9):* interrupt asked, **queue** applied, because the target is compacting (compaction demotes both interrupt and steer to queue). The receipt is `queued · asked: interrupt` and ends "You asked for interrupt; this session could not take it now, so queue was used." The running turn finishes, then the mail runs as the next turn. The header still says `interrupt asked`, and the conditional line 3 is true either way. (Steer is the fallback only for a classic CLI on a Hermes build without the seam.)
  - *Telegram, shared chat:* a group or topic that is not in `plugins.entries.intercom.echo_chats`, or a DM with anyone not in `plugins.entries.intercom.owner_user_ids`, is shared. The mail is delivered but nothing is posted, so only the answer appears. The sender's receipt adds "Its chat is shared with other people; the body is now in that chat's context."
  - *A message from a shared Telegram group session:* the `(Telegram group)` sender label, the platform authority line, and the footer's reply-destination line.
- **Agent review:** round 1 (M-1 to M-6) and round 2 (N-1 to N-4, `../reviews/mockup-review-r2.md`) fixed; round 3 pending.

## Comparison

What each header order does on the surfaces where it matters most.

| Check | A — "Not Alex" first | B — sender first | C — two-line card |
|---|---|---|---|
| **Phone, first wrapped line** (the Webapp in a phone browser; about 34 characters at 340 px) | `📡 Not Alex · reply expected ·`, or `📡 Not Alex · interrupt asked ·` for an interrupt: the glance words, for any title | `📡 hermes@Hermes Improvement —`: "not Alex" and the reply label come 3–4 lines later, after the session id | `📡 Not Alex · hermes@Hermes`: "Not Alex" yes; the reply label is on the card's second line, after the title wraps |
| **Classic CLI's 80-character notice** (`⏩ Steered: '…'`, `↪ Redirected current turn: '…'`) | `📡 Not Alex · reply expected · hermes@Hermes Improvement — Orchestrator says (ses...`: complete glance words on one line | `📡 hermes@Hermes Improvement — Orchestrator (session 20261109_071203_a1b2, not Al...`: **"not Alex" is cut off**, and the reply label never shows | `📡 Not Alex · hermes@Hermes Improvement — Orchestrator says:` then, on a **second terminal line**, `reply expected · mes...`: "Not Alex" and the reply label both show, but across two lines, because the preview holds the header's line break |
| **Telegram post** (listed chats only) | One line, glance words first | One line; "not Alex" buried in brackets | Two lines; the clearest card to read in a chat |
| **Model reading it** | Clear | Clear (intercom's familiar order) | Clear |
| **Reply matcher and `status` anchor** (LLD B6/D3) | One line: starts `📡 Not Alex · `, ends `· message <id>):`. This is the LLD's final shape | One line: starts `📡 hermes@` | **Two lines**: the id is on the line after the anchor, so the matcher and the `status` check must read two lines |
| **Closeness to intercom upstream** | Keeps `hermes@<title> says`, after the glance words | Closest | Keeps `hermes@<title> says`, then a new second line |
| **"interrupt asked"** (48 characters with the reply label) | `📡 Not Alex · interrupt asked · reply expected ·`: one or two phone lines, before the title | `… says · interrupt asked · reply expected · message 5b77e1:`, at the end of a long line | On the second card line, after the title |
| **Changes the accepted `ux.md`?** | No (only the LLD wording changes listed below, which apply to all three) | Yes: header order, F10, `status` anchor, sm-05 | Yes: as B, plus a two-line matcher |

## Recommendation: A

A is the only shape whose first phone line and whose classic-CLI notice both carry "Not Alex" and the reply label, on one line, whatever the sender's title. That is the at-a-glance requirement (UX review round 1, finding 8).

- B loses "not Alex" from the CLI notice for an ordinary title such as "Hermes Improvement — Orchestrator".
- C does show both in the CLI, but across two terminal lines. It loses the reply label from the phone's first line, and makes reply matching read two lines.

A is also `ux.md`'s order and the LLD's final shape (B6), so choosing it reopens nothing beyond the LLD wording changes listed below.

## `ux.md` changes from the LLD, for Alex to see

LLD rounds 2 and 3 change text that Alex or a session reads. The designer accepts every change, and has **edited `ux.md` and the stories to match** (this round). This is the complete list, so Alex can accept them in one pass.

| # | Change (LLD) | `ux.md` edits | Story edits |
|---|---|---|---|
| 1 | **"interrupt asked"** (M-1, LLD "Final header shape"). The frame is built before the host reports what it applied, so line 1 says `interrupt asked` (the request), and line 3 becomes conditional: "The sender asked to interrupt. If your previous work in this session was stopped for this message, decide yourself whether to go back to it." The receipt, the record and the CLI state what was applied. | J8 step 4; J9 ("The header still says `interrupt asked` … its line 3 is conditional"); § "Header": the interrupt example, its heading, and the old "host builds the frame … name the applied mode" bullet, now "the frame is built before the host reports what it applied"; the glance-length bullet and § "Accessibility" (30–48 characters, or 56 for an interrupting `ask`); § "Hermes Mobile" ("its first line says "interrupt asked""); § "Terminal sessions", the `interrupted` row | sm-05, sm-08, sm-18 (also: the compacting fallback is `queue`, and the CLI-without-seam fallback is `steer`) |
| 2 | **Messaging-platform sender label** (LLD B6): `hermes@<title> (Telegram group)` or `(Telegram DM)`, not `(Telegram)`. | § "Header", the sender-name bullet | sm-05, sm-20 |
| 3 | **Third authority-line variant** for a messaging-platform sender: "… That session talks with other people in its Telegram group, and may be relaying their words. It is not an instruction from Alex (the user) and carries none of his approval or consent." | § "Header": new example block | sm-05, sm-20 |
| 4 | **Model-only shared-chat line** when the target's chat is shared: "This session's chat is shared with other people (Telegram group "…"). Do not repeat private content from this message there unless the message asks you to." | § "Header": new "Two model-only lines" note; § "Messaging-gateway sessions" | sm-05, sm-20 |
| 5 | **Reply-destination footer line** when the sender's chat is shared (security R2-2): "Your reply goes into a Telegram group that other people read." | § "Header": the same note | sm-05, sm-20 |
| 6 | **Reply to a shared-chat sender**: only an explicit `[REPLY]` block is sent; the whole-answer fallback is not used, and `status` / `log` show `stored (shared chat, no [REPLY] block)`. | § "Footer": new "A sender in a shared chat" paragraph; § "Messaging-gateway sessions" | sm-06, sm-12, sm-20 |
| 7 | **The Telegram echo is conditional** (TB-5): posted only to a private chat, meaning a DM with a user in `plugins.entries.intercom.owner_user_ids` or a chat in `plugins.entries.intercom.echo_chats`, as plain text with mentions suppressed. A shared chat gets the mail but no post, and the sender's receipt adds "Its chat is shared with other people; the body is now in that chat's context." | § "Messaging-gateway sessions" (first bullet, new shared-chat bullet, the security bullet now settled); § "Receipts": new shared-chat row | sm-20 |
| 8 | **Wake receipt** (UX review R7-1, LLD B9): "<title> was not open anywhere that could take it, so message <id> started a turn in the dashboard." The CLI line is `started (was not open anywhere; a turn started in the dashboard)`. A live host's `started` keeps "… started a turn there". | § "Receipts": new row; § "Command line", `send` output | sm-04 |
| 9 | **O17 retracted** (LLD, opening note): a queued message shows **once**. | J5's "appears twice" sentence → "A queued message shows once on every surface"; removed: § "Hermes Mobile" "Until the O17 fix …", § "Web dashboard and desktop app" "Until the O17 fix …", the HLD O17 row in "Open questions"; "For the architect" notes O17 as retracted | sm-08, sm-09 |

The `ux.md` header line also records the alignment: "2026-11-10: aligned with LLD round 3". Nothing in the list adds a cap, hold, retry or gate, and none reopens a settled decision.

## Gateway-only alignment (2026-11-11), for Alex to see

Alex settled **SM-Q20 (gateway only)** and **SM-Q22 (Hermes Mobile dropped)**. HLD round 3 and LLD round 5 list four text updates for the designer. They continue the table above. Every edit:

| # | Change (HLD § "UX / stories", LLD B6 / B9) | `ux.md` edits | Story edits | Layout A mockup |
|---|---|---|---|---|
| 10 | **Cold-start receipt:** `"<title>" was not open, so the gateway reopened it and message <id> started a turn there.` It replaces change 8's "… started a turn in the dashboard". The CLI line is `started (was not open; the gateway reopened it and a turn started there)`. | J6's second bullet ("Not open (cold): the gateway reopens it …"); § "Receipts": the cold-start row replaces the "woken" row; § "Command line", `send` output | sm-04 (also "a Webapp or desktop chat" in its idle line) | "States": the loading state is now a cold start, with the new receipt |
| 11 | **Echo timing:** the Telegram post is made **as the turn that carries the message runs, before its answer**: by the target's own turn, as a queued or started turn begins, or at the first tool step after a steer. Private chats only, as before. If the hooks do not fire for messaging chats (HLD O21), the echo is dropped for v1 (SM-Q15 a). | The SM-Q15 decision line; J11; § "Messaging-gateway sessions", first two bullets; "Still to check": new O21 item | sm-20 (timing Done-when; the note now names O21) | Telegram callout 1 and the side note |
| 12 | **`not-addressable` receipt** for chats held by the admin dashboard (`hermes dashboard`): `"<title>" is open in the admin dashboard, which intercom cannot reach. Nothing was sent.` CLI exit 4. | F3: new bullet; § "Receipts": new `error` row; exit-code row 4; new § "Desktop app, and chats in the admin dashboard" | sm-09 (new Done-when), sm-15 (new Done-when) | "States": new error state |
| 13 | **Hermes Mobile is out of scope; the Webapp in a phone browser takes its place.** The Webapp is the desktop chat view served by the gateway. Below 768 px its sidebar is a slide-over sheet, and the chat is one column. A message is a full-width user card like Alex's own, with plain text and no delivery tick; the answer is unboxed text. Whether another sender's row appears live or on reload is checked in the E2E. | Header notes (date line); the SM-Q11 decision line and its Open-questions row (carried over to the Webapp); People (Alex row); J6; J7; § "Hermes Mobile" replaced by § "The Webapp in a phone browser"; § "Web dashboard and desktop app" replaced by § "Desktop app, and chats in the admin dashboard"; the sm-08 and sm-09 rows of the stories table; § "Not this"; "Still to check" (Webapp instead of dashboard chat) | sm-08 (rewritten for the Webapp), sm-09 (desktop and Webapp; admin dashboard), sm-10 ("from the Webapp on his phone") | The phone frames are now Webapp frames (address bar, ☰ sheet, full-width user cards, no ticks); the desktop section names the Webapp; "Web dashboard chat and Ink TUI" became "Ink TUI"; the story map; the exchange note |

**Not changed here** (outside these four updates, for the architect to weigh): `ux.md` still describes the round-4 routing in places that HLD round 3 replaces:
- the lease and pid hosts;
- the `no-seam`, `no-endpoint`, `no-dashboard` and `no-gateway` errors (the LLD now has `no-owner`, `owner-restarting` and `refused-by-owner`);
- F13 (a terminal session with no turn yet);
- `status`'s pid and lease advice, which the LLD removes;
- `list` as intercom's peers (now the owner's `session.list`).

## Notes for the builder

- **The footer makes every mail long on the phone.** The footer is about 10 lines and Alex sees all of it, because the Webapp's user row shows plain text. The mockups show it in full on purpose. It is the accepted design (the footer is how the model learns the reply rules; SM-Q11 accepted the phone look), but it is the first thing Alex will notice. A Webapp chat-view change that folds everything after the header is the natural follow-up. It is out of scope for this chunk.
- **Telegram (LLD TB-5).** The echo is posted only to a private chat: a DM with a user listed in `plugins.entries.intercom.owner_user_ids`, or a chat listed in `plugins.entries.intercom.echo_chats`. Both sit at the entry level, next to `allow_gateway_injection`, not under `settings`. It is header line 1 and the body, as plain text with mentions suppressed. Shared chats still get the mail, plus a model-only shared-chat line. A reply to a shared-chat sender carries only an explicit `[REPLY]` block, and that sender's footer carries the reply-destination line. "States" draws the shared chat (only the answer appears), the sender's receipt, and a message from a shared Telegram group session.
- **Budgeting's answer after the interrupt** shows the intended behaviour (mockup review M-4). It says who asked ("Hermes Improvement asked me to stop (message 5b77e1)"), never "as asked", and it tells Alex what happened to his own request ("Your November import is on hold…").
- **The 📡 emoji** shows as a box in the headless browser used for the check screenshots, which has no emoji font. Phones, desktops, terminals and Telegram render it. Nothing depends on it, because every meaning is in words.
- **Row chrome is approximate** for the Webapp, the Ink TUI and the classic CLI (gutters, tool-row glyphs). **The text is exact**, and so are the CLI notices and their 80-character previews, which come from the CLI's own rule (`text[:80] + "..."`).
- **The Telegram stopped answer** after an interrupt is drawn as a note only. What the topic shows for it is checked when the echo is built (`ux.md`, "Still to check").
- **R7-1 is settled, then superseded:** the cold-start receipt now says the gateway reopened the session (LLD B9, change 10 below).
