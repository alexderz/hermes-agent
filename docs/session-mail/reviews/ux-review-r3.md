# UX review, round 3: session-mail (DER-701)

Reviewer: UX reviewer (designer role, review loop only). Date: 2026-11-09.
Under review: `docs/session-mail/ux.md` and `docs/session-mail/stories/` at commit `f3e2c0e9d5`
(the diff from `395f5fb668`). The working tree has no changes to these files; `poc/` is untracked
and out of scope. Requirements are the same as in rounds 1 and 2.

## Round-2 findings

| # | Round-2 finding | Status |
|---|---|---|
| R2-1 | "Check status" could not be acted on | **Fixed.** `status` now reads the target's transcript, read only, and says found or not found (`ux.md:319-324`, F3 at `ux.md:87-88`). The tool result says what to do in each case (`ux.md:177`). The two error codes now split where the steer or submit call is sent (`ux.md:176`, `:302-303`). Architect item 4 carries both points as HLD changes. sm-12 and sm-15 have matching Done-when lines. |
| R2-2 | F9's `status` label depended on an unknown hook call | **Fixed.** The core rule (no reply, no one woken) holds either way. The label is conditional (`ux.md:106`, `:331`, sm-10). Architect item 3 states the precondition and asks for confirmation before Spec. |
| R2-3 | sm-06 contradicted the fallback rule | **Fixed.** It now says "for a mail that has its own block …", which matches `ux.md:243` and HLD D3 step 2. |
| R2-4 | Relabel every body line that starts with 📨 | **Fixed** (`ux.md:208`, sm-05, architect item 1). |
| R2-5 | sm-05 excluded replies | **Fixed.** |

The new text adds no cap, hold, retry, gate or pending state. The transcript check is a read, and
the text says so (`ux.md:324`). Nothing gives mail Alex's authority or invites empty
acknowledgements. Every "For the architect" item is flagged as an HLD change.

## New findings (minor, not blocking)

### R3-1. The transcript check should match the mail's header, not any `mail <id>` text

- **Where:** `ux.md:319` ("a user row that holds `mail <id>`"), architect item 4, sm-12.
- **What happens:** a user row in the target can contain `mail 3f2a9c` without being that mail.
  For example, Alex might quote it, or another mail's body might mention it. Matching any
  occurrence would print "found" for a mail that never landed. The sender would then not send
  again, and the mail would be lost without anyone knowing.
- **Fix:** match the way D3 does. Look for that mail's header line 1 (`📨 Mail (not Alex) …` or
  `📨 Reply (not Alex) …` ending `· mail <id>`) at the start of a line in a user row. Relabelled
  lookalikes then cannot match.

### R3-2. The "not found" advice depends on things the sender cannot see

- **Where:** `ux.md:321` (the compaction exception), and `ux.md:317` together with the
  plain-`unknown` case at `ux.md:88`.
- **What happens:** the senders can't act on the advice as written.
  - **The compaction exception.** The advice says "if the target was compacting, run `status`
    again a minute later". The sender cannot know whether the target was compacting.
  - **Sends still under way.** A `status` on a plain `unknown` mail can run while another process
    is still sending it, for example during a start that takes minutes. It can print "not found",
    and the line goes on to say that "sending again will not duplicate it". That is not true while
    the first send is still running.
- **Fix:** make the advice something the sender can act on without knowing the target's state.
  - For example: "`not found in the target's transcript (yet)`: if the send ended less than a
    minute ago, or the delivery is still `unknown`, run `status` again in a minute before sending."
  - This is advice to the reader, not a timer or a hold.

Verdict: meets requirements
Reviewed: ecca6044f8d5621e6cf7a559d0bc9d3dd89837c1b26d813647d98267d6879485
