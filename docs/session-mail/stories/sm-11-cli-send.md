# Story — Send a message from a cron job or script

- Id: `sm-11-cli-send`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` § "Command line"
- Person: a cron job or script (and Alex writing it)

## Required

- **As a** cron job or script
- **I want** `hermes intercom send --to … (--message … | --file …)` to deliver a message and tell me the result in one line and an exit code
- **So that** I can tell a session something without running a turn, and branch on what happened
- **Done when**
  - [ ] `send` takes `--to`, one of `--message`, `--file PATH` or `--file -`, and optional `--delivery` (default `steer`), `--from`, `--no-reply` and `--json`.
  - [ ] A delivery prints `message <id> → "<title>": <applied> (<reason>)`, with `asked: <requested>` when weaker, and exits 0.
  - [ ] Exit codes are 2 (usage: missing `--to`, neither or both of `--message` and `--file`, unknown `--delivery`), 3 (refused: ambiguous or unknown address, empty or whitespace-only body, own session), 4 (the host cannot take it), 5 (not delivered: no host, or not handed over), 6 (delivery unknown); error text goes to standard error.
  - [ ] `--json` prints the receipt object, on success and failure, with the same exit codes.
  - [ ] The header names the sender `hermes@script <--from>`, or `hermes@script cli` without `--from`.
  - [ ] `send` starts no turn in its own process.
- **Out of scope** — a `--wait` for the reply (use `status`); retries.
