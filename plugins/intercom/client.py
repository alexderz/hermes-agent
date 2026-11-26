"""intercom owner client — deliver through the profile's gateway owner.

Every chat surface of a v0.23 profile runs in its gateway owner, so intercom reaches a session
with the owner's existing canonical verbs over its ticketed socket:

- discovery: ``discover_gateway_endpoint(get_hermes_home(), timeout=2.0)``. Read-only; it never
  starts an owner. No endpoint is ``no-owner``; ``starting`` / ``draining`` is ``owner-restarting``.
- attach: ``connect_gateway(endpoint)`` with the discovered endpoint only, never ``None`` (``None``
  would start an owner or dial ``HERMES_TUI_GATEWAY_URL``, which this module never reads).
- every delivery starts with ``session.resume{omit_messages: true}``; only ``running`` and
  ``execution_generation`` are read from the answer, and nothing else of it is kept.

Mode table (an idle target always starts a turn):

  any        idle     resume -> prompt.submit                                start
  queue      running  resume -> prompt.submit{queued}                        queue
  steer      running  resume -> session.steer; rejected -> submit{queued}    steer | queue
  interrupt  running  resume -> session.redirect; rejected ->                interrupt/redirect |
                      session.interrupt -> submit{queued}                    interrupt/hard-interrupt

``stale_generation`` on a control verb (the turn ended under us) resumes once more and applies
the idle row. One message has one ``submission_id`` (``intercom-<message id>``), which the owner
admits once; nothing is ever re-sent.

Each verb runs ``asyncio.run`` on a fresh thread started with ``contextvars.copy_context().run``,
so the caller's profile context carries over and a caller inside an event loop is not blocked
from starting one.
"""

from __future__ import annotations

import asyncio
import contextvars
import threading

DELIVERIES = ("interrupt", "steer", "queue")

# detail -> (CLI exit code, fixed sentence). The text of an error is the sentence plus the
# exception's type name: never str(exc), which may carry a URL, a ticket or peer data.
ERRORS = {
    "not-addressable": (4, "The session is held by another runtime that intercom cannot reach."),
    "refused-by-owner": (4, "The gateway refused the call."),
    "no-owner": (5, "The gateway for this profile is not running."),
    "owner-restarting": (5, "The gateway is restarting."),
    "not-reachable": (5, "The gateway did not answer before the message was handed over."),
    "delivery-unknown": (6, "The gateway stopped answering after the message was handed over."),
}

# Owner refusal codes (GatewayRPCError's bounded reason) with a detail of their own. Any other
# refusal is still an answer that nothing was taken, so it is refused-by-owner with its code
# kept, as are permission_denied, unsupported_control and invalid_params.
_OWNER_CODES = {"runtime_coordination_required": "not-addressable"}
_STALE = "stale_generation"
# The gateway client's refusal of a request it never wrote (``GatewayClient.rpc`` on a closed
# socket). Not a listed name, so its fixed text is matched; PublishedNamesTests pins it.
_NOT_SENT = "Gateway disconnected before the request was sent; nothing was sent."
_DISCOVERY_TIMEOUT = 2.0


def submission_id(message_id: str) -> str:
    """The one submission id of a message: the owner admits it once per actor and session."""
    return f"intercom-{message_id}"


def deliver_sync(target: str, text: str, delivery: str, submission_id: str, *,
                 unless_closed_by_user: bool = False) -> dict:
    """Deliver *text* to session *target* using the mode table at the top
    of this module.

    Returns ``{"ok": True, "applied", "applied_detail", "admission_id", "instance_id"}``;
    ``admission_id`` is ``prompt.submit``'s id when the sequence ended in a submit, else ``None``;
    ``instance_id`` is the discovered owner's (``GatewayEndpoint.instance_id``). On failure:
    ``{"ok": False, "error": <detail>, "code": <owner code or None>, "exit", "message"}``.

    ``unless_closed_by_user`` defaults off. When set, ``prompt.submit`` carries that flag.
    Callers that omit it send the same params as before.
    """
    if delivery not in DELIVERIES:
        raise ValueError(f"delivery must be one of {', '.join(DELIVERIES)}")
    return _run(_deliver, target, text, delivery, submission_id, bool(unless_closed_by_user))


def lookup_admission(session_id: str, request_id: str, *, payload_digest: str | None = None) -> dict:
    """Read-only ``prompt.lookup_admission``. Never submits and never writes.

    Returns ``found`` (with ``admission_id`` and ``target_session_id``), ``proven_not_found``,
    ``unavailable``, or ``conflict``. A transport failure or an unusable answer is
    ``unavailable``. ``payload_digest`` is omitted from the request when it is absent.
    """
    params: dict = {"session_id": session_id, "request_id": request_id}
    if isinstance(payload_digest, str):
        params["payload_digest"] = payload_digest
    try:
        result = _run(_read, "prompt.lookup_admission", _lookup_fields, **params)
    except Exception:  # health: allow BLE001 -- a lost read is unavailable, not a write
        return {"outcome": "unavailable"}
    return _lookup_outcome(result)


