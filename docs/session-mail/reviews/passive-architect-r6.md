Commit: 4e86b227fb
Verdict: changes

Round 6: fire passive-note deadlines from the published `on_kanban_dispatch_tick` hook instead of a per-minute cron job (operator: "cron seems a rough way to do it").

The tick hook works, and it is the better mechanism: it runs inside the gateway, starts 5 s after boot, fires on idle ticks, needs no job, and is published. Two points in the proposal are not as assumed:
- **One tick, launch profile only.** There is one dispatcher per machine, and its hook reaches only the launch profile's plugin manager. Spike's deadlines will not fire in spike, so the handler has to sweep every profile itself (finding 2).
- **The handler blocks the dispatcher.** It runs inline in the dispatcher's worker thread, so it must hand off to a thread (finding 3).

With those in G16g, the mechanism is sound. Below are the findings, then the new G16g body and the G16f cells. Everything else from round 5 is kept: `within`, the refusals, one wake per deadline, waiting for the wake turn, consent and the compaction tip at fire time.

## Findings

**1. When the hook fires**

- **Every tick, idle included.** `_fire_dispatch_tick_hook` runs after every `dispatch_once`, after the board lock is released (`hermes_cli/kanban_db_dispatch.py:2026-2036`). That includes the unguarded fallback path (`:2021-2025`) and a lost lock (`skipped_locked`, `:2028-2029`). The outcome is `"idle"` when no activity counter moved (`hermes_cli/kanban_db.py:243-273`).
- **Empty or absent board.** The embedded dispatcher calls `dispatch_once` once per board per tick (`gateway/kanban_watchers_dispatcher.py:215-217`, `:174-213`). `list_boards` always returns `default` first (`hermes_cli/kanban_db_boards.py:122-125`), and a failed listing falls back to `default` (`gateway/kanban_watchers_common.py:37-46`). So the hook fires at least once per tick even with no tasks. With N boards it fires N times per tick, with `board=<slug>`.
- **Gating.** The hook is gated by `_kanban_observer_consumed` = `has_hook("on_kanban_dispatch_tick")` (`hermes_cli/kanban_db.py:184-192`, `:254-255`). It is true as soon as intercom registers the hook, and the cost is only payload assembly.
- **Timing.** The loop starts 5 s after boot (`gateway/kanban_watchers.py:265`) and ticks every `dispatch_interval_seconds`. The default is 60, with a floor of 1.0 (`gateway/kanban_watchers_dispatcher.py:49-54`).
- **`hermes pause`.** While paused, the loop skips `tick_once` (`gateway/kanban_watchers.py:283-286`, `gateway/kanban_watchers_common.py:100-110`), so **no hook fires**. Deadlines are held while paused and fire at the first tick after resume. That fits an emergency stop, because a wake starts agent work. The README should say so.
- **`dispatch_in_gateway: false`** (or `HERMES_KANBAN_DISPATCH_IN_GATEWAY=0`). The embedded loop never starts (`gateway/kanban_watchers.py:221-233`), so there is no tick and no hook in the gateway.
- **External daemon.** `hermes kanban daemon` is deprecated and exits 2 unless given `--force` (`hermes_cli/kanban_ops.py:158-178`). With `--force` it runs `dispatch_once` in its own CLI process. `plugins.invoke_hook`/`has_hook` lazily discover plugins (`hermes_cli/plugins.py:996-1004`, `:1044-1047`), so the hook does fire there, in that process's profile, and the handler can reach the owner from a CLI process. That works, but it is a deprecated path; G16g documents `wake-due` as the fallback instead (finding 4).
- **One-shot dispatch.** `hermes kanban dispatch` (one tick) also fires the hook. That is harmless, because the sweep is idempotent.
- **`dry_run=True` ticks fire too** (the kwarg). The handler ignores them.
- **Only one gateway per machine dispatches.** The dispatcher holds a machine-global singleton lock (`gateway/kanban_watchers.py:240-252`). A second gateway that loses it has no ticks, and the lock holder's sweep covers its profiles (finding 2).

