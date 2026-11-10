# Story — Choose how hard a message pushes

- Id: `sm-17-choose-delivery-mode`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` § "Tool description", § "Receipts"
- Person: a sender (session, cron job or script)

## Required

- **As a** sender
- **I want** to choose `delivery: interrupt | steer | queue` (steer by default) and be told which mode was actually applied
- **So that** I push exactly as hard as the situation needs, and know whether the other session's work was stopped, joined or left alone
- **Done when**
  - [ ] `delivery` omitted means `steer`, on the tool and the CLI.
  - [ ] The host applies the requested mode when the target supports it now; otherwise the strongest weaker one (interrupt > steer > queue), on every host.
  - [ ] An idle target starts a turn whatever the mode, and the receipt says `started`.
  - [ ] The receipt carries `requested` and `applied` (`interrupt`, `steer`, `queue` or `start`, with `applied_detail` `redirect` or `hard-interrupt`); its `message` sentence and the CLI line name the applied mode in words, and add "asked: <requested>" when it is weaker; the record stores both.
  - [ ] The tool description contains, word for word: "Only use interrupt when you intend to stop what the other session is doing right now (it is wrong, or the work is obsolete). Otherwise use steer (default) or queue."
  - [ ] An unknown `delivery` value is refused before anything is sent (CLI exit 2).
- **Out of scope** — a mode that waits for the target to be idle; any approval for interrupt (the sender's choice, settled).
