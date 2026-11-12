# Draft: listing pull request L-1

Status: nothing was posted, opened, or commented. This file is for review only. No pull request exists.

Where it would go: a pull request to NousResearch/hermes-agent. `plugins/AGENTS.md` asks for each new plugin-API name in its own pull request, with docs and a behavior test, naming the plugin that needs it.

Suggested title: Publish the gateway owner client on the plugin API

Asks: list these four names, document attaching to the profile's owner, and add the behavior test below. Change no runtime behavior. Do not add a `ctx` method in this pull request.

- `hermes_cli.gateway_runtime:discover_gateway_endpoint`
- `hermes_cli.gateway_client:connect_gateway`
- `hermes_cli.gateway_client:GatewayClientError`
- `hermes_cli.gateway_client:GatewayRPCError`

The plugin that needs them is intercom: a bundled plugin that delivers into another session of the same profile. The names are generic. Any plugin that attaches the way Ink and Desktop do can use them. Listing them publishes them to every plugin author, which is why each one is a real client surface and not a private helper.

This is one half of a single listing diff. The other half is L-2 (`CONTROL_FRAME_OPENERS` and `sanitize_user_prompt_text`). The fork landed both halves together. Split for upstream, this pull request introduces the shared files and the four client names. L-2 adds the two framing names, the relabel paragraphs, and the case-insensitive assertion in the same test. Union of the two pull requests:

- `hermes_cli/data/plugin_api.json` — one new group, source `public-api.md § Attaching to the profile's owner`, six entries.
- `scripts/gen_plugin_api_docs.py` — `render()` appends `scripts/gen_plugin_api_docs_footer.md` after the table (`utf-8-sig`). `--check` still exits 1 when the page is stale.
- `scripts/gen_plugin_api_docs_footer.md` — the generated section, new file.
- `website/docs/developer-guide/plugins/public-api.md` — regenerated from that. Not edited by hand.
- `tests/plugins/test_plugin_api_owner_client.py` — new behavior test.

No other file. `gateway_client.py`, `gateway_runtime.py`, `prompt_builder.py`, and `input_sanitize.py` are untouched.

A `ctx.owner_client()` wrapper would also satisfy boundary lint, and it is more code. This pull request does not add one. If a wrapper is preferred over publishing these names, it can replace the listing.

## Text to post

## Summary

Publish the gateway owner client so a plugin can attach to the profile's running `hermes gateway` and call its verbs. No behavior change. The client, discovery, and the verbs stay as they are. This only adds them to `hermes_cli/data/plugin_api.json`, regenerates the public API page, and proves the attach with a real owner.

Intercom is the plugin that needs the names. A plugin that drives another session of the same profile (a CLI command, a relay) today has to import unpublished modules, which boundary lint rejects once the plugin is bundled. The surface is the one Ink and Desktop already use, so it is listed for every plugin author and not as an intercom-only escape hatch.

## Names

New group in `hermes_cli/data/plugin_api.json`:

```json
{
  "source": "public-api.md § Attaching to the profile's owner",
  "entries": [
    "hermes_cli.gateway_runtime:discover_gateway_endpoint",
    "hermes_cli.gateway_client:connect_gateway",
    "hermes_cli.gateway_client:GatewayClientError",
    "hermes_cli.gateway_client:GatewayRPCError"
  ]
}
```

`discover_gateway_endpoint` reads the owner's live identity and never starts one. Its `endpoint` is `None` when no owner is ready. `connect_gateway` dials that endpoint and returns the client. `client.rpc(method, **params)` calls one verb. A refusal the owner sent raises `GatewayRPCError`, and `str()` of that exception is the bounded reason code. Any other client failure raises `GatewayClientError`.

## Docs

`scripts/gen_plugin_api_docs.py` appends `scripts/gen_plugin_api_docs_footer.md` verbatim after the generated table, so the prose cannot drift from a hand edit. The page is regenerated with `scripts/gen_plugin_api_docs.py`. `python scripts/gen_plugin_api_docs.py --check` exits 1 when `website/docs/developer-guide/plugins/public-api.md` is stale.

The new section is "Attaching to the profile's owner". For this pull request it says:

- Discovery never starts an owner. `endpoint is None` means there is no ready owner, and the caller does not dial.
- `connect_gateway` dials the discovered endpoint.
- `session.resume` takes the stored session id, subscribes the connection, and answers with the runtime id later verbs use. `omit_messages: true` keeps the transcript out of that answer.
- `prompt.submit` on that connection needs a `submission_id` the caller picks once per message.
- A drop after `prompt.submit` leaves the turn's outcome unknown. Resume the session to see whether it ran, and do not resend the work.
- The example raises `RuntimeError` when there is no endpoint, and maps `GatewayRPCError` to "the owner refused" plus the reason code.

The sibling pull request adds the two framing names to this same group and the relabel paragraphs to this same footer. Landing this one first leaves a section that attaches and submits. Landing the sibling adds sanitizing and the control-frame recipe to that section.

## Behavior test

`tests/plugins/test_plugin_api_owner_client.py`. Markers: `platforms("linux")`, `spawns_gateway_lookalike`.

A bundled test plugin `owner-probe` is written into a temp bundled-plugins directory, enabled in that home's `config.yaml`, and loaded through real discovery (`HERMES_BUNDLED_PLUGINS`). It registers `hermes owner-probe`. The test starts a real `hermes gateway run` in that temp home against a loopback fake model, with the gateway lock directory inside the temp root, the gateway start cap at 0, and the session-bus variables cleared, so discovery sees only the gateway this test started.

The session under test is an ordinary session of the same profile, created by another client (`session.create` with `source=cli`, then a seed `prompt.submit`). The plugin later finds it idle.

Cases this pull request owns:

- `private_import_findings` on the plugin directory is empty. On the base listing, the owner-client imports are findings. That is the red check.
- `hermes owner-probe --session <id> --text <text>` exits 0. The plugin calls `discover_gateway_endpoint`, `connect_gateway`, `session.resume` with `omit_messages: true`, then `prompt.submit` with a caller-chosen `submission_id`. The printed JSON has `resumed` and `submitted`. The owner persists the fake model's reply (`owner-probe-reply`) on that session.
- An unknown session id exits 3 and prints `rpc_error`. The plugin caught `GatewayRPCError` and printed `str(exc)`, the bounded code.
- A second home with the plugin enabled and no owner exits 4 and prints `{"error": "no-owner"}`. The plugin returns when `endpoint` is `None` and does not call `connect_gateway`.

The probe text in the shared test also carries a bracketed-paste wrapper and both `[System:` and `[SYSTEM:`. Asserting that those arrive relabelled and sanitized is the sibling pull request. This pull request's resume-and-submit case can send plain text; the sibling adds the relabel assertion to the same test.

## Not in this diff

No change to gateway behavior, session verbs, ticket minting, or prompt handling. No `ctx.owner_client()`. `sanitize_title` is not listed (it is a `SessionDB` method). The two framing names are the sibling pull request.