**2. Multiplexer: one tick for all profiles, in the launch profile only. The proposal assumes otherwise.**
- The kanban root is shared across profiles by design: `kanban_home()` is `get_default_hermes_root()` (`hermes_cli/kanban_db.py:401-409`). One runner starts one dispatcher behind the machine-global lock.
- Each tick's work runs in `asyncio.to_thread` under an **empty `Context`** (`gateway/kanban_watchers_common.py:21-34`), so no profile override is bound and `get_hermes_home()` is the launch home.
- `invoke_hook` dispatches to `get_plugin_manager()`, which is keyed by the current home (`hermes_cli/plugins.py:822-841`, `:728-734`). So only the **launch (default) profile's intercom** receives the tick. Spike's plugin manager never does, and the `profile_name` kwarg is the launch profile's (`hermes_cli/kanban_db.py:174-181`).
- **Change:** the handler sweeps every live profile with intercom enabled: the root, plus `<root>/profiles/<name>` checked with `PROFILE_ID_RE` and `named_profile_is_live`, with intercom enabled read as in G16d. For each one it runs the due-sweep inside G16d's `in_profile(name)`.
  - Rows, consent, compaction tip and owner discovery then resolve to that profile, exactly as a cross-profile send does.
  - A profile served by another gateway is reached through its own owner, by discovery under the override.
- If the launch profile has intercom disabled, nothing fires. The README says so, and `wake-due` covers that setup.

**3. The handler must not block the dispatcher. It defers to one thread.**
- The hook runs synchronously in the dispatcher's worker thread, inside `tick_once`'s per-board loop (`gateway/kanban_watchers_dispatcher.py:215-217`, `hermes_cli/kanban_db_dispatch.py:2035`). A slow owner call would delay the next board's dispatch and the whole tick.
- **Change:** on a non-`dry_run` tick, the handler starts one daemon thread that runs the sweep and returns at once, as the reply hook does (`plugins/intercom/replies.py:210-212`).
- A process-wide non-blocking lock means a sweep still running makes later ticks return without starting another. That also turns the N-boards-per-tick case into one sweep per interval.
- Inside the thread, all owner calls go through `client.deliver_sync`, which runs on its own thread (`plugins/intercom/client.py:101-114`).
- The record claim (`BEGIN IMMEDIATE`) keeps this exactly-once even when a gateway sweep, a `--force` daemon sweep and a manual `wake-due` all run at once.

**4. Keep `hermes intercom wake-due` as the documented fallback, and install nothing.**
- It calls the same `sweep()` function: about ten lines of CLI wiring.
- It covers `dispatch_in_gateway: false`, a launch profile without intercom, and operators who want to fire due deadlines by hand.
- It makes the sweep testable without a dispatcher, and lets G16f drive one deterministic cell.
- The README says the gateway fires deadlines on its own, and that a setup without the in-gateway dispatcher can schedule `hermes intercom wake-due` itself (for example with a no-agent cron job). G16g creates no job.

**5. Accuracy and restart.**
- A deadline fires at the first tick after `wake_at`, i.e. within `dispatch_interval_seconds` (60 s by default) plus the sweep.
- After a gateway restart, an overdue deadline fires about 5 s after boot plus one interval (`gateway/kanban_watchers.py:265`).
- The round-5 rule for dead wakes (a marker from an earlier owner instance, never consumed, fires once more) is unchanged.

**6. Test environment note for G16f.**
- `kanban_home()` follows `get_default_hermes_root()`. With a temp `HERMES_HOME`, the test gateway's dispatcher lock and boards live in the temp root, so it does not contend with the live gateway's lock. This holds as long as `HERMES_KANBAN_HOME` is unset in the test environment (`hermes_cli/kanban_db.py:405-407`).
- The harness can set `kanban.dispatch_interval_seconds: 1` (the floor) for fast cells.

**7. Conflicts with G16a–f, unchanged from round 5:**
- the G16c Tests line "restart clears wake markers";
- the G16c echo rule meaning the live-span echo only;
- G16e's README order.

The G16f deadline cells are given below.

--- G16g ---
## G16g — Deadline on a passive note (within, woken from the kanban dispatcher tick) (added 2026-11-14, SM-Q29; architect rounds 5–6)

Repo: `intercom` · branch `der-767/deadline` · builder claude · blocked by G16d

- Type: Task · Parent: `DER-767`
- Design: `docs/session-mail/passive.md` P7 in section 5 (architect rounds 5–6) — operator question SM-Q29, 2026-11-14 ("yes", with the tick hook instead of cron)
- Builder: Claude Opus

**Outcome:** a per-target passive note can carry a deadline. If it is still undelivered when the deadline passes, the target is woken once through Hermes's queue, and that turn carries the note. A note delivered earlier causes no wake. The gateway fires deadlines by itself from the published `on_kanban_dispatch_tick` hook; no job is installed.

