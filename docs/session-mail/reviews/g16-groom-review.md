Commit: be59c92c0c
Verdict: changes

Groom check of `/var/tmp/hermes-session-mail/build/items-g16.json` (G16a–G16f) against `docs/session-mail/passive.md` at be59c92c0c, the intercom repo at `integrate/session-mail` (`/var/tmp/hermes-session-mail/wt/intercom-main`, f1ad26c), and hermes-agent at be59c92c0c. Line numbers for intercom files are in intercom-main.

The items track the plan closely. Changes are needed because:
- one G16c mechanism breaks under the real CLI (finding 1);
- one G16c test expectation contradicts G16b's delivery rule (finding 2);
- G16c does not say how a wake is kept from being taken by another turn (finding 3);
- the wake frame would be echoed and answered twice (finding 4);
- G16e bumps the wrong file (finding 6);
- the plan's skill guidance is in no item (finding 7);
- a few test instructions point at helpers that don't exist.

## Blocking

**1. G16c: "`register()` clears outstanding wake markers" runs on every `hermes intercom` CLI call.**
- `hermes <plugin command>` calls `discover_plugins()` before parsing (`hermes_cli/main.py:3197-3221`), so intercom's `register()` runs in the CLI process too (`cli.py:77-86`, `__init__.py:359-394`).
- Example: a build watcher's second `hermes intercom send --delivery queue --key build-state` would clear the first send's marker, see no outstanding wake, and queue a second wake. That gives two turns, which is the exact failure keyed queue exists to prevent.
- *Replace the G16c "Restart" bullet with:*
  > Restart: the wake marker stores the owner's `instance_id` (from the discovered endpoint, `GatewayEndpoint.instance_id`; `client.deliver_sync` returns it in its outcome) with the admission id. A wake is outstanding only when its `instance_id` equals the current owner's. A send compares against the endpoint it discovers for delivery; `pre_llm_call` compares against the owner instance id, discovered once per process and cached. A marker from an earlier instance is dead: the next keyed send queues a new wake, and the pending row rides the target's next turn as a held note. Nothing clears markers at `register()`.
- *Add a test line:*
  > a CLI `register()` between two keyed queued sends does not cause a second wake; a marker from a different owner instance is treated as dead.

**2. G16c test "wake turn interrupted during its API call / non-retryable API error → the note stays pending and the next turn gets it" can't pass with G16b.**
- G16b confirms delivery at the turn's first `pre_api_request`. That fires before the request is sent (`agent/turn_api_request.py:60-101`), so a note in a turn interrupted *during* its API call is already confirmed. The plan says such notes "count as delivered: they are already in the saved user message" (`passive.md:65`).
- *Replace that test clause with:*
  > wake turn interrupted during its API call, or a non-retryable API error → the note is delivered (confirmed at the first request), is not re-offered, and no second wake is queued; a wake turn that stops before its first request → the note stays pending and the next turn gets it.

**3. G16c/G16b: an unrelated turn must not take a keyed queued row that has a live wake.**
- As written, G16b's `pre_llm_call` selects "the target lineage's `pending` per-target rows", and that includes keyed queued rows.
- If the operator types while a wake is queued, that turn would take the keyed message as a held note, and then the wake's turn runs with nothing in it.
- *G16b, first acceptance bullet: change* "selects the target lineage's `pending` per-target rows" *to:*
  > selects the target lineage's `pending` per-target rows with `requested='passive'` (G16c adds keyed queued rows whose wake is dead)
- *G16c, second bullet: append:*
  > Outside its wake turn, a keyed queued row is offered only when its wake is dead (finding-1 rule); a row with a live wake waits for its wake turn.

**4. G16c: the wake frame would be echoed and answered by the existing hooks.**
- The wake is a real framed span with a recorded `header_sha`, so:
  - the echo's `pre_llm_call` finds it and posts it to a private chat (`echo.py:420-422`, `:455-469`);
  - the reply hook makes its row a reply candidate (`replies.py:134-141`, `:180-182`).
