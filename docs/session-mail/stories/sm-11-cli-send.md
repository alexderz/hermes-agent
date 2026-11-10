# Story — Send mail from a cron job or script

- Id: `sm-11-cli-send`
- HLD / UX: `docs/session-mail/hld.md`, `docs/session-mail/ux.md` § "Command line"
- Person: a cron job or script (and Alex writing it)

## Required

- **As a** cron job or script
- **I want** `hermes session-mail send --to … (--message … | --file …)` to deliver mail and tell me the result in one line and an exit code
- **So that** I can tell a session something without running a turn, and branch on what happened
- **Done when**
  - [ ] `send` takes `--to`, one of `--message`, `--file PATH` or `--file -`, and optional `--from`, `--no-reply` and `--json`, as in `ux.md`.
  - [ ] A delivery prints `mail <id> → "<title>": <steered|queued|started> (<reason>)` on standard output and exits 0.
  - [ ] Exit codes are 2 for usage errors, 3 for a refused address, 4 for a target held by a command-line session, and 5 for an unreachable dashboard or another delivery error; error text goes to standard error.
  - [ ] `--json` prints one object with the mail id, target title and id, and result, on success and on failure, with the same exit codes.
  - [ ] The header names the sender `script "<--from>"`, or `script "cli"` without `--from`.
  - [ ] `send` starts no turn in its own process.
- **Out of scope** — a `--wait` for the reply; retries; sending to several targets at once.
