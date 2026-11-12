# Relay skills

G11 (DER-726). Replacement text for the live relay skills. The manager applies it at
deploy (G12 step 4), after intercom is enabled and the gateway has restarted. The
builder does not edit the live skills.

`scripts/dashboard_dispatch.py` targets the admin dashboard, whose chats intercom
cannot reach. A relay uses `hermes intercom send`. Flags, the list line and the
success line below are that CLI.

## Where the manager applies it

Three live skills still deliver with `dashboard_dispatch` or `hermes chat -q`.
Replace those deliveries with [Send](#send). Leave every other section.

1. **session-relay.** Replace "Send a turn". Replace the send command in "Scheduled
   updates into a desktop chat", including the hourly floor and the 600 s timeout
   (those belonged to a `hermes chat -q` turn). In "Asks go up to the liaison",
   replace the push and the retry (every 2 minutes, up to 30 minutes) with one send.
   Replace the rules and pitfalls that name `dashboard_dispatch` as the way to
   deliver, including a one-at-a-time cap and "the dispatcher never interrupts".
   Leave the Claude Code section, and leave the bullet that re-checks a target
   before relaunching work.
2. **toolbox-sdlc-manager.** Replace the steer into a running session, and the
   liaison push (including its retry). A line that only creates a session is not a
   relay: see [What send does not do](#what-send-does-not-do).
3. **house-host-operations.** In the reference that tells a session to start or
   continue with `dashboard_dispatch`, replace the continue / deliver half with
   [Send](#send).

Apply this only in the live home. Do not copy it into a skill in this repo.

## Send

A shell, a cron job, or a recipe that used to run the dispatcher:

```
hermes intercom send --to SESSION (--message TEXT | --file PATH | --file -) [--reply none|requested|waiting] [--delivery interrupt|steer|queue] [--from LABEL] [--json]
```

A session that has the intercom tool uses the tool, so the message is from that
session. The CLI always sends as a script. The header says `hermes@script <label>`,
where `<label>` is `--from`, or `cli` when `--from` is omitted. The settled line
for the tool, in place of the dispatcher command:

> To message another session, use the intercom tool (if it is not in your tool list, tool_describe it, then tool_call it): action="send", to = a session id (from list or a receipt), an exact title or Home, reply = none (a note), requested or waiting (required), message = your text. Write only something new; an answer comes back as a message.

The tool's `list` and `hermes intercom list` show the same ids. `reply` is required
on the tool and has no default. On the CLI it defaults to `none`. The shell recipes
below are the CLI. A session that cannot call the tool uses the CLI and sets
`--from` to its title. Answers to that send are stored and wake nothing; read them
with `hermes intercom status MESSAGE_ID`. A debate needs the tool.

The command starts no turn in the sending process. The target's chat stays usable.
The header names the sender and says it is not Alex. Write the message itself. Do
not add a second "not Alex" banner.

### Session id

```
hermes intercom list [--query TEXT] [--include-runs] [--limit N] [--json]
```

One line per session, newest first. Fields are separated by two spaces, in this
order: session id, title, project, last active, state (`running`, `idle` or
`closed`). A missing project or time is `—`. The lines are not padded.

```
local-7f3a91c2  Hermes Improvement — Orchestrator  hermes-improvement  2 min ago  running
local-1b9e04d7  Budgeting — Orchestrator  budgeting  now  idle
local-c0ffee21  Home  —  1 h ago  closed
```

`--to` is the session id, the first field. Pass that id. An exact title, or
`Home`, also addresses a session. A receipt's `target_session` (the `--json`
receipt) is the same id. `--query` filters on title or project, not on the id.
Cron, subagent and oneshot runs are left out unless `--include-runs`. `--limit`
defaults to 30 and only limits how many lines print.

`@<project>` is refused while project addressing is absent (exit 3):

```
Project addressing is not available on this Hermes. Use list (filter by project) and address the session by id.
```

No session is renamed. A title is whatever `hermes intercom list` prints.

### Flags

| Flag | Meaning |
|---|---|
| `--to` | Required. The session id from `hermes intercom list`, an exact title, or `Home`. |
| `--message` | The text. Pass this or `--file`, not both, and not neither. |
| `--file` | Read the text from `PATH`, or from stdin with `--file -`. Use this for a long body. |
| `--reply` | `none` (default), `requested`, or `waiting`. |
| `--delivery` | `interrupt`, `steer` (default), or `queue`. |
| `--from` | Script label in the header. Default `cli`, so the header says `hermes@script cli`. A cron job passes its name. |
| `--json` | Print the receipt as JSON on success and on a refusal or error (exit 3–6). The exit code does not change. Errors still go to stderr. A usage error (exit 2) prints nothing to stdout. |

`--reply none` is a note: nothing comes back. `--reply requested` asks for an
answer. `--reply waiting` means the sender needs the answer before going on; the
command still returns at once, and a session is woken with a new message. A script
has no session to wake. It reads a stored answer with
`hermes intercom status MESSAGE_ID`.

Omit `--delivery` for steer. Queue when the message can wait. Interrupt only for
this reason, word for word: Only use interrupt when you intend to stop what the
other session is doing right now (it is wrong, or the work is obsolete). Otherwise
use steer (default) or queue.

An idle target starts a turn. A target that is not open is reopened by the gateway.

### What a send prints

Success is one line on stdout, exit 0:

```
message 7c1d02ab → "Hermes Improvement — Orchestrator": steered (into its running turn)
```

The phrase is one of:

- `steered (into its running turn)`
- `queued (asked: steer; the steer was refused, runs after its current turn)` when the mode you asked for was refused and queue was used. The phrase names that mode.
- `queued (runs after its current turn)` when `--delivery queue` was asked for
- `interrupted (redirected its running turn)`
- `interrupted (stopped its running turn; runs next)`
- `started (was idle; a turn started)`
- `started (was not open; the gateway reopened it and a turn started there)`

Refusals and errors go to stderr. Exit codes:

| Code | Meaning |
|---|---|
| 0 | Delivered: interrupted, steered, queued or started |
| 2 | Usage: missing `--to`, neither or both of `--message` and `--file`, unknown `--delivery` or `--reply`, or `--file` cannot be read |
| 3 | Refused: unknown or ambiguous address, empty or whitespace-only body, your own session, a project address that cannot be used, or `no-owner-set` |
| 4 | `not-addressable`, `injection-off`, `refused-by-owner`, or `no-seam` |
| 5 | `no-owner`, `owner-restarting`, or `not-reachable` |
| 6 | Delivery unknown: handed over, no result recorded |

An admin-dashboard chat is exit 4. The stderr line is:

```
"<title>" is open in the admin dashboard, which intercom cannot reach. Nothing was sent.
```

On exit 5, the gateway is not there. Say so. Do not deliver with `hermes chat -q`
or `dashboard_dispatch.py`. On exit 6, run `hermes intercom status` with the
message id and follow what it prints.

### Examples

A cron note. `--reply` and `--delivery` are the defaults, `none` and `steer`:

```
hermes intercom send --to local-7f3a91c2 --from nightly-backup --message "Backup finished: 3.2 GB, 0 errors."
```

A long note from a file, asking for an answer:

```
hermes intercom send --to local-1b9e04d7 --reply requested --file note.txt --from nightly-backup
```

The same body on stdin:

```
hermes intercom send --to local-1b9e04d7 --reply none --from nightly-backup --file -
```

### Scheduled update

Send it into the session where the job was set up. Take that session's id from
`hermes intercom list`. One send. The body can tell that session to post the update
to Alex. `--reply none`, because the update is a note.

```
hermes intercom send --to SESSION --reply none --from CRON_NAME --file update.md
```

A send does not take ownership of the chat. It can land while someone is typing
there. Steer is the default, so it joins the running turn.

### Liaison push

The asks file stays the record. The push is one send of a short note: who is
writing, the file path, and the question ids. `--from` is the child session's
title. `--reply none`.

```
hermes intercom send --to LIAISON_ID --reply none --from "CHILD TITLE" --file note.txt
```

A busy liaison is steered, or queued when the steer is refused. The command prints
which. One send. The liaison still reads the file.

### Scope change into a running session

Point the note at the brief section and say it relays Alex's decision. Fold it in
at the next natural point. Do not restart the session.

```
hermes intercom send --to SESSION --reply none --delivery steer --file note.txt --from "SENDER TITLE"
```

`--delivery steer` is the default and can be omitted.

### Rules

- Write only something new. No thanks, "got it", "agreed", restating, or "I'll look later". If you have nothing new, do not send.
- A session that was asked for a reply and has nothing new ends its turn with `[SILENT]`. Nothing is sent.
- Debates are allowed. With the tool's `reply = requested` or `waiting`, an answer comes back as a new message. A CLI send is from a script: its answer is stored and wakes nothing; read it with `hermes intercom status MESSAGE_ID`. A `none` note gets nothing back.
- Default delivery is steer. Queue when the message can wait. Interrupt only with the sentence above.
- Do not send an empty or whitespace-only body.
- Batch questions into one message.
- Address a session by the id from `hermes intercom list`. An admin-dashboard chat is not a target.

## What send does not do

`hermes intercom send` delivers into a session that already exists. It does not
create a session, set its directory, or set its title.

`dashboard_dispatch.py --title` / `--cwd` starts a chat in the admin dashboard.
Intercom cannot reach that chat. Do not start a session there when a later relay
must address it. Create the owner session by the means already used for an owner
session. Then take its id from `hermes intercom list` and send the kickoff, and
every later message, with the command above. A session that is not open is
reopened by the gateway. The success line then says
`started (was not open; the gateway reopened it and a turn started there)`.