- With the newest row also a turn-id candidate, the sender would get two replies, one of them the whole answer sent against the wake row.
- *G16c, first bullet: after* "(`frame.build`, `header_sha` recorded)" *insert:*
  > on the row whose send submitted it, framed with `reply_mode='none'`; `echo._echo` skips rows that carry a wake marker; the only reply candidate in the wake turn is the newest row, through G16b's turn-id lookup
- The item already says "The wake line is never echoed". Keep that line, and add a test:
  > a private-chat target gets one echo (the newest version), never the wake line; a `requested` keyed queued message gets exactly one reply

## Should

**5. G16a and G16d test instructions point at helpers that don't exist.**
- No existing test fakes compression lineage. The tests use a real `SessionDB` in the temp home and build a compression child (`tests/test_replies.py:80-82`, `:470-473`).
- *G16a Tests: change* "lineage replacement across a compaction (fake SessionDB lineage as existing tests do)" *to:*
  > lineage replacement across a compaction (real `SessionDB` in the temp home: `end_session(<id>, "compression")` plus a child with `parent_session_id`, as `tests/test_replies.py:470-473` does)
- *G16d Tests: change* "fake owner and fake SessionDB as existing tests do" *to:*
  > a fake `client.deliver_sync`/`list_sessions` as `tests/test_route.py` does, and a real `SessionDB` in each temp home; the named home needs an identity marker (a `config.yaml`) to pass `hermes_constants.named_profile_is_live`
