# `poc/` — DER-701 session-mail Trial

This folder is a **frozen record of a trial**. It is not product code and not instructions to load.

1. **Frozen record.** `poc.md`, `trial_session_mail.py`, `sm_probe/` and `evidence-results.json`
   (round 1), and everything under `round2/` (round 2), record what each Trial ran and saw on
   2026-11-09. Nobody edits them afterwards. The one
   allowed edit: if a file here ever holds a secret, security removes it and has it rotated.
2. **Never imported into product paths.** Nothing in `plugins/`, `hermes_cli/`, `scripts/`,
   `tools/`, `tests/` or anywhere else may import, copy or merge code from `poc/`. If the trial
   proves out, Build rebuilds the code from the HLD and LLD with its own tests.

`sm_probe/` is a throwaway plugin. The harness copies it into a temporary `HERMES_HOME` for the
run only. The delivery rule under test (`scripts/dashboard_dispatch.py` at `1516a52669`) is
written into the run directory outside git, and is not copied here. Logs stay outside git.

`round2/intercom_overlay/` holds trial stand-ins: the core seam, which is monkeypatched host calls
rather than a Hermes patch, plus routing, the record and reply capture. The harness copies them
next to an **unedited** copy of intercom inside a temporary `HERMES_HOME`. Neither the intercom
clone nor any product path was edited, and none may import this code.
