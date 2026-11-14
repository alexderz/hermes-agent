Commit: a091a6ca9f
Verdict: changes

Round 4 review: P6 (other profiles, explicitly) and the in-profile rule for `all` (`git diff c878340aac HEAD -- docs/session-mail/passive.md`). Earlier rounds stay settled.

P6 can be built on the published API. The way to do it is to run the **whole target side of a send inside the target profile's home**, using `hermes_constants.set_hermes_home_override` (a published module). Everything downstream then works unchanged in the target profile: addressing, consent, the record row, framing, the owner attach, and later the target's own hooks (reply, echo, passive, keyed queue).

As written, P6 leaves four things open:
- where the row lives;
- how a reply gets home;
- the reverse attach direction, which fails as specified (finding 2);
- the ask waiter, which can't cross profiles.

It also adds a CLI flag and a `Bot Chat` keyword that aren't needed.

The `all` rule (`passive.md` §3, "Who gets `all` notes", sender's own profile only) is correct and costs nothing. A profile's hooks only ever read that profile's record (finding 1c), so `all` stays in-profile by construction; just refuse `profile` together with `to: all`.

## Answers to (a)–(f)

### (a) Attaching to another profile's owner

**Discovery.**
- `discover_gateway_endpoint(<spike home>)` finds no control socket of spike's own, so it falls through to `_served_by_multiplexer` (`hermes_cli/gateway_runtime.py:328-334`, `:225-253`).
- That queries the default multiplexer's `identify` and returns an endpoint with `profile_id` = spike's home and `control_home` = the multiplexer root (`:250`, `:156-159`).
- It is read-only and never starts an owner (`:318-323`).
- On this machine the default profile has `gateway.multiplex_profiles: true` (`~/.hermes/config.yaml:1103`), so spike is served there.

**Ticket.**
- `connect_gateway(endpoint)` mints a ticket through `_session_ticket(gateway_profile_home(get_hermes_home()), endpoint)` (`hermes_cli/gateway_client.py:336-339`).
- `control_home_for` takes the endpoint's `control_home` when it has one (`hermes_cli/gateway_client.py:278`, `hermes_cli/gateway_runtime.py:164-168`). The ticket request names `profile_id` = spike (`hermes_cli/gateway_client.py:282`).
- The multiplexer's control socket mints it only for a verified same-UID peer (`gateway/control_socket.py:381-388`, `:418-424`) and a matching `instance_id` (`:392-393`).

**Subject.**
- The subject is the socket's peer identity (`subject = params.get("subject", peer_subject)`, `gateway/control_socket.py:400`).
- Intercom must not pass `subject`. That parameter is only for a dashboard naming a structured login subject (`:400-404`, `hermes_cli/gateway_client.py:321-323`).

**Authorisation at the owner.**
- On redeem, the WebSocket binds to `authority_for_profile_id(runner, grant['profile_id'])`, which is spike's authority. It closes with 4403 if that profile isn't served (`gateway/run_api.py:493`, `:517-523`).
- The connection then runs under `owner_scope(authority)`, with `auth_identity.profile_id` = spike and `profile_scope` = `profile` (`:527-533`).
- There is no further actor or principal check. The gates are the same as for today's in-profile delivery: embedded chat enabled, a native peer, not draining (`:486-489`, `:509-515`).
- "Exclusive maintenance" refusals don't apply: `exclusive_maintenance` guards backup/restore only (`gateway/runtime_ownership.py:330-350`, `hermes_cli/backup.py:935`, `:1549`, `:1647`).

**The reverse direction (spike → default) fails as P6 specifies it.**
- Run from spike's context, `gateway_profile_home(get_hermes_home())` is spike's home. The default profile's endpoint has no `control_home`, so `control_home_for` returns spike's home (`hermes_cli/gateway_runtime.py:166-168`).
- The ticket query then dials spike's own control socket, which a served secondary doesn't have (`:226-228`), and the send fails.
- The fix is the home override around the attach (finding 2).
- `client._run` copies the context into its worker thread (`plugins/intercom/client.py:24-26`, `:101-114`), so the override set by the caller carries into discovery and the ticket mint.

### (b) Reading the target profile's sessions and Bot Chat read-only

- Every intercom read already follows `get_hermes_home()`:
  - `SessionDB()` defaults to `get_hermes_home() / "state.db"` at call time (`hermes_state.py:201-204`);
  - config loads `get_hermes_home() / "config.yaml"` (`hermes_cli/config.py:433-435`, with a per-path cache at `:2225-2229`);
  - the owner lister goes through the same `_discover()` (`plugins/intercom/client.py:130-136`).
- So under the override, the existing code reads spike's state without change: `address.resolve`, `address.list_sessions`, `scope.chat_scope`, `route._facts`. `SessionDB(read_only=True)` is already what intercom uses (`plugins/intercom/replies.py:332`).
- **Bot Chat needs no keyword.** A bot's canonical session is the one titled `Bot Chat` (`tools/bot_mode_probe.py:37`), and titles are unique per profile (`hermes_state_schema.py:137`). The existing exact-title rule (`plugins/intercom/address.py:84-86`) already resolves `to: "Bot Chat"`. spike is a Bot Mode profile (`profile.yaml` `ui_meta.hermes-bots`, "Cyber Defender").
- A Bot Chat that a `hermes -p spike chat` runner holds at that moment (`tools/bot_mode_dm.py:11`) is in another runtime. It is refused `not-addressable` as today (`plugins/intercom/client.py:41`, `:53`).

### (c) Where rows and reply bookkeeping live

**Rule: a message's row lives in its target profile's record.** The reasons:
1. Plugins load into one manager per profile home (`hermes_cli/plugins.py:716-733`), with module state isolated per manager (`:737-750`). spike's turns run spike's intercom instance.
2. That instance opens `get_hermes_home()/plugin-data/intercom/record.db` (`plugins/plugin_storage.py:27-33`, `plugins/intercom/record.py:91-96`), i.e. spike's file.
3. Every target-side consumer looks the row up there: the reply hook (`plugins/intercom/replies.py:93-108`), the echo (`plugins/intercom/echo.py:459-462`), passive handover and the keyed-queue wake (P2, P5).

Writing the row under the override puts it there with no new mechanism: `record.insert` at `plugins/intercom/route.py:134`. A row written to the sender's record would not be found: `requested` would never answer, private chats would get no echo, and passive and keyed queue couldn't work.

**Reply return.**
- The target's reply hook answers with `route.send(session_id, row["sender_session_id"], …)` (`plugins/intercom/replies.py:217-218`). That resolves the sender's id *in the target profile* and fails.
- Add a `sender_profile` column, set at send, and have `_deliver` pass `profile=row["sender_profile"]`.
- The reply then becomes a message to the sender, and its row lands in the sender's record by the same rule. The sender's own reply bookkeeping (`reply_state`, `reply_message_id`) stays on the original row in the target's record.

**`ask` cannot cross profiles.**
- The waiter is an in-process dict in the sender's module instance (`plugins/intercom/replies.py:236-249`).
- The target's `reply` tool runs in the target's instance and looks in its own `_waiters` (`:286-289`), so it never finds the waiter and the ask always times out.
- Refuse `profile` with `ask`.

**Status and log.** The sender's `status <id>` for a cross-profile message reads the target's record under the same override. The receipt names the profile, so `status` can take it from the receipt. Don't keep a mirror row.

### (d) Intercom disabled in the target profile

**Refuse every mode,** with the reason "session mail is not enabled in profile spike". P6's "live still works, passive and requested refused" isn't viable:
- With the plugin off in spike, none of its hooks run there. No reply is collected, so even `requested` on a live message is lost.
- No echo is posted, which breaks the trust-model promise for private chats (`plugins/intercom/README.md:169`).
- Nothing relabels lookalike frames on that side.
- Enabling the plugin is the target profile's opt-in. That is the profile-level form of the existing consent rule.

**Check:** under the override, read `plugins.enabled` / `plugins.disabled` with `load_config_readonly()` (`hermes_cli/config.py:1985-1989`). spike today has intercom enabled with `allow_gateway_injection: true` (`~/.hermes/profiles/spike/config.yaml:72-81`).

### (e) Consent and framing

- **Consent:** `injection_allowed()` already reads the config "now" through `load_config_readonly` (`plugins/intercom/route.py:174-185`). Under the override it reads the *target's* `allow_gateway_injection`, which is P6's rule, with no new code.
- **Chat scope and echo settings:** these must come from the target too.
  - `scope.rule` reads `echo_chats`/`owner_user_ids` through `ctx` (`plugins/intercom/scope.py:63-70`), and `ctx` is the *sender's* plugin context.
  - Read the target's `plugins.entries.intercom.settings` with `load_config_readonly()` under the override instead.
  - The same applies to `user_name` in the frame (`plugins/intercom/route.py:138`).
- **Order:** sender facts (`_Who`, the sender's scope) are computed before entering the override, in the sender's home (`plugins/intercom/route.py:95-99`, `:124-125`).
- **Framing:**
  - The header keeps its shape, which the reply regex needs (`plugins/intercom/replies.py:57`), but the sender label carries its profile: `hermes@default/<title>`.
  - The receipt names the target as `spike/<title>`.
  - The "not `<user>`, no approval" sentence is unchanged.
  - Same-user profiles are still peers, not the operator.

### (f) Simplest shape that meets the request

1. **Tool:** `profile` on `send` and `list` only.
   - **Refused:** `profile` with `to: all`, `profile` with `ask`, an unknown or deleted profile name, and intercom not enabled there.
   - **Name to home:** `default` maps to `get_default_hermes_root()`; any other name maps to `<root>/profiles/<name>`, checked with `PROFILE_ID_RE` and `named_profile_is_live` (`hermes_constants.py:302`, `:433`). All of these are published `hermes_constants` names.
2. **One helper, `in_profile(name)`:** `token = set_hermes_home_override(home)` and `try/finally reset_hermes_home_override(token)` (`hermes_constants.py:32-44`). `route.send(..., profile=…)` runs steps 1–7 inside it (`plugins/intercom/route.py:105-171`): resolve, scope, consent, insert, frame, hash, deliver.
3. **Record:** one new column, `sender_profile`. The reply hook's `_deliver` sends back with that profile.
4. **Everything else is unchanged.** Passive, keyed, keyed queue and echo all work cross-profile because the row is in the target's record and the target's hooks run there.
5. **No new CLI flag.** A script already sends in another profile with the global `hermes -p spike intercom send|list|status …`. Its sender is a script, whose replies are stored only (`plugins/intercom/replies.py:53`). That is the existing semantics, so P6's `--profile` duplicates `-p`.

## Findings

### Blocking

**1. Decide where rows live and how replies return.** This is the core of P6. Write the rule from (c):
- the row goes in the target profile's record, written under the override;
- `sender_profile` on the row;
- the reply hook delivers back with it;
- refuse `ask` with `profile`.

Without this, `requested` never answers across profiles, echo never fires, and passive and keyed queue can't work there.

**2. Run the whole target side, attach included, under `set_hermes_home_override(target_home)`.** As P6 states it (calling `discover_gateway_endpoint(<that home>)` only), spike → default fails at the ticket mint (`hermes_cli/gateway_client.py:337`, `hermes_cli/gateway_runtime.py:166-168`). The override also gives the target's consent, config, `state.db` and record for free (b, e). Compute the sender facts first, outside the override.

### Should

**3. Intercom disabled in the target: refuse every mode** (d), not "live still works".

**4. Read chat-scope settings and `user_name` from the target's config, not the sender's `ctx`** (`plugins/intercom/scope.py:63-70`, `plugins/intercom/route.py:138`).

**5. Drop the `--profile` CLI flag and the `Bot Chat` keyword.** `hermes -p <name> intercom …` already covers scripts, and the exact title `Bot Chat` is unique per profile (`hermes_state_schema.py:137`). In the README, say that `to: "Bot Chat"` with `profile=<bot>` is how to reach a bot.

**6. Attach as the socket peer and never pass `subject`.** State it, so nobody reaches for the dashboard path (`gateway/control_socket.py:400-404`).

### Minor

**7. Addressing scope in v1.** `@project` with `profile` should be refused. The project-addressing snapshot is the sender process's (`plugins/intercom/__init__.py:361-363`), and the plan lists only id, exact title and Home (`passive.md` P6).

**8. Migration.** A target `record.db` created by an older intercom gets the guarded `ALTER` on its first cross-profile open (P1). The new `sender_profile` column joins that list. Existing rows default to NULL, meaning "same profile".

**9. Tests (E2E, real imports, temp `HERMES_HOME` with a named profile served by the multiplexer):**
- default → spike and spike → default (the second is the case that fails without finding 2);
- `requested` answered back across profiles;
- a passive note to spike handed over at spike's next turn;
- target with injection off → refused;
- target with intercom disabled → refused;
- `profile` with `all` and `profile` with `ask` → refused;
- `to: "Bot Chat"` resolving in a Bot Mode profile.

## Verdict

Changes. Write findings 1 and 2 into P6; those are the design. Take 3–6 as stated. With those in, P6 is ready for the gate.
