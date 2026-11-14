Commit: 040e3db592
Verdict: changes

Round 5: P7, a per-message deadline on a passive note (SM-Q29), in `git diff 73b090e150 HEAD -- docs/session-mail/passive.md`. Intercom line numbers are in `integrate/session-mail` (f1ad26c). G16a–f are not changed here; conflicts with them are named in findings 5–8.

The behaviour P7 describes is sound and fits the existing wake mechanism. The open choice resolves cleanly: **a published `hermes intercom wake-due` command, run every minute by a no-agent Hermes cron job in each profile.** A timer in the owner process cannot be started reliably on the published API, and it would not exist after a restart until some turn ran, which is exactly when deadlines matter. Changes to P7 are needed: the mechanism, the rule for a row whose wake is in flight, the one-wake-per-deadline rule, and the deploy step. G16g is at the end.

## Findings

**1. Who fires the deadline: cron plus `wake-due`, not an owner timer.**

Why the owner timer fails:
- Plugins get no gateway-start hook. The full hook list (`hermes_cli/plugins.py:113-200`) has turn, session, kanban and gateway-dispatch events, but nothing that fires once when the owner comes up.
- `register()` also runs in every `hermes <plugin command>` process (`hermes_cli/main.py:3197-3221`). Inside the gateway it runs from synchronous config loaders (`gateway/config.py:583`, `gateway/config_loader.py:530`), not on the event loop.
- `ctx.spawn_task` needs a running loop (`hermes_cli/plugins_context.py:232-237`), so it can't tell owner from CLI reliably.
- Process identity by argv is banned (AGENTS.md, HX003).
- A timer started lazily from a hook (`pre_llm_call`) would not exist after a restart until some session runs a turn. When every session is idle, which is the case a deadline is for, nothing fires.

Why cron works, with no new host machinery:
- Hermes cron's built-in ticker scans every 60 s (`cron/scheduler_provider.py:152`, `:439`, and per served profile under multiplex at `:540`).
- `"every 1m"` is a valid interval schedule (`cron/jobs.py:784-806`).
- No-agent jobs run a script with no model call (`cron/jobs_invariants.py:11`). Empty stdout is a silent run with no delivery (`cron/scheduler.py:1546-1554`). A non-zero exit is reported (`:1537-1544`).
- The script must be a file under `<home>/scripts/` (`cron/jobs_invariants.py:16`, `:42`). A `.py` script runs on Hermes's own interpreter with the checkout on its path (`cron/scheduler_script.py:141-162`). Its environment carries the owning profile's `HERMES_HOME` (`cron/scheduler_script.py:476-482` → `build_subprocess_env`, `tools/environments/local.py` around line 400).
- **Restart:** jobs persist, the ticker resumes with the gateway, and `wake-due` decides by time, not by tick. A deadline that passed while the gateway was down fires at the first tick after it comes back.
- **Accuracy:** at most about two minutes after the deadline. P7 sets `within` ≥ 5 minutes.
- **Cost:** one short `hermes intercom wake-due` process per minute per profile. It does one indexed query and exits silently when nothing is due.

*Change to P7:* replace "Who fires the deadline: the architect decides …" with:

> Who fires it: `hermes intercom wake-due`, run every minute by a no-agent Hermes cron job in each profile that uses deadlines (deploy installs it; README documents the command). It wakes every passive note whose deadline has passed and has not had its wake, and prints nothing.

**2. One wake per deadline.** A target that vetoes turns, or runs the codex runtime, would otherwise be woken again every minute. That is a retry loop, and retries are settled out.

