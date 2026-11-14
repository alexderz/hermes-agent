# Session mail: passive delivery and keyed notes (Plan)

Status: Plan, round 3 (architect reviews folded in: `reviews/passive-architect-r1.md`, `reviews/passive-architect-r2.md`), for the operator's Plan/UX gate. Brief input: the vault's `requests/2026-11-14-session-mail-passive-keyed-brief.md` (operator's words, 2026-11-14). Everything settled for session mail stays settled: no caps, holds, retries or approval gates on delivery; gateway only; no core behaviour patch (published plugin API only); reply modes; `[SILENT]`; no general notifications or forwarding (2026-11-14).

## 1. What it does

A sender can mark a message **passive**: it does not wake, steer, queue or interrupt the target. Session mail keeps it in its record. The next time the target starts a turn, for any reason (the operator types, another message wakes it, a resume after reboot), session mail hands over every note held for it, oldest first, in that turn.

A passive note can carry a **key**. A new passive note with the same key for the same target replaces the held one: the older note leaves the pending list (kept in the record as `replaced`), and the new one takes the newest place. An hourly status sent to a session that sleeps 30 hours is one note when it wakes, not 30.

A keyed passive note can go to **`all`**: one note that every conversation session gets, newest version only, once, at its next turn (SM-Q27). The hourly subscription status uses it.

Mechanism: the published `pre_llm_call` hook, which runs once at the start of every turn of every gateway-hosted session; its text rides in that turn's user message and is replayed in later turns. Core puts hook text after the typed message, not before it.

## 2. How a sender uses it

Tool: `intercom(action="send", to=<id|title|Home|all>, message=..., reply=..., delivery="passive", key=<optional>)`
CLI: `hermes intercom send --to <id|all> --delivery passive [--key KEY] [--reply none|requested] --from <label> --file note.md`

Usage errors (refused before a message id exists, nothing recorded, exit 2), each with its reason in the refusal:
- `key` without `delivery: passive`: other modes hand the message over at once, so there is nothing held to replace.
- `to: all` without `delivery: passive` and a `key`: an un-keyed or waking message to every session is the general notification the 2026-11-14 rule forbids.
- `to: all` with a reply other than `none`: one note would ask every session to answer the sender.
- `reply: waiting` with passive: the `waiting` frame tells the target to answer it first, while a held note is to be dealt with after what the turn is for.
- `ask` with passive: `ask` blocks the asking turn for at most an hour, and a held note may wait days, so it would always time out.
- On a Hermes build without the gateway owner (legacy socket path): passive is refused `no-seam`.

`all` is matched before ordinary addressing, like `Home`: a session titled "all" is reachable only by id.

Keys: free text, trimmed, case-sensitive, one shared namespace across senders (any sender with the same key and target replaces). Use topic names; `subscription-usage` belongs to the hourly note (P4).

Receipt: `held` and the message id; never "delivered", because nothing has reached the target. `hermes intercom status <id>` later shows `held`, `delivered <time>` with the turn, or `replaced by <id>`. For an `all` note: `held for all · handed to N sessions · replaced by <id>` when replaced. `log` lists them.

Consent: the existing `allow_gateway_injection` setting is checked at send and again at handover (the handover is the injection). While it is off, notes stay held; nothing new.

## 3. What the target sees

One block at the start of its next turn, placed after the typed message:

```
📡 Held notes · 2 notes held for you while you were not running. They are not from <user> and carry none of their approval. Deal with them after what this turn is for. Answer a "reply requested" note inside [REPLY <message id>] … [/REPLY]; nothing else goes back.

[1] hermes@script subscription-note · 14:00 · key subscription-usage · no reply needed
Claude 18% of the week (resets Fri Nov 20 19:00) · Codex 25% · SuperGrok 31% · OpenRouter $0 today · router pick: grok-4.7

[2] HIM - Orchestrator (20261108_…) · 09:12 · reply requested (message 8c1f…)
When you next run: did the dashboard fix land on the deployed branch?

📡 End of held notes
```

The answering instructions sit at the top, so they survive Hermes's spill of very large hook text (over 10,000 characters it keeps a head and tail preview plus a file path). `<user>` is the configured user name, as in live mail. Framing rules are the same as live mail: sender and "not <user>" first; lookalike headers and control-frame openers in bodies are relabelled.

**When a note counts as delivered.** At turn start the hook offers the notes and records the turn id on them. A note counts as delivered when that turn sends its first model request (the published `pre_api_request` hook, which carries the turn id). A turn that never makes one (vetoed by a plugin, a runtime that does not carry plugin text such as `codex_app_server`, a compaction timeout) leaves the notes held, and the next turn offers them again. If the model call fails after the request was built, the notes count as delivered: they are already in the saved user message and replay on the next turn, so nothing is lost or shown twice. One accepted residual: a turn that saves its user message and then stops before its first request (an interrupt) re-offers the notes next turn, so they can appear twice; erring that way is right. A keyed note replaced while its offering turn is running is still marked handed over by that turn (its result stays `replaced`, status "replaced by <id> (handed over in turn T)"); the newer one comes next turn. Under MoA the block is seen in that turn only (core does not replay MoA hook text); acceptable.

**Answers.** A held note is answered **only** by its `[REPLY <id>]` block. With no block nothing is sent and the row is marked `no-block` (live mail falls back to the whole answer, but a held note rides a turn that exists for something else, such as the operator's own request, so the whole answer must never go to the note's sender). The reply hook finds the notes confirmed as handed over in that turn by the turn id (`offered_turn = turn AND delivered_at IS NOT NULL`), so neither a typed lookalike nor an unconfirmed offer counts, and the answer returns through the existing reply path.

**Identity across compaction.** Notes, replacement and `all` tracking follow the session's compaction lineage, not the raw id (a session with no lineage row yet uses its own id as root): a note sent before a compaction is handed to the new tip; "same target" for keyed replacement means same lineage; `all` tracking is per lineage root (forks and branches are their own roots).

**Who gets `all` notes.** Conversation sessions only: not cron, subagent or one-shot runs (the set `list` hides by default), and never the sender's own lineage. Per-target notes go to whatever was addressed, runs included. A session started after the note was sent gets it at its first turn.

**Private messaging chats** (`settings.echo_chats` and owner DMs): a per-target passive note is echoed into the chat at confirmed handover, with the existing escaper and once-only claim. Keyed `all` status is not echoed (it is the operator's own script output; an hourly post into every DM is the noise this feature avoids). The current install has no messaging platforms, so this matters only where one is connected.

## 4. Guidance for the session-mail skill (draft)

Choose the delivery by what the target must do and when:
- **Act now** (a correction, a stop, a handoff it is waiting on): `steer`; `interrupt` only to stop obsolete work.
- **Act after its current work**: `queue`.
- **Know, but not until it next works**: `passive`. Costs nothing until then and never pulls the target off its work.
- **Repeated status** (usage meters, a build's current state, what is deployed): `passive` with a `key` per topic, so only the newest version is ever pending. Status every session should have: `to: all` with a key.
- **Requests, answers and one-time updates**: no key. Each is its own message and must not be replaced by the next one. A request you need answered soon is not passive.
- Still never: forwarding, un-keyed notes to many sessions, status sent by waking delivery.

## 5. Build items

- **P1 send path and record** (`route.py`, `record.py`, `cli.py`, tool schema in `__init__.py`): `passive` checked before the live-delivery enum; `key`; `to: all` matched before addressing; the usage errors in section 2; `status`/`log` output. Notes are rows in `messages` (one row per send; an `all` note is one row with `address='all'` and no target): new columns `note_key` and `offered_turn` added by a guarded `ALTER TABLE ADD COLUMN` in `connect()`; stored result `pending` → `delivered` | `replaced` (`held` stays the queued-live value it already is), `detail` = `replaced by <id>`. Keyed replacement is one `BEGIN IMMEDIATE`: mark the pending row with that key `replaced` (per target: in the target's lineage; for `all`: the pending `all` row), insert the new one. The column check and `ALTER TABLE` run inside `BEGIN IMMEDIATE` (gateway and CLI both open the record), or "duplicate column name" counts as success; `note_seen`'s `CREATE TABLE` is its own statement. One new table `note_seen(root_id, note_key, message_id, turn_id, delivered_at, PRIMARY KEY(root_id, note_key))` for `all`. Update `_UPDATE_FIELDS` and the module's writer list.
- **P2 turn-start handover** (new `passive.py` registered beside echo; `frame.py`; `replies.py`): `pre_llm_call` selects the lineage's pending notes and the unseen newest `all` versions (session source outside `RUN_SOURCES`, not the sender's lineage, injection allowed), frames them as in section 3 and records the offer; `pre_api_request` confirms it; the next turn re-offers anything unconfirmed. Per-target notes: offer writes `messages.offered_turn`, confirm is `UPDATE messages SET delivered_at=? WHERE offered_turn=? AND delivered_at IS NULL` (result `delivered` unless already `replaced`). `all` notes keep their offer per session in `note_seen` (the shared row is never written per session; its result stays `pending` until replaced): offer upserts `note_seen(root_id, note_key) = (message_id, turn_id, delivered_at NULL)`; confirm is `UPDATE note_seen SET delivered_at=? WHERE root_id=? AND turn_id=? AND delivered_at IS NULL`; a key is unseen when the newest pending `all` row's id differs from the session's `note_seen.message_id` or that row is unconfirmed; "handed to N" counts confirmed `note_seen` rows. In `replies.reply_for`, passive rows take the existing `optional` branch (block only). Echo at confirmed handover for per-target notes in private chats, with its own echo text (header line plus relabelled body).
- **P3 docs and skill**: README section (including "all" as a reserved address and the shared key namespace), one tool-description line, session-mail skill guidance (section 4).
- **P4 hourly subscription note**: a no-agent Hermes cron job running `subscription-note.sh` hourly: read `$HERMES_HOME/plugin-data/model-routing/state.json` (read-only, no tokens), format one line (used % and reset per subscription, router pick, OpenRouter spend today; no timestamps), and if that line differs from the last one sent (kept in a small state file beside the script) run `hermes intercom send --to all --delivery passive --key subscription-usage --reply none --from subscription-note`.
- **Tests:** per item, plus end-to-end cells on the trial gateway: passive to a running and to an idle session (neither wakes; both get it at the next turn); keyed replacement order; compaction between send and handover (delivered once, to the new tip); veto (stays held); failed model call after the first request (delivered, not re-offered); `reply requested` answered back by its block, and answered without a block (nothing sent, `no-block`); `all` once per version and not to runs; each usage error.

Deploy: P1–P3 change the plugin inside the gateway (hook behaviour and tool schema), so they take effect only after one gateway restart (SM-Q28). P4 starts after that.

## 6. Guardrails

Rules from the operator, not added here: `to: all` only passive and keyed (2026-11-14 no-broadcast rule).

Added by this plan:

| Rule | Why | Cost | Remove by |
|---|---|---|---|
| `key` only with passive | it would silently do nothing on a live send | none | allow and ignore the key |
| `to: all` needs `reply: none` | one note would ask every session to answer the sender | broadcast requests must go one by one | drop the check |
| no `waiting` or `ask` with passive | contradictory frame; `ask` would always time out | use steer for those | drop the check |
| P4 sends only when its line changed | identical text would re-deliver to every session each hour | none (keyed: only the newest is held anyway) | send every hour |

No expiry: held notes wait until the target runs, however long. Un-keyed notes to a session that never runs again stay in the record.