**Acceptance:**
- **Send:** optional `within` (integer minutes) on `send`. Tool schema in `_schema` (`__init__.py:116-179`), with the description line "within: for a passive note, wake the target after this many minutes (at least 5) if it has not run". CLI `send --within MINUTES` (`cli.py:99-110`). Stored as `wake_at = created_at + within*60` in a new `wake_at` column, added by the guarded migration pattern from G16a.
- **Usage errors** (G16a style: refused before a message id exists, nothing recorded, CLI exit 2, the reason in plain words):
  - `within` with `to: all`: it would wake every session;
  - `within` with a delivery other than `passive`: those hand the message over at once;
  - `within` under 5 or not a whole number.
- **Receipt:** `held (wakes by HH:MM if not run)`, local time of `wake_at`. `status` adds `wakes by HH:MM`, then `woken <time> (turn <id>)` once the wake turn has started.
- **Replacement:** keyed replacement (G16a) is unchanged. The newer row carries its own `wake_at` (none if it has none), and a replaced row is never due.
- **The sweep, `deadline.sweep()`** (new module `deadline.py`, with the dual-import pattern from `echo.py:399-406`). For each profile in turn:
  1. **Which profiles:** the root, plus every `<root>/profiles/<name>` passing `hermes_constants.PROFILE_ID_RE` and `named_profile_is_live`, whose config enables intercom (the G16d rule).
  2. **Under the override:** each profile's sweep runs inside G16d's `in_profile(name)`.
  3. **Discover:** discover that profile's owner once (`client._discover`); with no owner, skip the profile.
  4. **Select due rows.** A row is due when all of these hold:
     - `requested='passive'`, `result='pending'`, `delivered_at IS NULL`;
     - `wake_at <= now`;
     - no consumed wake;
     - no live wake. "Live" uses the G16c marker rule: an `instance_id` equal to the discovered owner's.
  5. **Claim:** for each due row, oldest first, in its own `BEGIN IMMEDIATE`, write the wake marker (owner `instance_id` plus a claim time) only while the row is still due.
  6. **Fire:**
     - check `injection_allowed()` (`route.py:174-185`); if it is off, release the claim and leave the row held;
     - re-resolve the target's compression tip (`address.py:196-200`);
     - submit the G16c wake line through `client.deliver_sync(tip, wake, "queue", submission_id)`. The line is built with `frame.build` and `reply_mode='none'`, with `header_sha` recorded on the note's row, and reads "a held note from `<sender>` is due; it follows".
  7. **Record** the admission id on the marker.
  8. **Failure:** a delivery failure releases the claim and logs one line. The sweep never raises.
- **Tick hook:** `register()` registers `on_kanban_dispatch_tick` (published, `hermes_cli/plugins.py:183-192`).
  - The handler ignores `dry_run=True`.
  - Otherwise it starts one daemon thread running `deadline.sweep()` and returns at once. A process-wide non-blocking lock makes the handler return without starting another sweep while one is running. It never blocks the dispatcher's tick (the hook runs inline in the dispatcher's worker thread, `gateway/kanban_watchers_dispatcher.py:215-217`).
  - The hook reaches only the launch profile's plugin manager (`hermes_cli/plugins.py:822-841`, dispatcher context `gateway/kanban_watchers_common.py:21-34`). That is why the sweep covers every profile itself.
- **`hermes intercom wake-due`:** a new CLI verb (`register_parser`, `cli.py:99-160`) that runs `deadline.sweep()` once in the foreground. It prints nothing on success, exits 0 unless the run itself fails, and is the documented fallback for setups without the in-gateway dispatcher. Nothing schedules it.
- **Wake turn:**
  - G16b's `pre_llm_call` recognises the wake span in `user_message`, using the existing span finder that G16c uses. It marks the wake consumed (`wake_turn = turn_id`) and hands over the target's held passive notes with G16b's frame and offer/confirm. The row named by the wake is included.
  - The wake span itself is never a reply candidate and is never echoed. The note is echoed at confirmed handover in a private chat, exactly as G16b does.
  - After its wake is submitted, a deadline row is offered only in its wake turn, or when its wake is dead (the G16c rule for keyed queued rows).
- **One wake per deadline:**
  - A consumed wake is never re-sent, even if its turn delivered nothing (veto, a runtime that carries no plugin text).
  - A wake from an earlier owner instance that was never consumed counts as dead. The next sweep fires it once more, which covers a deadline that passed, or a wake queue lost, across a gateway restart.
