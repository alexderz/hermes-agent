Commit: 228bb7044a
Verdict: changes

Round 2 review of `docs/session-mail/passive.md` (diff `c3ccdbb41e..228bb7044a`). All twelve round-1 findings are written into the plan, and eleven are written correctly. The exception is the reply path (round-1 finding 1): the reply now finds the right notes but would send back the wrong text. That is new blocking finding 1, and it needs one sentence and one branch in `replies.reply_for`. The other new findings are a should (`all` offer state, a gap in round-1 finding 2) and builder-level detail. With finding 1 fixed I would call it ready for the gate.

## Round-1 findings, checked against the revision

| # | Round-1 finding | Where it is now | Status |
|---|---|---|---|
| 1 | Reply hook can't see passive notes | §3 "Answers" (`passive.md:56`), P2 (`:77`) | The notes are found by turn id, but the text sent back is wrong: new finding 1. The plan should also say only *confirmed* notes count (new finding 4). |
| 2 | Veto / codex runtime / timeout loses notes | §3 "When a note counts as delivered" (`:54`), P2 (`:77`) | Correct for per-target notes. Turn ids are unique per turn (`agent/turn_context.py:646-648`). `pre_api_request` carries the turn id (`agent/turn_api_request.py:82`) and doesn't fire for auxiliary calls such as turn-start compaction (`hermes_cli/plugins.py` VALID_HOOKS comment, `pre_auxiliary_call`). The offer state for `all` notes is not specified: new finding 2. |
| 3 | `held` already means queued | P1 (`:76`): stored `pending` → `delivered` \| `replaced`; receipt still says "held" | Correct. |
| 4 | Lineage keys | §3 "Identity across compaction" (`:58`) | Correct. Edge case: new finding 5. |
| 5 | Schema and migration | P1 (`:76`) | The design is right. The builder needs two mechanics spelled out: new finding 3. |
| 6 | `to: all` rules | §2 (`:22-23`, `:28`, `:34`), §3 "Who gets `all` notes" (`:60`) | Correct: `reply: none`, `all` as a reserved address, per-recipient handover rules, consent checked at send and at handover, sender's own lineage excluded. |
| 7 | Echo | §3 "Private messaging chats" (`:62`), P2 (`:77`) | Correct. The builder needs a passive echo text, because `echo.echo_text` builds from a live span header (`plugins/intercom/echo.py:445-449`). Covered by new finding 6. |
| 8 | codex runtime, MoA, spill | `:52`, `:54` | Correct. The top line of the block is about 330 characters, inside the 500-character head the spill keeps (`tools/hook_output_spill.py:25`). |
| 9 | Which sessions get `all` | `:60`, P2 (`:77`) | Correct: by session source outside `RUN_SOURCES` (`plugins/intercom/address.py:28`). |
| 10 | Legacy path | §2 (`:26`) | Correct: passive is refused `no-seam`. |
| 11 | Section 6 rules | §6 (`:84-95`) | Correct. The operator's rule is split out from the plan's own rules, `reply: none` is added, and the `waiting` reason is fixed. |
| 12 | Smaller gaps | `:30`, `:32`, `:79`, `:80` | Correct: status for `all` notes, shared key namespace, `$HERMES_HOME`, `--from subscription-note`, state file, timestamp-free comparison, compaction/veto/failed-call/reply tests. |

## New findings

### Blocking

**1. A `reply requested` passive note would send the target's whole answer back to the sender.**
- The block tells the target: "Answer a "reply requested" note inside [REPLY <message id>] … [/REPLY]; nothing else goes back" (`passive.md:41`). §3 says such a note is "answered like live mail" (`:56`).
- Live mail falls back to the whole answer when there is no block. For `requested`/`waiting`, `reply_for` takes `answer.strip()` as the reply unless the sender is in a shared chat (`plugins/intercom/replies.py:166-174`).
- For live mail that fallback is right, because the turn exists for the message. A passive note rides a turn that exists for something else: the operator's typed request, a cron prompt, a reboot resume.
- Example: Alex asks a session about a deploy. The turn also carries a held `requested` note. The model answers Alex without a `[REPLY]` block. The whole answer, written for Alex, goes to the note's sender as "the reply", and that violates the block's own promise. With two such notes, it goes to both senders.

