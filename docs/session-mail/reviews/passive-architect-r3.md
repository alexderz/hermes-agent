Commit: ae67c282e7
Verdict: changes

Round 3 review: the operator's addition of keyed queue (`git diff 2515729e2b HEAD -- docs/session-mail/passive.md`). Keyed passive is unchanged; my round-2 points were folded in at 2515729e2b and I did not re-check them here.

The behaviour the operator asked for is sound. P5's trigger is not: `on_session_end` does not fire at the end of every turn. It is skipped on exactly the paths P5 claims to cover (interrupted and failed turns). As a result, the plan needs a "running?" check, two sweeps and a turn-end race fix to work around it. A simpler design uses Hermes's own queue for timing and session mail's record for content. It reuses P2, and needs no turn-end hook, no running check and no sweep (finding 2).

## Answers to the questions

### 1. Does `on_session_end` fire at the end of every gateway turn, with the session id?

**No.** It fires only from `finalize_turn` (`agent/turn_finalizer.py:886-897`). When it fires, its kwargs are `session_id` (the agent's current id, so the new tip after a mid-turn compaction), `turn_id`, `completed`, `failed`, `interrupted`, `turn_exit_reason` and `platform`.

`finalize_turn` has exactly one caller, `_finalize_from_state` (`agent/conversation_loop.py:1609-1613`). Every path that returns a result directly bypasses it:

| Turn kind | Bypass |
|---|---|
| Interrupt during an API call or its retry wait | `abort_turn_on_interrupt` via `_verdict("return", …)` (`agent/turn_api_error.py:171`, `:435`), returned at `agent/conversation_loop.py:1603` |
| Non-retryable client error | `agent/turn_api_error.py:363` |
| Retries exhausted | `agent/turn_api_error.py:412` |
| Other early results | `agent/conversation_loop.py:1746`, `:1760`, `:1773`, `:1784`, `:1791` |
| Terminal partial exits | Commented "This path never reaches finalize_turn" (`agent/turn_tool_validation.py:56-59`, `agent/turn_truncation.py:448`, `:510`) |
| Preflight-compression timeout | `agent/conversation_loop.py:1719` |
| Codex app-server turns | `agent/conversation_loop.py:1625`, `:1638` |

Outside `run_conversation`, the hook also never fires when:
- an exception escapes it (caught by the owner at `tui_gateway/prompt_turn.py:1215-1216`);
- a turn is refused before it starts (`tui_gateway/prompt_turn.py:1150-1151`, `:1195-1201`);
- the agent has `_persist_disabled` (`agent/turn_finalizer.py:886`).

So "end of every turn, interrupted ones included" (`passive.md` P5) is false for the cases that matter most. A keyed queued message held while its target's turn is interrupted mid-request, or fails, is never handed over until something else happens.

### 2. Is it safe to call the owner client from inside `on_session_end`?

**Yes, there is no deadlock.**
- The hook runs on the turn thread inside `_invoke_agent`. That thread does not hold `history_lock`, which it takes only in `run_body`'s `finally` (`tui_gateway/prompt_turn.py:1228`).
- `deliver_sync` runs `asyncio.run` on its own thread and talks to the owner over its socket (`plugins/intercom/client.py:24-26`, `:101-114`).
- At that moment `session["running"]` is still `True`; it is cleared later, at `tui_gateway/prompt_turn.py:1238`.
- So `prompt.submit{queued}` takes the busy path and is queued (`tui_gateway/methods_prompt.py:894-912`, `tui_gateway/session_auto_continue.py:400-406`). It is then drained first among the post-turn follow-ups (`tui_gateway/prompt_turn.py:1280`, `tui_gateway/session_auto_continue.py:457-466`).

**But it must be deferred to a daemon thread.**
- `deliver_sync` joins its worker (`plugins/intercom/client.py:111`). It would block the turn thread for discovery (up to 2 s, `client.py:57`) plus two RPCs, before `message.complete` is emitted (`tui_gateway/prompt_turn.py:1209`).
- The reply hook already defers for the same reason (`plugins/intercom/replies.py:210-212`).
- A deferred submit may land after `running` is cleared. It then starts a turn directly (`tui_gateway/methods_prompt.py:895-897`), which is also correct.

### 3. Is "running" known reliably at send time?

**No.**
- `route.send` never sees it. `deliver_sync` does the `session.resume` and the submit as one call and returns only the outcome (`plugins/intercom/client.py:10-11`, `:64-75`).
- `_is_live` asks `session.list` whether the session is open, not whether it is running (`plugins/intercom/route.py:332`).
- P5 would need a new resume-only read, and that read races (question 4).

### 4. The race: a keyed queued send arriving exactly as the turn ends

There is a window between `on_session_end` (`agent/turn_finalizer.py:888`) and `running = False` (`tui_gateway/prompt_turn.py:1238`). A send in that window:
1. reads "running";
2. stores its row as pending;
3. waits for a turn end that has already fired.

The row is stranded. No turn starts until something else wakes the session.

### 5. The restart/crash sweep

- **"At plugin start":** `register()` runs while the gateway is loading, before the owner serves RPCs. `deliver_sync` would get `no-owner`/`owner-restarting` (`plugins/intercom/client.py:6-7`, `:42-43`) and would block boot. The sweep would have to be a thread that waits for the owner, as `resume-after-reboot` does (`plugins/intercom/README.md:162`).
- **"At each send":** one resume RPC per held row on every send. It races `on_session_end`, and it exists only to cover the gaps in question 1.

### 6. Lineage

P5 already matches on lineage, which is right: the hook's `session_id` is the tip after rotation. Any wake sent later must resolve the target's current tip at that moment (`plugins/intercom/address.py:196-200`), not the id stored at send time.

### 7. Replacement across modes

"Its own mode then applies" (`passive.md` §2, Keys) is fine while nothing has been handed to Hermes. Once a wake is in Hermes's queue, a plugin cannot withdraw it. The plan needs a rule for that case (finding 4).

## Findings

### Blocking

**1. P5's handover trigger misses interrupted, failed and other turns.**
Evidence is under question 1. Because of these gaps, P5 also needs the running check (question 3), the per-send sweep (question 5) and a turn-end race fix (question 4). *Change:* replace the trigger with finding 2. If the manager keeps `on_session_end`, the plan must still add all three of:
- a deferred submit;
- a fix for the turn-end window (after storing, re-check from a thread that waits until the target is idle);
- a fallback for every bypass path listed under question 1.

### Should

**2. Simpler design with the same behaviour: let Hermes's queue time the turn, and let the record supply its content.**

How it works:
- **Store.** A keyed queued send is stored like a keyed passive note: `pending`, `note_key`, and the same replacement transaction. It also carries a wake marker, e.g. a `wake_admission` column.
- **Send.** In the same `BEGIN IMMEDIATE`: if no earlier pending row with this key already has an outstanding wake, this send submits one after commit. The wake is a framed session-mail message, built by `frame.build` with its `header_sha` recorded (`plugins/intercom/route.py:138-150`), saying "keyed update `<key>` from `<sender>`; the current version follows". It goes through the ordinary queue path: `deliver_sync(target, wake, "queue", submission_id)`.
  - An idle target starts at once and a busy one queues, as plain queue does (`plugins/intercom/client.py:14-15`).
  - No running check is needed.
- **Handover.** When the wake's turn starts, P2's `pre_llm_call` finds the wake span in `user_message`, using the existing span finder (`plugins/intercom/replies.py:93-108`, as echo does at `plugins/intercom/echo.py:420-422`). It offers the newest pending row for that key and lineage as the turn's context, with offer and confirm exactly as P2 already specifies.
- **Replies.** Answers come back through the turn-id lookup. Because this turn exists for the message, the reply uses the normal `requested` branch, not the passive block-only branch.

Why it is simpler and correct:

| Concern | Result |
|---|---|
| The race | Gone. The send's transaction and the wake turn's claim are both `BEGIN IMMEDIATE` (`plugins/intercom/record.py:339`). If the send commits first, it replaces the row and inherits the wake, and the turn shows the newest version. If the claim commits first, the wake is used up, the send sees no outstanding wake and queues a new one. That is a second turn, which is correct because the information arrived after the first turn started. |
| Turn-end coverage | Not needed. Hermes drains its queue after every turn, including turns that raised (`tui_gateway/prompt_turn.py:1215-1216` then `:1280`). |
| Sweeps | None. |
| New hooks | None. |
| Running check | None. |

Restart: Hermes's queue is in memory (`session["queued_prompts"]`, `tui_gateway/session_auto_continue.py:467`), so a wake is lost on restart, as a plain queued message is today. At `register()`, clear outstanding wake markers; no RPC is needed. The pending row then rides the target's next turn as a passive note, which is better than plain queue, which loses the message. If the operator wants a wake after restart, keep only a deferred, owner-waiting sweep at start and drop the per-send one.

Cost: the turn's prompt is a session-mail line, not the message text. The text arrives after it, in the same user message, which is core behaviour.

**3. `key` with `ask` must be refused.**
- `ask` takes a `delivery` (`plugins/intercom/replies.py:251-253`) and its waiter is keyed by message id (`:246-249`). A replaced ask would leave its waiter to time out.
- §2's rule covers only steer and interrupt. *Change:* "`key` with `ask`: refused (the asker waits on that exact message)."

**4. Write the cross-mode replacement rule for an outstanding wake.**
- Under finding 2, a passive note replacing a queued row whose wake is already in Hermes's queue cannot cancel that wake. The wake turn then carries the newest version of the key, here the passive note.
- *Change:* "A wake already queued still runs and carries the newest version of the key." Alternatively, scope keys by mode, `(lineage, key, mode)`, so passive and queued never replace each other. That is simpler to state and test, and nothing in the operator's request needs cross-mode replacement. I lean towards scoping by mode.

### Minor

**5. Receipts and status for keyed queue.**
- A busy target's receipt should say `queued (replaceable, key <k>)`, not `held`. `held` is the passive word, and the receipt to an idle target already says "started".
- `status` reads `replaced by <id>`, or `delivered <time>` with the turn.
- Plain `queue` keeps its stored `result='held'` (`plugins/intercom/route.py:159`). Keyed rows use `pending`, as passive does.

**6. Echo for keyed queue.** In a private chat the echo should post the newest version at confirmed handover, using the per-target passive echo text. It should not post the wake line, which the existing echo would otherwise find and post (`plugins/intercom/echo.py:455-469`). Give the wake frame no echo, e.g. by skipping rows that carry a wake marker.

**7. Tests for P5** (whichever trigger the manager chooses):
- a keyed send at the exact moment the turn ends, done by holding the record transaction;
- a turn interrupted during its API call;
- a non-retryable API error;
- a gateway restart with an outstanding wake;
- cross-mode replacement, under the rule picked in finding 4;
- `key` with `ask` refused.

The plan's current "interrupted turn still hands over" test would fail on `main` with the `on_session_end` trigger when the interrupt lands during the request (`agent/turn_api_error.py:171`).

## Verdict

Changes. Replace P5's trigger (finding 1) with the queue-timed design in finding 2, or keep `on_session_end` and add all three items listed under finding 1. Add the `ask` refusal (finding 3) and the cross-mode rule (finding 4). Keyed passive and the rest of the plan stand as they were in round 2.
