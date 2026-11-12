# poc/v023/ — Trial record for DER-686 on the v0.23 base

Two rules apply to everything in this folder:

1. **Frozen record.** These files are the record of a trial, not product code and not
   instructions to load. They are not edited after the Trial, except to remove a secret
   (security removes it and has it rotated).
2. **Never imported into product paths.** Nothing here is imported, copied or merged into
   `hermes_cli/`, `gateway/`, `tui_gateway/`, `apps/`, `plugins/` or any other product path. If
   the trial proves out, Build rebuilds what it needs from the note.

The parent folder `poc/` is the separate, frozen record of the v0.22 trial; it is not changed.

Contents:

- `poc.md` — question, setup, evidence, conclusion, what Build must rebuild.
- `trial_gateway_oneshot.py` — the harness (a gateway daemon and a `hermes chat -q --oneshot` CLI
  on a temporary `HERMES_HOME`, a fake local model, a second gateway client).
- `evidence-results.json` — the run's check results, temporary paths replaced by a placeholder.
