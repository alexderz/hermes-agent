## Attaching to the profile's owner

A plugin that drives sessions from outside a turn (a CLI command, a relay) attaches to the profile's
owner, the running `hermes gateway`, the same way Ink and Desktop do. `discover_gateway_endpoint`
reads the owner's live identity and never starts one; its `endpoint` is `None` when there is no ready
owner. `connect_gateway` dials that endpoint and returns the client; `client.rpc(method, **params)`
calls one owner verb. A refusal the owner sent raises `GatewayRPCError`, whose `str()` is the bounded
reason code; any other client failure (a refused ticket, a dropped socket) raises its base class
`GatewayClientError`. A drop after `prompt.submit` leaves the turn's outcome unknown: resume the
session to see whether it ran, and never resend the work on it.

`session.resume` takes the stored session id, subscribes the connection to the session and answers
with the runtime id that later verbs use; `prompt.submit` on that connection needs a
`submission_id` the caller picks once per message.

Text a plugin submits on another party's behalf goes through `sanitize_user_prompt_text`, the
owner's own prompt cleanup. `CONTROL_FRAME_OPENERS` lists the openers of Hermes' own control frames
(`[System: ...]`, the steer marker, ...); relabel any of them in relayed text, in any letter case
(as hosted rooms do), so it cannot pass for a frame Hermes wrote.

```python
import re
import secrets

from agent.prompt_builder import CONTROL_FRAME_OPENERS
from hermes_cli.gateway_client import GatewayRPCError, connect_gateway
from hermes_cli.gateway_runtime import discover_gateway_endpoint
from hermes_cli.input_sanitize import sanitize_user_prompt_text
from hermes_constants import get_hermes_home

FRAME = re.compile(r"\[(?=" + "|".join(o.replace("]", r"\]") for o in CONTROL_FRAME_OPENERS) + ")",
                   re.IGNORECASE)


async def submit(session_id: str, text: str) -> dict:
    endpoint = discover_gateway_endpoint(get_hermes_home()).endpoint
    if endpoint is None:
        raise RuntimeError("no running owner for this profile")
    text = FRAME.sub("[quoted ", sanitize_user_prompt_text(text))
    async with connect_gateway(endpoint) as client:
        try:
            live = (await client.rpc("session.resume", session_id=session_id, omit_messages=True))["session_id"]
            return await client.rpc("prompt.submit", session_id=live, text=text,
                                    submission_id=secrets.token_hex(8))
        except GatewayRPCError as exc:
            raise RuntimeError(f"the owner refused: {exc}") from None
```
