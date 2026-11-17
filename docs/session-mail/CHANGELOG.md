# session-mail changelog (DER-701)

One line per landed item.

- 2026-11-11 G1 (DER-716): Listing PR: publish the owner-client and framing names in `plugin_api.json` — alexderz/hermes-agent@651fd1baa2
- 2026-11-11 G2 (DER-717): Owner client `client.py` — alexderz/hermes-intercom@04d7da58d4
- 2026-11-11 G5 (DER-719): Chat scope `scope.py` — alexderz/hermes-intercom@1789aed644
- 2026-11-11 G7 (DER-720): Framing `frame.py` — alexderz/hermes-intercom@d42e904b88
- 2026-11-12 G8 (DER-721): Record `record.py` — alexderz/hermes-intercom@f033c482d8
- 2026-11-12 G4 (DER-718): Addressing `address.py`, and `list` — alexderz/hermes-intercom@7d7201a676
- 2026-11-12 G3 (DER-722): Send path `route.py` — alexderz/hermes-intercom@54581f02bd
- 2026-11-12 G9 (DER-723): Replies and the in-process `ask`, `replies.py` — alexderz/hermes-intercom@44c520eed6
- 2026-11-12 G6 (DER-724): Echo `echo.py` — alexderz/hermes-intercom@2c356055ee
- 2026-11-12 G10 (DER-725): CLI, tool schema, caps removal and the legacy path — alexderz/hermes-intercom@dbb6b2d6ec
- 2026-11-12 G11 (DER-726): Relays on `hermes intercom send` — alexderz/hermes-agent@8eda6b5760
- 2026-11-12 G13 (DER-727): Upstream drafts (drafts only; nothing is posted) — alexderz/hermes-intercom@badc1f7f6e
- 2026-11-12 G14 (DER-728): Owner E2E of the integrated plugin (split from G-2) — alexderz/hermes-agent@f37fb90e79
- 2026-11-12 G12 (DER-729): Vendor into hermes-agent, then deploy (gateway restart) — alexderz/hermes-agent@6052059ea6
- 2026-11-12 G15 (DER-745): Reboot warning and resume through intercom — alexderz/hermes-intercom@44e09f2976
- 2026-11-14 G16a (DER-767): Passive send path and record (passive, key, to: all) — alexderz/hermes-intercom@cd4bacef16
- 2026-11-14 G16b (DER-767): Turn-start handover of held notes (offer, confirm, answers, echo) — alexderz/hermes-intercom@86a66164f0
- 2026-11-14 G16c (DER-767): Keyed queue: wake through Hermes's queue, newest version from the record — alexderz/hermes-intercom@02a290587e
- 2026-11-14 G16d (DER-767): Other profiles, explicitly (profile on send and list) — alexderz/hermes-intercom@639cd6c1b1
- 2026-11-14 G16g (DER-767): Deadline on a passive note (within, woken from the gateway's kanban dispatcher tick) — alexderz/hermes-intercom@72620b3769
- 2026-11-14 G16e (DER-767): README and version for passive, keys and profiles — alexderz/hermes-intercom@5298d843bf
- 2026-11-14 G16f (DER-767): End-to-end cells on a real gateway owner for passive, keyed queue, profiles and deadlines — hermes-agent@47adcd0fa3 (landed by manager: E2E 52/52 and reviewer approve; scripts/check adds no finding over the parent, per the Verify ruling)
- 2026-11-14 G16h (DER-767): list shows the profile's Bot Chat (hidden session) — alexderz/hermes-intercom@911039cffa
- 2026-11-14 G16i (DER-767): Webapp shows session-mail messages folded, like bot messages — alexderz/hermes-intercom@8a15373ea3
- 2026-11-15 G17a (DER-792): Inbound: the intercom_peer platform delivers webhook posts into Bot Chat — alexderz/hermes-intercom@c8605a7211
- 2026-11-15 G17b (DER-792): Outbound: Bot Chat sends to peer:<name>, and replies to peers are block only — alexderz/hermes-intercom@8d464bd4ce
- 2026-11-15 G17c (DER-792): Peer proxy: Caddy JSON renderer, reload hook and unit (deploy assets) — alexderz/hermes-intercom@bf9c9cb5b9
- 2026-11-15 G17d (DER-792): Remote agent instructions and README for peers — alexderz/hermes-intercom@2d2c2bdd0c
- 2026-11-15 G17e (DER-792): End-to-end trial: a remote peer through the proxy into Bot Chat and back — alexderz/hermes-agent@8087c3691e
- 2026-11-15 G17f (DER-792): Proxy access log and peer security notes (spike review) — alexderz/hermes-intercom@d01aa54714
- 2026-11-16 G17g (DER-792): Tunable per-peer body limit in the proxy (64 KB default) — alexderz/hermes-intercom@64d9c5e025
- 2026-11-16 G17h (DER-792): Outbound bearer auth for routine webhooks — alexderz/hermes-intercom@99ed8dbe18
