Commit: c3ccdbb41e
Verdict: changes

Review of `docs/session-mail/passive.md` against the brief (`requests/2026-11-14-session-mail-passive-keyed-brief.md`), the deployed plugin (`plugins/intercom/`) and core. The approach works on the published API alone. Three things the plan promises or assumes don't hold in the code (findings 1-3), and the record design is missing its identity key and migration (findings 4-5). Everything else is should or minor.

## Answers to the six questions (short)

1. **Feasibility.** Yes. Every gateway-hosted turn goes through `build_turn_context` (`agent/conversation_loop.py:1699`), which calls `_collect_pre_llm_call_context` once per turn (`agent/turn_context.py:1339`). That covers Webapp/desktop/TUI/CLI chats, `prompt.submit`/queue turns, an idle session started by a steer, cron runs (`cron/scheduler.py:1989` → `run_conversation`) and resumed sessions. A steer into a *running* turn starts no turn and fires no `pre_llm_call` (`plugins/intercom/echo.py:377-381`), which is correct for "next turn". Forks with `_persist_disabled` (background review, `agent/background_review.py:1016`) skip the hook (`agent/turn_context.py:915-916`). The kwargs are `session_id` (the tip, after `recover_rotated_compression_session` at `:1238`), `turn_id`, `task_id`, `platform`, `parent_session_id` and `is_first_turn` (`:921-932`). The context is persisted: `_stamp_api_content_sidecar` writes it to the row's `api_content` (`:1093-1137`), it is persisted before the first call (`:1389`), and it is replayed byte-stable on later turns (`:1486-1494`). Exceptions: findings 2 and 8.
2. **Identity across compaction.** The plan doesn't address this. Finding 4.
3. **Exactly-once.** The plan's veto promise can't be implemented as written. Finding 2.
4. **Existing hooks.** The reply hook can't see held notes, and echo is undecided. Findings 1 and 7. The legacy drain and the reboot commands don't conflict (finding 10).
5. **Simplicity.** Section 6 verdicts are in finding 11. Reuse `messages` for the notes; add only one small table for `all` (finding 5).
6. **Missing pieces.** Findings 5, 6, 7, 9 and 12.

## Findings

### Blocking

**1. A `reply requested` passive note can never be answered: the reply hook won't see it.**
- `on_post_llm_call` scans only `turn_rows(user_message, conversation_history)` (`plugins/intercom/replies.py:134`, `:111-122`).
- `user_message` is `original_user_message`, the typed text (`agent/turn_finalizer.py:499`). Hook context lives only in that row's `api_content` sidecar, never in `user_message`.
- Even if the hook did see it, the section 3 frame (`[1] … reply requested (message 8c1f…)`) has no `📡 Not … message <id>):` … `📡 End of message <id>` span. It also has no `header_sha`, and `find_messages` needs both (`replies.py:57`, `:93-108`).
- Result: `requested` on passive, which the plan advertises in section 2, silently goes nowhere.

