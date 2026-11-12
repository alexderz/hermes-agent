"""The TUI sidecar's secret callback saves a ``clarify(secret_file=...)`` answer to the file, not ``.env``.

Drives the real wired callback (``_wire_callbacks``) and server request: the renderer gets the
``secret`` frame with the destination in its metadata and answers it; the file holds the value, the
profile ``.env`` is never touched and the tool result carries only the file's facts.
"""
from __future__ import annotations

import json

import pytest

from tests.tui_gateway.test_secret_capture_session import _client, _gateway

pytestmark = pytest.mark.platforms("posix")

DUMMY = "dummy-" + "tui-file-0a7c3e"  # built by concatenation: a fake value


def test_tui_secret_file_answer_is_written_to_the_file_not_the_env(monkeypatch, tmp_path):
    from tools.clarify_tool import clarify_tool

    server, server_requests, _skills_tool = _gateway(monkeypatch)
    server._wire_callbacks("session-A")
    monkeypatch.setattr("hermes_cli.config.save_env_value_secure",
                        lambda *a: (_ for _ in ()).throw(AssertionError("a file secret went to .env")))
    target = tmp_path / "work" / "xyz-key"
    target.parent.mkdir()
    with server._sessions_lock:
        server._sessions["session-A"] = {"agent": object(), "session_key": "key-A"}
    tokens = server._set_session_context("turn-A", ui_session_id="session-A")
    try:
        frames, _ = _client(server, server_requests, monkeypatch, {"session-A": DUMMY})
        raw = clarify_tool([{"question": "XYZ API key"}], callback=lambda _q: {},
                           secret_file={"name": "XYZ API key", "path": str(target)})
    finally:
        server._clear_session_context(tokens)
        with server._sessions_lock:
            server._sessions.pop("session-A", None)
        server_requests.reset_for_tests()

    assert DUMMY not in raw
    assert json.loads(raw)["secret_file"]["path"] == str(target)
    assert target.read_text(encoding="utf-8") == DUMMY
    [frame] = [f for f in frames if f.get("method") == "secret"]
    assert frame["params"]["metadata"]["destination"]["path"] == str(target)
    assert DUMMY not in json.dumps(frames)
