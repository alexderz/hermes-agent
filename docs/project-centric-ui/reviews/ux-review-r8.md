Round 8: finding 6 and both round-7 nits are fixed, so the verdict is **meets requirements**. One line in `pcu-20` missed the archived qualifier, but it is a nit and needs no further round.

- **Finding 6, fixed.** F2's "outside the tree's window" case (`ux.md:82`) and `pcu-20:17` now say the main chat comes back once a message is sent in it, and that opening it alone is not enough. That matches the tree picking chats by last activity (`tui_gateway/methods_projects.py:349`).
- **Archived nit, fixed in the main "Done when".** `pcu-20:16` now adds "unless Spec's direct lookup covers archived chats (HLD Risks)", which matches the HLD's Tree-window risk. F2's rule ("or by a direct lookup, if Spec adds one", `ux.md:79`) already leaves room for that.
- **Stale reference nit, fixed.** `ux.md:8` now cites both a3404cae4d and the clarification commit 3b4e3a2f9f.

**Nit, no change needed:** the out-of-scope line at `pcu-20:21` still says archived is excluded ("opening an archived main chat on tap (the one rule in `ux.md` F2 excludes it)"). Give it the same "unless Spec's lookup covers archived" wording as line 16 when convenient. It doesn't change what Alex sees.

Verdict: meets requirements

Reviewed: `9a701e4c663cf2e5f56cf395d7be85cb6ce5728c7f9f56c1c53811845314a4f3  ux.md`. Git status in `wt/v023`: `ux.md` and 17 stories modified; `pcu-18` to `pcu-23` and `reviews/ux-review-r6.md` untracked; all uncommitted on 3b4e3a2f9f.