*Change:*
- §3 "Answers": "A passive note is answered only by its `[REPLY <id>]` block. With no block, nothing is sent and the row is marked `no-block`, as for `optional`."
- P2: in `reply_for`, passive rows take the existing `optional` branch (`replies.py:167-169`).
- Add a test: passive `requested` note, answer without a block → nothing delivered, `reply_state='no-block'`.

### Should

**2. Offer and confirm for `all` notes can't use `messages.offered_turn`.**
- An `all` note is one row shared by every session (`passive.md:76`). If each session's `pre_llm_call` wrote `offered_turn` on that row, concurrent sessions would overwrite each other.
- The confirm statement quoted in P2 (`WHERE offered_turn = ? AND delivered_at IS NULL`, `:77`) would then confirm the row for one session only, and mark the shared row delivered.

*Change: P2 states the per-session rule for `all`, kept in `note_seen`.*
- **Offer:** upsert `note_seen(root_id, note_key) := (message_id, turn_id, delivered_at NULL)`.
- **Confirm:** `UPDATE note_seen SET delivered_at = ? WHERE root_id = ? AND turn_id = ? AND delivered_at IS NULL`.
- **Unseen means:** the newest pending `all` row for the key has a `message_id` different from the session's `note_seen` row, or that row's `delivered_at` is NULL.
- **Scope of `offered_turn`:** it is per-target only. The `all` row's `result` stays `pending` until it is replaced.
- **Status:** "handed to N" counts `note_seen` rows with that `message_id` and `delivered_at` set.
- **Replacement:** P1's "mark the lineage's pending row with that key `replaced`" (`:76`) becomes, for `all`: "mark the pending `all` row with that key `replaced`".

### Minor

**3. Migration mechanics.**
- `connect()` runs on every record call, in more than one process (gateway and CLI). `_open_lock` is per process only (`plugins/intercom/record.py:36`, `:93`). Two processes that both see a missing column will both run `ALTER TABLE`, and one fails with "duplicate column name". Do the check and the `ALTER` inside `BEGIN IMMEDIATE`, or treat that error as success.
- `_SCHEMA` runs through `conn.execute` (`record.py:109`), which accepts one statement only. The `note_seen` `CREATE TABLE` needs its own `execute`, not a second statement in the same string.

**4. The reply lookup should require confirmation.** Use "handed over in that turn" = `offered_turn = turn_id AND delivered_at IS NOT NULL`.
- `post_llm_call` also fires for a vetoed turn, through finalize (`agent/conversation_loop.py:1620-1622`, `agent/turn_finalizer.py:495`).
- An unconfirmed offer must not become a reply candidate.

**5. A note replaced in the middle of a turn.**
- Sequence: turn T offers keyed note A, a new A′ arrives and marks A `replaced`, then T's first request confirms. The model saw A this turn and gets A′ next turn, which is the right behaviour.
- Rule to write down: confirm sets `delivered_at` on the row regardless, but `result` stays `replaced`.
- Status for that row: "replaced by A′ (handed over in turn T)".

**6. Builder details to put in the plan.**
- **Lineage root fallback:** at hook time the session row already exists (`_ensure_session_row` `agent/turn_context.py:1328` runs before the hook at `:1339`). But `get_compression_lineage` returns `[]` for a missing row (`hermes_state_compression.py:919-921`). Fall back to `session_id` as the root.
- **User name:** the sample block hardcodes "not from Alex" (`passive.md:41`). The frame should use the configured user name through `frame._consent` (`plugins/intercom/frame.py:418`), as live mail does.
- **Echo text:** the echo for passive notes needs its own text (header line plus relabelled body). `echo.echo_text` needs a live span (`plugins/intercom/echo.py:445-449`).

**7. Known residual double-show (accepted, but say so).** A turn can persist its user row with the block (`agent/turn_context.py:1389`) and then stop before its first model request, for example on an interrupt. The note is then re-offered and appears twice. That is the right way to err, but §3's "nothing is lost or shown twice" (`passive.md:54`) should be limited to failures after the request is built.

## Verdict

Changes: only finding 1 is blocking, and its fix is one sentence in §3 plus one branch in `reply_for`. Fold in finding 2 as well, and it is ready for the gate. Findings 3-7 can go in the LLD.