- *G16d Tests: change* "(the override governs discovery, ticket home, state.db, config and record)" *to:*
  > (the fake `deliver_sync` asserts `get_hermes_home()` is the target home when called, and the row, `state.db` lookups and config reads are the target's; discovery and the ticket mint are proven end to end in G16f)

  A unit test with a fake owner never runs discovery or the ticket mint.

**6. G16e: `pyproject.toml` is not the plugin's version.** It is the test config, `name = "hermes-intercom-tests"`, `version = "0.0.0"` (`pyproject.toml:6-8`). The plugin version is in `plugin.yaml:2` (`0.3.0`).
- *Change* "`plugin.yaml` and `pyproject.toml` version 0.4.0" *to:*
  > `plugin.yaml` version 0.4.0, and its `description` mentions passive and keyed messages (`pyproject.toml` is the test config; leave it)
- *Change the verify line* `grep -n "0.4.0" plugin.yaml pyproject.toml` *to:*
  > grep -n '^version: 0.4.0$' plugin.yaml

**7. The plan's skill guidance (P3, section 4) is in no item.**
- The session-mail skill is in the live install (`~/.hermes/skills/autonomous-ai-agents/session-mail/SKILL.md`), not in either repo, so no builder can edit it, and the live install is out of scope.
- *G16e, add an acceptance bullet:*
  > `docs/skill-guidance.md`: the section-4 "Choosing a delivery" text, ready to paste; the manager applies it to the installed session-mail skill at deploy.
- *G16f "Blocks" line: change* "deploy (manager: subtree pull, deployed branch, idle-gated gateway restart)" *to:*
  > deploy (manager: subtree pull, deployed branch, idle-gated gateway restart, session-mail skill guidance from `docs/skill-guidance.md`)

**8. G16d: profile-qualified header only on cross-profile sends.** "sender label carries its profile" applies to every send as written. That would change every live frame and break the existing frame and route tests.
- *Change the Framing bullet to:*
  > Framing: on a send with `profile` (a different profile from the sender's), the sender label carries its profile (`hermes@<profile>/<title>`) and the receipt names `<profile>/<title>`; same-profile frames are unchanged. `profile` naming the sender's own profile is the same as no `profile`.

**9. G16d should be blocked by G16c, not only by G16b.** Both rewrite `route.send`, the record migration list and `replies.py`, and AGENTS.md says "Execution — Parallelism: serial".
- *G16d: change* `blockers: ['G16b']` *to* `['G16c']`, *and* "Blocked by: G16b" *to* "Blocked by: G16c".
- *G16c "Blocks": change* "G16e" *to* "G16d".

**10. G16f: the cron-source cell can't be run by the harness.**
- The world builds owner-attached, classic-CLI and ntfy sessions only (`tests/plugins/intercom/test_e2e_owner.py:94-96`, `:135-136`). Proving "not to a cron-source session" needs that session to run a turn, i.e. a real cron run. The exclusion is already unit-tested in G16b.
- *Change* "delivered once to each conversation session, not to a cron-source session, not to the sender" *to:*
  > delivered once to each conversation session and not to the sender (the run-source exclusion is unit-tested in G16b)

## Minor

**11. G16a status text.** The plan's "replaced by <id> (handed over in turn T)" (`passive.md:65`) is in no item's acceptance.
- *G16a Receipt bullet: after* "`replaced by <id>`" *insert:*
  > (`replaced by <id> (handed over in turn <T>)` when the row also has `delivered_at`)

**12. G16a `key` with queue.** "stored like plain queue until G16c" is ambiguous.
- *Replace with:*
  > delivered as plain queue, with `note_key` recorded and no other effect, until G16c

**13. G16b: name the code seams a builder must touch.**
- `on_post_llm_call` returns early when no span is found (`replies.py:134-136`), so the turn-id candidates must be added before that return.
- The block-only rule keys on `requested='passive'`, not on "found by turn id". Keyed queued rows found by turn id keep the normal `requested` branch.
- `reply_for`'s `optional` branch tests `row["reply_mode"]` (`replies.py:167-169`).
- `passive.py` uses the dual `from . import …` / `import …` pattern (`echo.py:399-406`), because the tests import top-level modules (`tests/test_route.py:15-16`).
- Per-target frames carry the existing shared-chat line when the target's stored scope is shared. For `all` notes the scope is computed per recipient at handover.
- *Append as a "Code pointers" bullet.*

**14. G16d: name the published helpers.** `hermes_constants.get_default_hermes_root` (`hermes_constants.py:302`), `PROFILE_ID_RE` (`:401`), `named_profile_is_live` (`:433`), `set_hermes_home_override`/`reset_hermes_home_override` (`:32-44`). "Intercom enabled" means `intercom` is in the target's `plugins.enabled` and not in `plugins.disabled`, read with `load_config_readonly()` under the helper (`hermes_cli/config.py:1985`).
- *Append to the "Name to home" and refusal bullets.*

**15. G16f blockers.** The E2E does not need the README, so blocking on G16e only delays it. Optional: make G16f blocked by G16d, and make G16e block deploy instead.

## Checked and fine

- **G16a:** usage errors, migration shape, the `note_seen` DDL as its own statement, same-mode replacement, `held` kept for plain queue and `pending` for notes. These match `passive.md:22-35` and `:87`. CLI `--delivery` choices and `--message`/`--file` exist (`cli.py:101-106`).
- **G16b:** offer/confirm SQL, the compact and full frames, `all` selection, veto re-offer, block-only answers and echo rules. These match `passive.md:55-73` and `:88`.
- **G16f:** the harness files, conftest `--intercom-src` (`tests/plugins/intercom/conftest.py:17-31`), and `run_tests.sh` with `--fail-on-skip`, `--file-retries` and `--file-timeout` (`scripts/run_tests_parallel.py:1284`, `:1344`, `:1380`). `-- --intercom-src=…` is forwarded (`scripts/run_tests.sh:25-30`). The veto cell can use the harness's hook-probe plugin (`tests/plugins/intercom/_owner_world.py:459-460`).
- **Guards beyond the plan:** none found. The refusals, consent checks and `all` limits in the items are all the plan's.
