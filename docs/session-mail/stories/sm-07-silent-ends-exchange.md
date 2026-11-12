# Story — Debate until there is nothing new, then [SILENT]

- Id: `sm-07-silent-ends-exchange`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` (J2, F8)
- Person: two sessions in a debate; Alex reading it afterwards

## Required

- **As a** session in an exchange with another session
- **I want** to keep answering for as long as I have something new, and to end it by answering `[SILENT]`
- **So that** a debate can run its course with no counter cutting it short, and ends without empty "agreed" ping-pong
- **Done when**
  - [ ] Two sessions exchange at least four rounds by automatic replies, each a new message with its own id, on any pair of chat surfaces (for example a terminal and a Webapp chat).
  - [ ] An answer that is `[SILENT]` as a whole, on its first or last line, or a reply block that is empty or `[SILENT]`, or an empty answer, sends nothing, and the record says "silent".
  - [ ] `[SILENT]` mid-sentence is sent as content.
  - [ ] The plugin has no hop, round, rate, duplicate, length or daily limit (intercom's four caps are removed), and no timer that ends an exchange.
  - [ ] The no-empty-replies rule and the instruction to answer `[SILENT]` when there is nothing new both appear, as written in `ux.md`, in the tool description and in every footer variant, the `ask` footer included.
- **Out of scope** — any cap or loop detector.
