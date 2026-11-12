"""A ``clarify(secret_file=...)`` value reaches the file and nothing else, end to end on the session authority.

The Desktop / Webapp path: a stored local session on a real session authority (its own test home and
session database), the turn's secret callback bound by ``secret_prompt_scope``, the ``secret`` server
request delivered to the attached viewer, and its answer dispatched as a response frame through the
viewer's ``AuthorityConnection``. While the card waits, a garbled copy of the answer frame goes
through the real WebSocket read loop (``tui_gateway.ws.handle_ws``). Hermes file logging runs at DEBUG
into the test home. Afterwards the file holds the value with mode 0600, and the value appears in no
tool result, no frame sent to the viewer, no file under the test home (session database and its WAL,
logs, sessions) and no captured log record.
"""
from __future__ import annotations

import asyncio
import logging
import os
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from gateway.config import Platform
from tests.waiting import async_wait_until

pytestmark = pytest.mark.platforms("posix")

DUMMY = "dummy-" + "e2e-file-value-c41f9a7b"  # built by concatenation: a fake value, never a real secret
QUESTION = [{"question": "XYZ API key, used by the xyz sync timer"}]


def _files_holding(root: Path, needle: bytes) -> list[str]:
    return [str(p) for p in root.rglob("*") if p.is_file() and needle in p.read_bytes()]


async def _garbled_frame_through_the_ws_read_loop(monkeypatch, frame_text: str) -> None:
    from tui_gateway import server, ws as ws_mod
    monkeypatch.setattr(server, "_start_backend_heartbeat_refresher", lambda: None)
    monkeypatch.setattr(server, "resolve_skin", lambda: "default")
    monkeypatch.setattr(server, "_ensure_skin_watcher", lambda: None)
    monkeypatch.setattr(server, "register_live_transport", lambda *_a, **_k: None)
    monkeypatch.setattr(server, "_WS_ORPHAN_REAP_GRACE_S", 0)

    class GarbledViewer:
        frames = [frame_text]

        async def accept(self):
            pass

        async def send_text(self, line):
            pass

        async def receive_text(self):
            if self.frames:
                return self.frames.pop(0)
            raise ws_mod._WebSocketDisconnect()

        async def close(self):
            pass

    await ws_mod.handle_ws(GarbledViewer())


@pytest.fixture
def hermes_file_logs(tmp_path):
    """Hermes's own file logging (agent.log, errors.log, gateway.log) at DEBUG, into the test home."""
    import hermes_logging
    hermes_logging._logging_initialized = False
    hermes_logging._reset_queued_handlers()
    root = logging.getLogger()
    before, level = list(root.handlers), root.level

    def start(home: Path) -> Path:
        return hermes_logging.setup_logging(hermes_home=home, mode="gateway", log_level="DEBUG", force=True)
    yield start
    hermes_logging._reset_queued_handlers()  # flushes and closes the file handlers
    for handler in [h for h in root.handlers if h not in before]:
        root.removeHandler(handler)
        handler.close()
    root.setLevel(level)
    hermes_logging._logging_initialized = False


@pytest.mark.asyncio
async def test_a_secret_file_value_lands_only_in_the_file(tmp_path, monkeypatch, caplog, hermes_file_logs):
    import hermes_logging
    from gateway.session_secret_prompt import secret_prompt_scope
    from gateway.session_server_requests import waiting
    from tests.gateway.test_onboarding_on_the_authority import _desktop, _request
    from tools.clarify_tool import clarify_tool

    caplog.set_level(logging.DEBUG)
    desktop = await _desktop(tmp_path, monkeypatch, [])
    home = tmp_path / ".hermes"
    log_dir = hermes_file_logs(home)
    work = tmp_path / "work"
    work.mkdir()
    target = work / "xyz-api-key"
    try:
        stored = (await _request(desktop, 1, "onboarding.start", {"rerun": True}))["result"]["stored_session_id"]
        assert "result" in await _request(desktop, 2, "session.resume", {"session_id": stored})
        live = desktop.authority.sessions[stored]
        turn = SimpleNamespace(_approval_owner=(desktop.authority, stored, 1),
                               _ctx=SimpleNamespace(source=SimpleNamespace(platform=Platform.LOCAL)))

        def run_the_tool():
            with secret_prompt_scope(turn, SimpleNamespace()):
                return clarify_tool(QUESTION, callback=lambda _questions: {},
                                    secret_file={"name": "XYZ API key", "path": str(target)})
        result = asyncio.get_running_loop().run_in_executor(None, run_the_tool)
        await async_wait_until(lambda: waiting(live.event_stream, stored, "secret"), timeout=5)
        [card] = [f for f in desktop.transport.frames if f.get("method") == "secret"]
        destination = card["params"]["metadata"]["destination"]
        assert destination["path"] == str(target) and destination["mode"] == "0600"
        assert str(target) in card["params"]["prompt"]

        answer = {"jsonrpc": "2.0", "id": card["id"], "result": {"value": DUMMY + "\n"}}
        garbled = str(answer).replace("'", '"')[:-2]  # the answer frame cut off: not JSON
        await _garbled_frame_through_the_ws_read_loop(monkeypatch, garbled)
        assert waiting(live.event_stream, stored, "secret")  # the garbled frame answered nothing

        assert await desktop.connection.dispatch(answer) is None
        raw = await asyncio.wait_for(result, 10)
        desktop.authority.db.append_message(stored, "tool", content=raw, tool_name="clarify", tool_call_id="call-1")
    finally:
        await desktop.connection.close()
    hermes_logging._reset_queued_handlers()  # flush every queued record to the log files

    assert target.read_text(encoding="utf-8") == DUMMY
    assert stat.S_IMODE(os.stat(target).st_mode) == 0o600
    assert DUMMY not in raw and str(target) in raw
    assert not any(DUMMY in repr(f) for f in desktop.transport.frames)
    assert any(p.stat().st_size for p in log_dir.glob("*.log"))  # the logs did record this run
    assert any(p.name.startswith("state.db") or p.suffix == ".db" for p in home.rglob("*")), "no session database"
    assert _files_holding(home, DUMMY.encode()) == []
    assert any("ws parse error" in r.getMessage() for r in caplog.records)
    assert DUMMY not in caplog.text