def owner_instance() -> str | None:
    """The running owner's ``instance_id`` from read-only discovery, or None when there is none."""
    endpoint, failure = _discover()
    instance = getattr(endpoint, "instance_id", None) if failure is None else None
    return instance if isinstance(instance, str) and instance else None


def list_sessions(scope: str = "live", picker: bool = False) -> dict:
    """Read-only ``session.list``: ``{"ok": True, "sessions": [rows]}`` or an error dict."""
    return _run(_read, "session.list", lambda r: {"sessions": list(r.get("sessions") or [])},
                scope=scope, picker=picker)


def receipt(admission_id: str, *, session_id: str) -> dict:
    """Read-only ``prompt.receipt`` for one admission of *session_id* (the wire needs both).

    ``{"ok": True, "status": "queued"|"started"|"unknown"|"terminal", "outcome"}`` or an error dict.
    """
    return _run(_read, "prompt.receipt", lambda r: {"status": r.get("status"), "outcome": r.get("outcome")},
                session_id=session_id, admission_id=admission_id)


# ── internals ────────────────────────────────────────────────────────────────


def _run(fn, *args, **kwargs):
    box: dict = {}

    def body():
        try:
            box["value"] = asyncio.run(fn(*args, **kwargs))
        except BaseException as exc:  # health: allow BLE001 -- the worker hands this to the caller, which re-raises it
            box["error"] = exc

    thread = threading.Thread(target=contextvars.copy_context().run, args=(body,),
                              name="intercom-owner", daemon=True)
    thread.start()
    thread.join()
    if "error" in box:
        raise box["error"]
    return box["value"]


def _failure(detail: str, exc: BaseException | None = None, code: str | None = None) -> dict:
    exit_code, sentence = ERRORS[detail]
    message = f"{sentence} ({type(exc).__name__})" if exc is not None else sentence
    return {"ok": False, "error": detail, "code": code, "exit": exit_code, "message": message}


def _structured_refusal(data) -> dict:
    """The owner refusal fields. Other ``error.data`` keys stay off the receipt."""
    if not isinstance(data, dict):
        return {}
    kept = {}
    for key in ("reason", "field", "detail"):
        value = data.get(key)
        if isinstance(value, str) and value:
            kept[key] = value
    for key in ("revision", "execution_generation"):
        value = data.get(key)
        if type(value) is int:
            kept[key] = value
    if data.get("admitted") is False:
        kept["admitted"] = False
    return kept


def _refusal(exc) -> dict:
    code = str(exc)  # GatewayRPCError's str is the owner's bounded reason code
    failure = _failure(_OWNER_CODES.get(code, "refused-by-owner"), exc, code)
    data = _structured_refusal(getattr(exc, "data", None))
    if data:
        failure["data"] = data
    return failure


def _applied(applied: str, detail: str | None = None, admission_id=None) -> dict:
    return {"ok": True, "applied": applied, "applied_detail": detail,
            "admission_id": admission_id if isinstance(admission_id, str) else None}


_LOOKUP_OUTCOMES = ("found", "proven_not_found", "unavailable", "conflict")


def _lookup_fields(answer) -> dict:
    body = answer if isinstance(answer, dict) else {}
    return {"outcome": body.get("outcome"), "admission_id": body.get("admission_id"),
            "target_session_id": body.get("target_session_id"),
            "payload_digest": body.get("payload_digest"),
            "canonical_session_id": body.get("canonical_session_id")}


def _lookup_outcome(result) -> dict:
    if not isinstance(result, dict) or result.get("ok") is not True:
        return {"outcome": "unavailable"}
    outcome = result.get("outcome")
    if outcome not in _LOOKUP_OUTCOMES:
        return {"outcome": "unavailable"}
    named = {}
    canonical = result.get("canonical_session_id")
    if isinstance(canonical, str) and canonical:
        named["canonical_session_id"] = canonical
    if outcome != "found":
        return {"outcome": outcome, **named}
    admission = result.get("admission_id")
    if not isinstance(admission, str) or not admission:
        return {"outcome": "unavailable"}
    return {"outcome": "found", "admission_id": admission,
            "target_session_id": result.get("target_session_id"),
            "payload_digest": result.get("payload_digest"), **named}


def _discover():
    """``(endpoint, None)`` or ``(None, failure)``. Never selects the legacy path."""
    from hermes_constants import get_hermes_home
    from hermes_cli.gateway_runtime import discover_gateway_endpoint

    try:
        found = discover_gateway_endpoint(get_hermes_home(), timeout=_DISCOVERY_TIMEOUT)
    except Exception as exc:  # health: allow BLE001 -- discovery failure is a not-reachable result
        return None, _failure("not-reachable", exc)
    if getattr(found, "state", None) in ("starting", "draining"):
        return None, _failure("owner-restarting")
    endpoint = getattr(found, "endpoint", None)
    if endpoint is None:
        return None, _failure("no-owner")
    return endpoint, None


