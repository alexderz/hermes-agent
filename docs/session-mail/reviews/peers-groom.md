Commit: 94977e7657
Verdict: changes

Groom check of `docs/session-mail/g17-items.md` (94977e7657) against `docs/session-mail/peers.md` (7991f1c4a9), the architect round-1 findings, the intercom repo (`wt/intercom-main` at 8a15373) and hermes-agent (`wt/v023`).

The items follow the plan faithfully, and the order works. Five things need fixing before build:
- G17c's JSON would refuse every peer (finding 1).
- G17c's reload would not revoke (finding 2).
- G17a has no way to tell `route.send` the sender is a peer (finding 3).
- G17a needs a `peers.json` loader that the items create only in G17b (finding 4).
- G17b and G17e need certificate details Python 3.14 enforces (finding 7).

The rest are precision and trimming.

Caddy facts below come from a loopback trial: Caddy v2.11.4, the G17c JSON shape (one TLS policy with no `match`, a leaf folder verifier, a cert from files), `XDG_CONFIG_HOME`/`XDG_DATA_HOME` in a temp dir. The temp dirs were deleted afterwards, and nothing listened off loopback.

Trial results:
- Own path: 200.
- Other peer's path and `/p/x/...`: 403.
- Case, `..` and `%2D` tricks: rewritten to the cert's own path.
- No cert, an unpinned cert, wrong SNI and no SNI: refused at the handshake.

## Findings

1. **G17c · High · `g17-items.md:73`: the JSON expression must use the full placeholder.**
   - `{tls_client_subject}` is Caddyfile shorthand. In JSON it is never expanded: the route answered 403 for the correct cert, while `{http.request.tls.client.subject}` answered 200. `caddy validate` passes both, so nothing would catch it before deploy.
   - Change `expression {tls_client_subject} == "CN=<cn>"` to:
     > expression `{http.request.tls.client.subject} == "CN=<cn>"` (the full placeholder; the Caddyfile shorthand `{tls_client_subject}` is not expanded in JSON, so it never matches)
   - Add to the unit tests: "the expression uses `{http.request.tls.client.subject}`".

2. **G17c · High · `g17-items.md:74, 76`: the hook must force the reload, or revoke and rotation silently do nothing.**
   - The leaf folder is read only at provision.
   - Trial: I removed the pin and ran `caddy reload` with the same config file. Caddy logged `"config is unchanged"`, and a **new** connection with the revoked cert still got 200.
   - With `--force`, the old keep-alive connection was dropped (broken pipe) and a new one got `bad certificate`.
   - Removing a peer changes the routes, so the JSON changes anyway. But a replaced cert under the same name (renewal, or revoke and reissue) renders identical JSON and is never picked up.
   - Change line 74 to:
     > `deploy/peer-proxy/proxy-reload` (sh): renders to a temp file and runs `caddy validate --config <tmp>`. Then `caddy reload --force --config <tmp> --address unix/<admin-socket>`: `--force` is required, because the leaf folder is read only at provision and Caddy skips an unchanged config. Only after a successful reload does it rename the temp file over the config. It takes the same path arguments as `render.py` plus `--config-out`, so `trial.sh` runs the shipped hook unchanged. It never calls any CA helper. On failure it exits non-zero with a clear message, leaving the running config and the file untouched.
   - In line 76, replace "removing a pin and running the hook refuses that peer on its next connection with resumption attempted" with:
     > removing a pin and running the hook refuses that peer on a new connection (resumption attempted) and on a keep-alive connection opened before the hook; replacing a pin with a new cert under the same name and running the hook accepts only the new cert (proves `--force`)
   - This also settles plan line 107: keep-alive can stay at the default.

3. **G17a · High · `g17-items.md:17, 20`: `route.send` has no way to take a peer sender.**
   - The sender is a session or a script, nothing else (`intercom-main/route.py:177`).
   - The session-only gates would run for a peer: the own-session check (`route.py:247`) and the sender chat scope (`route.py:192, 253`).
   - The frame would put "session unknown" in the header (`frame.py:802-803, 410`) and look up a source phrase (`frame.py:827-828`).
   - Add to the line-17 bullet:
     > `route.send` gains a keyword `peer=<name>` (the sender argument is then None). It builds `_Who.peer(name)`, records `sender_source='peer'`, `sender_label=<name>` and no `sender_session_id`, and takes the script gates: no own-session check, no sender chat scope.
   - Add to the line-20 bullet:
     > The peer header names `remote agent <name>`, with no `session …` part; `frame.build` treats `peer` like `script` for `session_id`, `source_phrase` and `ask_to` (`frame.py:802-803, 827-828`).

