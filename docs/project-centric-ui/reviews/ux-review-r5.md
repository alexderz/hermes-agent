Round 5: findings 12–15 are all fixed and the edits break nothing, so the verdict is **meets requirements**.

**Findings 12–15, re-checked**

12. **Fixed: cut-off turns.** F11 (`ux.md:137-141`) now matches HLD "Restarts and owner turns".
    - A planned restart waits for a running main-chat turn, or asks Alex first (rule 1). Restarts stay announced.
    - A long turn ends idle with its transcript, and Alex re-runs the kickoff with a "continue" prompt.
    - A turn under 15 minutes may auto-continue with a recovery note, at most twice.
    - The kickoff exits with a failure, with no reconnect, and the failure shows in the unit's status.

    `pcu-16:25-26` match this and can be checked.
13. **Fixed: plain typing on the dashboard.** J7 step 3 (`ux.md:120`) and `pcu-16:22` state that plain typing interrupts by default, point to `/queue` and `/steer`, and contrast this with the phone. U11 gives Alex the setting change as a config choice. It matches `display.busy_input_mode` defaulting to `interrupt` (`config_defaults.py:830`).
14. **Fixed: kickoff location.** `pcu-16:31` and the Q4 assumption (`ux.md:19`) now say the kickoff is a `hermes` command of the Projects plugin (HLD part 6). Only switching the kickoff unit to it is Alex's tooling.
15. **Fixed: another profile's working main chat.**
    - J7 (`ux.md:117`) and `pcu-16:21` are limited to the dashboard's own profile, which covers all six of Alex's main chats.
    - F9 (`ux.md:146`) says what happens otherwise: the open is refused like F10, and the phone can still steer if it is connected to that profile.
    - U9 (`ux.md:289`) leaves the wording to Spec.

    This matches `web_server_chat.py:390-392` and `:466-468`.

**Nothing broken.** The Q4 assumption now sits after Q3. The fixes add no new controls, screens or deferred items, and every new user-facing line is a plain sentence.

**Two layout nits, no change needed:**
- U11 is indented as a sub-bullet of item 10 (U7) at `ux.md:287`, not its own numbered item.
- J6 and J7 sit under "Important failures and edge cases" after F8, and F9 follows F11. Moving J6/J7 under "Happy paths" and putting the F items in order would help readers.

Verdict: meets requirements

Reviewed: `bab4b61e47d006f02a2354ad641a25391aae43fcabfaa5ce449a37b57a01cd89  ux.md`. Git status: `ux.md`, `pcu-11` and `pcu-12` modified; `pcu-16`, `pcu-17` and `reviews/ux-review-r4.md` untracked; all uncommitted.