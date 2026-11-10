# Story — Debate until there is nothing new, then [SILENT]

- Id: `sm-07-silent-ends-exchange`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` (J2, F4)
- Person: two sessions in a debate; Alex reading it afterwards

## Required

- **As a** session in an exchange with another session
- **I want** to keep answering for as long as I have something new, and to end it by answering `[SILENT]`
- **So that** a debate can run its course with no counter cutting it short, and ends without empty "agreed" ping-pong
- **Done when**
  - [ ] Two sessions exchange at least four rounds by automatic replies, each round a new mail with its own id.
  - [ ] An answer that is `[SILENT]` as a whole, on its first line or on its last line, or a reply block that is empty or `[SILENT]`, or an empty answer, sends nothing, and the outbox records "silent" for that mail.
  - [ ] `[SILENT]` in the middle of a sentence is sent as content.
  - [ ] The plugin has no hop, round, rate, duplicate or daily limit, and no timer that ends an exchange.
  - [ ] The no-empty-replies rule **and** the instruction to answer `[SILENT]` when there is nothing new both appear, as written in `ux.md`, in the tool description and in every footer variant.
- **Out of scope** — any cap or loop detector; a summary of the debate.
