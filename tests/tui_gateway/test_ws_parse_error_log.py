"""A malformed incoming WebSocket frame is logged by its length, never its content.

A masked card's answer frame (``secret``, ``sudo``, vault prompts) carries the typed value; a frame the
gateway cannot parse used to land in the gateway log as a 240-character ``payload=%r`` preview.
"""
from __future__ import annotations

import asyncio
import json
import logging

DUMMY = "dummy-value-7Qx2-not-a-real-key"


def test_a_garbled_secret_answer_frame_is_logged_by_length_only(monkeypatch, caplog):
    from tui_gateway import server, ws as ws_mod

    monkeypatch.setattr(server, "_start_backend_heartbeat_refresher", lambda: None)
    monkeypatch.setattr(server, "resolve_skin", lambda: "default")
    monkeypatch.setattr(server, "_ensure_skin_watcher", lambda: None)
    monkeypatch.setattr(server, "register_live_transport", lambda *_a, **_k: None)
    monkeypatch.setattr(server, "_WS_ORPHAN_REAP_GRACE_S", 0)
    garbled = '{"jsonrpc": "2.0", "id": "srv-1", "result": {"value": "' + DUMMY + '"'  # cut off: no closing braces
    sent: list[str] = []

    class FakeWS:
        def __init__(self):
            self.frames = [garbled]

        async def accept(self):
            pass

        async def send_text(self, line):
            sent.append(line)

        async def receive_text(self):
            if self.frames:
                return self.frames.pop(0)
            raise ws_mod._WebSocketDisconnect()

        async def close(self):
            pass

    with caplog.at_level(logging.DEBUG):
        asyncio.run(ws_mod.handle_ws(FakeWS()))

    [record] = [r for r in caplog.records if r.getMessage().startswith("ws parse error")]
    assert f"payload_chars={len(garbled)}" in record.getMessage()
    assert not any(DUMMY in r.getMessage() for r in caplog.records)
    assert DUMMY not in caplog.text
    assert any(json.loads(line).get("error", {}).get("code") == -32700 for line in sent)
