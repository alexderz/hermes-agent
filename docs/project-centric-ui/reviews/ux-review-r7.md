Round 7: findings 1–5 and the round-6 nits are all fixed, and the UX matches the HLD clarifications at 3b4e3a2f9f. One new problem came from the F2 rewrite, so the verdict is **changes needed**, with a one-line fix.

**Round-6 findings, re-checked**

1. **Fixed: status words.** The status table at `ux.md:125-135` and `pcu-19:14-19` give a visible word for every dot state the main chat row can show, and leave other rows unchanged. This matches HLD part 2's new bullet; the HLD leaves the exact words to the UX.
   - **Draft:** leaving it out is correct. Draft only happens on a row with no stored id (`session-status-dot.tsx:132-134`), and a main chat always has one.
   - **Settled:** the "Main chat" row with a project-colour or grey dot also matches the code (`:81-87`).
   - **Note for the architect:** two HLD lines don't match the code. Part 2 says "idle shows no dot" (it shows a small dot), and the test list names a draft case the main chat row can never reach. Neither changes what Alex sees.
2. **Fixed: the not-found rule.** F2 (`ux.md:78-82`), `pcu-18:12` and `pcu-20:7-9` state the HLD's one rule. The tap opens the main chat only when it is found among the project's chats, and the three not-found cases (archived, deleted, outside the tree's window) behave like having no main chat. A tap never tries to open a chat it hasn't found.
3. **Fixed: seeding.** The Q3 assumption (`ux.md:20`), Not this (`ux.md:179`) and `pcu-08:13-21` now name `hermes project set-owner`. They also cover `--clear`, refusing an unknown or other-profile id, the undo file appended as each change is made, and the same command for later projects. This matches HLD decision 4.
4. **Fixed: rollout.** F9 (`ux.md:101-105`), the phone bullet (`ux.md:157`) and `pcu-21:10` match HLD decision 6:
   - the restart is announced and drain-first, and runs only when no main-chat turn is running;
   - it waits up to 30 minutes, after which any turn on any surface is cut;
   - an interrupted turn auto-continues on the next message within an hour;
   - Alex reloads on the laptop and reopens the home-screen copy;
   - seeding needs no restart.
5. **Fixed: switching projects.** J2 step 3 (`ux.md:46`) and `pcu-18:8` now go through the back row, as the code does.

All four nits are fixed. The `/new` notice text is left to Spec (`ux.md:70`, `pcu-23:15`). The size ratchet requires both the file and `ChatSidebar` to shrink (`pcu-18:21`). The live check now includes the CLI being killed mid-turn (`pcu-22:22`). The HLD reference at `ux.md:8` names the committed rewrite.

**New finding**

6. **"Opening the chat brings it back" is probably wrong.** F2's "outside the tree's window" case (`ux.md:82`) and `stories/pcu-20-no-main-chat-unchanged.md:17` say that opening the chat from search, or using it again, brings the row and the tap back.
   - **Breaks:** "Done when" lines must hold up when checked. The tree picks its window by last activity (`tui_gateway/methods_projects.py:349`, `order_by_last_active=True`, `min_message_count=1`). Sending a message updates last activity, but nothing shows that simply opening a chat does. The "opened from search" half of the line would then fail.
   - **Fix:** say "once a message is sent in it" (or "used again"), and drop "opened from search", unless Spec confirms that opening alone counts.

**Nits, no change needed**
- **Archived with the lookup:** the HLD's Risks say that with the `session.info` lookup, Spec decides whether an archived main chat counts as found. `pcu-20:16` ("never tries to open it") and its out-of-scope line rule that out. Add "unless Spec's lookup covers archived (HLD Risks)" so Spec isn't boxed in.
- **Stale reference:** `ux.md:8` could also cite the clarification commit 3b4e3a2f9f.

Verdict: changes needed

Reviewed: `a5eff6d7de0dd068f9ce87a939b67dc9c6e55acdf7957ee47e26b9ee904797b5  ux.md`. Git status in `wt/v023`: `ux.md` and 17 stories modified; `pcu-18` to `pcu-23` and `reviews/ux-review-r6.md` untracked; all uncommitted on 3b4e3a2f9f. I ran nothing against a live `HERMES_HOME`.