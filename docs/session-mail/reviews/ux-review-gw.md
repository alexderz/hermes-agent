# UX review, gateway-only delta: session-mail (DER-701)

Reviewer: UX reviewer (designer role, review loop only). Date: 2026-11-11.

Under review: `git diff 9821be07da 031b25c450 -- docs/session-mail/ux.md docs/session-mail/stories
docs/session-mail/mockups`, in worktree `wt/v023`, with the working tree at `031b25c450`. This is
checked against my last verdicts (UX round 7, mockup round 3).

Requirements:
- Alex's settled SM-Q20 (gateway only) and SM-Q22 (Hermes Mobile dropped; the Webapp in the phone's
  browser replaces it; the old dashboard is admin-only);
- HLD round 3 and LLD round 5 at `031b25c450`;
- the stated taste: Alex sees at a glance that a row is not him, from which session, and whether a
  reply is expected; colour always with a label; the existing look on each surface.

**How I checked:**
- **The Webapp claims** were read against `apps/desktop/src`: `hooks/use-mobile.ts`,
  `components/ui/sidebar.tsx`, `components/assistant-ui/thread/user-message.tsx`,
  `user-message-text.tsx`, `content.ts` and `styles.css`, plus the server-side steer projection in
  `tui_gateway/session_history.py` and `hermes_cli/web_routers/sessions.py`.
- **Mockup A** was rendered with headless Chromium.
- **`ux.md` and the stories** were searched for leftover Mobile and dashboard wording.

## What holds

- **Webapp facts that match the code:**
  - The sidebar becomes a slide-over Sheet below 768 px (`DOCKED_SIDEBAR_MIN_PX = 768`,
    `use-mobile.ts`; `sidebar.tsx:158`).
  - A user row is a full-width card (`w-full … rounded-xl border bg-(--dt-user-bubble)`,
    `user-message.tsx:80`).
  - There is no delivery tick; the row has only a hover time.
  - The assistant answer is flat, not boxed.
  - The header never starts with `Message from`, so the inter-agent fold regex
    (`user-message.tsx:97`) does not catch it. `📡` matches no other user-row special case either
    (`PROCESS_NOTIFICATION_RE`, `content.ts:3`).
  - The steer wrapper is stripped server-side for history (`session_history.py:331`,
    `sessions.py:720`).
- **The `not-addressable` receipt** matches LLD B9 word for word. It is in F3, § "Receipts", exit
  4, the desktop / admin-dashboard section, sm-09 and sm-15, and it is drawn in mockup A's states.
- **The cold-start receipt** and its CLI line match LLD B9 (J6, § "Receipts", sm-04).
- **The echo timing** matches LLD B6 (as the carrying turn runs, before its answer; a queued or
  started message at turn start, a steered one at the first tool step), with HLD/LLD O21's fallback
  to SM-Q15 (a) in sm-20 and "Still to check".
- **Hermes Mobile:** every explicit mention is now "out of scope (SM-Q22)" or "replaces Hermes
  Mobile". SM-Q11 is carried over to the Webapp, and it is shown to Alex in "Open questions".
- **The README's change table (10–13)** matches the `ux.md` and story hunks.
- **Nothing** adds a cap, hold, retry or gate.

## Findings

### GW-1. The Webapp clamps every user row to four lines; the design and mockup say Alex sees it all (blocking)

