"""dashboard_dispatch delivery into an existing session never cancels or redirects its work.

Steer when a turn is running, queue (``queued: true``) when steering is refused, start a turn
when the session is idle.
"""
import argparse
import asyncio
import json
import sys

import pytest

from scripts import dashboard_dispatch as dd


class FakeWS:
    """Answers each JSON-RPC request with a scripted result (or error) per method."""

    def __init__(self, replies):
        self.replies = replies
        self.sent = []
        self._out = []

    async def send(self, raw):
        req = json.loads(raw)
        self.sent.append(req)
        reply = self.replies[req["method"]]
        frame = {"jsonrpc": "2.0", "id": req["id"]}
        frame.update({"error": reply["error"]} if "error" in reply else {"result": reply})
        self._out.append(json.dumps(frame))

    async def recv(self):
        return self._out.pop(0)


def deliver(replies, steer=True):
    ws = FakeWS(replies)
    outcome = asyncio.run(dd._deliver(ws, "live1", "hello", 5.0, steer=steer))
    return outcome, ws.sent


def test_running_turn_takes_the_steer():
    outcome, sent = deliver({"session.steer": {"status": "queued", "text": "hello"}})
    assert outcome == "steered"
    assert [r["method"] for r in sent] == ["session.steer"]


def test_idle_session_starts_a_turn_through_a_queued_submit():
    outcome, sent = deliver({"session.steer": {"status": "rejected", "text": "hello"},
                             "prompt.submit": {"status": "streaming"}})
    assert outcome == "started"
    assert [r["method"] for r in sent] == ["session.steer", "prompt.submit"]
    assert sent[1]["params"] == {"session_id": "live1", "text": "hello", "queued": True}


def test_refused_steer_queues_behind_the_running_turn():
    outcome, sent = deliver({"session.steer": {"error": {"code": 4010, "message": "agent does not support steer"}},
                             "prompt.submit": {"status": "queued"}})
    assert outcome == "queued"
    assert sent[-1]["method"] == "prompt.submit" and sent[-1]["params"]["queued"] is True


def test_no_steer_always_submits_queued():
    outcome, sent = deliver({"prompt.submit": {"status": "queued"}}, steer=False)
    assert outcome == "queued"
    assert [r["method"] for r in sent] == ["prompt.submit"]
    assert sent[0]["params"]["queued"] is True


def test_a_submit_that_starts_no_turn_is_an_error():
    # e.g. a voice stop phrase answers {"voice_stopped": true}: not a delivery, and nothing to wait for.
    with pytest.raises(RuntimeError, match="no turn"):
        deliver({"session.steer": {"status": "rejected"}, "prompt.submit": {"voice_stopped": True}})


def test_steer_timeout_does_not_fall_back_to_a_second_send(monkeypatch):
    async def slow_rpc(ws, rid, method, params, timeout):
        raise TimeoutError(f"{method}: no reply within {timeout:.0f}s")

    monkeypatch.setattr(dd, "_rpc", slow_rpc)
    with pytest.raises(TimeoutError, match="may or may not"):
        asyncio.run(dd._deliver(object(), "live1", "hello", 5.0, steer=True))


# --- _main: which sessions are steered, and when it waits for the turn to start ---------------------------


class _Connect:
    def __init__(self, ws):
        self.ws = ws

    async def __aenter__(self):
        return self.ws

    async def __aexit__(self, *exc):
        return False


def run_main(monkeypatch, replies, **args):
    import types

    ws = FakeWS(replies)
    fake = types.ModuleType("websockets")
    fake.connect = lambda *a, **kw: _Connect(ws)
    monkeypatch.setitem(sys.modules, "websockets", fake)
    monkeypatch.setattr(dd, "_read_key", lambda _p: "k")
    waited = []

    async def fake_wait(_ws, sid, timeout):
        waited.append(sid)
        return "message.start"

    monkeypatch.setattr(dd, "_wait_started", fake_wait)
    ns = argparse.Namespace(url="http://127.0.0.1:1", key_file=None, title=None, cwd=None, resume=None,
                            prompt="hello", prompt_file=None, timeout=5.0, start_timeout=5.0, steer=True)
    for k, v in args.items():
        setattr(ns, k, v)
    out = asyncio.run(dd._main(ns))
    return out, [r["method"] for r in ws.sent], waited


def test_new_session_is_never_steered(monkeypatch):
    out, methods, waited = run_main(monkeypatch, {"session.create": {"session_id": "live1"},
                                                  "prompt.submit": {"status": "streaming"}}, title="T")
    assert methods == ["session.create", "prompt.submit"]
    assert out["delivery"] == "started" and waited == ["live1"]


def test_queued_delivery_detaches_without_waiting(monkeypatch):
    out, methods, waited = run_main(monkeypatch, {"session.resume": {"session_id": "live1"},
                                                  "session.steer": {"status": "rejected"},
                                                  "prompt.submit": {"status": "queued"}}, resume="s1")
    assert methods == ["session.resume", "session.steer", "prompt.submit"]
    assert out["delivery"] == "queued" and out["started"] is None and waited == []


def test_steered_delivery_detaches_without_waiting(monkeypatch):
    out, methods, waited = run_main(monkeypatch, {"session.resume": {"session_id": "live1"},
                                                  "session.steer": {"status": "queued"}}, resume="s1")
    assert methods == ["session.resume", "session.steer"]
    assert out["delivery"] == "steered" and waited == []
