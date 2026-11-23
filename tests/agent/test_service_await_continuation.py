"""Conditional continuation for a real service result.

STEP2 is returned only when the request already contains the worker's marker and
exit 0. Exit 3 produces a different token and never STEP2.

The released-wait proof kills an isolated helper subprocess, reattaches the same
invocation, and admits the receipt through a private SessionAuthority. ``_schedule``
is the existing fixture no-op, so this is not a live gateway chat, a host crash,
or a reboot. The parent answer is conditional on ledger growth and the stored
payload bytes.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import textwrap
import time
import uuid
from pathlib import Path

import pytest

# ``_pin`` replaces uuid.uuid4 on the shared uuid module. Test ids must keep the original.
_real_uuid4 = uuid.uuid4

ROOT = Path(__file__).resolve().parents[2]
_STEP_MARKER = "HERMES_WAIT_STEP_OK"
_EXIT3_MARKER = "HERMES_WAIT_EXIT3"


def _user_bus() -> bool:
    if not shutil.which("systemd-run") or not shutil.which("systemctl"):
        return False
    runtime = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return os.path.exists(os.path.join(runtime, "bus"))


pytestmark = [
    pytest.mark.platforms("linux"),
    pytest.mark.skipif(not _user_bus(), reason="user systemd bus is not available"),
]


def _own(request, unit: str) -> None:
    owned = getattr(request.node, "live_system_guard_owned_units", None)
    if not isinstance(owned, set):
        owned = set(owned or ())
        request.node.live_system_guard_owned_units = owned
    owned.add(unit)
    if unit.endswith(".service"):
        owned.add(unit[: -len(".service")])


def _bus_env() -> dict:
    from tools.process_registry import systemd_user_bus_env
    return systemd_user_bus_env()


def _stop_owned(unit: str) -> None:
    env = _bus_env()
    subprocess.run(["systemctl", "--user", "stop", unit], check=False, capture_output=True, text=True, env=env)
    subprocess.run(["systemctl", "--user", "reset-failed", unit], check=False, capture_output=True, text=True, env=env)


def _pin(monkeypatch, hex_id: str) -> str:
    class _Fixed:
        hex = hex_id + "ffff"

    monkeypatch.setattr("tools.process_registry.uuid.uuid4", lambda: _Fixed())
    return f"hermes-bg-proc_{hex_id}.service"


def _message_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            _message_text(part.get("text") if isinstance(part, dict) else part) for part in content
        )
    return "" if content is None else str(content)


def _exit_code(text: str):
    try:
        body = json.loads(text)
    except ValueError:
        return None
    if isinstance(body, dict):
        return body.get("exit_code")
    return None


def _parent_step(grew: bool, payload: str, marker: str):
    """STEP2 only when the admitted ledger text already holds the real marker and exit 0."""
    if grew and marker in payload and "exit code 0" in payload:
        return "STEP2"
    return None


def _forget_services() -> None:
    """The registry is a process singleton and FakeLLM reuses ``call_fake_1``.

    Drop this file's service rows and receipts so the next case is a new command,
    not a resume of the previous tool call id.
    """
    from hermes_constants import get_hermes_home
    from tools.process_registry import process_registry

    ids = []
    for table in (process_registry._running, process_registry._finished):
        for session in list(table.values()):
            if getattr(session, "service_unit", ""):
                ids.append(session.id)
                table.pop(session.id, None)
                process_registry._completion_consumed.discard(session.id)
    process_registry._write_checkpoint()
    directory = get_hermes_home() / "logs" / "process-results"
    for session_id in ids:
        (directory / f"{session_id}.json").unlink(missing_ok=True)


def _turn(monkeypatch, request, command: str, marker: str, other_marker: str):
    from run_agent import AIAgent
    from tests.e2e.core.history._helpers import NO_BACKGROUND_REVIEW, OFFLINE_CONFIG
    from tests.fakes.fake_llm_provider import FakeLLMServer, Text, ToolCall, write_hermes_home
    import tools.process_registry_service as service_mod

    _forget_services()
    home = Path(os.environ["HERMES_HOME"])
    saved = {}
    for name in ("config.yaml", ".env"):
        path = home / name
        saved[name] = path.read_bytes() if path.exists() else None
    hex_id = _real_uuid4().hex[:12]
    unit = _pin(monkeypatch, hex_id)
    _own(request, unit)
    launches = {"n": 0}
    real_launch = service_mod._launch_unit

    def _count(session):
        launches["n"] += 1
        return real_launch(session)

    monkeypatch.setattr(service_mod, "_launch_unit", _count)
    answers = []

    def respond(record):
        messages = (record.get("body") or {}).get("messages") or []
        tool_texts = [_message_text(item.get("content")) for item in messages if item.get("role") == "tool"]
        for text in tool_texts:
            if marker in text and _exit_code(text) == 0:
                answers.append("STEP2")
                return Text("STEP2")
            if other_marker in text and _exit_code(text) == 3:
                answers.append("EXIT3")
                return Text("EXIT3")
        if not tool_texts:
            answers.append("tool")
            return ToolCall("terminal", {"command": command, "service": "await", "timeout": 60})
        answers.append("NO_MARKER")
        return Text("NO_MARKER")

    try:
        with FakeLLMServer(respond) as server:
            write_hermes_home(
                home, server.base_url,
                extra_config=OFFLINE_CONFIG + NO_BACKGROUND_REVIEW + 'approvals:\n  mode: "off"\n',
            )
            agent = AIAgent(
                provider="custom", base_url=server.base_url, api_key="sk-fake", model="fake-model",
                session_id=f"svc-await-{hex_id}", quiet_mode=True, platform="cli", skip_memory=True,
                skip_context_files=True, load_soul_identity=False, skip_background_review=True,
                enabled_toolsets=["terminal"], max_iterations=4,
            )
            try:
                result = agent.run_conversation("run the waited command", conversation_history=[], task_id=f"task-{hex_id}")
            finally:
                agent.close()
            requests = server.main_requests()
        return result, requests, answers, launches["n"], unit
    finally:
        _stop_owned(unit)
        for name, data in saved.items():
            path = home / name
            if data is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(data)


def test_conditional_responder_continues_only_after_the_real_exit(request, monkeypatch):
    result, requests, answers, launches, _unit_name = _turn(
        monkeypatch, request,
        f"printf '{_STEP_MARKER}\\n'; exit 0", _STEP_MARKER, _EXIT3_MARKER,
    )
    assert launches == 1, (launches, result)
    assert answers == ["tool", "STEP2"], answers
    assert len(requests) == 2, requests
    tool_texts = [
        _message_text(item.get("content"))
        for item in requests[1].get("messages") or [] if item.get("role") == "tool"
    ]
    assert any(_STEP_MARKER in text and _exit_code(text) == 0 for text in tool_texts), tool_texts
    assert result.get("final_response") == "STEP2", result
    assert "EXIT3" not in (result.get("final_response") or "")


def test_conditional_responder_does_not_continue_after_exit_3(request, monkeypatch):
    result, requests, answers, launches, _unit_name = _turn(
        monkeypatch, request,
        f"printf '{_EXIT3_MARKER}\\n'; exit 3", _STEP_MARKER, _EXIT3_MARKER,
    )
    assert launches == 1, (launches, result)
    assert answers == ["tool", "EXIT3"], answers
    assert "STEP2" not in answers
    assert len(requests) == 2, [len(requests), answers]
    tool_texts = [
        _message_text(item.get("content"))
        for item in requests[1].get("messages") or [] if item.get("role") == "tool"
    ]
    assert any(_EXIT3_MARKER in text and _exit_code(text) == 3 for text in tool_texts), tool_texts
    assert _STEP_MARKER not in "\n".join(tool_texts)
    assert result.get("final_response") == "EXIT3", result
    assert "STEP2" not in (result.get("final_response") or "")


_HELPER = textwrap.dedent("""\
    import json
    import os
    import shlex
    import sys
    import time
    from pathlib import Path

    sys.path.insert(0, os.environ["HERMES_WAIT_ROOT"])
    hex_id = os.environ["HERMES_WAIT_HEX"]
    flag = os.environ["HERMES_WAIT_FLAG"]
    state_path = Path(os.environ["HERMES_WAIT_STATE"])
    marker = os.environ["HERMES_WAIT_MARKER"]
    session_key = os.environ["HERMES_WAIT_SESSION_KEY"]
    tool_call_id = os.environ["HERMES_WAIT_TOOL_CALL"]

    class _Fixed:
        hex = hex_id + "ffff"

    import tools.process_registry as registry_mod
    registry_mod.uuid.uuid4 = lambda: _Fixed()
    import tools.process_registry_service as service_mod
    launches = {"n": 0}
    real_launch = service_mod._launch_unit

    def _count(session):
        launches["n"] += 1
        return real_launch(session)

    service_mod._launch_unit = _count
    from tools.approval_context import set_current_observability_context
    set_current_observability_context(tool_call_id=tool_call_id)
    from tools.process_registry import process_registry
    from tools.process_registry_service import run_terminal_service

    command = (
        "while [ ! -f " + shlex.quote(flag) + " ]; do sleep 0.2; done; "
        "printf '%s\\n' " + shlex.quote(marker) + "; exit 0"
    )
    try:
        raw = run_terminal_service(
            command=command, mode="await", cwd=os.environ["HERMES_WAIT_WORKDIR"],
            task_id="svc-await-helper", session_key=session_key, timeout=2,
            env_vars=None, pty=False, env_type="local",
        )
        result = json.loads(raw)
        session = process_registry.get(result.get("session_id") or "")
        if session is not None:
            session.watcher_platform = "discord"
            session.watcher_chat_id = "42"
            session.watcher_user_id = "42"
            session.session_key = session_key
            session.parent_session_id = os.environ.get("HERMES_SESSION_ID") or ""
            process_registry._write_checkpoint()
        payload = json.dumps({
            "session_id": result.get("session_id"),
            "invocation": result.get("service_invocation_id"),
            "boot": result.get("service_boot_id"),
            "unit": result.get("service_unit"),
            "tool_call_id": tool_call_id,
            "launches": launches["n"],
            "result": result,
        })
        temporary = state_path.with_suffix(".tmp")
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(state_path)
    except Exception as exc:
        temporary = state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"error": str(exc), "launches": launches["n"]}), encoding="utf-8")
        temporary.replace(state_path)
        raise
    time.sleep(300)
