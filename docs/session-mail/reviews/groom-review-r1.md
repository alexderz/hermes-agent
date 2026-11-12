Commit: fbb00076f4

Verdict: changes needed

Reviewed `docs/session-mail/groom.md` at `fbb00076f4` against `lld.md` (round 9; build table,
B1–B12, § Verify, § Land, § Rollout, § Planned items), following groom-step § 2.

What holds:
- **LLD build items:** each of G-1 … G-13 maps to one groom item. The G14 split (E2E out of G-2)
  is reasoned and raised for the manager.
- **Dropped LLD edges:** G-2 ← G-1 and G-7 ← G-1 are dropped correctly. All six names exist at
  the base (`agent/prompt_builder.py:572`, `hermes_cli/input_sanitize.py:50`,
  `hermes_cli/gateway_client.py:48,58,319`, `hermes_cli/gateway_runtime.py:318`). The runtime
  private-import check only warns (`hermes_cli/plugin_validate_private_imports.py`), so G14 does
  not need G1 either. Only boundary lint at G12 does.
- **Graph:** "Blocked by" and "Blocks" agree in both directions. There are no cycles. The waves
  match the edges.
- **Gates:** both gates are needed: G14 before the one gateway restart, and the operator's
  restart window on G12.
- **Hygiene:** no secrets, house host names or local absolute paths appear in any body
  (`hosts/<gateway-host>/…` is a placeholder).

## Blocking

1. **G14's Verify command cannot run: the runner rejects `--intercom-src`.**
   `scripts/run_tests.sh` forwards bare flags to `scripts/run_tests_parallel.py`.
   `_pytest_flag_error` (`:1075-1104`, called at `:1435-1437`) checks every bare flag against a
   pytest parser that has only setuptools plugins loaded. A `pytest_addoption` in
   `tests/plugins/intercom/conftest.py` is not loaded there, so `--intercom-src=<intercom-repo>`
   fails with `unrecognized arguments` before any test runs. Separately, the harness *skips*
   when no plugin source is found, so a wrong path gives a green run that proves nothing.
   **Fix:** in G14 Verify, write
   `scripts/run_tests.sh --fail-on-skip tests/plugins/intercom/test_e2e_owner.py -- --intercom-src=<intercom-repo>`
   (an explicit `--` is forwarded as-is). Add `--fail-on-skip` to G12's
   `scripts/run_tests.sh tests/plugins/intercom/` line as well.

2. **G14's failure path does not hold back G12.** The Verdict bullet says a failure "is filed as
   a fix item blocked by this one". G14 then closes, which meets G12's only E2E blocker, and the
   fix items block nothing. So G12 can vendor and deploy on a failed E2E, which defeats the gate
   the Graph describes.
   **Fix:** write that every fix item filed from a failing G14 verdict **blocks G12** and ends
   with a G14 re-run, and that G12 needs a **passing** G14 verdict. There is one exception: an
   O21 failure resolved by the LLD's own fallback (no echo for v1, SM-Q15 → a). Name it as a G6
   change that also blocks G12.

3. **G13's scrub Verify always fails.** `grep -nE -i '<pattern>' docs/upstream/` greps a
   directory without `-r`. It exits 2 ("Is a directory"), so `test $? -eq 1` can never pass.
   The pattern is also an unnamed placeholder, so the body is not self-contained.
   **Fix:** `grep -rnE -i "$HOUSE_PATTERN" docs/upstream/; test $? -eq 1`. State that the manager
   supplies `HOUSE_PATTERN` when the builder starts, as a shell variable, never written into the
   ticket. Add a generic check the builder can run alone:
   `grep -rnE '(/home/|/var/|/srv/|/Users/|[0-9]{1,3}(\.[0-9]{1,3}){3})' docs/upstream/; test $? -eq 1`.

## Minor

4. **No item builds the B9 receipt wording.** G3 says it "returns the B9 receipt", but its
   acceptance names only `target_session` and `shared_chat`. G10 names only exit codes. Not
   assigned to any item:
   - the `reply` field (it echoes the framed `reply_mode`);
   - the readable line ending `(session <id>)`;
   - the cold-start sentence (`"<title>" was not open, so the gateway reopened it and message <id> started a turn there.`);
   - the `not-addressable` sentence;
   - candidates' ids on `ambiguous` and `unknown`.

   **Fix:** add these to G3's acceptance, which builds the receipt in step 7. Cover them in
   `test_route.py`.

