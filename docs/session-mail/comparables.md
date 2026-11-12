# Comparables — session-mail (session-to-session messaging)

How others let one agent session message another. Written before locking the HLD shape.

- Slug: `session-mail`
- Brief / options map: `docs/session-mail/brief.md` (round 6, Refine: pass, round 5). The
  research note in the Hermes Improvement vault (`research/session-messaging.md`, sections
  1–2b) names the first candidates; this page checks each one at its source.
- Date: `2026-11-09` (round 2: intercom became the base)

Agent Tincan was also named in the research. It is out of scope for this chunk (cross-machine
agents, SM-Q6 "maybe later"), so it is not used as a comparable here.

## The base, not a comparable: intercom and its forks

Since Alex's decision "Build on intercom" (brief decision 1), `majordave/hermes-intercom` is the
**base** we extend, through our fork `alexderz/hermes-intercom`. What it does, and what we change
or add, is in the brief's mapping table and the HLD's parts P2 and P3. It is not listed below as
a comparable.

- `majordave/hermes-intercom` (MIT, implements #81885, last push 2026-09-04):
  <https://github.com/majordave/hermes-intercom>
- Our fork: <https://github.com/alexderz/hermes-intercom>
- **Prior art: `miyu4u/hermes-intercom`** (4 commits ahead of majordave, 2026-11-04):
  <https://github.com/miyu4u/hermes-intercom>
  - It adds `gateway_peers.py`, a "same-workspace gateway transport with correlated replies",
    and redesigns the frame into a readable header with a verbatim body.
  - Its transport runs over v0.23's **unified** gateway (CLI, TUI, desktop and ACP sessions),
    not the messaging gateway, so it does not reach Telegram.
  - It needs `hermes_cli.gateway_client`, `discover_gateway_endpoint` and
    `gateway.session_context.bound_session_key`. All three are in `v0.23.0`; none is in our
    v0.22.0 base.
  - **Steal later:** at the v0.23 rebase, its transport may replace our lease-and-socket
    lookup for tui sessions, and its readable-header frame is worth comparing with our A′
    header.
  - **Won't copy now:** anything that depends on v0.23 APIs.

## 1. Hermes Bot Mode: `message_agent` and the live-owner mailbox

- **Who / what** — Hermes itself, v0.22.0: `tools/bot_mode_dm.py` (the `message_agent` tool),
  `tools/bot_live_delivery.py` (durable handoff to a live Bot Chat owner, adapted from upstream
  PR #101564), `tools/bot_relay.py`, `gateway/bot_loop_guard.py`.
  <https://github.com/NousResearch/hermes-agent/blob/v0.22.0/tools/bot_live_delivery.py>
- **What they did**
  - The sender's text gets a stamp the sender cannot write: `Message from 🤖 <name> (@handle): `
    (`bot_mode_dm.py:243`). The tool description tells the model not to write the prefix
    itself (`:113`). A relay rewrites the stamp so the reply address is right
    (`bot_relay.py:240-257`).
  - The live-owner mailbox is a durable record per message that moves
    `queued → claimed → terminal` under a file lock. A claim never expires, so a crash leaves
    an inspectable unknown outcome rather than a second run. Receipts are permanent.
  - The turn carries a `turn_author` object, which only memory providers see.
  - A loop guard (`gateway.bot_loop_guard.max_hops`) stops bot-to-bot reply chains.
- **Steal**
  - The plugin writes the sender stamp. The sender comes from the calling session and is
    never typed by the model.
  - One durable record per message, written by the sender's side, never deleted in normal use.
  - "Never run the same input twice" as a rule: we never retry, and a reply is stored once per
    mail id.
- **Won't copy**
  - Profile addressing and the `Bot Chat` title gate (`find_canonical_owner`). Our targets are
    ordinary sessions inside one profile.
  - Delivery only at idle points (the poller claims a ticket only when no turn and no human
    prompt are pending). Settled decision 3 says steer right away, with no hold.
  - The hop loop guard. Settled decision 5 says no caps.
  - The claim state machine. Without a worker there is nothing to claim. The record keeps one
    delivery result instead.

## 2. `Sahil-SS9/hermes-walkie-talkie`

- **Who / what** — A community Hermes plugin (MIT) for same-machine peer messaging between
  independent Hermes sessions, with groups and structured requests. Last push 2026-10-31.
  <https://github.com/Sahil-SS9/hermes-walkie-talkie>
- **What they did**
  - A harness-neutral core (`agent_peer`) behind a Hermes adapter (`hermes_peer`).
  - Same-user local transport: Unix sockets, or Windows named pipes. No TCP and no central
    daemon.
  - Receipts per delivery: `delivered`, `held`, `refused` or `unreachable`.
  - A busy recipient is held and released at the host's queue-safe boundary. An active turn is
    never interrupted, and cancelling a request is only advisory.
  - It needs a `ctx.inject_message(mode=, target_session=)` seam from upstream PR #83661, which
    was closed unmerged. On a host without that seam the plugin refuses to run.
- **Steal**
  - Keep the transport-and-delivery core apart from the Hermes glue. Our delivery code is one
    module shared by the plugin and the existing dispatcher script.
  - "Never interrupt an active turn" as a hard rule.
  - The `unreachable` outcome as its own result, separate from a refusal.
- **Won't copy**
  - Its larger seam (#83661: `mode` plus `target_session`, an `on_session_open` event and
    slash-command context). We **steal its `mode=queue|steer|interrupt` shape**, now our one
    core seam (brief decision 11, HLD D1), but only that argument. Our host falls back to a
    weaker mode instead of returning False, and reports the mode it applied.
  - Groups, broadcasts, request tracking, inbox tools and a desktop panel. That is much more
    than Alex asked for.
  - Holding mail until the next boundary instead of steering it in.

## 3. Claude Code cross-session messaging (`SendMessage`, `ListAgents`)

- **Who / what** — Anthropic's Claude Code: the `SendMessage` and `ListAgents` tools between a
  user's own Claude Code sessions and agent-team teammates.
  <https://code.claude.com/docs/en/cross-session-messaging> and
  <https://code.claude.com/docs/en/agent-teams> ("Messages between agents").
- **What they did**
  - The address is the session's name. An ambiguous name is refused, and the sender is told to
    pick one of the listed candidates.
  - The harness, not the sender, wraps the message as `<cross-session-message from="…">`. The
    receiver is told that it came from another Claude session, not from the user.
  - A peer cannot approve a permission prompt or give consent for the user. A session that was
    denied an action may not ask a peer to do it ("permission laundering").
  - Messages queue and drain at the receiver's next tool round. A reply goes to the `from`
    address. In a team, a teammate's final answer reaches the lead on its own when the
    teammate goes idle.
- **Steal**
  - The authority rule, word for word in spirit: mail is a peer's message, it carries no
    approval, and work that was blocked for the sender goes back to Alex, not to a peer.
  - Refusing an ambiguous address with the candidates (settled decision 2 says the same).
  - The final answer as the reply, with nothing to call (settled decision 4).
- **Won't copy**
  - A non-user frame produced by the harness. In Claude Code the harness owns the frame. In
    Hermes the steer frame is core code that the caller cannot choose
    (`agent/prompt_builder.py:561-611`). A frame patch would cover steered mail only (HLD D2,
    SM-Q7).
  - Inbox files under the user's home directory. Our delivery is made by the process that
    hosts the target, through intercom's socket and the core seam.

## 4. Upstream #106423 "peer session messaging" (and #136861, #123218)

- **Who / what** — A pull request by a Hermes maintainer (open), its rebase onto current main
  (#136861, open), and a broader variant (#123218, open).
  <https://github.com/NousResearch/hermes-agent/pull/106423>,
  <https://github.com/NousResearch/hermes-agent/pull/136861>,
  <https://github.com/NousResearch/hermes-agent/pull/123218>
- **What they did**
  - An opt-in core toolset, `peer_messaging`, with `peer_sessions` (list recent sessions from
    the session store) and `peer_send` (to an exact session id).
  - A filesystem mailbox under `$HERMES_HOME/runtime/peer_messages/<session>/`. The activity
    hook drains it into the existing mid-turn steer channel. An idle session gets the mail at
    the start of its next turn; it does not start one.
  - The injected text names the sending session and says it carries peer-agent, not user,
    authority.
  - Caps of 50 pending messages per inbox and 8,000 characters per message. #123218 refuses
    gateway sessions. None of the three has automatic replies, and none is merged.
- **Steal**
  - Provenance stated in the text: the sender session, and "not user authority". That is our
    A′ authority line.
  - Riding the existing steer channel instead of new injection machinery, for the steer mode.
  - Exact session-id targeting, and refusing unknown targets without side effects.
- **Won't copy**
  - A new **core** tool. The root `AGENTS.md` footprint ladder prefers a plugin, and Alex chose
    intercom (decision 1).
  - Waiting for the next turn instead of waking an idle session (decision 3: an idle target
    starts a turn).
  - The inbox and size caps (decision 5), and refusing gateway sessions (decision 9).
