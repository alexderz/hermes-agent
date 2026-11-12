"""The TUI sidecar refuses ``clarify(secret_file=...)`` before any ``secret`` request reaches the renderer.

The Ink card shows only the prompt text the model wrote (and labels it as an environment variable), so it
cannot show the file's destination apart from it; only the Webapp and desktop app's secret dialog can.
"""
from __future__ import annotations

import json
import os

from tests.tui_gateway.test_secret_capture_session import _client, _gateway


def test_tui_refuses_a_secret_file_request_without_sending_a_card(monkeypatch, tmp_path):
    from tools.clarify_tool import clarify_tool

    server, server_requests, _skills_tool = _gateway(monkeypatch)
    server._wire_callbacks("session-A")
    (tmp_path / "work").mkdir()
    with server._sessions_lock:
        server._sessions["session-A"] = {"agent": object(), "session_key": "key-A"}
    tokens = server._set_session_context("turn-A", ui_session_id="session-A")
    try:
        frames, _ = _client(server, server_requests, monkeypatch, {"session-A": "dummy-never-typed"})
        result = json.loads(clarify_tool([{"question": "XYZ API key"}], callback=lambda _q: {},
                                         secret_file={"name": "XYZ API key", "path": str(tmp_path / "work" / "k")}))
    finally:
        server._clear_session_context(tokens)
        with server._sessions_lock:
            server._sessions.pop("session-A", None)
        server_requests.reset_for_tests()

    assert "needs the Hermes Webapp or desktop app" in result["error"]
    assert not any(f.get("method") == "secret" for f in frames)
    assert os.listdir(tmp_path / "work") == []