""")


def _payload_texts(authority, owner) -> list[str]:
    rows = authority.persistence.admissions.list(session_id=owner, pending_only=False)
    texts = []
    for row in rows:
        payload = getattr(row, "payload", None)
        texts.append(json.dumps(payload, default=str) if payload is not None else "")
    return texts


def _drive_released_unit(monkeypatch, tmp_path, metadata, route, unit, hex_id):
    """Start, kill, and recover the helper off the event loop.

    The wait is a real subprocess and ``systemctl show``. Keeping it synchronous
    avoids blocking the asyncio loop that later admits the receipt. The caller
    owns ``unit`` before this runs so a failure still stops that name.
    """
    from tools.process_registry import ProcessRegistry
    from tools.process_registry_service import pending_service_events, refresh_service_session
    import tools.process_registry_service as service_mod

    marker = f"HERMES_WAIT_CONT_{hex_id}"
    flag = tmp_path / "worker-flag"
    state_path = tmp_path / "helper-state.json"
    script = tmp_path / "helper.py"
    script.write_text(_HELPER, encoding="utf-8")
    log_path = tmp_path / "helper.log"
    parent_launches = {"n": 0}
    real_launch = service_mod._launch_unit

    def _count(session):
        parent_launches["n"] += 1
        return real_launch(session)

    monkeypatch.setattr(service_mod, "_launch_unit", _count)
    seen = {}
    real_cleanup = service_mod._cleanup_unit_if_match

    def _snap(session):
        seen["cleanup_show"] = service_mod.systemctl_show(session.service_unit)
        return real_cleanup(session)

    monkeypatch.setattr(service_mod, "_cleanup_unit_if_match", _snap)
    env = os.environ.copy()
    env["HERMES_HOME"] = str(tmp_path)
    env["HERMES_RUNTIME_DIR"] = str(tmp_path / "runtime")
    env["TMPDIR"] = str(tmp_path)
    env["HERMES_WAIT_HEX"] = hex_id
    env["HERMES_WAIT_FLAG"] = str(flag)
    env["HERMES_WAIT_STATE"] = str(state_path)
    env["HERMES_WAIT_MARKER"] = marker
    env["HERMES_WAIT_SESSION_KEY"] = route
    env["HERMES_WAIT_TOOL_CALL"] = f"call-{hex_id}"
    env["HERMES_WAIT_ROOT"] = str(ROOT)
    env["HERMES_WAIT_WORKDIR"] = str(tmp_path)
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    for key in (
        "HERMES_API_KEY", "HERMES_SESSION_TOKEN", "OPENAI_API_KEY", "TELEGRAM_BOT_TOKEN",
        "HERMES_SESSION_KEY", "HERMES_SESSION_PLATFORM", "_HERMES_GATEWAY",
    ):
        env.pop(key, None)
    # The helper inherits this process. A previous agent case leaves its session id
    # here, and that pin is already closed. The receipt must name this authority.
    env["HERMES_SESSION_ID"] = metadata["gateway_session_id"]
    proc = None
    log = open(log_path, "w", encoding="utf-8")
    try:
        proc = subprocess.Popen([sys.executable, str(script)], env=env, stdout=log, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline and not state_path.exists():
            if proc.poll() is not None:
                break
            time.sleep(0.1)
        log.flush()
        assert state_path.exists(), log_path.read_text(encoding="utf-8", errors="replace")[-2000:]
        proc.kill()
        proc.wait(timeout=5)
        state = json.loads(state_path.read_text(encoding="utf-8"))
        assert "error" not in state, state
        assert state["launches"] == 1, state
        assert state["unit"] == unit, state
        assert parent_launches["n"] == 0
        fresh = ProcessRegistry()
        assert fresh.recover_from_checkpoint() >= 1
        row = fresh.get(state["session_id"])
        assert row is not None
        assert row.service_invocation_id == state["invocation"]
        assert row.pid is None
        assert row.systemd_unit == ""
        assert row._reader_thread is None
        assert row.exited is False
        active = subprocess.run(
            ["systemctl", "--user", "is-active", unit], check=False, capture_output=True, text=True,
            env=_bus_env(),
        )
        assert active.stdout.strip() in {"active", "activating"}, active.stdout
        flag.write_text("go", encoding="utf-8")
        output = ""
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                output = Path(row.output_log).read_text(encoding="utf-8", errors="replace")
            except OSError:
                output = ""
            if marker in output:
                break
            time.sleep(0.2)
        assert marker in output, output[-500:]
        refresh_service_session(fresh, row, publish=False)
        assert row.exited is True and row.exit_code == 0, (row.exit_code, row.completion_reason)
        receipt = tmp_path / "logs" / "process-results" / f"{row.id}.json"
        stored = json.loads(receipt.read_text(encoding="utf-8-sig"))
        assert stored.get("exit_code") == 0
        assert marker in (stored.get("output") or "")
        assert stored.get("admission_pending") is True
        events = [item for item in pending_service_events() if item.get("session_id") == row.id]
        assert len(events) == 1, events
        assert events[0]["started_at"] == stored["started_at"]
        show = seen.get("cleanup_show") or {}
        assert show.get("NRestarts") == "0", show
        assert parent_launches["n"] == 0
        return {
            "unit": unit,
            "marker": marker,
            "state": state,
            "row_id": row.id,
            "events": events,
            "stored": stored,
            "receipt": receipt,
            "parent_launches": parent_launches,
        }
    finally:
        if proc is not None and proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
        log.close()


@pytest.mark.asyncio
async def test_released_wait_recovers_once_and_admits_the_real_exit(request, monkeypatch, tmp_path):
    """Private authority and a killed helper. Not a live chat, host crash, or reboot."""
    from gateway.session_authority import SessionAuthority
    from tests.gateway.test_automation_notification_category import _native_owner
    from tools.process_registry import ProcessRegistry
    from tools.process_registry_notifications import format_process_notification
    from tools.process_registry_service import pending_service_events

    runner, authority, _adapter, _source, metadata = await _native_owner(tmp_path, monkeypatch, "human-1")
    route = metadata["gateway_session_key"]
    owner = authority.logical_owner(metadata["gateway_session_id"])
    hex_id = _real_uuid4().hex[:12]
    unit = f"hermes-bg-proc_{hex_id}.service"
    _own(request, unit)
    try:
        driven = _drive_released_unit(monkeypatch, tmp_path, metadata, route, unit, hex_id)
        marker = driven["marker"]
        state = driven["state"]
        events = driven["events"]
        stored = driven["stored"]
        receipt = driven["receipt"]
        parent_launches = driven["parent_launches"]
        before = _payload_texts(authority, owner)
        assert not any(marker in text for text in before)
        text = format_process_notification(events[0])
        assert text and marker in text and "exit code 0" in text, text
        injected = await runner._inject_watch_notification(text, events[0])
        assert injected is True, injected
        after = _payload_texts(authority, owner)
        matching = [text for text in after if marker in text and "exit code 0" in text]
        assert len(matching) == 1, after
        assert _parent_step(len(matching) > len([item for item in before if marker in item]), matching[0], marker) == "STEP2"

        stored["output"] = (stored.get("output") or "") + "\nDRIFT"
        receipt.write_text(json.dumps(stored), encoding="utf-8")
        drifted = next(item for item in pending_service_events() if item.get("session_id") == driven["row_id"])
        drifted_text = format_process_notification(drifted)
        assert "DRIFT" in (drifted_text or "")
        scheduled = []
        monkeypatch.setattr(SessionAuthority, "_schedule", lambda self, ref: scheduled.append(ref))
        again = await runner._inject_watch_notification(drifted_text, drifted)
        assert again is True, again
        assert scheduled == []
        stayed = _payload_texts(authority, owner)
        assert len([text for text in stayed if marker in text]) == 1
        assert _parent_step(False, drifted_text or "", marker) is None

        fresh_again = ProcessRegistry()
        fresh_again.recover_from_checkpoint()
        assert fresh_again.get(driven["row_id"]) is None
        assert parent_launches["n"] == 0
        assert state["launches"] == 1
    finally:
        if unit:
            _stop_owned(unit)
        authority.runner.session_store.close_all_db_handles()
