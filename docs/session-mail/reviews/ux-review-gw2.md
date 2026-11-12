# UX review, gateway-only delta round 2: session-mail (DER-701)

Reviewer: UX reviewer (designer role, review loop only). Date: 2026-11-11.

Under review: the working-tree changes in `wt/v023` (`git diff -- docs/session-mail/ux.md
docs/session-mail/stories docs/session-mail/mockups`, on top of `2e9eccb474`): `ux.md`, 18 stories,
mockup A and its README.

Requirements: the same as in `ux-review-gw.md`, against LLD `6ccea9121f` and the HLD at that commit.

**How I checked:**
- **Reading.** I read the whole of `ux.md` and the changed Done-when lines.
- **Leftovers.** I searched `ux.md`, the stories, the README and mockup A for the removed routing
  words: `no-dashboard`, `no-endpoint`, `no-seam`, `no-gateway`, lease, F13, O18, "dashboard chat",
  the old echo path and "plain text with mentions".
- **Rendering.** Mockup A's phone frames were rendered with headless Chromium.
- **Code.** The clamp, expand and edit gestures were checked in
  `apps/desktop/src/components/assistant-ui/thread/user-message.tsx`.

## GW findings

| # | Finding | Status |
|---|---|---|
| GW-1 | The Webapp clamps every user row to four lines | **Fixed:** § "The Webapp in a phone browser" now has the clamp, the fade, the sticky row and "plain apart from inline code and fences". F10 and sm-08 say "after a tap to expand". The README builder note now says the fold already exists. Mockup A draws the rows clamped and fading, then the first mail expanded (rendered and confirmed). The glance words stay in the clear part, as before. **One gesture detail is still wrong; see GW2-1.** |
| GW-2 | Round-4 routing left in `ux.md` | **Fixed.** One model, the gateway owner: the *owner* definition, People, J4–J10, F1–F7 and the receipts, exit 4/5, `status` (the owner's admission receipt or the anchored transcript check, with the idempotent message id), `list` as the owner's `session.list`. F13 and the O18 row are deleted. The classic CLI notices moved to "Still to check" as expected, not promised; sm-19 no longer requires them. `injection-off` now applies to every delivery. Interrupt falls back only to a hard interrupt (J9, sm-17, sm-18), which matches LLD B1. No removed code or dashboard-wake wording remains in `ux.md`, the README or mockup A, apart from one story line (GW2-2). |
| GW-3 | Echo settings path and format | **Fixed.** Every occurrence now reads `plugins.entries.intercom.settings.echo_chats` / `settings.owner_user_ids`, with `"<platform>:<id>"` values. The echo is "escaped for the chat's renderer …; a platform with no escaper gets no echo". It matches LLD round 5. |
| GW-4 | A steered message with no further tool step is never echoed | **Fixed as a stated gap.** `ux.md` § "Messaging-gateway sessions" says it plainly, and "For the architect" item 1 carries it with a proposed fallback. A new, honest item 2 notes that a bare `[SILENT]` may reach a chat on the v0.23 owner path, and it is listed under "Still to check". |
| GW-5 | Small leftovers | **Fixed:** sm-10 now says "interrupt asked"; "phone row"; "user card"; the README's LLD reference is updated. |

Nothing added is a cap, hold, retry or gate. No Hermes Mobile promise remains. The only remaining
mentions say it is out of scope, or that the Webapp replaces it.

## New findings (minor, not blocking)

### GW2-1. The expand gesture doesn't match the code: a desktop click opens the editor, and on a phone you tap a button, not the row

- **Where:**
  - § "Desktop app" ("on desktop a click expands it");
  - § "The Webapp in a phone browser" ("until Alex **taps the row to expand it**");
  - F10 and sm-08 ("a tap expands the row");
  - the README ("a tap or click expands it");
  - mockup A ("after Alex taps the row").
- **What the code does:**
  - **Touch** (`TouchUserBubble`, `user-message.tsx:343-390`): the prose stays plain, selectable
    text. Below it are an explicit **expand chevron** (`aui_user-touch-expand`) and an **edit
    button**. A tap on the row itself does not expand it.
  - **Mouse** (`user-message.tsx:655-665`): a click on the row **opens the edit composer**, and the
    clamp lifts only there (the comment at `:400-404`). Sending that edit "reverts (interrupt +
    rewind)". Only read-only watch windows toggle the clamp on click.
- **Why it matters:** the requirement is that the view is described from the real code.
  - On desktop, the documented way to read a full message puts Alex in an editor.
  - Sending from that editor would rewind the turn and send the peer's text as his own prompt.
    Cancelling is harmless.
- **Fix:**
  - **Phone:** "tap the expand chevron under the row".
  - **Desktop:** "click opens the edit composer, which shows the whole text; press Esc to leave it.
    Sending an edit rewinds the turn and sends the text as Alex's own, as for any user row."
  - Match F10, sm-08, the README and the mockup caption ("after Alex taps ⌄").

### GW2-2. sm-15 keeps the removed lease-based `status` advice

- **Where:** sm-15, the delivery-unknown Done-when: "… and for a classic CLI or gateway target
  that is still busy, tells the sender to wait for its current turn to end before sending again".
- **What happens:** `ux.md` § `status` now uses the owner's admission receipt (`admitted:
  queued / started / finished` or `not admitted`), or the anchored transcript check for a steered
  message. The busy-host advice is gone.
- **Fix:** "After it, `status` shows the owner's admission (`admitted: …` / `not admitted`) or, for
  a steered message, whether its header is in the target's transcript, as in `ux.md`."

Verdict: meets requirements
Reviewed: 387f213e5a5bf55aaeba99aeba2e70a5513a7b35ab72f3aaeb335651f1be1d8a
