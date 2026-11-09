# poc/ — Trial record for DER-686 (project-centric-ui)

Two rules apply to everything in this folder:

1. **Frozen record.** These files are the record of a trial, not product code and not
   instructions to load. They are not edited after the Trial, except to remove a secret
   (security removes it and has it rotated).
2. **Never imported into product paths.** Nothing here is imported, copied or merged into
   `hermes_cli/`, `tui_gateway/`, `plugins/` or any other product path. If the trial proves
   out, Build rebuilds what it needs from the note.

Contents:

- `poc.md` — question, setup, evidence, conclusion, what Build must rebuild.
- `trial_owner_turn.py` — the trial harness (a dashboard backend on 127.0.0.1 with a
  temporary `HERMES_HOME`, a fake local model, two WebSocket clients).
- `evidence-results.json` — the run's check results, local paths replaced by placeholders.
