# Draft: update on NousResearch/hermes-agent#81885

Status: nothing was posted, opened, or commented. This file is for review only.

Where it would go: a comment on <https://github.com/NousResearch/hermes-agent/issues/81885>. No pull request.

Asks:

1. Record the gateway-only design. On current Hermes, one gateway owner per profile hosts the sessions Ink, Desktop, the classic CLI, and messaging platforms attach to. Cross-session delivery is a client of that owner. A session the owner holds for another runtime is not addressable.
2. Record the owner verbs that do that delivery (below). This comment asks for no new core behavior and no new `inject_message` mode.
3. Treat the Trial round 3 finding as a defect. Inside the owner, the published `ctx.inject_message` returned `True` and ran nothing when the call was addressed by session id.

## Text to post

Update from a gateway-only intercom build on Hermes v0.23 (Trial round 3, calls made from inside the gateway owner).

### Gateway only

One gateway owner per profile is the host for every session this design can reach: a session attached the way Ink and Desktop attach, a classic CLI session, and a messaging-platform session. Delivery is a client of that owner, over the same-UID control-socket ticket. There is no second host, no per-process inbox for those sessions, and no new core seam.

A session the owner answers with `runtime_coordination_required` is held by another runtime (a standalone admin dashboard is the case we hit). Those chats are not addressable. This update does not ask for a dashboard delivery leg.

Cold sessions are restored by the owner. `session.resume` brings a stored session back, and `prompt.submit` starts the turn. Trial round 3 restored an owner-attached session after an owner restart in about 0.7 s, then ran the message.

### Owner verbs

Discovery is read-only: `discover_gateway_endpoint` on the profile home. It never starts an owner. No ready endpoint means there is no owner to call.

Attach with `connect_gateway` on that endpoint only. A new connection `session.resume`s the target (`omit_messages: true`) before it may submit. Resume also restores a cold session. The caller keeps `running` and `execution_generation` from that answer.

Then one of the owner's existing verbs, strongest at or below the request. An idle target always starts a turn.

| Requested | Target running | Calls after `session.resume` | What ran |
|---|---|---|---|
| any | no | `prompt.submit` | start |
| `queue` | yes | `prompt.submit` with `queued: true` | queue, after the current turn |
| `steer` | yes | `session.steer`. On `rejected`, `prompt.submit` with `queued: true` | steer into the running turn, or queue |
| `interrupt` | yes | `session.redirect`. On `rejected`, `session.interrupt`, then `prompt.submit` with `queued: true` | redirect, or a hard interrupt |

`prompt.submit` takes a `submission_id` the caller picks once per message. The owner admits that id once. A lost answer after the verb was sent is unknown, and the caller does not send the message again. `stale_generation` on steer or redirect means the turn ended between resume and the call: resume once more and apply the idle row.

Trial round 3 ran this sequence from inside the owner for steer, queue, interrupt (as redirect), and idle start, on owner-attached, classic CLI, and messaging sessions. The cold start above was the same client after an owner restart.

`post_llm_call` fired in the owner for those turns. A reply sent from that hook reached a sender of another owner-hosted kind.

The Python names `connect_gateway` and `discover_gateway_endpoint` are not on the public plugin API today. Publishing them is a separate listing request and changes no gateway behavior. The verbs themselves are the owner's wire API.

### `ctx.inject_message` returned `True` and ran nothing

Inside the owner, the published `ctx.inject_message(text, session_key=<session id>)` returned `True` for every session kind tried: owner-attached, classic CLI, messaging, and a session held by the admin dashboard. No message ran.

The call wants the route key. A plugin has no published way to read that key. Even a call that did run would be queue-only: it becomes a queued producer admission, with no steer, redirect, or interrupt.

An accepted-then-dropped `True` is the defect. A session-id target that the owner does not run should not be reported as success. The owner verbs above are what actually delivered.

This comment asks for that `True` to be treated as a bug. It does not ask for a new inject mode, a core behavior change, or a second host.
