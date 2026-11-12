# Chunk — session-mail: session-to-session messaging, built on intercom (gateway only)

- Slug: `session-mail` (working name; the shipped plugin is `intercom`)
- Type: Epic
- Track: Hermes Improvement (`PROJECT.md`, fork work on `alexderz/hermes-agent`); n/a as a
  tracker id
- HLD: `docs/session-mail/hld.md` (round 3, gateway only)
- LLD: `docs/session-mail/lld.md` (round 7, gateway only: security rounds 5 and 6, the steered echo)
- Groom: `.agents/design/session-mail/groom.md` (frozen)
- project-main: `integrate/session-mail-023` (hermes-agent) and `integrate/session-mail`
  (intercom)
- Land path: merge-and-delete after explicit Review (local, serialized);
  push item branches and project-main; no internal PRs

Epic: `DER-701`.

## Repos

| Repo | Holds | project-main | Item branches | Trunk |
|---|---|---|---|---|
| `alexderz/hermes-agent` (this repo) | The `plugin_api.json` listing PR (G-1); the vendored plugin `plugins/intercom` (G-12); the owner E2E test; the design docs | `integrate/session-mail-023` (cut from `alex/v0.23.1-canary-1110`) | `der-701/<item>`, cut from project-main | A feature branch onto `alex/v0.23.1-canary-1110`, fast-forwarded and deployed with `git pull --ff-only` (rule 19). Nothing goes onto `alex/v0.22.0-mobile-fixes`. The listing is recorded in `PROJECT.md` as the only fork patch |
| `alexderz/hermes-intercom` (fork of `majordave/hermes-intercom`) | The plugin source (G-2 … G-11) and the upstream drafts in `docs/upstream/` (G-13) | `integrate/session-mail` (created at Groom from `ae90a2a`) | `der-701/<item>`, cut from project-main | project-main merged into the fork's `main` after Review. The upstream pull requests are drafted, never opened by an agent |

**Order for anything touching intercom:**
1. The intercom change lands on intercom's project-main first.
2. hermes-agent takes it with `git subtree add` (first time) or `git subtree pull --prefix
   plugins/intercom <intercom remote> integrate/session-mail`. There is no `--squash`.
3. A fix is never made in `plugins/intercom` alone.

**Commits in the `wt/v023` worktree** run with an isolated `HERMES_HOME`, or with hooks off: the
lefthook setup otherwise provisions into the account's real home.

## Required

- **Why this slice, why now:**
  - On the live v0.23 install, every chat surface Alex uses runs in the gateway owner (SM-Q20).
  - Trial round 3 proved that intercom, as a client of that owner, can deliver every mode (plus
    idle and cold start) and route replies back with the owner's existing verbs.
  - So the slice is one plugin plus a listing-only core PR, with no behaviour patch (this
    replaces settled decision 11).
- **Done:** Trunk: both project-mains on trunk; tickets landed and verified against LLD § Verify:
  - every mode, plus idle and cold start, on Webapp, desktop, Ink TUI, classic CLI and messaging
    sessions (the owner E2E);
  - admin-dashboard chats refused `not-addressable`;
  - replies, `[SILENT]` and debates;
  - SM-Q9 senders;
  - the private-chat echo, or its documented fallback (O21);
  - the chat rule;
  - addressing;
  - the record and the CLI;
  - no caps or retries;
  - intercom's tests;
  - `boundary_lint` clean;
  - the relay skills on `hermes intercom send`;
  - the upstream drafts in `docs/upstream/`, with nothing posted.

  Deployed with one announced gateway restart, enabled through house-infra.
- **Children:** none filed yet. The planned items are LLD G-1 … G-13 (the manager files them at
  Groom):
  1. G-1, the listing PR (Claude Opus);
  2. G-2, the owner client (Claude Opus);
  3. G-3, the send path (Claude Opus);
  4. G-4, addressing (Grok 4.7);
  5. G-5, chat scope (Claude Opus);
  6. G-6, the echo, including the steered echo before a final answer (Claude Opus);
  7. G-7, framing (Grok 4.7);
  8. G-8, the record (Grok 4.7);
  9. G-9, replies and `ask` (Claude Opus);
  10. G-10, the CLI, tool schema, caps and the capability-selected legacy path (Grok 4.7);
  11. G-11, relays (Grok 4.7; the manager edits the skills);
  12. G-12, vendor and deploy (Grok 4.7; the manager restarts);
  13. G-13, upstream drafts (Grok 4.7).
- **Wave view:** not kept here; manager posts one Epic comment only on
  reshape (item added or canceled, blocker set)
- **Blocked by:**
  - Alex's acceptance of the LLD (SM-Q18), including the operator power (HLD O23), and of the
    UX deltas. Security accepted the trust boundaries at `6ccea9121f` (round 6); if Alex
    declines O23, the fallback predicate needs a short security re-check.
  - DER-686 does not block.
- **Blocks:** none

## Optional

- **Risks only this chunk carries:**
  - upstream may decline the listings (the fork then carries them as its only patch);
  - the gateway restart stops every chat at once;
  - drift between `plugins/intercom` and alexderz/hermes-intercom.
- **Operator timezone for after-act:** US Central.