4. **G17a/G17b · Medium · `g17-items.md:17` vs `44`: who creates `peers.py`.**
   - G17a must read `peers.json`, but "New `peers.py`: loads `plugin-data/intercom/peers.json`" belongs to G17b. Two builders would each write a loader.
   - Line 17: replace "(format in P2: … this item only reads `name`)" with:
     > through a new `peers.py` with `load()` (format in P2: `name`, `url`, `auth`, `secret_file`; `name` must match `^[a-z0-9-]{1,63}$`; a bad file means no peers). This item uses only `name`.
   - Line 44: replace "New `peers.py`: loads …" with:
     > `peers.py` (from G17a) gains `send(...)`, the one entry for every outbound peer post, reached from `route.send` when `to` starts with `peer:`.

5. **G17b · Medium · `g17-items.md:45-46`: the tool's `reply` → `wants_reply` mapping, and where the branch sits.**
   - `route.send` refuses a missing reply mode first (`route.py:161`).
   - Add to line 45:
     > The `peer:` branch runs after the reply-mode check. The mapping is `reply: none` → `wants_reply: false`, `requested` → `true`; `waiting` is refused ("a remote agent cannot hold your turn; use requested"). A reply from the hook (`optional`, with `reply_to`) posts `wants_reply: false`.

6. **G17b · Medium · `g17-items.md:46, 50`: TLS "always verified" contradicts "a fake HTTPS or HTTP server"; `auth: url` is ambiguous; redirects are unspecified.**
   - Line 46: replace "`auth: url` → the secret is part of the URL read from `secret_file`" with:
     > `auth: url` → the full URL is read from `secret_file`; `url` holds the same URL with the secret part replaced by `…`, for `list` and receipts only.
   - Also add to line 46:
     > Only `https://` URLs load; anything else is not a peer. Redirects are not followed: a 3xx is an error.
   - Line 50: replace "a local fake HTTPS or HTTP server on 127.0.0.1 … where the test needs it" with:
     > a local fake HTTPS server on 127.0.0.1 with a throwaway CA, trusted through `SSL_CERT_FILE` in the test environment (no CA option in `peers.json`)

7. **G17b/G17c/G17e · Medium · `g17-items.md:50, 76, 129`: Python 3.14 rejects a bare throwaway CA.**
   - `ssl.create_default_context()` sets `VERIFY_X509_STRICT`. In the trial, a CA without `keyUsage` failed with "CA cert does not include key usage extension". The outbound client in G17b and the e2e in G17e both verify that way.
   - Add once, to G17b's test bullet and G17e's outcome:
     > Throwaway certs carry strict-mode extensions: the CA has `basicConstraints=critical,CA:TRUE`, `keyUsage=critical,keyCertSign,cRLSign` and `subjectKeyIdentifier=hash`; each leaf has `authorityKeyIdentifier=keyid` and a SAN (`DNS:` or `IP:127.0.0.1`); peer client leaves have `extendedKeyUsage=clientAuth`.

8. **G17c · Medium · `g17-items.md:73`: "stdlib only" cannot read a CN from a PEM.**
   - The Python stdlib has no public X.509 parser.
   - Replace "one route per `*.pem` in `--active` whose CN is a valid peer name (…; others skipped with a warning)" with:
     > one route per top-level `<name>.pem` in `--active` whose stem matches `^[a-z0-9-]{1,63}$` (others skipped with a warning; they stay trusted at TLS through the folder loader but have no route, so they get 403). The expression requires the subject `CN=<name>`, so a file whose cert names someone else also gets 403.
   - Add to G17d's README bullet (line 108): "pins are named `<name>.pem`".

9. **G17c · Medium · `g17-items.md:73`: the ACME mode is unspecified and cannot be trialled.**
   - "`--acme-dns <provider module json file>` passed through verbatim" leaves the builder to invent the TLS automation JSON. Loopback cannot exercise it; the installed Caddy does have `dns.providers.route53` and `tls.issuance.acme`.
   - Replace that parenthesis with:
     > or `--acme-dns <file>`, whose JSON object is used verbatim as the `provider` of `apps.tls.automation.policies[0].issuers[0].challenges.dns`, with `subjects: [<server-name>]`, issuer `acme`, `http` and `tls-alpn` challenges disabled, and `apps.tls.certificates.automate: [<server-name>]`. That mode is covered by a unit test of the JSON only; the trial uses `--cert/--key`.