async def _read(method, project, **params):
    endpoint, failure = _discover()
    if failure is not None:
        return failure
    from hermes_cli.gateway_client import GatewayRPCError, connect_gateway

    result = None
    try:
        async with connect_gateway(endpoint) as client:
            answer = await client.rpc(method, **params)
            result = {"ok": True, **project(answer if isinstance(answer, dict) else {})}
    except GatewayRPCError as exc:
        if result is None:
            result = _refusal(exc)
    except Exception as exc:  # health: allow BLE001 -- a lost read is a not-reachable result
        if result is None:
            result = _failure("not-reachable", exc)
    return result


async def _deliver(target, text, delivery, sub_id, unless_closed_by_user=False):
    endpoint, failure = _discover()
    if failure is not None:
        return failure
    from hermes_cli.gateway_client import GatewayClientError, GatewayRPCError, connect_gateway

    owner = _Owner(target, text, sub_id, GatewayRPCError, GatewayClientError,
                   unless_closed_by_user=bool(unless_closed_by_user))
    result = None
    try:
        async with connect_gateway(endpoint) as client:
            owner.client = client
            result = await owner.apply(delivery)
            if result.get("ok") is True:
                instance = getattr(endpoint, "instance_id", None)
                result["instance_id"] = instance if isinstance(instance, str) else None
    except GatewayRPCError as exc:
        if result is None:
            result = _refusal(exc)
    except Exception as exc:  # health: allow BLE001 -- an in-flight loss stays delivery-unknown
        # In doubt only while a steer, redirect or submit is out without an answer.
        if result is None:
            result = _failure("delivery-unknown" if owner.in_flight else "not-reachable", exc)
    return result


class _Owner:
    """One delivery's call sequence on one attached connection."""

    def __init__(self, target, text, sub_id, rpc_error, client_error, *,
                 unless_closed_by_user=False):
        self.target, self.text, self.sub_id = target, text, sub_id
        self.rpc_error, self.client_error = rpc_error, client_error
        self.unless_closed_by_user = bool(unless_closed_by_user)
        self.client = None
        self.in_flight = False

    async def resume(self):
        snapshot = await self.client.rpc("session.resume", session_id=self.target, omit_messages=True)
        snapshot = snapshot if isinstance(snapshot, dict) else {}
        # Keep these two fields only: the rest of the snapshot can carry session
        # content, and nothing here needs it.
        return snapshot.get("running") is True, snapshot.get("execution_generation")

    async def hand(self, method, **params):
        """A call that may admit the message: in doubt until the owner answers, or until the
        gateway client says it never wrote the request."""
        self.in_flight = True
        try:
            answer = await self.client.rpc(method, session_id=self.target, **params)
        except self.client_error as exc:
            if isinstance(exc, self.rpc_error) or str(exc) == _NOT_SENT:
                self.in_flight = False
            raise
        self.in_flight = False
        return answer if isinstance(answer, dict) else {}

    async def submit(self, queued):
        params = {"text": self.text, "submission_id": self.sub_id}
        if queued:
            params["queued"] = True
        if self.unless_closed_by_user:
            params["unless_closed_by_user"] = True
        return (await self.hand("prompt.submit", **params)).get("admission_id")

    async def apply(self, delivery):
        running, generation = await self.resume()
        if not running:
            return _applied("start", admission_id=await self.submit(queued=False))
        if delivery == "queue":
            return _applied("queue", admission_id=await self.submit(queued=True))
        try:
            if delivery == "steer":
                return await self.steer(generation)
            return await self.redirect(generation)
        except self.rpc_error as exc:
            if str(exc) != _STALE:
                raise
        # The turn ended between resume and the control call: resume once more, then the idle row.
        await self.resume()
        return _applied("start", admission_id=await self.submit(queued=False))

    async def steer(self, generation):
        status = (await self.hand("session.steer", text=self.text, execution_generation=generation)).get("status")
        if status == "queued":
            return _applied("steer")
        if status == "rejected":
            return _applied("queue", admission_id=await self.submit(queued=True))
        return _failure("delivery-unknown")

    async def redirect(self, generation):
        status = (await self.hand("session.redirect", text=self.text, execution_generation=generation)).get("status")
        if status == "redirected":
            return _applied("interrupt", "redirect")
        if status == "rejected":
            await self.client.rpc("session.interrupt", session_id=self.target, execution_generation=generation)
            return _applied("interrupt", "hard-interrupt", await self.submit(queued=True))
        return _failure("delivery-unknown")
