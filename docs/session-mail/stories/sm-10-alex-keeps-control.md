# Story — Alex keeps control of mail-started turns

- Id: `sm-10-alex-keeps-control`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` (J6, F5)
- Person: Alex

## Required

- **As** Alex
- **I want** to steer or stop any turn that mail started or joined, from the phone, the dashboard or the desktop, and to keep my draft when mail arrives while I type
- **So that** sessions talking to each other never take the session away from me
- **Done when**
  - [ ] A turn started by mail runs in the dashboard, and Alex can open it on Hermes Mobile, steer it and stop it.
  - [ ] Stopping a mail-started turn works like stopping any turn; the mail stays in the transcript and the outbox.
  - [ ] A turn Alex stops, or one that fails, sends no reply and wakes no one, and `status` for its mail shows `no reply recorded` (the reply hook does not run for such turns; HLD O9).
  - [ ] When mail starts a turn while Alex is typing in that session, his draft is unchanged, and his send is handled as a send into a busy session (steer or queue, by his client's usual rule).
  - [ ] When Alex is mid-turn and mail steers in, his turn keeps running and is not redirected.
- **Out of scope** — approval gates or holds for mail (settled: none); notifications for mail.

## Optional

- Notes: stopping is the only way Alex ends a debate early, since nothing is capped. The Trial showed the reply hook does not run for an interrupted or failed turn (HLD O9), so this needs no extra rule.
