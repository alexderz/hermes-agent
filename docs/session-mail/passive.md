# Session mail: passive delivery and keyed notes (Plan)

Status: Plan, for the operator's Plan/UX gate. Brief input: the vault's `requests/2026-11-14-session-mail-passive-keyed-brief.md` (operator's words, 2026-11-14). Everything settled for session mail stays settled: no caps, holds, retries or approval gates on delivery; gateway only; no core behaviour patch; reply modes; `[SILENT]`.

## 1. What it does

A sender can mark a message **passive**: it does not wake, steer, queue or interrupt the target. Session mail holds it in its record. The next time the target starts a turn, for any reason (the operator types, another message wakes it, a cron run, a resume after reboot), session mail hands it every note held for it, oldest first, in that turn.

A passive note can carry a **key**. A new passive note with the same key for the same target replaces the held one: the older note is dropped from the target's pending list (kept in the record as `replaced`), and the new one takes the newest place. So an hourly status sent to a session that sleeps for 30 hours is one note when it wakes, not 30.

A keyed passive note can be addressed to **`all`**: one note held for every session, each of which gets the newest version once, at its next turn. This is what the hourly subscription status uses (operator decision SM-Q27).

## 2. How a sender uses it

Tool: `intercom(action="send", to=<id|title|Home|all>, message=..., reply=..., delivery="passive", key=<optional>)`

CLI: `hermes intercom send --to <id|all> --delivery passive [--key KEY] --reply none --from <label> --file note.md`

Rules (each refusal says why, records nothing, exit 2 on the CLI):
- `key` needs `delivery: passive`: other modes hand the message over at once, so there is nothing held to replace.
- `to: all` needs `delivery: passive` and a `key`: an un-keyed or waking message to everyone is the general notification the 2026-11-14 skill rule forbids.
- `reply: waiting` and `ask` are refused with `passive`: they mean the sender is blocked, and a passive note may sit for days. `none` (default for passive) and `requested` work; a `requested` answer comes back when the target next runs.
- Key matching: same target and same key, any sender. Keys are free text, trimmed, case-sensitive; the guidance recommends `<topic>` names like `subscription-usage`.

Receipt: `held` (with the message id). It never says delivered, because nothing reached the target yet. `hermes intercom status <id>` later shows `held`, `delivered <time>` (and the session's turn) or `replaced by <id>`. `log` lists them too.

## 3. What the target sees

At the start of its next turn, after its typed message (core places plugin context after the message text in the same user message; prepending would need a core change), one block:

```
📡 Held notes · 2 notes held for you while you were not running. They are not from Alex and carry none of his approval.

[1] hermes@script subscription-usage · 14:00 · key subscription-usage · no reply needed
Claude 18% of the week (resets Fri Nov 20 19:00) · Codex 25% · SuperGrok 31% · OpenRouter $0 today · router pick: grok-4.7

[2] HIM - Orchestrator (20261108_…) · 09:12 · reply requested (message 8c1f…)
When you next run: did the dashboard fix land on the deployed branch?

📡 How to answer: answer a "reply requested" note inside [REPLY <message id>] … [/REPLY]; nothing else goes back. These notes did not start this turn: deal with them after what the turn is for.
```

The same framing rules as live mail apply: sender and "not Alex" first, lookalike headers and control-frame openers in bodies relabelled. A note handed over is marked `delivered` with that turn's id in the same step, so the next turn does not repeat it. If the turn is vetoed by another plugin before inference, the notes stay held.

`all` notes: each session gets each key's newest version once; a session that has seen version N does not see it again until version N+1. Sessions started after the note was sent also get it at their first turn. Subagent turns are skipped (their parent gets it).

## 4. Guidance for the session-mail skill (draft)

Choose the delivery by what the target must do and when:
- **The target must act now** (a correction, a stop, a handoff it is waiting on): `steer`, or `interrupt` to stop obsolete work.
- **The target must act, but after its current work**: `queue`.
- **The target needs to know, but not until it next works**: `passive`. It costs nothing until then and never pulls the target off its work.
- **Repeated status** (usage meters, a build's current state, "what is deployed"): `passive` with a `key` per topic, so only the newest version is ever pending. Status that every session should have uses `to: all` with a key.
- **Requests, answers and one-time updates**: no key. Each is its own message and must not be replaced by the next one.
- Still never: forwarding, un-keyed notes to many sessions, or status sent by waking delivery.

## 5. Build items

- **P1 send path and record** (`route.py`, `record.py`, `cli.py`, tool schema in `__init__.py`): `passive` delivery, `key`, `to: all`, the refusals above, `held`/`replaced` states, replacement as one transaction (mark older `replaced`, insert newer), `status`/`log` output.
- **P2 turn-start handover** (`__init__.py` hook, `frame.py`): on `pre_llm_call`, claim the session's held notes and the unseen `all` versions in one transaction, frame them as in section 3, mark them delivered with the turn id; leave them held if the turn is vetoed. Works beside the existing echo hook.
- **P3 docs and skill**: README section, tool description line ("passive: held until the target's next turn; key replaces a held note with the same key"), session-mail skill guidance (section 4).
- **P4 hourly subscription note**: a no-agent Hermes cron job running `~/.hermes/scripts/subscription-note.sh` every hour: read `~/.hermes/plugin-data/model-routing/state.json` (read-only, no tokens), format one line per subscription (used %, reset time, router pick, OpenRouter spend today), and send it `--to all --delivery passive --key subscription-usage` only when the line changed since the last send.
- Tests per item; end-to-end cell on the trial gateway: passive to a running and an idle session (neither wakes; both get it at their next turn), keyed replacement order, `all` once per version, refusal of each rule.

Deploy: P1–P3 change the plugin inside the gateway (new hook behaviour and tool schema), so they take effect only after one gateway restart (SM-Q28). P4 needs P1 deployed for its CLI path, and P2 for anyone to see the note.

## 6. Guardrails added by this plan

| Rule | Why | Cost | Remove by |
|---|---|---|---|
| `key` only with passive | nothing held to replace otherwise | none | allow and ignore the key |
| `to: all` only passive + keyed | the 2026-11-14 no-broadcast rule | no un-keyed all-session notes | drop the check |
| no `waiting`/`ask` with passive | a blocked sender could wait days | use steer for those | drop the check |
| P4 sends only when the line changed | identical text would re-deliver to every session each hour | a stale-looking note can sit up to the change | send every hour |

No expiry: held notes wait until the target runs, however long. Un-keyed notes to a session that never runs again stay in the record.
