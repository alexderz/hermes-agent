# Comparables — session-mail (session-to-session messaging)

How others let one agent session message another. Written before locking the HLD shape.

- Slug: `session-mail`
- Brief / options map: `docs/session-mail/brief.md` (Refine: pass, round 3). The research note
  in the Hermes Improvement vault (`research/session-messaging.md`, sections 1–2b) already names
  these candidates; this page checks each one at its source.
- Date: `2026-11-09`

Agent Tincan was also named in the research. It is out of scope for this chunk (cross-machine
agents, SM-Q6 "maybe later"), so it is not used as a comparable here.

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
  - The claim state machine. Without a worker there is nothing to claim. The outbox keeps one
    delivery result instead.

## 2. `majordave/hermes-intercom`

- **Who / what** — A community Hermes plugin (MIT) implementing upstream issue #81885, "Local
  cross-session messaging (intercom)". Last push 2026-09-04.
  <https://github.com/majordave/hermes-intercom>
- **What they did**
  - One multiplexed tool, `intercom`, with `list`, `send` and `ask` actions.
  - Each process registers a `0600` Unix socket and finds its live `HermesCLI` object with a
    garbage-collector scan.
  - An idle receiver gets the text in its input queue and starts a turn by itself. A busy one is
    steered between tool calls, or the text is parked for the next turn through `pre_llm_call`.
  - Every send returns a receipt: `delivered`, `held` or `refused`.
  - A compact frame, `📡 hermes@<session-name> says:`, and echo suppression that strips quoted
    headers. The README says the text is inert: it cannot approve actions or run slash
    commands.
  - Per-peer rate limit (6 per minute), a 120-second duplicate filter and a pending-queue cap.
- **Steal**
  - The delivery ladder, which matches Alex's rule: steer when busy, start a turn when idle.
  - A synchronous receipt for every send, so the sender knows what happened.
  - A one-line emoji frame that names the sending session, and stripping quoted copies of it.
  - Stating plainly that delivered text cannot approve actions or run slash commands.
- **Won't copy**
  - One interactive CLI per process, found by a GC scan. Our targets live by the dozen inside
    the one dashboard process. Intercom can only park mail there until the next turn.
  - The rate limit, duplicate filter and queue cap (settled decision 5).
  - Replies sent with the tool. Settled decision 4 says the final answer goes back on its own.

## 3. `Sahil-SS9/hermes-walkie-talkie`

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
  - Its reliance on a core seam that upstream rejected. Settled decision 1 rules out a core
    patch without a real blocker.
  - Groups, broadcasts, request tracking, inbox tools and a desktop panel. That is much more
    than Alex asked for.
  - Holding mail until the next boundary instead of steering it in.

## 4. Claude Code cross-session messaging (`SendMessage`, `ListAgents`)

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
    (`agent/prompt_builder.py:561-611`), and a core patch needs a real blocker (HLD, decision
    D1).
  - Inbox files under the user's home directory. Our delivery goes over the dashboard
    WebSocket, so the phone sees the result.
