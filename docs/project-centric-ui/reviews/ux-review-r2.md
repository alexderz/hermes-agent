Re-review round 2: all 10 findings from round 1 are fixed, but the new other-profile journey (F9 and `pcu-15`) adds one gap, so the verdict is still **changes needed**. It is a one-paragraph fix.

**Round-1 findings, re-checked**
1. **Fixed: nav position.** "Directly after Sessions" now appears in `ux.md:18`, `:36`, `:133` and `pcu-01:7`.
2. **Fixed: plugin decision.** `ux.md:18` and open question 3 (`:222`) now follow the HLD's plugin choice.
3. **Fixed: "New chat here" side effect.** It is stated and checkable (`ux.md:55`, `:153`, `pcu-04:10`), with open question U8 for Alex. This now matches `hld.md:105-109`.
4. **Fixed: addresses.** No URLs remain in the requirements. Each page "has its own address", and Back, scroll position and bookmarks are kept (`ux.md:135`, `:150`, `pcu-01:8`, `pcu-03:7`, `:15`).
5. **Fixed: Live badge and message counts.** Both are dropped from the dashboard and listed in Not this (`ux.md:201-202`), with open question U7 for Alex. Hermes Mobile keeps a running state paired with a label. That is consistent with the HLD's tree-only read.
6. **Fixed: family rule.** It is limited to messages (`pcu-10:10`, `ux.md:212`), so the folder line no longer conflicts.
7. **Fixed: project-page states.** Loading, failure with Retry, and not-found are in F6 (`ux.md:90-91`) and `pcu-03:19-21`.
8. **Fixed: Home page.** Home has no **New chat here** and shows its own plain line instead (F8, `ux.md:98`, `pcu-04:12`). The folder message now applies only to declared projects (`ux.md:78`).
9. **Mostly fixed: other-profile chats.** F9 and `pcu-15` are added. See the new finding below.
10. **Fixed: tap counts.** They are split by device (`pcu-02:8-9`, `pcu-07:10`, `:12`, `ux.md:40`, `:166`).

**New finding**

11. **Switching profile has a lasting side effect that isn't stated.** This affects `ux.md:105`, `stories/pcu-15-other-profile-chat.md:9`, and U9 at `ux.md:235`.
   - **What the design says:** opening a chat from another profile switches the dashboard's profile, and the profile banner names it.
   - **Breaks:** the journey should not leave Alex in a state that misroutes his next action. This is the same kind of side effect as finding 3, and the code shows two problems:
     - The banner (`web/src/components/ProfileScopeBanner.tsx:5-14`) means "new chats, config, keys and so on now land in that profile", and the switch stays after Chat. Alex's next **New chat here** on a default-profile project would then start in the other profile, outside that project's tree.
     - The banner is hidden whenever the chosen profile is the dashboard's own (`:14`). So `pcu-15:9` cannot pass when the chat belongs to the dashboard's own profile while another profile is selected.
   - **Fix:** in F9 and `pcu-15`, state that the switch persists and what it changes (new chats and settings go to that profile until Alex switches back). Either add a "Done when" that **New chat here** always starts in the project's own profile, or list that as a known side effect beside U8. Reword `pcu-15:9` to "the dashboard's profile is the chat's profile (the banner shows it when that is not the dashboard's own profile)".
   - **Nit, no change needed:** `pcu-15:8` and `:10` are alternatives. That is acceptable because U9 tracks the choice, but Spec must cross out one of them.

Nothing else in the changes breaks a requirement. Everything stays inside slice 1, and every new message is a plain sentence with a text label.

Verdict: changes needed

Reviewed: `sha256sum docs/project-centric-ui/ux.md` = see below; git status: `ux.md` and 7 stories modified, `pcu-15` untracked