- **README section "Deadlines"** (written here; G16e keeps it). It covers:
  - `within` and its refusals;
  - that the gateway fires a deadline at the first kanban dispatcher tick after it (`kanban.dispatch_interval_seconds`, default 60 s; first tick about 5 s after boot);
  - that nothing fires while `hermes pause` is engaged, and due deadlines fire after resume;
  - that with `kanban.dispatch_in_gateway: false`, or with intercom disabled in the default profile, deadlines fire only when `hermes intercom wake-due` runs, which the operator may schedule;
  - that cross-profile deadlines are fired by the same sweep.
- **Profiles:** `within` works with G16d's `profile`. The row is in the target's record, and the sweep visits that profile.
- **Tests:** new `tests/test_deadline.py`, with a fake `client.deliver_sync`/`_discover` as `tests/test_route.py` does, a real `SessionDB` in the temp home, and a named profile home as in `tests/test_profiles.py`:
  - each usage error;
  - the receipt and status text;
  - not yet due → no wake;
  - due → exactly one wake through `deliver_sync(..., "queue", ...)` with `reply_mode='none'`;
  - delivered before the deadline → no wake;
  - two overlapping sweeps (hold the record transaction) → one wake;
  - a consumed wake is not re-sent on later sweeps;
  - a marker from a different owner instance, never consumed → fires once more;
  - injection off at fire time → no wake, row still held;
  - a target compacted between send and deadline → the wake goes to the new tip;
  - a due row in the named profile's record is woken by a sweep started in the root profile, and `get_hermes_home()` inside the fake `deliver_sync` is the named home;
  - a profile with intercom disabled is skipped;
  - the tick handler with `dry_run=True` does nothing;
  - the tick handler returns before the sweep finishes (a fake `deliver_sync` that blocks), and a second tick during a running sweep starts no second sweep;
  - the wake turn hands over the note and other held notes, and the wake span is neither a reply candidate nor echoed;
  - the note is echoed once at confirmed handover in a private chat;
  - after the wake is submitted, a different turn does not take the note; after a dead wake, it does;
  - a keyed replacement before the deadline takes the new row's `within`, and a replacement without `within` leaves nothing due;
  - `wake-due` with no owner → exit 0, nothing printed;
  - a passive note with `within` and `profile` lands in the target's record with `wake_at` set.

**Verify:**
```
cd <intercom-repo>
HERMES_HOME="$(mktemp -d)" <hermes-test-python> -I -m unittest discover -s tests -p 'test_deadline.py' -t . -v
HERMES_HOME="$(mktemp -d)" <hermes-test-python> -I -m unittest discover -s tests -p 'test_*.py' -t .
git grep -n -i -E "$HOUSE_PATTERN" -- . ':!tests/fixtures' ; test $? -eq 1
```

- **Blocked by:** G16d · **Blocks:** G16f
- **Out of scope:** everything the plan marks settled (no caps, holds, expiry, retries or approval gates on delivery; gateway only; published plugin API only, no core change; reply modes; `[SILENT]`; no general notifications or forwarding); the live install; any cron job or other scheduler setup (none is installed; `wake-due` is documented only); a timer of our own inside the gateway process; the subscription monitor's own sender (built elsewhere).
--- end ---

--- G16f ---
Add to G16f's acceptance list, before the subscription-monitor cell. The world config sets `kanban.dispatch_interval_seconds: 1`, leaves `kanban.dispatch_in_gateway` at its default, and runs with `HERMES_KANBAN_HOME` unset, so the temp gateway holds its own dispatcher lock:

- deadline: a passive note with `within` to an idle session, its `wake_at` moved into the past in the record → within a few dispatcher ticks the session gets exactly one new turn (the fake model sees the wake line and the held note in that turn's user message), `status` shows `woken … (turn …)`, and no second turn follows over the next several ticks;
- deadline delivered first: a note with `within` handed over at the session's next turn before its `wake_at` → after `wake_at` passes, no wake turn over several ticks;
- deadline across a restart: a note whose `wake_at` passes while the owner is stopped → after `hermes gateway run` restarts, the session gets one wake turn at an early tick (about 5 s after boot plus one interval);
- deadline in another profile: a named profile served by the multiplexer (as in the other-profiles cell), a note with `within` from default to a named-profile session → when it is due, that session gets one wake turn from the default gateway's tick;
- deadline fallback: with `kanban.dispatch_in_gateway: false` in a second world (or the same world restarted with it), a due note causes no wake until `hermes intercom wake-due` runs once (CLI, exit 0, no output), after which the session gets one wake turn.
--- end ---