- **Where:**
  - `ux.md` § "The Webapp in a phone browser" ("a full-width card … with the text plain");
  - the README's "Notes for the builder" ("Alex sees all of it, because the Webapp's user row shows
    plain text");
  - mockup A's phone frames and their note ("The footer and closing line are visible to Alex
    too"), which draw every row in full;
  - F10 ("the header and closing line show where the message starts and ends");
  - sm-08 ("In a row joined with Alex's own steer or queued text, the 📡 header and
    `📡 End of message <id>` are both visible").
- **Requirement broken:** the phone view must be described from the real code. The stated taste is
  "at a glance" on the main surface. "Done when" lines must be checkable.
- **What the code does:**
  - Every user row renders inside `StickyHumanMessageContainer` with `sticky-human-clamp`:
    `max-height: calc(4 * line-height …)`, `overflow: hidden`, and a fade mask from 55%
    (`styles.css:1962-1971`).
  - On touch, a tap toggles `expanded` to lift the clamp (`user-message.tsx:400-456`, `:504`).
  - The row is also sticky: it parks at the top while the answer streams.
  - The text goes through a small markdown pipeline (inline code, fences, `@file:` chips;
    `user-message-text.tsx`). It is not strictly plain.
- **Effect on the design:**
  - **Good:** the glance words stay. Line 1 (`📡 Not Alex · reply expected ·`) and the start of
    `hermes@<title>` sit in the unfaded top half. The "footer makes every mail long on the phone"
    problem mostly goes away: the footer is hidden until Alex taps.
  - **Wrong as written:**
    - the README note and the mockup note;
    - sm-08's joined-row line, and F10 for a joined row that starts with Alex's words. There, the
      📡 header can fall into the fade, and the closing line is never visible without a tap.
  - The mockup's phone frames do not show what Alex will see.
- **Fix:**
  - Describe the clamp in § "The Webapp in a phone browser": four lines, fading; tap to expand;
    sticky at the top while the answer streams.
  - Redraw mockup A's phone rows clamped, with one row shown expanded after a tap.
  - Reword sm-08's joined-row Done-when and F10: "after a tap to expand".
  - Replace the builder note: the follow-up "fold" already exists as the clamp.
  - Say "plain text, apart from inline code and fences".

### GW-2. `ux.md` still describes the removed round-4 routing, including a dashboard-and-phone promise (blocking)

- **Where** (`ux.md` at `031b25c450`):
  - the "host" definition (line 28: "the dashboard (which also serves desktop and the web chat)");
  - J10's exception and **F13** ("the sender wakes the session in the dashboard … the turn and its
    answer appear **in the dashboard and on the phone**"), and the HLD O18 row in "Open questions";
  - F3: `no-seam`, the "waking path … dashboard refuses with 4090" bullet, and `injection-off`'s "A
    classic CLI target is not affected";
  - F4: `no-dashboard`, `no-endpoint`, `no-gateway`, and the matching receipt rows and exit-5 row;
  - F5 ("over its socket, or over the dashboard socket when waking");
  - F6 ("a detached dashboard turn reaped …");
  - F7 ("no dashboard runs");
  - J8 step 5 ("the dashboard, desktop and phone show …");
  - `status`'s pid and lease advice, and the `host: dashboard` sample;
  - `list` as intercom's peers;
  - stories: sm-15 (`no-seam`, `no-dashboard`, `no-endpoint` lines), sm-12 (the live-state line)
    and sm-19 (the lease / F13 line).
- **Requirement broken:**
  - Settled SM-Q20.
  - HLD round 3, "Superseded decisions": the dashboard route and wake path are removed, lease-pid
    routing is removed, "one host: the owner", and O18 is "**Closed by SM-Q20** … every session is
    owner-hosted".
  - LLD round 5 B2 step 3: consent is required for **every** delivery, and the classic CLI "is no
    longer a host".
  - The LLD's error table: `no-owner`, `owner-restarting`, `not-reachable` (exit 5);
    `not-addressable`, `injection-off`, `refused-by-owner` (exit 4).
  - F13 is also a leftover phone-and-dashboard promise, which is exactly what this check is for.
- **Why it blocks:** the README lists these as "not changed here … for the architect to weigh".
  But the architect has already settled them in HLD round 3 and LLD round 5. As it stands, the
  `ux.md` Alex accepts describes two designs at once, and a builder reading F3–F7 or sm-15 would
  test errors that no longer exist.
- **Fix:** one alignment pass to LLD round 5:
  - replace the host definition with "the gateway owner";
  - delete F13, J10's exception and the O18 row;
  - rewrite F3, F4 and F5 and the receipts / exit table to the LLD's error set (keeping each
    sentence's style);
  - drop the CLI exemption from `injection-off`;
  - simplify `status`'s advice to the owner's receipt and the transcript check;
  - make `list` the owner's `session.list`;
  - update sm-12, sm-15 and sm-19 to match.
  - The classic CLI is now an owner client. Whether it still prints `⏩ Steered` / `↪ Redirected`
    for input another client steers in is unknown, so move § "Terminal sessions"' notices table to
    "Still to check" until the E2E shows it.

### GW-3. The echo settings path and format no longer match the LLD (minor)

- **Where:** `ux.md` § "Messaging-gateway sessions", sm-20, the README (Telegram notes and the
  "shared chat" state), and mockup A's Telegram note. They use `plugins.entries.intercom.echo_chats`
  and `owner_user_ids` at entry level, "as plain text with mentions suppressed".
- **Requirement:** LLD round 5 (lines 117–124, 248) moves both under `settings`, with
  `"<platform>:<id>"` values. LLD B6 says `post_message` has no plain-text or no-mentions option,
  so the echo is escaped per platform renderer, and "a platform with no escaper gets no echo".
  (This reverses mockup review N-3, which followed the older LLD.)
- **Fix:** use `plugins.entries.intercom.settings.echo_chats: ["telegram:<chat id>", …]` and
  `settings.owner_user_ids`. Say "escaped for the chat's renderer (links and mentions made inert);
  a platform with no escaper gets no echo".

### GW-4. A steered message whose turn makes no further tool call is never echoed (minor; for the architect)

- **Where:** `ux.md` § "Messaging-gateway sessions" ("for a steered message at the first tool step
  after the steer lands") and sm-20's first Done-when ("one bot message is posted … before its
  answer"). Compare LLD B6: the steered case posts from "the first `post_tool_call` of the running
  turn after the steer row appears".
- **What happens:** a steer lands after a tool batch. If the model's next step is the final answer,
  with no further tool call, `post_tool_call` never fires, so no echo is posted. The UX promises one
  for every message to a private chat.
- **Fix:** either the LLD adds a fallback for that case (the architect's call), or `ux.md` and
  sm-20 state the gap: "a steered message whose turn ends without another tool step is not echoed;
  the answer still appears".

### GW-5. Small leftovers (minor)

- **sm-10:** "says so in its first line ("interrupt")". It should be "interrupt asked".
- **`ux.md:281`:** "the first wrapped line of a phone bubble". It should be "of a phone row".
- **`ux.md:497`:** "user bubble". It should be "user card".
- **The README's LLD reference** still cites round 3. It should cite round 5.

Verdict: changes needed
Reviewed: 44a13a8174a0b589171a8d25460a845391a403d8a35ba6cbc1e8e54b6c36a459