5. **G2's interface does not cover what G3 and G10 need from the owner.**
   - B7's `admission_id` comes from `prompt.submit`, but G2's `deliver_sync` names no return
     shape.
   - G10's `status` reads `prompt.receipt`, and no G2 method wraps it.

   **Fix:** state that `deliver_sync` returns `applied`, `applied_detail` and `admission_id` (or
   an error code). Add a read-only `receipt(admission_id)` beside `list_sessions`. Note both
   under "For the manager" item 4, like the injected lister.

6. **Two LLD test rows have no single owner.**
   - **(a) The late steer:** "a steer that lands during the final request is echoed by the later
     turn's `pre_llm_call`" (G-6 row). It is in G6's acceptance, but G6's Verify note does not
     name it, and G14's GW-4 bullet covers only "a steer followed by the final answer".
   - **(b) The per-platform escaper unit tests** (G-6 row): G7 builds `ECHO_ESCAPERS`, and both
     G6's and G7's Verify notes claim it.

   **Fix:**
   - For (a), add the late-steer case to G14's GW-4 bullet; it needs a real turn finalizer.
   - For (b), give the per-platform escaper tests to G7 (`test_frame.py`). Leave G6 the
     missing-escaper warning and the post decision.

7. **G14 is not self-contained about the temp home's config.** Delivery is refused
   `injection-off` without consent (B2 step 3), and the echo cells need a private chat.
   **Fix:** add to G14 Acceptance → Harness that the harness writes `config.yaml` with:
   - `plugins.enabled: [intercom]`;
   - `plugins.entries.intercom.allow_gateway_injection: true`;
   - `settings.user_name`;
   - `settings.echo_chats` naming the fake ntfy chat;
   - one unlisted ntfy group for the N4 and shared-chat cells.

8. **G1's behaviour test needs a fake model.** `prompt.submit` on an idle session starts a turn.
   **Fix:** state in G1's acceptance that the owner runs with a fake-model provider in the temp
   `HERMES_HOME`, as in G14.

9. **Acceptance misses some LLD test-row assertions.**
   - G3 (G-3 row): "`reply_mode` is stored as passed" and "`injection-off` for **every** target
     kind".
   - G8 (G-8 row): "two writers" (the sender's row and hash; the owner's reply fields and reply
     row).
   - G10 (G-10 row):
     - `--to @x` without project addressing exits 3 with the `project-addressing-unavailable`
       text;
     - the tool mentions `@<project>` when the check is true;
     - with discovery `None`, `starting` or `draining`, `inbox.start()` is never called.

   **Fix:** add each line to that item's acceptance.

10. **G11's first Verify line is not a check.**
    `git diff integrate/session-mail-023 -- scripts/dashboard_dispatch.py   # docstring lines only`
    always exits 0. **Fix:** use a check that fails on a code change, for example
    `python -I -c "import ast,sys;a,b=(ast.parse(open(p).read()) for p in sys.argv[1:]);[n.body.pop(0) for n in (a,b) if ast.get_docstring(n)];sys.exit(ast.dump(a)!=ast.dump(b))" <(git show integrate/session-mail-023:scripts/dashboard_dispatch.py) scripts/dashboard_dispatch.py`.
    Or, if the manager drops the note ("For the manager" 2), use
    `git diff --exit-code integrate/session-mail-023 -- scripts/dashboard_dispatch.py`.

11. **G12's Verify does not run the vendored plugin's own suite.**
    `scripts/run_tests.sh tests/plugins/intercom/` runs only the E2E. The unit tests under
    `plugins/intercom/tests/` (intercom's `unittest` style) are never run against the vendored
    copy. **Fix:** add
    `( cd plugins/intercom && HERMES_HOME="$(mktemp -d)" <hermes-test-python> -I -m unittest discover -s tests -p 'test_*.py' -t . )`.

12. **The Graph prose is wrong about G14.** It says G14 "is the only blocker of G12 that is not
    already met by an earlier wave", but G11 is in wave 5 too. **Fix:** say that G14 and G11
    both close in wave 5, and that G14 is the only gate.
