Round 6 (v0.23 Webapp rewrite): the redesign fits the new surface and Alex can finish every main job, but it needs **changes**. I found five issues: two contradict the HLD, two are missing failure or rollout states, and one is a journey step that can't be done as written. The parts that already meet the requirements:
- Every story is checkable.
- The pinned main chat shows both in its project and in Pinned, as in the HLD.
- Steering is a live check with nothing built.
- All 16 retired stories carry a clear "Retired (v0.23 move) … do not build" banner, and nothing deferred comes back.

**Findings**

1. **"Every status is a word" only covers Working.** This is in `ux.md:119`, `:130`, `:173`, `stories/pcu-19-main-chat-first.md:14` and `stories/pcu-21-phone-webapp.md:17`.
   - **Breaks:** the stated taste (status colour paired with a word). The row's status dot has six states, not one (`apps/desktop/src/app/chat/session-status-dot.tsx:29-80`): working, stalled, needs-input (amber, "the one act-now color"), background, unread and draft. Their words exist only as aria labels and hover titles. The UX adds a visible word for working only. On the main chat row, the amber "needs input" dot or the green "finished" dot would stay colour-only next to "Main chat", which a phone can't hover. The HLD's part 2 (`hld.md:130-144`) and its test list (`:293`) don't include the "Working" word at all.
   - **Fix:**
     - Give the main chat row a visible word for each dot state it can show, for example "Main chat · Working" (also for stalled), "Main chat · Needs your answer" and "Main chat · Finished". Or narrow the claim to say which states get a word.
     - Ask the architect to add the status word to part 2 and its vitest list.

2. **What a tap does when the main chat is missing disagrees with the HLD.** This is F2 at `ux.md:78-82` and `stories/pcu-20-no-main-chat-unchanged.md:15`.
   - **Breaks:** HLD part 2 (`hld.md:131-138`) opens the main chat whenever "the project node has an owner", and hides only the row when no row matches. The UX says the tap opens nothing. As designed, a tap could try to open a deleted chat.
   - **Also missing:** the HLD's third no-match case, a main chat that has fallen outside the tree's window (`hld.md:137`, Risk `:348-350`). With five of the six main chats ended, that is the likely way Alex would lose the mark.
   - **Fix:**
     - State one rule: the tap opens the main chat only when it is found among the project's rows (or by the lookup Spec may add). Ask the architect to make HLD part 2 say the same.
     - Add the "outside the window" case to F2 and `pcu-20`, with what Alex sees. If Spec adds the `session.info` lookup, the row and the tap still work.

3. **The seeding story disagrees with the HLD.** This is in `ux.md:162`, `stories/pcu-08-main-chats-seeded.md:16-19` and the Q3 assumption at `ux.md:20`.
   - **Breaks:** HLD decision 4 (`hld.md:219-226`, `:273`).
     - Seeding is six runs of a new `hermes project set-owner <project> <session-id>` / `--clear` verb, which refuses a session that doesn't exist in the profile.
     - That verb is also how a later project gets its main chat.
     - The undo file is appended during the run, entry by entry.

     The UX says "one `projects.update` call", and `pcu-08:19` says the undo file is written "before changing anything".
   - **Fix:**
     - Name `set-owner` in `ux.md:162` and `pcu-08`.
     - Reword `pcu-08:19` to: "each change appends its previous and new value to an undo file under backups; the undo puts back the previous values, which clears the six pointers".
     - Add a "Done when" line: set-owner refuses an unknown or other-profile session id.

4. **The deploy is not covered as a user-facing failure or step.** No F entry, and nothing in `pcu-21` or `pcu-22`.
   - **Breaks:** the failure-journey check, and consistency with HLD decision 6 (`hld.md:239-266`) and the brief's constraint (`brief.md:73`). What the HLD's rollout means for users:
     - The one gateway restart is drain-first and interrupts every running turn on every surface, including family members' chats and messaging, if a turn runs past the 1,800-second drain.
     - Webapp tabs reconnect, and an interrupted chat turn auto-continues on the next message within an hour.
     - The feature appears only after a reload on laptop and phone, and the phone's home-screen copy is one of those.
   - **Fix:** add an F entry for rollout:
     - the restart is announced and waits until no main-chat turn is running;
     - what an interrupted turn looks like afterwards;
     - Alex reloads the Webapp, or closes and reopens the home-screen copy, to get the new tap.

     Add a "Done when" to `pcu-21`: after the deploy and a reopen, the phone shows the new behaviour.

5. **"Click the project name again" can't be done.** This is J2 step 3 at `ux.md:46`.
   - **Breaks:** "can Alex finish the job". In an entered project the sidebar shows a back row, not the project row (`apps/desktop/src/app/chat/sidebar/index.tsx:1965`, `ProjectBackRow` → `exitProjectScope`), so there is no project name to click again.
   - **Fix:** reword to "From the entered project, the main chat is the first row. To switch, he taps Back, then another project, which opens that project's main chat."

**Nits, no change needed**
- `ux.md:8` still says the HLD is "being rewritten in parallel". It is now committed at a3404cae4d.
- The `/new` notice in J5 and `pcu-23:15` differs from the HLD's wording (`hld.md:211`). Settle one text at Spec.
- `pcu-18:20` says `index.tsx` must be "no longer than" before. The HLD (`hld.md:139-144`, `:296`) requires both that file and `ChatSidebar` to end smaller.
- `pcu-22:27` treats "the command-line process exits mid-turn" as an unknown, but the HLD Trial already showed steer and stop work after the CLI was killed (`hld.md:109`, `:333`). It could be a "Done when" for the live check.

Verdict: changes needed

Reviewed: `116965e4b789dbe47926884962a4a936e836426c36176cbd56b66cce118cfe4d  docs/project-centric-ui/ux.md`. Git status in `wt/v023`: `ux.md` and 17 stories modified, `pcu-18` to `pcu-23` untracked, all uncommitted on a3404cae4d. I ran nothing against a live `HERMES_HOME`.