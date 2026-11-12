# Story — Say whether an answer is wanted: reply none, requested or waiting

- Id: `sm-13-no-reply-needed`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` (J1, J3; § "Footer", variants; reply modes, 2026-11-11)
- Person: a sender (session, cron job or script); the target session; Alex

## Required

- **As a** sender
- **I want** to say, every time, whether I need an answer: none (a one-way note), requested, or waiting (I cannot go on without it)
- **So that** notes cost no reply traffic, answers I need come back, and Alex sees at a glance which is which
- **Done when**
  - [ ] `intercom(action="send", …)` requires `reply: none | requested | waiting`, with no default; a `send` without it is refused as a usage error before anything is sent.
  - [ ] `hermes intercom send` takes `--reply none|requested|waiting`, default `none`; `--no-reply` is gone.
  - [ ] Header line 1 reads `no reply needed`, `reply requested` or `waiting on your reply`.
  - [ ] **`none`:** the footer's lines 1–5 are replaced by "No reply is needed and none will be sent. If something here is wrong or blocks you, send a new message with the intercom tool."; the reply hook never sends anything back for it, even when it was steered into a busy turn with a long answer (no block capture, no whole-answer fallback); the receipt ends "No answer was asked for, and none will come back."
  - [ ] **`requested`:** today's footer (`[REPLY <id>]` block, whole-answer fallback, `[SILENT]`, the shared-chat rule).
  - [ ] **`waiting`:** captured exactly like `requested`; the footer adds "The sender cannot go on until you answer: answer this first, briefly."; the sender's call returns at once, and the answer wakes the sender as usual.
  - [ ] The record stores `reply_mode` instead of `expect_reply`.
- **Out of scope** — blocking the sender's call (that is `ask`, sm-21); any cap or hold.
