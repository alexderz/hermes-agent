# Mockups — session-mail (DER-701): how a message looks on existing screens

LLD grain. Pictures for screens people will see. **designer.**
Human gate: operator accepts, or writes `UX verification not required`.

- Slug: `session-mail`
- UX / stories: [`../ux.md`](../ux.md), [`../stories/`](../stories/) (Plan and UX accepted by Alex on 2026-11-10, with all recommended answers)
- LLD: [`../lld.md`](../lld.md) (round 7, `32db590f88`: gateway only; security reviews 5 and 6; the steered echo)
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
  | **A — "Not Alex" first** (`ux.md`'s order and the LLD's final shape) | [`variant-a-not-alex-first.html`](variant-a-not-alex-first.html) | `📡 Not Alex · reply requested · hermes@Hermes Improvement — Orchestrator says (session local-7f3a91c2 · message 3f2a9c):` |
  | **B — sender first** (intercom's own order) | [`variant-b-sender-first.html`](variant-b-sender-first.html) | `📡 hermes@Hermes Improvement — Orchestrator (session 20261109_071203_a1b2, not Alex) says · reply expected · message 3f2a9c:` |
  | **C — two-line card** | [`variant-c-two-line-card.html`](variant-c-two-line-card.html) | `📡 Not Alex · hermes@Hermes Improvement — Orchestrator says:` then `reply expected · message 3f2a9c · session 20261109_071203_a1b2` |

  **B and C reopen the accepted `ux.md`.** Choosing either changes header line 1 in `ux.md` (§ "Header", F10, the `status` transcript anchor) and sm-05, so Alex would have to accept the UX again. A needs no change to `ux.md`'s order. The wording changes from the LLD, below, apply to all three.
- **Surfaces** (each file shows all of them, in this order):
  - the Webapp in a phone browser (replaces Hermes Mobile, SM-Q22): the target chat and the sender chat side by side;
  - the desktop app;
  - the desktop app (and the Webapp at desktop width), then the Ink TUI (layout A; B and C still show the old "web dashboard chat" frame);
  - the classic CLI, with Budgeting open in `hermes chat` (layout A: the expected notices, still to be confirmed in the E2E, since the CLI is now an owner client);
  - a Telegram topic, drawn as listed in `plugins.entries.intercom.settings.echo_chats`, with the shared (unlisted) case in "States";
  - states.
- **The exchange shown everywhere**, with the real wording from `ux.md` and the LLD:
  1. "Hermes Improvement — Orchestrator" steers mail 3f2a9c into Alex's running turn with "Budgeting — Orchestrator".
  2. Budgeting's answer to Alex carries a `[REPLY 3f2a9c]` block.
  3. The block arrives back in Hermes Improvement as mail 8e41b0, labelled "reply optional".
  4. Hermes Improvement's answer writes no `[REPLY 8e41b0]` block, so nothing is sent: a reply goes back only from an explicit block (reply modes, 2026-11-11). Layouts B and C still show the earlier `[REPLY 8e41b0][SILENT][/REPLY]` ending.
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
  - *Fallback (J9):* interrupt asked, the owner refused the redirect, so it stopped the turn hard: chip `interrupted · hard-interrupt`, receipt "Message 5b77e1 stopped the running turn of "Budgeting — Orchestrator"; it runs as that session's next turn." Interrupt never falls back to steer or queue (LLD round 5 B1). The header still says `interrupt asked`, and the conditional line 3 is true (layout A; B and C still show round 3's queue fallback).
  - *Telegram, shared chat:* a group or topic that is not in `plugins.entries.intercom.settings.echo_chats`, or a DM with anyone not in `plugins.entries.intercom.settings.owner_user_ids`, is shared. The mail is delivered but nothing is posted, so only the answer appears. The sender's receipt adds "Its chat is shared with other people; the body is now in that chat's context."
  - *A message from a shared Telegram group session:* the `(Telegram group)` sender label, the platform authority line, and the footer's reply-destination line.
- **Agent review:** round 1 (M-1 to M-6) and round 2 (N-1 to N-4, `../reviews/mockup-review-r2.md`) fixed; round 3 pending.

## Comparison

What each header order does on the surfaces where it matters most.

| Check | A — "Not Alex" first | B — sender first | C — two-line card |
|---|---|---|---|
| **Phone, first wrapped line** (the Webapp in a phone browser; about 34 characters at 340 px) | `📡 Not Alex · reply requested ·`, or `📡 Not Alex · interrupt asked ·` for an interrupt: the glance words, for any title | `📡 hermes@Hermes Improvement —`: "not Alex" and the reply label come 3–4 lines later, after the session id | `📡 Not Alex · hermes@Hermes`: "Not Alex" yes; the reply label is on the card's second line, after the title wraps |
| **Classic CLI's 80-character notice** (`⏩ Steered: '…'`, `↪ Redirected current turn: '…'`) | `📡 Not Alex · reply requested · hermes@Hermes Improvement — Orchestrator says (ses...`: complete glance words on one line | `📡 hermes@Hermes Improvement — Orchestrator (session 20261109_071203_a1b2, not Al...`: **"not Alex" is cut off**, and the reply label never shows | `📡 Not Alex · hermes@Hermes Improvement — Orchestrator says:` then, on a **second terminal line**, `reply expected · mes...`: "Not Alex" and the reply label both show, but across two lines, because the preview holds the header's line break |
| **Telegram post** (listed chats only) | One line, glance words first | One line; "not Alex" buried in brackets | Two lines; the clearest card to read in a chat |
| **Model reading it** | Clear | Clear (intercom's familiar order) | Clear |
| **Reply matcher and `status` anchor** (LLD B6/D3) | One line: starts `📡 Not Alex · `, ends `· message <id>):`. This is the LLD's final shape | One line: starts `📡 hermes@` | **Two lines**: the id is on the line after the anchor, so the matcher and the `status` check must read two lines |
| **Closeness to intercom upstream** | Keeps `hermes@<title> says`, after the glance words | Closest | Keeps `hermes@<title> says`, then a new second line |
| **"interrupt asked"** (49 characters with the reply label) | `📡 Not Alex · interrupt asked · reply requested ·`: one or two phone lines, before the title | `… says · interrupt asked · reply expected · message 5b77e1:`, at the end of a long line | On the second card line, after the title |
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
| 7 | **The Telegram echo is conditional** (TB-5): posted only to a private chat, meaning a DM with a user in `plugins.entries.intercom.settings.owner_user_ids` or a chat in `plugins.entries.intercom.settings.echo_chats`, escaped for the chat's renderer (LLD round 5 corrects round 3's plain text). A shared chat gets the mail but no post, and the sender's receipt adds "Its chat is shared with other people; the body is now in that chat's context." | § "Messaging-gateway sessions" (first bullet, new shared-chat bullet, the security bullet now settled); § "Receipts": new shared-chat row | sm-20 |
| 8 | **Wake receipt** (UX review R7-1, LLD B9): "<title> was not open anywhere that could take it, so message <id> started a turn in the dashboard." The CLI line is `started (was not open anywhere; a turn started in the dashboard)`. A live host's `started` keeps "… started a turn there". | § "Receipts": new row; § "Command line", `send` output | sm-04 |
| 9 | **O17 retracted** (LLD, opening note): a queued message shows **once**. | J5's "appears twice" sentence → "A queued message shows once on every surface"; removed: § "Hermes Mobile" "Until the O17 fix …", § "Web dashboard and desktop app" "Until the O17 fix …", the HLD O17 row in "Open questions"; "For the architect" notes O17 as retracted | sm-08, sm-09 |

The `ux.md` header line also records the alignment: "2026-11-10: aligned with LLD round 3". Nothing in the list adds a cap, hold, retry or gate, and none reopens a settled decision.

## Gateway-only alignment (2026-11-11), for Alex to see

Alex settled **SM-Q20 (gateway only)** and **SM-Q22 (Hermes Mobile dropped)**. HLD round 3 and LLD round 5 list four text updates for the designer. They continue the table above. Every edit:

| # | Change (HLD § "UX / stories", LLD B6 / B9) | `ux.md` edits | Story edits | Layout A mockup |
|---|---|---|---|---|
| 10 | **Cold-start receipt:** `"<title>" was not open, so the gateway reopened it and message <id> started a turn there.` It replaces change 8's "… started a turn in the dashboard". The CLI line is `started (was not open; the gateway reopened it and a turn started there)`. | J6's second bullet ("Not open (cold): the gateway reopens it …"); § "Receipts": the cold-start row replaces the "woken" row; § "Command line", `send` output | sm-04 (also "a Webapp or desktop chat" in its idle line) | "States": the loading state is now a cold start, with the new receipt |
| 11 | **Echo timing:** the Telegram post is made **as the turn that carries the message runs, before its answer**: by the target's own turn, as a queued or started turn begins, or at the first tool step after a steer (corrected in row 20: just before the model's next request). Private chats only, as before. If the hooks do not fire for messaging chats (HLD O21), the echo is dropped for v1 (SM-Q15 a). | The SM-Q15 decision line; J11; § "Messaging-gateway sessions", first two bullets; "Still to check": new O21 item | sm-20 (timing Done-when; the note now names O21) | Telegram callout 1 and the side note |
| 12 | **`not-addressable` receipt** for chats held by the admin dashboard (`hermes dashboard`): `"<title>" is open in the admin dashboard, which intercom cannot reach. Nothing was sent.` CLI exit 4. | F3: new bullet; § "Receipts": new `error` row; exit-code row 4; new § "Desktop app, and chats in the admin dashboard" | sm-09 (new Done-when), sm-15 (new Done-when) | "States": new error state |
| 13 | **Hermes Mobile is out of scope; the Webapp in a phone browser takes its place.** The Webapp is the desktop chat view served by the gateway. Below 768 px its sidebar is a slide-over sheet, and the chat is one column. A message is a full-width user card like Alex's own, with plain text and no delivery tick; the answer is unboxed text. Whether another sender's row appears live or on reload is checked in the E2E. | Header notes (date line); the SM-Q11 decision line and its Open-questions row (carried over to the Webapp); People (Alex row); J6; J7; § "Hermes Mobile" replaced by § "The Webapp in a phone browser"; § "Web dashboard and desktop app" replaced by § "Desktop app, and chats in the admin dashboard"; the sm-08 and sm-09 rows of the stories table; § "Not this"; "Still to check" (Webapp instead of dashboard chat) | sm-08 (rewritten for the Webapp), sm-09 (desktop and Webapp; admin dashboard), sm-10 ("from the Webapp on his phone") | The phone frames are now Webapp frames (address bar, ☰ sheet, full-width user cards, no ticks); the desktop section names the Webapp; "Web dashboard chat and Ink TUI" became "Ink TUI"; the story map; the exchange note |

### Gateway-only round 2 (2026-11-11): UX delta review GW-1 to GW-5, and LLD round 5 (`6ccea9121f`)

| # | Change | `ux.md` edits | Story edits | Layout A mockup |
|---|---|---|---|---|
| 14 | **The Webapp's four-line clamp** (GW-1, from `apps/desktop` `sticky-human-clamp`). A user row shows about four lines, fading from halfway; a tap expands it; it is sticky at the top while the answer streams; the text is plain apart from inline code and fences. | § "The Webapp in a phone browser" (new clamp bullet, plain-text wording, the joined-row note); § "Desktop app" (same clamp, click to expand); F10 ("after a tap to expand") | sm-08 (new clamp Done-when; the joined row "after a tap to expand") | Phone rows clamped and fading; the first mail drawn again expanded after a tap; the "What to look at" notes; this README's builder note (the fold already exists) |
| 15 | **One routing model: the gateway owner** (GW-2, LLD round 5). The owner hosts every chat surface; consent is required for every delivery; the error set is `not-addressable`, `injection-off`, `refused-by-owner` (exit 4) and `no-owner`, `owner-restarting`, `not-reachable` (exit 5); `status` uses the owner's admission receipt or the transcript check; `list` is the owner's `session.list`; addressing has no endpoint names; interrupt falls back only to a hard interrupt. | The *owner* definition (Words); People; J4, J5, J6 (idle and cold-start timing), J8 steps 2 and 5, J9 (rewritten: redirect refused → hard interrupt), J10 (the terminal is an owner client; the O18 exception removed); F1 (candidates), F2, F3 and F4 (rewritten to the LLD error set, with receipt wording), F5 (the owner's admission; idempotent per message id), F6, F7; **F13 deleted**; the `to` parameter row; the receipts table (removed `no-seam`, `no-dashboard`, `no-endpoint`, `no-gateway` and the start-wait row; added `refused-by-owner`, `no-owner`, `owner-restarting`; new `not-reachable` and `injection-off` wording); § "Terminal sessions" (rewritten; the CLI notices table moved to "Still to check"); the CLI `list`, `send` output, exit-code rows 4 and 5, the `status` sample and its advice, the `log` sample; the HLD O18 Open-questions row removed; "Still to check"; "Differences" (CLI verbs); "For the architect" (rewritten) | sm-01, sm-02 (no endpoint names), sm-03, sm-04, sm-05, sm-06, sm-07, sm-11 (exit codes), sm-12 (`status`, `list`), sm-14, sm-15 (the LLD error set), sm-17 and sm-18 (interrupt falls back to a hard interrupt only), sm-19 (owner client; the CLI notices no longer required; the F13 line removed), sm-22 (rewritten for the owner) | The J9 fallback state is now a hard interrupt; the classic CLI section is labelled "expected notices, checked in the E2E" |
| 16 | **Echo settings and escaping** (GW-3, LLD round 5). `plugins.entries.intercom.settings.echo_chats` and `settings.owner_user_ids`, with `"<platform>:<id>"` values; the echo is escaped for the chat's renderer, and a platform with no escaper gets no echo. This reverses mockup review N-3, which followed LLD round 3. | § "Messaging-gateway sessions" (first bullet, shared-chat bullet) | sm-20 | The Telegram note, the shared-chat state's title |
| 17 | **The steered echo** (GW-4). Round 2 stated a gap: no echo when the turn makes no further tool call. **Fixed in LLD round 7** (`32db590f88`, B6): the steered echo is posted from `pre_api_request`, before the model's next request, tool call or answer alike. | § "Messaging-gateway sessions" (the steered timing; the gap sentence removed); "For the architect" (the item removed) | sm-20 (the gap Done-when replaced; its first Done-when's timing) | The Telegram note |
| 18 | **A bare `[SILENT]` answer in a messaging chat on v0.23** is no longer claimed to stay out of the topic: that came from v0.22's internal-event path, and the LLD does not cover it. | § "Messaging-gateway sessions"; "Still to check"; "For the architect" item 2 | sm-20 (the claim becomes an E2E check) | — |
| 19 | **Small leftovers** (GW-5). | "a phone row" (glance bullet); "user card" ("Still to check") | sm-10 ("interrupt asked") | — (this README's LLD reference now cites round 5) |

### Final alignment (2026-11-11): LLD round 7 (`32db590f88`) and UX review GW2-1, GW2-2

| # | Change | `ux.md` edits | Story edits | Layout A mockup |
|---|---|---|---|---|
| 20 | **Steered echo fixed in the LLD** (row 17). | § "Messaging-gateway sessions": "for a steered message just before the model's next request reads it … A steer that arrives after the turn's last request becomes the next turn, and is echoed as that turn begins. Each message is echoed once."; "For the architect": GW-4 removed, one item left (bare `[SILENT]` in a messaging chat) | sm-20: two Done-whens | Telegram note |
| 21 | **The expand gesture, from the real code** (GW2-1, `user-message.tsx`). Phone: the expand chevron ⌄ under the row (a tap on the row does not expand). Desktop: a click opens the edit composer; leave with Esc, because sending an edit rewinds the turn. | § "The Webapp in a phone browser" (clamp bullet; the joined-row note); § "Desktop app"; F10 | sm-08 (two Done-whens) | Caption "after Alex taps ⌄", an "⌄ expand · ✎ edit" line under the clamped row, the "What to look at" note; this README's builder note |
| 22 | **sm-15's leftover status advice** (GW2-2). | — | sm-15: "`status` shows the owner's admission (`admitted: …` / `not admitted`) or, for a steered message, whether its header is in the target's transcript, as in `ux.md`." | — |

### Reply modes (2026-11-11): `reply: none | requested | waiting`, ids for follow-ups

Decided by the manager on Alex's "you decide" (`prompts/reply-modes-spec.md`): fewer tokens, no acknowledgement traffic, and a definitive way to address sessions. The architect updates `lld.md` in parallel. Layout A only.

| # | Change | `ux.md` edits | Story edits | Layout A mockup |
|---|---|---|---|---|
| 23 | **`reply` replaces `expect_reply`**, required on `send` with no default. Labels: `no reply needed` (`none`), `reply requested`, `waiting on your reply` (`waiting`); `ask` reads `sender paused: use intercom reply` (row 29). | Parameters table (`reply`; and `include_runs`, `query`, `limit` for `list`); tool description (rewritten, shorter: 273 words, was 300; the catalog sentence and Alex's interrupt sentence unchanged); § "Header" (labels; examples now `reply requested`; glance lengths 30–49, 61 for an interrupting `ask`); § "Accessibility"; SM-Q8 decision line; J1 step 1 (`reply="requested"`), J8, J12 (ask label), F12; the sm-13 row of the stories table; "Differences"; Open questions U2 (settled), SM-Q8 and SM-Q16 rows; "Still to check" (CLI previews) | sm-01 (parameters), sm-05 (labels, footer kinds), sm-08 (label), sm-13 (rewritten), sm-14, sm-21 (label; "use `ask` only when blocked") | Every header and CLI preview reads `reply requested`; the tool rows show `reply requested` |
| 24 | **`none` sends nothing back**: no block capture, no whole-answer fallback (closes the gap where a `none` note steered into a busy turn mailed back that turn's whole answer). Footer lines 1–5 become "No reply is needed and none will be sent. If something here is wrong or blocks you, send a new message with the intercom tool." | § "Footer" variants (new `none` row); "What sends nothing"; "Several messages in one turn"; receipts (`reply: none` row); J3 | sm-06, sm-07 (the `none` footer carries no `[SILENT]`), sm-13 | New "States" frame: a one-way note from a script, expanded |
| 25 | **`waiting`**: captured like `requested`; the footer adds "The sender cannot go on until you answer: answer this first, briefly."; the sender's call does not block. | § "Footer" variants (new `waiting` row); receipts (`reply: waiting` row); tool description | sm-13 | — |
| 26 | **Replies (`reply optional`) go back only from an explicit `[REPLY <id>]` block**, never from the whole answer, so nothing loops back by default; debates continue through blocks. | § "Footer" variants (reply row: lines 1–2 and 5, row 29); J1 step 6 (no `[SILENT]` block needed), J2 (rewritten); "What sends nothing" | sm-06, sm-07 | Reply mails (8e41b0, c41d77) carry the reply footer; step 4 writes no block |
| 27 | **CLI `--reply none\|requested\|waiting`, default `none`**, replacing `--no-reply`. | § "Command line" (usage, `send` bullet, exit code 2); J3 (no flag needed) | sm-11 | — |
| 28 | **Discovery and ids**: `list` gives id, title, project, last active and state (`running` / `idle` / `closed`), newest 30 first, runs only with `include_runs`, `query` filters; every receipt carries the target's session id; the description says to use ids for follow-ups. | Parameters; the `list` note under the description; receipts intro; § "Command line" `list` (flags and a sample); J1 step 2 | sm-01, sm-02, sm-12 | — |

### Reply modes, review (2026-11-11): UX review RM-1 to RM-5

| # | Change | `ux.md` edits | Story edits | Layout A mockup |
|---|---|---|---|---|
| 29 | **A reply's footer no longer says the whole answer goes back** (RM-1). Lines 1–2 become one line, in LLD B5's words: "Only a `[REPLY <id>] … [/REPLY]` block is sent back to session "<title>"; nothing else is. Write one only if you have more to say. Do not call intercom send to answer. (…tool hint…)". Line 5: "write no block (or a `[SILENT]` one)" (RM-5). | § "Footer" variants, the reply row ("1–2, 5") | sm-05, sm-06 (new checks) | Both reply mails (8e41b0, c41d77) carry it |
| 30 | **`ask` and `waiting` read differently** (RM-2). The `ask` label is `sender paused: use intercom reply`, and its footer starts "The sender's turn is paused until you answer". `send` + `waiting` keeps `waiting on your reply`. In the description: "ask delivers and pauses your turn …: use it only when this turn cannot go on without the answer, otherwise send with reply: waiting", and "waiting if they should answer first but your turn can go on". | Tool description (two sentences); § "Header", reply-label bullet and the glance lengths (30–55 characters, 67 for an `ask` with interrupt); § "Accessibility"; J12; the `ask` footer row; "Differences"; SM-Q16 row; "For the architect" item 3 | sm-05, sm-13, sm-21 | — (no `ask` drawn) |
| 31 | **Every `send` example names `reply`** (RM-3). | J8 step 1 (`reply="requested"`); the relay-skill line (adds `reply = none (a note), requested or waiting (required)` and session ids) | — | The tool rows already show it |
| 32 | **The missing-`reply` refusal** (RM-4): `refused` / `reply-missing`, "Nothing was sent: choose reply: none, requested or waiting." Nothing is recorded. | § "Receipts" (new row); "For the architect" item 2 (quote it in LLD B2) | sm-01, sm-13 | — |
| 33 | **Small points** (RM-5): the `none` footer keeps the tool hint; the `waiting` receipt reads "You marked it as waiting: your call returns now, and the answer will come back as a new message."; every example uses v0.23 `local-…` ids (`local-7f3a91c2`, `local-1b9e04d7`, `local-5d1f0a3e`). | § "Footer" `none` row; § "Receipts" `waiting` row; all header, `status` and receipt examples | sm-13 | All headers; the refused-address candidates |

### Project addressing (2026-11-11): `@project` only when the project feature is present

Alex: "Project messaging needs to detect if our project plugin is there and not offer that if it's not; we can't rely on naming." The architect updates `lld.md` in parallel. Layout A only.

| # | Change | `ux.md` edits | Story edits | Layout A mockup |
|---|---|---|---|---|
| 34 | **No title fallback; `@<slug>` only through DER-686's `owner_session_id`, and only when the feature is present.** The feature check is: the projects plugin named by `settings.project_plugin` is enabled, and `projects.db` has `owner_session_id`. It runs at register and on each call. | New § "Project addressing" under the tool description; the `to` parameter row; the SM-Q10 decision line and its Open-questions row (**withdrawn**: no rename of "Model Master") | sm-02 (rewritten) | — |
| 35 | **Two description variants**, differing only in the `to` sentence. The default (feature absent, the launch state) never mentions `@`. The present variant adds `@<project-slug> (that project's owner session)`. | Tool description (the default variant; its heading says so); § "Project addressing" (the present variant's `to` sentence); the relay-skill line (no `@project`) | sm-02 | — |
| 36 | **Two refusals**, exit 3: `project-addressing-unavailable` ("Project addressing is not available on this Hermes. Use list (filter by project) and address the session by id.") and `no-owner-set` ("Project @<slug> has no owner session set. Address a session by id (from list).", LLD B3 wording, PA-1). | F1 (the unknown-address example is now a mistyped title), new F1b; § "Receipts" (two rows); exit code 3 | sm-02, sm-03 | New error state: `send → @budgeting` refused `project-addressing-unavailable` |
| 37 | **Journeys address by id or title**, because `@project` is absent at launch. | J1 (`list` with `query="budgeting"`, then `send` to `local-1b9e04d7`); J3 (the cron job sends to the exact title); J8 (the id from J1's receipt) | — | The sender's tool rows: a `list` call, then sends to `local-1b9e04d7`; the exchange note |

## Notes for the builder

- **The Webapp clamps every user row to four lines** (`sticky-human-clamp`: about four lines, fading from 55%; the row is sticky at the top while the answer streams). The fold earlier rounds asked for as a follow-up already exists. The glance words (`📡 Not Alex · <reply label> ·`) sit in the clear part. **On a phone** the expand chevron ⌄ under the row lifts the clamp (a tap on the row itself does not; an edit button sits beside it). **On desktop** a click on the row opens the edit composer, which shows the whole text; leave it with Esc, because sending an edit rewinds the turn and sends the text as Alex's own. Mockup A draws the rows clamped, and the first mail once more after a tap on ⌄.
- **Telegram (LLD TB-5, B6).** The echo is posted only to a private chat: a DM with a user listed in `plugins.entries.intercom.settings.owner_user_ids`, or a chat listed in `plugins.entries.intercom.settings.echo_chats`, with `"<platform>:<id>"` values (for example `"telegram:<chat id>"`). It is header line 1 and the body, escaped for the chat's renderer so links and mentions are inert (`post_message` has no plain-text option); a platform with no escaper gets no echo. Shared chats still get the mail, plus a model-only shared-chat line. A reply to a shared-chat sender carries only an explicit `[REPLY]` block, and that sender's footer carries the reply-destination line. A steered message is echoed just before the model's next request reads it, whether that step is a tool call or the answer (LLD round 7 B6, `pre_api_request`); each message is echoed once.
- **Budgeting's answer after the interrupt** shows the intended behaviour (mockup review M-4). It says who asked ("Hermes Improvement asked me to stop (message 5b77e1)"), never "as asked", and it tells Alex what happened to his own request ("Your November import is on hold…").
- **The 📡 emoji** shows as a box in the headless browser used for the check screenshots, which has no emoji font. Phones, desktops, terminals and Telegram render it. Nothing depends on it, because every meaning is in words.
- **Row chrome is approximate** for the Webapp, the Ink TUI and the classic CLI (gutters, tool-row glyphs). **The text is exact**, and so are the CLI notices and their 80-character previews, which come from the CLI's own rule (`text[:80] + "..."`).
- **The Telegram stopped answer** after an interrupt is drawn as a note only. What the topic shows for it is checked when the echo is built (`ux.md`, "Still to check").
- **R7-1 is settled, then superseded:** the cold-start receipt now says the gateway reopened the session (LLD B9, change 10 below).