10. **G17c · Low · `g17-items.md:76`: one trial case proves nothing on loopback.**
    - In the trial everything is loopback, so "8644-style upstream not reachable except through the proxy" cannot fail. G17e covers the bind.
    - Delete ", 8644-style upstream not reachable except through the proxy".
    - Also in line 76, replace "wrong SNI and no SNI refused" with "wrong SNI and no SNI refused at the handshake". That is what the trial shows with the single no-`match` policy and the cert from files; give the expected result exactly.

11. **G17d · Medium · `g17-items.md:104-105`: the answer table is wrong for TLS failures, and the shell JSON is fragile.**
    - An unpinned or revoked cert never gets an HTTP code; it fails the handshake.
    - Building JSON with quotes and newlines in plain `sh` without `jq` is error-prone.
    - Line 104: replace "the exact shell function that builds the JSON body …" with:
      > the exact shell function that takes a file holding the JSON body `{"text", "reply_to"?, "wants_reply"?}` (you write that file), signs the bytes `<ts>.` plus the file with `openssl dgst -sha256 -hmac` (V2), and posts it with `--data-binary @<file>`
    - Line 105: replace "403 = wrong path or certificate;" with:
      > a TLS handshake failure (curl exit 35 or 56, no HTTP code) = your certificate is not accepted: stop and tell the operator; 403 = the path is not your certificate's; 421 = you did not use `--resolve` with the server name; 404 = your route is not configured yet: stop and tell the operator; 400/413 = fix the body;

12. **G17e · Medium · `g17-items.md:129-134`: missing harness facts, and an overbuilt TLS matrix.**
    - Harness facts the builder needs:
      - `home_config` is hard-coded (`tests/plugins/intercom/_owner_world.py:486-511`).
      - The plugin copy drops `docs` and `tests` (`_owner_world.py:549-550`).
      - Bot Chat is a session titled `Bot Chat` (`test_e2e_owner.py:680`).
    - Add to the outcome:
      > Shared-helper changes: `home_config` gains an optional YAML block, used for `platforms.webhook` (loopback, free port), `platforms.intercom_peer` and the per-peer static route. `World` writes `plugin-data/intercom/peers.json` and sets `SSL_CERT_FILE` in the owner environment (finding 7). The canonical Bot Chat is a session titled `Bot Chat`, as in `test_e2e_owner.py:680`.
      > The inbound post is made by running the shell function from `<intercom-src>/docs/peer-instructions.md`, extracted from its fenced block, so the G17d text is proved.
      > A delivery failure comes from switching `allow_gateway_injection` off for one post (`route.py:318` reads it fresh on every send).
    - Overbuilt: G17c's `trial.sh` already proves the whole TLS and routing matrix. Replace line 133 with:
      > Through the proxy: the pinned post above, and one refused case (an unpinned cert); the full TLS and routing matrix is G17c's `trial.sh`.
    - Line 132: replace "a cron delivery to `intercom_peer` are refused" with:
      > a cron delivery to `intercom_peer:<name>` (`cron/scheduler_delivery.py:632-643` goes through the validator) and to bare `intercom_peer` (no home channel) deliver nothing

13. **G17a/G17b/G17c · Low · `g17-items.md:24-28, 52-57, 80-86`: Verify cannot show the new tests ran.**
    - The suite passes even if the new file is missing or misnamed. G16 added a focused, verbose run (`g16-items.md:27`).
    - Add before the full-suite line:
      - G17a: `HERMES_HOME="$(mktemp -d)" <hermes-test-python> -I -m unittest discover -s tests -p 'test_peer_inbound.py' -t . -v`
      - G17b: the same with `test_peer_outbound.py`.
      - G17c: the same with `test_peer_proxy_render.py`.
    - G17c: say the test imports `deploy/peer-proxy/render.py` with `importlib.util.spec_from_file_location`, because the hyphen makes `peer-proxy` unimportable as a package.

14. **G17a · Low · `g17-items.md:20`: the word "peer" already means something else.**
    - The current authority line and README call another Hermes session "a peer" (`intercom-main/README.md:112, 289-290`, and `frame.py` `_authority`). A sender kind `peer` meaning "remote agent" will confuse readers of frames and code.
    - Add:
      > Frame text says "remote agent" for this kind and never "peer"; the existing session wording stays.

15. **Order · ok.**
    - G17a → b → c → d (intercom) → e (hermes-agent) is right: G17e needs all four, and needs G17d's text to prove it (finding 12).
    - G17c does not depend on G17b in code; the edge exists only because the build is serial (AGENTS.md "Parallelism: serial"). Fine as is.
    - Note for the subtree pull: `deploy/peer-proxy/` will be vendored into `plugins/intercom/` in hermes-agent. It is never imported. Say so in the README section.

Not overbuilt elsewhere. The `list` peers, the one fixed schema clause and the unit template are all in the plan.
