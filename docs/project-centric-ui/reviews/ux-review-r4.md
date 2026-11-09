Round 4: the new steering design meets Alex's requirement in substance, but four points disagree with the HLD or the code, so the verdict is **changes needed**. In substance:
- J6 and `pcu-16` cover open, queue, guide, correct and stop from today's phone app.
- F10 and `pcu-17` give a held chat a better option than "New conversation".
- The Not this list keeps cross-process steering and an early v0.23.0 move out of scope.
- `pcu-11`, `pcu-12` and U7 match HLD part 6 and the HLD's Q1 note.

**Findings**

12. **After a cut-off turn, the chat is not always idle.** F11 (`ux.md`, "*Dashboard restart*" bullet) and `stories/pcu-16-steer-working-main-chat.md:24` say that after a dashboard restart or a dropped kickoff, "both surfaces show the chat idle".
   - **Breaks:** HLD "Restarts and owner turns" (`hld.md:289-311`).
     - A short turn (started less than 15 minutes ago, at most twice) auto-continues on the next cold resume, including the phone's. The phone may then show the chat working again with a recovery note, not idle.
     - HLD rule 1 says a planned restart does not happen while an owner turn runs unless Alex chooses it. F11 only says "restarts stay announced", which reads as if a deploy simply kills the turn.
   - **Fix:** split F11 into two cases.
     - A long turn: idle, with the transcript; re-run the kickoff with a "continue" prompt.
     - A short turn: it may resume on its own when the phone or kickoff reopens it.

     Add that a planned restart waits for a running main-chat turn or asks Alex first. Reword `pcu-16:24` to match, for example "idle, or auto-continued for a turn under the freshness window".

13. **A plain message in the dashboard chat interrupts the turn by default.** J7 step 3 (`ux.md`) says a plain message while it works "follows the terminal UI's busy-input setting".
   - **Breaks:** the failure-journey check and low friction. That setting defaults to `interrupt` (`hermes_cli/config_defaults.py:830`, brief fact 23). On the dashboard, Alex typing a note into a multi-hour main-chat turn stops that turn, unlike the phone flow in J6.
   - **Fix:** state the default in J7 and add a line to `pcu-16`. Plain typing in a working chat on the dashboard interrupts it; use `/queue` or `/steer` to keep it running. Or list "set `display.busy_input_mode` to `queue`/`steer`" as an Alex choice next to U7.

14. **The story puts the kickoff client in the wrong place.** `pcu-16:29` says "the kickoff client is Alex's tooling, outside the fork branch (brief A6, refine round 3)".
   - **Breaks:** HLD part 6 and "Decision: where the kickoff client lives" (`hld.md:146-170`, `:231-250`). The HLD rejects code outside the fork as a side repo (rule 19) and makes the kickoff a CLI command of the same fork plugin. Only the unit's one-line command change stays in Alex's tooling.
   - **Fix:** reword it as "the kickoff is a `hermes` CLI command in the Projects plugin (HLD part 6); switching the kickoff unit to it is Alex's tooling".

15. **A working main chat in another profile cannot be joined from the dashboard.** J7 (`ux.md`) and `pcu-16:21` promise that **Open main chat** on the dashboard joins the same running turn. That holds only in the dashboard's own profile.
   - **Breaks:** the failure-journey check, together with F9. A profile-scoped dashboard chat does not attach to the dashboard's in-memory backend; it starts its own (`hermes_cli/web_server_chat.py:390-392`, `:466-468`). Under F9 (a), opening a working main chat that lives in another profile hits the 4090 refusal, which is F10's "open in another window", not J7.
   - **Fix:**
     - Limit J7 and `pcu-16:21` to main chats in the dashboard's own profile, which covers all six of Alex's.
     - Add a line to F9 or F10 saying what happens for another profile's working main chat.
     - Note it under U9 or the HLD's Profiles open item for Spec.

**Nit, no change needed:** the new Q4 assumption sits before Q3 in the assumptions list (`ux.md`, top). Reorder it when convenient.

Verdict: changes needed

Reviewed: `68a6392ccd8ae64f3ed315e2fbe41cd0c63d955297edb02d5e15ed27abae690c  ux.md`. Git status: `ux.md`, `pcu-11` and `pcu-12` modified, `pcu-16` and `pcu-17` untracked, all uncommitted on top of 93afd30c9e.