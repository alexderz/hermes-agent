"""dashboard_dispatch delivery into an existing session never cancels or redirects its work.

Steer when a turn is running, queue (``queued: true``) when steering is refused, start a turn
when the session is idle.
"""
import asyncio
import json

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


def test_submit_never_omits_the_queued_flag():
    # Without queued=True a busy submit follows display.busy_input_mode, whose default redirects the turn.
    for steer_reply in ({"status": "rejected"}, {"error": {"code": 4010, "message": "x"}}):
        _, sent = deliver({"session.steer": steer_reply, "prompt.submit": {"status": "queued"}})
        assert all(r["params"].get("queued") is True for r in sent if r["method"] == "prompt.submit")
