# model-routing (Hermes plugin)

Limit-aware model routing for Alex's subscriptions (Claude Max 20x, ChatGPT Pro Lite, SuperGrok Heavy, with OpenRouter as the pay-per-use tier). Linear: DER-675 (Hermes routing), under DER-630 (limit-aware provider/model routing). Design: `decisions/2026-11-08-routing-design-proposal.md` in the vault `alexderz/vault-hermes-improvement`.

## Version 0.1 (step 1): readers and status, advisory only

- `hermes model-routing collect` reads usage once and writes `<HERMES_HOME>/plugin-data/model-routing/state.json` (0600), plus a line in `history.jsonl`. Every read is a read-only quota GET, so no tokens are spent.
  - Claude, ChatGPT/Codex and OpenRouter: Hermes's own `agent.account_usage` fetchers, the same path as `hermes usage`.
  - SuperGrok: `cli-chat-proxy.grok.com/v1/billing?format=credits` with Hermes's `xai-oauth` login from the credential pool. The pool refreshes the token under Hermes's lock, so the Grok CLI's 12-hour token problem does not apply.
- `hermes model-routing status [--json]`, `/routing` in any session, and a dashboard tab called **Usage** show one card per subscription: the big used percent and `P: ±N%` (headroom against the weekly pace line; minus means over pace), most over pace first, plus the would-be pick.
- Pace, latch and on-demand rules are in `pace.py` (pure functions, unit-tested).
- Nothing changes which model runs yet. Steps 2 to 5 (limit-error handling, cooldown file, per-turn route hook, on-demand tier) follow the design.

## Install (on Saturn, as `hermes`)

    ln -sfn ~/src/hermes-model-routing ~/.hermes/plugins/model-routing
    hermes plugins enable model-routing
    cp deploy/hermes-model-routing-collect.* ~/.config/systemd/user/
    systemctl --user daemon-reload && systemctl --user enable --now hermes-model-routing-collect.timer
    systemctl --user restart hermes-dashboard   # only to mount the dashboard tab's API the first time

## Tests

    python3 -I -m unittest discover -s tests
