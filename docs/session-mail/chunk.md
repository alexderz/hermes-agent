# Chunk — session-mail: session-to-session messaging, built on intercom

- Slug: `session-mail` (working name; the shipped plugin is `intercom`)
- Type: Epic
- Track: Hermes Improvement (`PROJECT.md`, fork work on `alexderz/hermes-agent`); n/a as a
  tracker id
- HLD: `docs/session-mail/hld.md` (round 2)
- LLD: n/a until Spec (`docs/session-mail/lld.md`)
- Groom: `.agents/design/session-mail/groom.md` (frozen)
- project-main: `integrate/session-mail` in **each** repo below
- Land path: merge-and-delete after explicit Review (local, serialized);
  push item branches and project-main; no internal PRs

Epic: `DER-701`.

## Repos

| Repo | Holds | project-main | Item branches | Trunk |
|---|---|---|---|---|
| `alexderz/hermes-agent` (this repo) | The core seam (HLD P1); the wake module from `scripts/dashboard_dispatch.py` (P5); the vendored plugin `plugins/intercom` (P6); the design docs | `integrate/session-mail` | `der-701/<item>`, cut from project-main | project-main fast-forwarded into `alex/v0.22.0-mobile-fixes`, then deployed with `git pull --ff-only` (rule 19). The seam is listed in `PROJECT.md` as a fork patch |
| `alexderz/hermes-intercom` (fork of `majordave/hermes-intercom`) | The plugin source: transport changes (P2), our additions (P3), the gateway endpoint (P4), the upstream drafts in `docs/` (P7) | `integrate/session-mail` (created at Groom from `ae90a2a`) | `der-701/<item>`, cut from project-main | project-main merged into the fork's `main` after Review. The upstream pull request to majordave is drafted, never opened by an agent |

**Order inside an item that spans both repos:**
1. The intercom change lands on intercom's project-main first.
2. Hermes-agent's project-main then takes it with `git subtree pull --prefix plugins/intercom
   <intercom remote> integrate/session-mail`. There is no `--squash`, so authorship survives.
3. A fix is never made in `plugins/intercom` alone.

How intercom reaches the install is SM-Q14. The design follows its recommendation (subtree);
see HLD O6.

## Required

- **Why this slice, why now:**
  - Alex widened the scope to every kind of session, chose three delivery modes, and chose
    our intercom fork as the base (brief decisions 1, 3, 9, 11).
  - The dispatch fix and the queue-aware reapers are already on project-main (`3d4d482eb9`).
  - Intercom already has the transport and the tool; what it lacks is the seam, multi-session
    hosts, the modes, addressing, the record and replies.
  - The slice covers every host Alex named, in the HLD's build order, so the most-used targets
    (dashboard chats, terminals) work first.
- **Done:** Trunk: both project-mains on trunk; tickets landed+verified against the brief's
  "Verify later" list:
  - delivery modes on each host;
  - a CLI `steer` that does not interrupt;
  - many sessions per process with no cross-delivery;
  - exactly-once routing;
  - waking a session that is live nowhere;
  - replies, `[SILENT]` and debates;
  - the SM-Q9 senders;
  - the Telegram topic post (SM-Q15);
  - addressing;
  - the record and the CLI;
  - no caps or retries;
  - no-seam behaviour;
  - intercom's tests;
  - the tool list;
  - the phone;
  - the upstream drafts in `docs/`, with nothing posted.

  Deployed with the announced dashboard and gateway restarts, enabled through house-infra.
- **Children:** none filed yet. Planned items (the manager files them at Groom), in build order:
  1. **Seam, tui_gateway and CLI hosts** (hermes-agent): `inject_message(mode=…)`, applied mode
     returned, `mode=None` unchanged, tests.
  2. **Wake module** (hermes-agent): the dispatcher rule moved into an importable module; the
     script becomes a wrapper with identical flags.
  3. **Intercom transport** (intercom): lease-`pid` routing, many sessions per process, the seam
     with feature detection, same-session refusal, caps removed, the A′ frame and relabel rule.
  4. **Intercom additions** (intercom): addressing, the `delivery` argument and receipt, the
     record, automatic replies, `hermes intercom send|status|list`.
  5. **Vendor and deploy, step 1** (hermes-agent and house-infra): subtree, enable, dashboard
     restart, relay-skill edit by the manager.
  6. **Seam, gateway host** (hermes-agent), and **gateway endpoint** (intercom): endpoint role,
     `lookup_by_session_id` routing, silence, the SM-Q15 post. Then the gateway restart.
  7. **Upstream drafts** (intercom `docs/`): #81885 update, intercom pull request, seam pull
     request, for Alex.
- **Wave view:** not kept here; manager posts one Epic comment only on
  reshape (item added or canceled, blocker set)
- **Blocked by:**
  - SM-Q14 (deploy method, asked of Alex elsewhere) for item 5;
  - security's Spec review of HLD B4 for item 6;
  - Trial round 2 (HLD, PoC questions) before Spec is accepted.
  - DER-686 does not block (addressing falls back to the title rule).
- **Blocks:** none

## Optional

- **Risks only this chunk carries:**
  - drift between `plugins/intercom` and alexderz/hermes-intercom (rule above);
  - the seam is a core fork patch that must be re-applied at the v0.23 rebase (HLD O16);
  - untrusted gateway text steering Alex's sessions (HLD B4);
  - processes started before the deploy cannot receive mail until restarted.
- **Operator timezone for after-act:** US Central.