*Rule:* a note is due when all of these hold:
- `requested='passive'`, `result='pending'` and `delivered_at IS NULL`;
- `wake_at <= now`;
- no consumed wake (its wake turn has started);
- no live wake (an instance-scoped marker equal to the current owner's, the G16c rule).

A wake that was queued and then lost in a restart (dead marker, never consumed) fires once more after the restart. That is the "expired after restart fires on the next check" case P7 asks for. *Add to P7.*

**3. After its wake is submitted, the note waits for its wake turn.**
- Otherwise another turn (the operator typing) takes the note first, and the wake turn then runs a model call with nothing in it.
- G16c already has this rule for keyed queued rows ("a row with a live wake waits for its wake turn"). Reuse it for deadline rows.
- Before the deadline, and after a dead wake, the note rides any turn as usual.
- *Add to P7:* "Once its wake is submitted, the note is offered in the wake's turn (or when the wake is dead)."

**4. Cross-profile deadlines need the job in the target profile.** The row lives in the target's record (P6), so the target profile's `wake-due` fires it. *Add to P7:* "deploy installs the job in every profile with intercom enabled". The README states that a deadline needs the job in the target profile.

**5. Conflict, G16c Tests.**
- "restart clears wake markers and the row rides the next turn" contradicts G16c's own Restart bullet ("Nothing clears markers at `register()`"). That bullet is the round-groom fix.
- G16g relies on the bullet. The manager should reword that test to: "a marker from an earlier owner instance is dead and the row rides the next turn".

**6. Conflict, G16c echo rule.**
- "`echo._echo` skips rows that carry a wake marker" must mean the live-span echo only. That is the path that would post the wake line (`echo.py:420-422`, `:455-469`).
- A deadline note carries a wake marker and must still get G16b's confirmed-handover echo in a private chat.
- If the G16b/G16c builders route the passive echo through `echo._echo`, deadline notes lose their echo. G16g asserts the echo, so a wrong reading shows up as a failing test. The manager should confirm the intended reading with the G16c builder.

**7. Conflict, G16e README order.**
- G16e is blocked by G16d and owns the README and version, so as ordered it documents no `within` and no `wake-due`.
- G16g below writes its own README section.
- The manager should either make G16e blocked by G16g (the README is then whole at 0.4.0), or accept G16g's section as written.

**8. Conflict, G16f has no deadline cells.** The plan's Tests list them (`passive.md` P7 / Tests), and G16g blocks G16f, but G16f's acceptance doesn't include them. The manager should add to G16f:
- a deadline-passed note wakes an idle session once, and that turn carries it;
- a note delivered before its deadline causes no wake;
- a deadline that passed while the owner was stopped fires after `hermes gateway run` restarts and the job runs;
- `wake-due` run from a no-agent cron job in a named profile wakes that profile's session.

**9. P7 against the code: the rest checks out.**
- The new tool parameter lands in `_schema` (`__init__.py:116-179`) and the CLI flag in `register_parser` (`cli.py:99-110`).
- The refusals belong with G16a's usage errors (before a message id exists, exit 2).
- `wake_at` goes in the same guarded migration as G16a's columns (`record.py:85-118`).
- Replacement "takes the new note's `within`" falls out naturally: the newer row carries its own `wake_at`. The replaced row is never due, because due requires `result='pending'`.
- The wake reuses G16c's `deliver_sync(target, wake, "queue", submission_id)` path (`client.py:64-75`). Re-resolve the target's compression tip at fire time (`address.py:196-200`), because the session may have compacted since the send.
- Consent is checked at fire time (`route.py:174-185`): with injection off, no wake is sent and the note stays held.

--- G16g ---
## G16g — Deadline on a passive note: `within`, woken by `hermes intercom wake-due` from cron

Repo: `intercom` · branch `der-767/deadline` · builder claude · blocked by G16d

- Type: Task · Parent: `DER-767`
- Design: `docs/session-mail/passive.md` P7 in section 5 (architect round 5) — operator question SM-Q29, 2026-11-14
- Builder: Claude Opus

**Outcome:** a per-target passive note can carry a deadline. If it is still undelivered when the deadline passes, the target is woken once through Hermes's queue, and that turn carries the note. A note delivered earlier causes no wake.

**Acceptance:**
- **Send:** optional `within` (integer minutes) on `send`. Tool schema in `_schema` (`__init__.py:116-179`), with the description line "within: for a passive note, wake the target after this many minutes (at least 5) if it has not run". CLI `send --within MINUTES` (`cli.py:99-110`). Stored as `wake_at = created_at + within*60` in a new `wake_at` column, added by the guarded migration pattern from G16a.
- **Usage errors** (G16a style: refused before a message id exists, nothing recorded, CLI exit 2, the reason in plain words):
  - `within` with `to: all`: it would wake every session;
  - `within` with a delivery other than `passive`: those hand the message over at once;
  - `within` under 5 or not a whole number.
- **Receipt:** `held (wakes by HH:MM if not run)`, local time of `wake_at`. `status` adds `wakes by HH:MM`, then `woken <time> (turn <id>)` once the wake turn has started.
- **Replacement:** keyed replacement (G16a) is unchanged. The newer row carries its own `wake_at` (none if it has none), and a replaced row is never due.
- **`hermes intercom wake-due`:** a new CLI verb (`register_parser`, `cli.py:99-160`). Its run:
  1. Discover the owner once (`client._discover`). With no owner, exit 0 and print nothing.
  2. Select due rows. A row is due when all of these hold:
     - `requested='passive'`, `result='pending'`, `delivered_at IS NULL`;
     - `wake_at <= now`;
     - no consumed wake;
     - no live wake. "Live" uses the G16c marker rule: an `instance_id` equal to the discovered owner's.
  3. Process each due row oldest first, in its own `BEGIN IMMEDIATE`: claim the row by writing the wake marker (owner `instance_id` plus a claim time) only while it is still due.
  4. Then:
     - check `injection_allowed()` (`route.py:174-185`); if it is off, release the claim and leave the row held;
     - re-resolve the target's compression tip (`address.py:196-200`);
     - submit the G16c wake line through `client.deliver_sync(tip, wake, "queue", submission_id)`. The line is built with `frame.build` and `reply_mode='none'`, with `header_sha` recorded on the note's row, and reads "a held note from `<sender>` is due; it follows".
  5. Record the admission id on the marker.
  6. A delivery failure releases the claim and logs one line to stderr. Exit 0 unless the run itself fails.
  7. Print nothing on success, so the no-agent cron run stays silent (`cron/scheduler.py:1546-1554`).
- **Wake turn:**
  - G16b's `pre_llm_call` recognises the wake span in `user_message`, using the existing span finder that G16c uses. It marks the wake consumed (`wake_turn = turn_id`) and hands over the target's held passive notes with G16b's frame and offer/confirm. The row named by the wake is included.
  - The wake span itself is never a reply candidate and is never echoed. The note is echoed at confirmed handover in a private chat, exactly as G16b does.
  - After its wake is submitted, a deadline row is offered only in its wake turn, or when its wake is dead (the G16c rule for keyed queued rows).
- **One wake per deadline:**
  - A consumed wake is never re-sent, even if its turn delivered nothing (veto, a runtime that carries no plugin text).
  - A wake from an earlier owner instance that was never consumed counts as dead. The next `wake-due` run fires it once more, which covers a deadline that passed, or a wake queue lost, across a gateway restart.
- **Cron job:**
  - The README (section "Deadlines") gives the one-time setup per profile. Put `intercom-wake-due.py` in `<profile home>/scripts/`, containing:
    ```
    import sys
    from hermes_cli.main import main
    sys.argv = ["hermes", "intercom", "wake-due"]
    main()
    ```
  - Then run:
    ```
    hermes [-p <profile>] cron create "every 1m" --no-agent --script intercom-wake-due.py --name intercom-wake-due
    ```
  - It states that a deadline fires within about two minutes after `wake_at`, and that a cross-profile deadline needs the job in the target profile.
  - `wake-due` never creates the job itself; deploy runs the setup.
- **Profiles:** `within` works with G16d's `profile`. The row is in the target's record, so the target profile's job fires it.
- **Tests:** new `tests/test_deadline.py`, with a fake `client.deliver_sync`/`_discover` as `tests/test_route.py` does and a real `SessionDB` in the temp home:
  - each usage error;
  - the receipt and status text;
  - not yet due → no wake;
  - due → exactly one wake through `deliver_sync(..., "queue", ...)` with `reply_mode='none'`;
  - delivered before the deadline → no wake;
  - two overlapping `wake-due` runs (hold the record transaction) → one wake;
  - a consumed wake is not re-sent on later runs;
  - a marker from a different owner instance, never consumed → fires once more;
  - injection off at fire time → no wake, row still held;
  - a target compacted between send and deadline → the wake goes to the new tip;
  - the wake turn hands over the note and other held notes, and the wake span is neither a reply candidate nor echoed;
  - the note is echoed once at confirmed handover in a private chat;
  - after the wake is submitted, a different turn does not take the note; after a dead wake, it does;
  - a keyed replacement before the deadline takes the new row's `within`, and a replacement without `within` leaves nothing due;
  - no owner → exit 0, nothing printed;
  - a passive note with `within` and `profile` lands in the target's record with `wake_at` set.

**Verify:**
```
cd <intercom-repo>
HERMES_HOME="$(mktemp -d)" <hermes-test-python> -I -m unittest discover -s tests -p 'test_deadline.py' -t . -v
HERMES_HOME="$(mktemp -d)" <hermes-test-python> -I -m unittest discover -s tests -p 'test_*.py' -t .
git grep -n -i -E "$HOUSE_PATTERN" -- . ':!tests/fixtures' ; test $? -eq 1
```

- **Blocked by:** G16d · **Blocks:** G16f
- **Out of scope:** everything the plan marks settled (no caps, holds, expiry, retries or approval gates on delivery; gateway only; published plugin API only, no core change; reply modes; `[SILENT]`; no general notifications or forwarding); the live install, including creating the cron job (deploy does that from the README); a timer inside the gateway process; the subscription monitor's own sender (built elsewhere).
--- end ---