*Change:* the handover stores the turn id on each note it hands over. In `on_post_llm_call`, add those rows (looked up by the hook's `turn_id`, `agent/turn_finalizer.py:498`) to the candidates, then run the existing `_is_candidate`/`reply_for`/`_answer` path unchanged. No span or hash is needed: a turn-id lookup can't be spoofed by a typed lookalike. The section 3 wording stays.

**2. "If the turn is vetoed by another plugin before inference, the notes stay held" can't be done in `pre_llm_call`. And a one-step claim loses notes on some runtimes.**
- Hook results are collected in a loop (`agent/turn_context.py:938-953`). No hook sees another hook's veto, and intercom may run before the vetoing plugin.
- A veto then rewrites the row to the withheld placeholder and pops `api_content` (`:866-904`). So the notes are marked delivered but gone.
- The same happens on the opt-in `codex_app_server` runtime. It skips the sidecar (`:1385`), and `_codex_app_server_turn` never passes `plugin_user_context` (`agent/conversation_loop.py:1628-1633`), so the model never sees the block.
- The same happens on a `context_compression_timeout` turn, which drops this turn's row (`agent/turn_context.py:388`).

*Change, which is also the simplest correct rule for question 3:*
- (a) In `pre_llm_call`, in one `BEGIN IMMEDIATE`, select the target's pending notes and unseen `all` versions. Frame them and write `offered_turn = turn_id`. Don't mark them delivered.
- (b) In `pre_api_request` (already registered by echo, `plugins/intercom/echo.py:417`; its kwargs carry `turn_id`, `agent/turn_api_request.py:82`), on the first request whose `turn_id` matches, set `delivered_at` (and the `all` seen row) in one statement: `WHERE offered_turn = ? AND delivered_at IS NULL`.
- (c) A later `pre_llm_call` offers again any note whose offer was never confirmed.

How this handles each case:
- A veto, a codex-runtime turn or a preflight timeout makes no generic API request, so the notes stay held.
- If the model call fails after the request is built, the notes count as delivered. They are already in the persisted row and replayed on the next turn (`agent/turn_context.py:1389`, `:1486-1494`), so nothing is lost and nothing is shown twice.
- Two concurrent turns in different sessions touch different rows (per-target notes are lineage-scoped; `all` seen rows are keyed per session root), and `BEGIN IMMEDIATE` (`plugins/intercom/record.py:339`) serialises the rest. One session has one turn at a time.

The fallback is to keep the one-step claim at `pre_llm_call` and drop the veto sentence. Today no other plugin registers `pre_llm_call` (only `plugins/intercom/__init__.py:271` and `echo.py:416` do). But the codex-runtime loss would remain, so I recommend the two-step rule. Section 3's sentence becomes: "A note counts as delivered once the turn sends its first model request. A turn that never makes one leaves it held."

**3. `held` is already a stored result with a different meaning.**
`route.send` writes `result="held"` for a *queued* live message (`plugins/intercom/route.py:159`). Reusing it for passive notes makes `status`/`log` and any query on `result` ambiguous. *Change:* store passive notes as `result='pending'` → `'delivered'` | `'replaced'`. The receipt and CLI can still print "held", but the stored value must be distinct.

**4. The record must key on compaction lineage, not the raw session id. This applies to delivery, replacement and `all` seen-tracking.**
- At send time the target resolves to the compression *tip* (`plugins/intercom/address.py:185-200`). After a later compaction the running id is a new tip, so an equality match on `target_session_id` misses every note sent before the compaction.
- Delivery: match the hook's `session_id` through its lineage, as replies already do (`replies._lineage`, `plugins/intercom/replies.py:326-344`, with `record.by_target_lineage`, `plugins/intercom/record.py:244-266`).
- Replacement: "same target" means same lineage. Otherwise a keyed note sent before a compaction and one sent after it both stay pending, which defeats the 30-hour case in the brief.
- `all` seen-tracking: key on the lineage root (`SessionDB.get_compression_lineage(id)[0]`, `hermes_state_compression.py:916`). It is stable across every rotation. Forks and branches are their own roots on purpose (`hermes_state_compression.py:919-920`).

*Change:* add one paragraph to section 5 P1/P2 naming these three rules.

### Should

**5. The schema and migration are unspecified. Reuse `messages` for the notes and add only one table.**
- `_SCHEMA` is `CREATE TABLE IF NOT EXISTS` (`plugins/intercom/record.py:50-82`). On the deployed `record.db` it won't add columns, so the builder needs a guarded `ALTER TABLE ADD COLUMN` (checked with `PRAGMA table_info`) in `connect()`.
- Notes stay rows in `messages`, one per send. Add `note_key` and `offered_turn`. Reuse `delivered_at`, `result` (finding 3) and `detail` (`replaced by <id>`). `requested='passive'` already records the asked mode.
- An `all` note is **one** row (`address='all'`, `target_session_id` NULL). Don't fan out a row per session.
- Add one table, `note_seen(root_id, note_key, message_id, turn_id, delivered_at, PRIMARY KEY(root_id, note_key))`. A session gets the newest non-replaced `all` row for a key when `note_seen.message_id` differs.
- A per-session row in `messages` would have to fake its NOT NULL sender/body/reply fields, so don't put seen state there.
- `record._UPDATE_FIELDS` (`plugins/intercom/record.py:44-48`) needs the new fields, and the module docstring's writer list (`plugins/intercom/record.py:14-18`) needs the handover writer.

**6. `to: all` needs its own rules in the send path.** `route.send` assumes one resolved target: resolve → own-session → target scope → consent (`plugins/intercom/route.py:105-131`). The plan should state:
- `all` is matched before `address.resolve`. A session titled "all" becomes unreachable by title, the same as `Home`. Say so in the README.
- The sender's own lineage is excluded at handover.
- `target_chat_scope` and the shared-chat line are computed **per recipient at handover**, because there is no target at send time.
- `injection_allowed()` (`plugins/intercom/route.py:174`) is checked at send time for every passive note. It should also be checked at handover, because the handover is the injection. While it is off, notes stay pending; this is the existing consent rule, not a new hold.
- `to: all` requires `reply: none`. Otherwise one note asks every session to answer the sender. This is the one guardrail I'd add, because it protects something real.

**7. Echo to private chats needs a decision for the gate.**
- The trust model promises that a message to a private chat is posted into that chat "so you see what your session was told" (`plugins/intercom/README.md:169`).
- The echo hooks only find `📡 Not …` spans with a matching `header_sha` (`plugins/intercom/echo.py:455-469`), so a passive note would get **no** echo.
- `claim_echo` is per message row (`plugins/intercom/record.py:199-213`), so an `all` row could echo into only one chat.

*Proposal for the gate:* per-target passive notes echo at confirmed handover, using the existing escaper and claim. Keyed `all` status doesn't echo: it is the operator's own script output, and an hourly post into every DM would be exactly the noise this feature exists to avoid. One sentence in section 3 is enough.

**8. Some runtime paths need one sentence each.**
- The `codex_app_server` runtime never carries plugin context (finding 2). Under the two-step rule its notes just wait. Say so.
- Under MoA, context is composed per request but not stamped as a sidecar (`agent/turn_context.py:1385`, `:1488-1493`). The model sees the block for that turn only; later turns don't replay it. Acceptable, but write it down.
- Hook context over `hooks.output_spill.max_chars` (default 10,000; `tools/hook_output_spill.py:24`) is spilled to a file with a 500-char head and tail (`agent/turn_context.py:942-952`). A large backlog of un-keyed notes therefore arrives as a preview plus a path, and the `[REPLY <id>]` instructions in the middle can be cut off. This is not a cap, but section 3 should say it. Keep the "How to answer" line at the **top** of the block so it survives the head preview.

**9. The session-kind filter for `all` and for subagents needs a mechanism.**
- Section 3 says "Subagent turns are skipped" but not how. `parent_session_id` comes from `agent._parent_session_id` (`agent/turn_context.py:930`). It is a delegation field (`agent/session_persistence.py:447-455`), not a session kind.
- Cron and oneshot runs aren't mentioned. As written, every hourly cron run would get the subscription block at turn 1 (cron turns fire the hook, `cron/scheduler.py:1989`).

*Change:* at handover, read the session's `source` from SessionDB. Hand `all` notes only to sessions outside `address.RUN_SOURCES` (`plugins/intercom/address.py:28`), the same set `list` hides by default. Per-target notes go to whatever was addressed.

### Minor

**10. Hooks that don't conflict; state it in the plan.**
- The legacy drain `_on_pre_llm_call` is registered only together with the legacy inbox (`plugins/intercom/__init__.py:253-274`, `:339-340`).
- `delivery: passive` on the legacy path should be refused with `no-seam`, since gateway only is settled. Name it.
- The echo `pre_llm_call` returns `None` (`plugins/intercom/echo.py:420-422`). The new handover can live in the same module or a new `passive.py` registered beside it.
- `reboot-notice` steers into running turns, so no handover happens there.
- `resume-after-reboot` wakes sessions, and the held block lands after its framed message, which is correct.

**11. Section 6, rule by rule.**
- `key` only with passive: **keep**. It is a usage error, refused like `reply-missing` before a message id exists (`plugins/intercom/route.py:90-91`). "Allow and ignore" would hide a mistake.
- `to: all` only passive + keyed: **keep**. This is the 2026-11-14 operator rule, not a new guardrail. Move it out of the "added by this plan" table and add `reply: none` (finding 6).
- No `waiting`/`ask` with passive: **keep, but fix the reason**.
  - `waiting` doesn't block the sender: "your call returns; the answer arrives as a new message" (`plugins/intercom/__init__.py:98-100`). The real conflict is that the `waiting` frame tells the target "answer this first" (`plugins/intercom/frame.py:531-532`), while the passive block says "deal with them after what the turn is for".
  - `ask` is a separate action that blocks in process for at most 3600 s (`plugins/intercom/replies.py:240-262`), so a passive ask would always time out.
- P4 sends only when the line changed: **keep, but move it to P4**. It is script behaviour, not a plugin rule. Compare only the formatted line (no timestamps), or it never matches.

**12. Smaller gaps.**
- `status` for an `all` row must say something, e.g. `pending for all · seen by N sessions · replaced by <id>`. "Delivered <time> (and the session's turn)" doesn't fit a row with N handovers.
- Key matching is "any sender", so any peer session can overwrite `subscription-usage` for every session. That is acceptable because every sender is the operator's own session, but the guidance should say keys are a shared namespace and name `subscription-usage` as reserved for P4.
- P4 reads `~/.hermes/plugin-data/model-routing/state.json`. The script should use `$HERMES_HOME`, which matters for profiles. The file exists; its keys are `subscriptions`, `openrouter`, `pick` and others.
- P4 should name its sender label (`--from subscription-note`) and its last-sent state file.
- The tool schema change (`delivery` enum at `plugins/intercom/__init__.py:142`, new `key`) lands only at the settled restart (SM-Q28). `route.send` raises on any delivery not in `client.DELIVERIES` (`plugins/intercom/route.py:86-87`), so the passive branch must come before that check.
- Tests should include an E2E compaction case: send a note, compact the target, check the note is delivered once to the new tip. Also a two-step case: veto → stays pending; failed model call after the first request → delivered, not re-offered.
