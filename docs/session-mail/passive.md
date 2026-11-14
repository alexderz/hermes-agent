# Session mail: passive delivery and keyed notes (Plan)

Status: Plan, round 7 (architect reviews folded in: `reviews/passive-architect-r1.md` to `-r4.md`; operator scope addition: other profiles explicitly, `all` stays in-profile; operator scope addition 2026-11-14: keys work with queue too), for the operator's Plan/UX gate. Brief input: the vault's `requests/2026-11-14-session-mail-passive-keyed-brief.md` (operator's words, 2026-11-14). Everything settled for session mail stays settled: no caps, holds, retries or approval gates on delivery; gateway only; no core behaviour patch (published plugin API only); reply modes; `[SILENT]`; no general notifications or forwarding (2026-11-14).

## 1. What it does

A sender can mark a message **passive**: it does not wake, steer, queue or interrupt the target. Session mail keeps it in its record. The next time the target starts a turn, for any reason (the operator types, another message wakes it, a resume after reboot), session mail hands over every note held for it, oldest first, in that turn.

A passive note can carry a **key**. A new passive note with the same key for the same target replaces the held one: the older note leaves the pending list (kept in the record as `replaced`), and the new one takes the newest place. An hourly status sent to a session that sleeps 30 hours is one note when it wakes, not 30.

A key also works with **queue** (operator, 2026-11-14). A keyed queued message to a target that is busy is held by session mail; Hermes's own queue carries only a short wake line (a plugin cannot edit that queue). A newer one with the same key replaces it. When the target's current turn ends, Hermes runs the wake as its next turn and session mail puts the newest version into it. To an idle target a keyed queued message starts a turn at once, as queue always does, so nothing is there to replace. Example: a build watcher queues "build state: verifying G3" while the owner is busy, then "build state: G3 landed"; the owner, when its turn ends, gets one turn with the second.

A keyed passive note can go to **`all`**: one note that every conversation session gets, newest version only, once, at its next turn (SM-Q27). The first use is the subscription monitor's status line (built in that monitor, not here).

Mechanism: the published `pre_llm_call` hook, which runs once at the start of every turn of every gateway-hosted session; its text rides in that turn's user message and is replayed in later turns. Core puts hook text after the typed message, not before it.

## 2. How a sender uses it

Tool: `intercom(action="send", to=<id|title|Home|all>, message=..., reply=..., delivery="passive", key=<optional>)`
CLI: `hermes intercom send --to <id|all> --delivery passive [--key KEY] [--reply none|requested] --from <label> --file note.md`; keyed queue: `--delivery queue --key KEY`.

Usage errors (refused before a message id exists, nothing recorded, exit 2), each with its reason in the refusal:
- `key` with `steer` or `interrupt`: they hand the message over at once, so there is nothing held to replace. (`key` works with `passive` and `queue`.)
- `key` with `ask`: the asker waits on that exact message, so a replaced ask would leave it waiting until timeout.
- `to: all` without `delivery: passive` and a `key`: an un-keyed or waking message to every session is the general notification the 2026-11-14 rule forbids.
- `to: all` with a reply other than `none`: one note would ask every session to answer the sender.
- `reply: waiting` with passive: the `waiting` frame tells the target to answer it first, while a held note is to be dealt with after what the turn is for.
- `ask` with passive: `ask` blocks the asking turn for at most an hour, and a held note may wait days, so it would always time out.
- On a Hermes build without the gateway owner (legacy socket path): passive is refused `no-seam`.

`all` is matched before ordinary addressing, like `Home`: a session titled "all" is reachable only by id.

Keys: free text, trimmed, case-sensitive, one shared namespace across senders. Replacement is per target lineage, key and mode: a keyed passive note replaces only a held passive note with that key, and a keyed queued message only a held queued one (architect round 3: simpler to state and test, and nothing asked for cross-mode replacement). Use topic names; `subscription-usage` belongs to the subscription monitor.

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

**Compact form (operator, 2026-11-14: reduce token burn).** When no held note asks for a reply, the block is one line per note and no instructions, about 35–50 tokens for a status line:

```
📡 Held note (subscription-monitor, 14:00; not from <user>, no reply): Subs: Claude 18% wk · Codex 25% · SuperGrok 31% · OR $0 · pick grok-4.7
```

The full block above is used only when at least one note asks for a reply. Where tokens go: a held note costs its size once, in the turn that receives it, and then sits in that session's history (cheaper cached input) until compaction. So the cost is per-delivery size × how many new versions a key gets × how many sessions run a turn while a version is unseen. Keys already guarantee one pending version; the sender decides how often a new one exists.

The answering instructions sit at the top, so they survive Hermes's spill of very large hook text (over 10,000 characters it keeps a head and tail preview plus a file path). `<user>` is the configured user name, as in live mail. Framing rules are the same as live mail: sender and "not <user>" first; lookalike headers and control-frame openers in bodies are relabelled.

**When a note counts as delivered.** At turn start the hook offers the notes and records the turn id on them. A note counts as delivered when that turn sends its first model request (the published `pre_api_request` hook, which carries the turn id). A turn that never makes one (vetoed by a plugin, a runtime that does not carry plugin text such as `codex_app_server`, a compaction timeout) leaves the notes held, and the next turn offers them again. If the model call fails after the request was built, the notes count as delivered: they are already in the saved user message and replay on the next turn, so nothing is lost or shown twice. One accepted residual: a turn that saves its user message and then stops before its first request (an interrupt) re-offers the notes next turn, so they can appear twice; erring that way is right. A keyed note replaced while its offering turn is running is still marked handed over by that turn (its result stays `replaced`, status "replaced by <id> (handed over in turn T)"); the newer one comes next turn. Under MoA the block is seen in that turn only (core does not replay MoA hook text); acceptable.

**Answers.** A held note is answered **only** by its `[REPLY <id>]` block. With no block nothing is sent and the row is marked `no-block` (live mail falls back to the whole answer, but a held note rides a turn that exists for something else, such as the operator's own request, so the whole answer must never go to the note's sender). The reply hook finds the notes confirmed as handed over in that turn by the turn id (`offered_turn = turn AND delivered_at IS NOT NULL`), so neither a typed lookalike nor an unconfirmed offer counts, and the answer returns through the existing reply path.

**Identity across compaction.** Notes, replacement and `all` tracking follow the session's compaction lineage, not the raw id (a session with no lineage row yet uses its own id as root): a note sent before a compaction is handed to the new tip; "same target" for keyed replacement means same lineage; `all` tracking is per lineage root (forks and branches are their own roots).

**Who gets `all` notes.** Sessions of the sender's own profile only (operator, 2026-11-14), and of those conversation sessions only: not cron, subagent or one-shot runs (the set `list` hides by default), and never the sender's own lineage. Per-target notes go to whatever was addressed, runs included. A session started after the note was sent gets it at its first turn.

**Private messaging chats** (`settings.echo_chats` and owner DMs): a per-target passive note is echoed into the chat at confirmed handover, with the existing escaper and once-only claim. Keyed `all` status is not echoed (it is the operator's own script output; an hourly post into every DM is the noise this feature avoids). The current install has no messaging platforms, so this matters only where one is connected.

## 4. Guidance for the session-mail skill (draft)

Choose the delivery by what the target must do and when:
- **Act now** (a correction, a stop, a handoff it is waiting on): `steer`; `interrupt` only to stop obsolete work.
- **Act after its current work**: `queue`. If you may send the same kind of update several times while it is busy (a build's state), add a `key` so only the newest one wakes it.
- **Know, but not until it next works**: `passive`. Costs nothing until then and never pulls the target off its work.
- **Repeated status** (usage meters, a build's current state, what is deployed): `passive` with a `key` per topic, so only the newest version is ever pending. Status every session should have: `to: all` with a key, a terse one-line body, and a new version only when the change matters to a reader (a threshold crossed, a decision-relevant value changed), not on every refresh.
- **Requests, answers and one-time updates**: no key. Each is its own message and must not be replaced by the next one. A request you need answered soon is not passive.
- Still never: forwarding, un-keyed notes to many sessions, status sent by waking delivery.

## 5. Build items

- **P1 send path and record** (`route.py`, `record.py`, `cli.py`, tool schema in `__init__.py`): `passive` checked before the live-delivery enum; `key`; `to: all` matched before addressing; the usage errors in section 2; `status`/`log` output. Notes are rows in `messages` (one row per send; an `all` note is one row with `address='all'` and no target): new columns `note_key` and `offered_turn` added by a guarded `ALTER TABLE ADD COLUMN` in `connect()`; stored result `pending` → `delivered` | `replaced` (`held` stays the queued-live value it already is), `detail` = `replaced by <id>`. Keyed replacement is one `BEGIN IMMEDIATE`: mark the pending row with that key `replaced` (per target: in the target's lineage; for `all`: the pending `all` row), insert the new one. The column check and `ALTER TABLE` run inside `BEGIN IMMEDIATE` (gateway and CLI both open the record), or "duplicate column name" counts as success; `note_seen`'s `CREATE TABLE` is its own statement. One new table `note_seen(root_id, note_key, message_id, turn_id, delivered_at, PRIMARY KEY(root_id, note_key))` for `all`. Update `_UPDATE_FIELDS` and the module's writer list.
- **P2 turn-start handover** (new `passive.py` registered beside echo; `frame.py`; `replies.py`): `pre_llm_call` selects the lineage's pending notes and the unseen newest `all` versions (session source outside `RUN_SOURCES`, not the sender's lineage, injection allowed), frames them as in section 3 and records the offer; `pre_api_request` confirms it; the next turn re-offers anything unconfirmed. Per-target notes: offer writes `messages.offered_turn`, confirm is `UPDATE messages SET delivered_at=? WHERE offered_turn=? AND delivered_at IS NULL` (result `delivered` unless already `replaced`). `all` notes keep their offer per session in `note_seen` (the shared row is never written per session; its result stays `pending` until replaced): offer upserts `note_seen(root_id, note_key) = (message_id, turn_id, delivered_at NULL)`; confirm is `UPDATE note_seen SET delivered_at=? WHERE root_id=? AND turn_id=? AND delivered_at IS NULL`; a key is unseen when the newest pending `all` row's id differs from the session's `note_seen.message_id` or that row is unconfirmed; "handed to N" counts confirmed `note_seen` rows. In `replies.reply_for`, passive rows take the existing `optional` branch (block only). Echo at confirmed handover for per-target notes in private chats, with its own echo text (header line plus relabelled body).
- **P3 docs and skill**: README section (including "all" as a reserved address and the shared key namespace), one tool-description line, session-mail skill guidance (section 4).
- **First consumer, built elsewhere** (operator, 2026-11-14: "Hourly note is part of the sub monitor, not mail session and is our first use case"): the subscription monitor (model-routing collector) sends its status line with `hermes intercom send --to all --delivery passive --key subscription-usage --reply none --from subscription-monitor` when the line changed. Request to its owner: the vault's `requests/2026-11-14-subscription-note-via-session-mail.md`. Session mail's end-to-end test uses that exact call.
- **P5 keyed queue** (`route.py`, `passive.py`, `record.py`, `frame.py`; architect round 3): Hermes's queue times the turn, session mail's record supplies its content. A keyed queued send is stored `pending` with its key (same replacement transaction as passive) plus a wake marker. In the same `BEGIN IMMEDIATE`: if no earlier pending row with this key and lineage has an outstanding wake, the send submits one after commit: a framed session-mail line ("keyed update `<key>` from `<sender>`; the current version follows", `header_sha` recorded) through the ordinary queue path (`deliver_sync(target, wake, "queue", id)`), so an idle target starts at once and a busy one queues, with no running check. When the wake's turn starts, P2's `pre_llm_call` finds the wake span in `user_message` with the existing span finder and offers the newest pending row for that key and lineage as the turn's context, with P2's offer and confirm. A send that commits before the wake turn claims replaces the row and inherits the wake (the turn shows the newest); one that commits after queues a new wake (a second turn, correct, since the news came after the first started). Hermes drains its queue after every turn, failed ones included, so no turn-end hook or sweep is needed. Answers use the normal `requested` branch (this turn exists for the message). Restart: Hermes's queue is in memory, so an outstanding wake is lost; `register()` clears wake markers (no RPC) and the pending row then rides the target's next turn as a passive note, which is better than plain queue, which loses the message. Receipt: `started` for an idle target, `queued (replaceable, key <k>)` for a busy one; stored result `pending` (plain queue keeps `held`). The wake line is never echoed; the newest version is echoed at confirmed handover in private chats.
- **P6 other profiles, explicitly** (operator, 2026-11-14: "sessions can explicitly message other profiles chats and bot sessions"; architect round 4). A new optional `profile` argument on the tool's `send` and `list`. Without it nothing changes: everything stays in the sender's profile. With it:
  - `list profile=spike` lists that profile's sessions; `send profile=spike to=<id|exact title|Home>` sends into one. A bot is reached by its exact title: `to: "Bot Chat", profile: "<bot profile>"` (titles are unique per profile, so no keyword is needed).
  - **Mechanism:** the sender's facts are computed first, in its own profile; then the whole target side (resolve, chat scope, consent, record row, frame, owner attach, deliver) runs inside one helper, `in_profile(name)`, which wraps it in the published `set_hermes_home_override(<target home>)` / `reset_hermes_home_override`. Discovery, the ticket mint (with the multiplexer's control home), `state.db`, config and the record then all resolve to the target profile, in both directions (default to spike and spike to default). The client attaches as the socket peer and never passes `subject`. Profile name to home: `default` is the root, others `<root>/profiles/<name>`, checked with the published profile-name and liveness helpers.
  - **Rows live in the target profile's record**, so the target's own hooks find them: replies, echo, held notes and keyed queue all work across profiles with no extra mechanism. One new column, `sender_profile` (NULL = same profile); the reply hook sends the answer back with that profile.
  - **The target profile's settings govern:** its `allow_gateway_injection`, its echo and owner settings, its configured user name (read from its config, not from the sender's plugin context).
  - **Refused, with the reason:** `profile` with `to: all` (`all` stays in the sender's profile); `profile` with `ask` (the asker's wait lives in its own process and the answer would never find it); `profile` with `@project`; an unknown or deleted profile; a profile where intercom is not enabled ("session mail is not enabled in profile spike": without its hooks there, replies, echo and framing protection would silently not happen).
  - **Framing:** the sender label carries its profile (`hermes@default/<title>`), receipts name the target as `spike/<title>`; "not <user>, no approval" is unchanged: same-user profiles are peers, not the operator.
  - **Scripts:** no new CLI flag; `hermes -p spike intercom send|list|status` already runs in another profile.

- **P7 deadline on a passive note** (operator, 2026-11-14, SM-Q29): optional `within` (minutes, at least 5; CLI `--within MINUTES`) on a per-target passive send. The note is handed over at the target's next turn as usual; if it is still undelivered when `within` runs out, session mail wakes the target then with a framed wake line through the ordinary queue path (the same wake mechanism as keyed queue: `reply_mode='none'`, never echoed, instance-scoped marker), and that turn carries the note (and any other held notes) through P2's offer and confirm. Delivered earlier: nothing happens at the deadline. Refused, with reasons: `within` with `to: all` (it would wake every session), `within` with a non-passive delivery (they hand over at once), `within` under 5. A keyed note replaced before its deadline takes the new note's `within` (none if the new one has none). Receipt: `held (wakes by HH:MM if not run)`. Who fires it (operator 2026-11-14: "cron seems a rough way to do it"; architect round 6): the gateway's own clock, the published `on_kanban_dispatch_tick` hook. The embedded kanban dispatcher ticks inside the gateway every `kanban.dispatch_interval_seconds` (60 s by default), from 5 s after boot, idle ticks included; there is one dispatcher per machine and the hook reaches the launch profile's intercom only, so the handler sweeps every live profile with intercom enabled under `in_profile(name)`. It hands the sweep to one daemon thread (never blocking the dispatcher; a sweep still running makes later ticks return at once), and the record claim keeps it exactly once. No job, no script, no setup. A deadline fires within one tick of its time; an overdue one about 5 s after a gateway restart plus one tick; nothing fires while `hermes pause` is on (held until resume). `hermes intercom wake-due` runs the same sweep by hand, documented as the fallback for setups without the in-gateway dispatcher; we install nothing. One wake per deadline: a consumed wake is never re-sent; a wake from an earlier gateway instance that was never consumed fires once more. Once its wake is submitted, the note is offered in the wake's turn (or when the wake is dead), not taken by another turn.
- **Tests:** per item, plus end-to-end cells on the trial gateway: passive to a running and to an idle session (neither wakes; both get it at the next turn); keyed replacement order; compaction between send and handover (delivered once, to the new tip); veto (stays held); failed model call after the first request (delivered, not re-offered); `reply requested` answered back by its block, and answered without a block (nothing sent, `no-block`); `all` once per version and not to runs; each usage error; other profiles: default to spike and spike to default, `requested` answered back across profiles, a passive note to spike handed over at its next turn, target with injection off or intercom disabled refused, `profile` with `all` or `ask` refused, `to: "Bot Chat"` in a Bot Mode profile; deadline: a note delivered before its deadline causes no wake; an undelivered one wakes the target once at the deadline and that turn carries it; a deadline that passed during a gateway restart fires after it; replacement takes the new deadline; each refusal; keyed queue: two keyed queued sends during a running turn produce one next turn with the newer text; a keyed queued send to an idle target starts at once; a send committed at the moment the wake turn claims (by holding the record transaction); a turn interrupted during its API call and a non-retryable API error (the wake still runs next); a gateway restart with an outstanding wake (the row rides the next turn as a passive note); passive and queued with the same key do not replace each other; `key` with `ask` refused.

Deploy: P1–P3 and P5 change the plugin inside the gateway (hook behaviour and tool schema), so they take effect only after one gateway restart. SM-Q28 (operator, 2026-11-14): restart "when all sessions are idle": a transient unit polls `hermes intercom list --json --include-runs` and restarts the gateway the first time no session is running, then runs the post-restart check; announced when scheduled. The subscription monitor can start sending after that.

## 6. Guardrails

Rules from the operator, not added here: `to: all` only passive and keyed (2026-11-14 no-broadcast rule).

Added by this plan:

| Rule | Why | Cost | Remove by |
|---|---|---|---|
| `key` not with steer, interrupt or ask | it would silently do nothing on a send handed over at once; a replaced ask would leave its asker waiting | none | allow and ignore the key |
| `to: all` needs `reply: none` | one note would ask every session to answer the sender | broadcast requests must go one by one | drop the check |
| no `waiting` or `ask` with passive | contradictory frame; `ask` would always time out | use steer for those | drop the check |

No expiry: held notes wait until the target runs, however long. Un-keyed notes to a session that never runs again stay in the record.
