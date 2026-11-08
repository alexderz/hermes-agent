# model-routing (fork-only bundled plugin)

Limit-aware model routing for Alex's subscriptions: Claude Max 20x, ChatGPT Pro Lite and SuperGrok Heavy, with OpenRouter as the pay-per-use tier.

- **Where it lives:** only in the fork `alexderz/hermes-agent`, on branch `alex/model-routing`. That branch is merged into the deployed branch `alex/v0.22.0-mobile-fixes`.
- **Linear:** DER-675.
- **Design:** `decisions/2026-11-08-routing-design-proposal.md` in the vault `alexderz/vault-hermes-improvement`.

## Version 0.1: readers, meter and status (advisory only)

- `hermes model-routing collect` reads usage once. It writes `<HERMES_HOME>/plugin-data/model-routing/state.json` (mode 0600) and adds a line to `history.jsonl`.
  - Every read is a read-only quota GET, so it never spends tokens.
  - Claude, ChatGPT/Codex and OpenRouter use Hermes's `agent.account_usage` fetchers.
  - SuperGrok uses `cli-chat-proxy.grok.com/v1/billing` with Hermes's `xai-oauth` pool login, which Hermes refreshes under its own lock.
- A systemd user timer runs the collector every 15 minutes. house-infra owns that timer (`hosts/saturn/hermes.py`).
- Where to see the readings:
  - **Web dashboard:** a one-line meter under the chat (the `chat:bottom` slot) and in the sidebar footer (`header-right`), plus a full **Usage** tab.
  - **Desktop app:** a status-bar meter with a detail popover (`desktop/plugin.js`).
  - `/routing` in any session, or `hermes model-routing status`.
- The meter shows `Claude 16% P+7`: the percent of the weekly quota used, then the headroom against the weekly pace line. Minus means over pace. The dot colour always comes with this text.
- `POST /api/plugins/model-routing/refresh` reads every provider immediately. It runs at most once a minute.
- Nothing changes which model a session uses yet.

## Enable

The plugin is bundled, but Hermes plugins are opt-in, so run `hermes plugins enable model-routing`. On Saturn, house-infra does this.

## Tests

    cd plugins/model-routing && python3 -I -m unittest discover -s tests
