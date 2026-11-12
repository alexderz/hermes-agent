# Story — Debate until there is nothing new, then [SILENT]

- Id: `sm-07-silent-ends-exchange`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` (J2, F8)
- Person: two sessions in a debate; Alex reading it afterwards

## Required

- **As a** session in an exchange with another session
- **I want** to keep answering for as long as I have something new, and to end it by writing no reply block (or a `[SILENT]` one)
- **So that** a debate can run its course with no counter cutting it short, and ends without empty "agreed" ping-pong
- **Done when**
  - [ ] Two sessions exchange at least four rounds, each answer to a reply written as an explicit `[REPLY <id>]` block, each a new message with its own id, on any pair of chat surfaces (for example a terminal and a Webapp chat).
  - [ ] A reply answered with no block sends nothing. An answer that is `[SILENT]` as a whole, on its first or last line, or a reply block that is empty or `[SILENT]`, or an empty answer, sends nothing, and the record says "silent".
  - [ ] `[SILENT]` mid-sentence is sent as content.
  - [ ] The plugin has no hop, round, rate, duplicate, length or daily limit (intercom's four caps are removed), and no timer that ends an exchange.
  - [ ] The no-empty-replies rule and the instruction to answer `[SILENT]` when there is nothing new both appear, as written in `ux.md`, in the tool description and in every footer variant, the `ask` footer included, except the `reply: none` footer, where nothing can go back (it says "No reply is needed and none will be sent").
- **Out of scope** — any cap or loop detector.
