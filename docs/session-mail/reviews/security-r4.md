Commit: 4e3bff6a39
Verdict: accept on trust boundaries

# Security gate, round 4 (delta): DER-701 session-mail

Read: `git diff 5119747616 4e3bff6a39 -- docs/session-mail/lld.md`. The other files in the range
(`ux.md`, stories, mockups, `reviews/security-r3.md`) are wording alignment; I did not re-review
them, as instructed.

## Round-3 notes

| Note | Status | Where |
|---|---|---|
| N1 | Handled | B1 step 1 reads the scope from the raw `platform`, `chat_id`, `chat_type` and `user_id`. The `restore_identity` re-pin is optional, and its `None` "never counts as no origin". I-1 tests a call with no runner: a group row gives `shared` and an owner DM gives `private` |
| N2 | Handled | B1 step 3: any read error gives `shared` unless the source was positively read as local, and a missing `sessions` row gives `shared`. I-1 covers a corrupt `origin_json` and a missing row |
| N3 | Handled | B8 step 2 and the R2-4 row now say "cannot be reproduced from the echo alone. It is not a secret", with the reason it is acceptable (echoes go only to `private` chats) |
| N4 | Handled, with one note | B8 `ask`: after a wake, the waiter re-reads the target's lease and binds to its pid. I-5 covers it. The fallback is in R4-1 |
| N5 | Handled going forward | Both commits in this range (`eac95661b3`, `4e3bff6a39`) are authored `hermius-maximus@users.noreply.github.com` |

Nothing else in the delta touches a trust boundary. The header, mockup and `ux.md` alignment
lines change no authority, egress or writer.

## Finding

### R4-1 — note: say how "the dashboard's registry entry" is identified in the N4 fallback

`lld.md`, B8 `ask`, "After a wake (N4)": "If no lease is there yet, it falls back to the pid of the
dashboard's own intercom registry entry for the same `hermes_home`."

Registry entries carry no dashboard role. Every field in them is self-asserted by the process that
wrote it (the reason for F11), so a choice based on entry fields alone could bind the waiter to
whichever same-UID process wrote a plausible entry. The impact is low, because it stays within
one OS user and the `request_id` is still required. But the binding should rest on something the
dashboard proves, as the gateway role rests on `get_running_pid()`.

**Fix (at Build, I-5):** take the pid that owns the loopback listening socket on
`127.0.0.1:<dashboard_port>`, or the dashboard's own pid record if one exists. Accept a registry
entry only when its `pid` equals that pid. If neither resolves, leave the waiter unbound to any
other pid, so the ask times out; that fails closed. Add that case to the I-5 wake test.

## Acceptance

Security's accept on trust boundaries stands at `4e3bff6a39`. R4-1 goes to I-5 at Build.
