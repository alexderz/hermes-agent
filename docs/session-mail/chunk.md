# Chunk — session-mail: session-to-session messaging

- Slug: `session-mail`
- Type: Epic
- Track: Hermes Improvement (`PROJECT.md`, fork work on `alexderz/hermes-agent`); n/a as a
  tracker id
- HLD: `docs/session-mail/hld.md`
- LLD: n/a until Spec (`docs/session-mail/lld.md`)
- Groom: `.agents/design/session-mail/groom.md` (frozen)
- project-main: `integrate/session-mail`
- Land path: merge-and-delete after explicit Review (local, serialized);
  push item branches and project-main; no internal PRs

Epic: `DER-701`.

## Required

- **Why this slice, why now** — Alex's sessions cannot message each other. Relays today run
  `scripts/dashboard_dispatch.py` from skills, with no record, no reply path and no sender
  name, and every agent-key turn is credited to Alex. The steer-then-queue fix (`1516a52669`,
  branch `alex/dispatch-steer-queue`) has just made dispatch safe for busy sessions. The plugin
  reuses that rule. This slice is the smallest one that does all of Alex's ask: one plugin,
  with a tool, a CLI, an outbox and a reply hook, plus moving the dispatcher's rule into one
  shared module. There is no worker and no core patch.
- **Done** — Trunk: project-main is on trunk. It is fast-forwarded into the deployed branch
  `alex/v0.22.0-mobile-fixes`, deployed with `git pull --ff-only`, enabled through house-infra,
  and live after one announced dashboard restart. The tickets are landed and verified against
  the brief's "Verify later" list:
  - steer, queue and start, each with the 📨 header, and never an interrupt or redirect;
  - errors returned to the sender and recorded;
  - replies by the same rule, `[SILENT]` sending nothing, a debate that stops only at
    `[SILENT]`, and a steered mail's reply taken from its `[REPLY <id>]` block;
  - finished agent senders stored, not woken;
  - existing sessions get the tool after the restart;
  - addressing after `/compress`;
  - the outbox and the CLI;
  - the phone shows the header as the first line;
  - no caps and no retries.
- **Children** — none filed yet. Planned items (the manager files them at Groom):
  1. Take `1516a52669` onto the branch, then move the delivery rule into a fork module that
     the script wraps (HLD P1/P2).
  2. Plugin skeleton: addressing, outbox and mail framing (P3, D2, D5).
  3. The `session_message` tool and the `hermes session-mail` CLI (D4).
  4. The `post_llm_call` reply hook (D3).
  5. Deploy: house-infra enable and the announced restart (D6).
- **Wave view** — not kept here; manager posts one Epic comment only on
  reshape (item added or canceled, blocker set)
- **Blocked by** — none as an issue id. Item 1 needs commit `1516a52669` (branch
  `alex/dispatch-steer-queue`, reviewed and deployed by the "Session Messaging" session). The
  Trial (HLD, PoC questions) runs before Spec is accepted. DER-686 does not block: addressing
  falls back to the title rule (HLD D5).
- **Blocks** — none

## Optional

- **Risks only this chunk carries:**
  - A real model may act on mail as if Alex had said it (HLD O1/O7).
  - Queued mail is lost on a restart or to the reaper (HLD O10).
  - The deploy restart cuts the phone off and kills running owner turns. Share it with
    DER-686 if both are ready together (HLD O8).
- **Operator timezone for after-act:** US Central.
