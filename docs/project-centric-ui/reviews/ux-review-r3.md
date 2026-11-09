Round 3: finding 11 is fixed and the edits break nothing else. The verdict is **meets requirements**.

**Finding 11, re-checked: fixed.**
- **Lasting switch is now stated.** F9 (a) at `ux.md:106` and `pcu-15:15` say the profile switch persists. Until Alex switches back, new chats, config, keys, skills and model all go to that profile. U9 at `ux.md:238` carries the same choice for Alex.
- **Banner line now matches the code.** `pcu-15:15` says the banner shows only when the chosen profile is not the dashboard's own, which is how `ProfileScopeBanner.tsx:14` behaves. The line is now checkable in every case.
- **"New chat here" is protected.** `ux.md:108`, `pcu-04:16` and `pcu-15:17` require it to start in the project's own profile, whatever profile the dashboard was left on. If Spec finds this needs new HLD work, it falls back to a stated side effect beside U8, so nothing is left hidden.
- **The two alternatives are clear.** (a) switch and open, or (b) explain and stop, with "Spec picks one" written into the "Done when" at `pcu-15:14`. U9 records which one is chosen.

**Nothing else broke.** These edits touch only F9, `pcu-04` and `pcu-15`, and the rest of `ux.md` and the other stories are unchanged from round 2. The new message in F9 (b) is a plain sentence with no ids or codes, and nothing deferred comes back.

**One nit, no change needed:** under alternative (b), a tap opens nothing. That is softer than F9's first bullet ("Opening it must land in that chat", `ux.md:104`) and the "I want" in `pcu-15:10`. (b) still never opens a wrong or empty chat, which is the story's "so that". When Spec picks (b), it should reword those two lines to "never lands in a wrong or empty chat".

Verdict: meets requirements

Reviewed: `272e77fd5959450b58a44837a9b7a5de2fd77698b92fdda5cee3c9ff5649951e  ux.md`. Git status: `ux.md` and stories `pcu-01` to `pcu-04`, `pcu-06`, `pcu-07` and `pcu-10` modified, `pcu-15` untracked, all uncommitted.