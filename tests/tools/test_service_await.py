"""Required-result user services: one systemd unit, one outcome, no second launch.

The entry is the real ``terminal`` tool. A missing user bus skips the file.
Each test names its own unit before any mutating systemctl call.
Classifier cases that pass a show dict are labeled and do not launch a unit.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.interrupt import set_interrupt

# ``_pin`` replaces uuid.uuid4 on the shared uuid module. Test ids must keep the original.
_real_uuid4 = uuid.uuid4


def _user_bus() -> bool:
    if not shutil.which("systemd-run") or not shutil.which("systemctl"):
        return False
    runtime = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return os.path.exists(os.path.join(runtime, "bus"))


pytestmark = [
    pytest.mark.platforms("linux"),
    pytest.mark.skipif(not _user_bus(), reason="user systemd bus is not available"),
]

_MARKER = "HERMES_WAIT_OK"


@pytest.fixture(autouse=True)
def _clear_interrupt_bit():
    set_interrupt(False)
    yield
    set_interrupt(False)


def _own(request, unit: str) -> None:
    owned = getattr(request.node, "live_system_guard_owned_units", None)
    if not isinstance(owned, set):
        owned = set(owned or ())
        request.node.live_system_guard_owned_units = owned
    owned.add(unit)
    if unit.endswith(".service"):
        owned.add(unit[: -len(".service")])


def _bus_env() -> dict:
    """Pytest isolation drops the login bus. The product derives it; checks must too."""
    from tools.process_registry import systemd_user_bus_env
    return systemd_user_bus_env()


def _systemctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["systemctl", "--user", *args],
        check=False, capture_output=True, text=True, env=_bus_env(),
    )


def _stop_owned(unit: str) -> None:
    _systemctl("stop", unit)
    _systemctl("reset-failed", unit)


def _pin(monkeypatch, hex_id: str) -> str:
    class _Fixed:
        hex = hex_id + "ffff"

    monkeypatch.setattr("tools.process_registry.uuid.uuid4", lambda: _Fixed())
    return f"hermes-bg-proc_{hex_id}.service"


def _count_launches(monkeypatch):
    import tools.process_registry_service as service_mod

    seen = {"launches": 0, "cleanup_show": None}
    real_launch = service_mod._launch_unit

    def count(session):
        seen["launches"] += 1
        return real_launch(session)

    monkeypatch.setattr(service_mod, "_launch_unit", count)
    real_cleanup = service_mod._cleanup_unit_if_match

    def snap(session):
        seen["cleanup_show"] = service_mod.systemctl_show(session.service_unit)
        return real_cleanup(session)

    monkeypatch.setattr(service_mod, "_cleanup_unit_if_match", snap)
    return seen


def _loads(raw):
    if isinstance(raw, dict):
        return raw
    return json.loads(raw)


def _dispatch(args: dict, tool_call_id: str, task_id: str):
    import tools.terminal_tool  # registers the terminal tool
    from tools.approval_context import (
        reset_current_observability_context,
        set_current_observability_context,
    )
    from tools.registry import registry

    tokens = set_current_observability_context(tool_call_id=tool_call_id)
    try:
        raw = registry.dispatch("terminal", args, task_id=task_id)
    finally:
        reset_current_observability_context(tokens)
    return _loads(raw)


def _up(unit: str) -> bool:
    result = _systemctl("is-active", unit)
    return result.stdout.strip() in {"active", "activating"}


def _show(unit: str) -> dict:
    import tools.process_registry_service as service_mod

    return service_mod.systemctl_show(unit) or {}


def _take_events(session_id: str) -> list:
    from tools.process_registry import process_registry

    mine, keep = [], []
    while True:
        try:
            evt = process_registry.completion_queue.get_nowait()
        except Exception:
            break
        if evt.get("session_id") == session_id:
            mine.append(evt)
        else:
            keep.append(evt)
    for evt in keep:
        process_registry.completion_queue.put(evt)
    return mine


def _release(unit: str) -> None:
    from tools.process_registry import process_registry

    found = []
    for table in (process_registry._running, process_registry._finished):
        for session in list(table.values()):
            if getattr(session, "service_unit", "") == unit:
                found.append(session)
    for session in found:
        process_registry._running.pop(session.id, None)
        process_registry._finished[session.id] = session
    if not found:
        return
    try:
        process_registry._write_checkpoint()
    finally:
        for session in found:
            process_registry._finished.pop(session.id, None)
            process_registry._completion_consumed.discard(session.id)


@contextmanager
def _unit(request, monkeypatch):
    hex_id = _real_uuid4().hex[:12]
    unit = _pin(monkeypatch, hex_id)
    _own(request, unit)
    seen = _count_launches(monkeypatch)
    try:
        yield SimpleNamespace(
            hex=hex_id, unit=unit, seen=seen,
            tool_call_id=f"call-{hex_id}", task_id=f"task-{hex_id}",
        )
    finally:
        set_interrupt(False)
        _stop_owned(unit)
        _release(unit)


def _session(session_id: str):
    from tools.process_registry import process_registry

    return process_registry.get(session_id)


def _list_entry(session_id: str):
    from tools.process_registry import process_registry

    for entry in process_registry.list_sessions(include_service_receipts=True):
        if entry["session_id"] == session_id:
            return entry
    return None


def _until_exited(session_id: str, timeout: float = 15):
    from tools.process_registry import process_registry
    from tools.process_registry_service import refresh_service_session

    deadline = time.monotonic() + timeout
    session = process_registry.get(session_id)
    while time.monotonic() < deadline and session is not None and not session.exited:
        refresh_service_session(process_registry, session)
        if session.exited:
            break
        time.sleep(0.2)
        session = process_registry.get(session_id)
    return session


def test_await_deadline_floor_survives_background_and_over_cap():
    from tools.terminal_tool import FOREGROUND_MAX_TIMEOUT, _terminal_deadline_floor

    assert _terminal_deadline_floor({"service": "await", "background": True, "timeout": 700}) == 700.0
    assert _terminal_deadline_floor({"service": "notify", "timeout": 700}) is None
    assert _terminal_deadline_floor({"background": True, "timeout": 5}) is None
    assert _terminal_deadline_floor({"timeout": FOREGROUND_MAX_TIMEOUT + 1}) is None


def test_terminal_service_await_returns_the_worker_exit(request, monkeypatch):
    """A real ``terminal(service=await)`` call returns the worker's exit from the
    retained unit, not a foreground child and not the systemd-run client."""
    from hermes_cli.cli_process_dock import process_status
    from tools.process_registry import process_registry

    with _unit(request, monkeypatch) as case:
        result = _dispatch(
            {"command": f"printf '{_MARKER}\\n'; exit 0", "service": "await",
             "background": True, "timeout": 700},
            case.tool_call_id, case.task_id,
        )
        assert result.get("exit_code") == 0, result
        assert result.get("service") == "await", result
        assert _MARKER in (result.get("output") or ""), result
        assert result.get("systemd_unit") in (None, ""), result
        assert result.get("service_invocation_id"), result
        assert result.get("status") == "exited", result
        assert case.seen["launches"] == 1, case.seen
        show = case.seen["cleanup_show"] or {}
        assert show.get("NRestarts") == "0", show
        assert show.get("Id") == case.unit, show
        assert show.get("SubState") in {"exited", "failed"}, show
        assert show.get("Result") == "success", show
        assert show.get("ExecMainCode") == "1", show
        assert show.get("ExecMainStatus") == "0", show
        session = _session(result["session_id"])
        assert session is not None and session.notify_on_complete is False
        assert session.admission_pending is False
        assert _take_events(session.id) == []
        entry = _list_entry(session.id)
        assert entry is not None and "attention" not in entry, entry
        assert process_status(entry) == "done"


def test_exit_code_comes_from_the_terminal_show(request, monkeypatch):
    import tools.process_registry_results as results
    import tools.process_registry_service as service_mod

    seen = {}
    real = results.write_frozen_result

    def wrapped(session_id, record, *, strict=False):
        if strict and "show" not in seen:
            seen["show"] = service_mod.systemctl_show(record.get("service_unit") or "")
        return real(session_id, record, strict=strict)

    monkeypatch.setattr(results, "write_frozen_result", wrapped)
    with _unit(request, monkeypatch) as case:
        result = _dispatch(
            {"command": "printf 'HERMES_WAIT_EXIT3\\n'; exit 3", "service": "await", "timeout": 60},
            case.tool_call_id, case.task_id,
        )
        assert result.get("exit_code") == 3, result
        show = seen.get("show") or {}
        assert show.get("Result") == "exit-code", show
        assert show.get("ExecMainStatus") == "3", show
        session = _session(result["session_id"])
        assert session is not None and session.notify_on_complete is False
        assert _take_events(session.id) == []
        assert case.seen["launches"] == 1


def test_notify_stays_running_and_a_live_success_code_is_not_an_exit(request, monkeypatch):
    from tools.process_registry_service import classify_show

    with _unit(request, monkeypatch) as case:
        result = _dispatch(
            {"command": "sleep 30", "service": "notify"},
            case.tool_call_id, case.task_id,
        )
        assert result.get("exit_code") is None, result
        assert result.get("status") == "running", result
        assert result.get("process_running") is True, result
        assert result.get("systemd_unit") in (None, ""), result
        session = _session(result["session_id"])
        assert session is not None and session.exited is False
        show = _show(case.unit)
        assert show.get("SubState") not in {"exited", "failed"}, show
        labeled = classify_show(session, {
            "LoadState": "loaded", "InvocationID": session.service_invocation_id,
            "SubState": "running", "Result": "success", "ExecMainCode": "0", "ExecMainStatus": "0",
        })
        assert labeled == ("running",), labeled
        assert case.seen["launches"] == 1
        assert _up(case.unit)


def test_execmain_stop_and_continue_are_not_terminal():
    """Labeled classifier only. Not a live execution."""
    from tools.process_registry_service import classify_show

    session = SimpleNamespace(service_invocation_id="inv-1", service_stop_intent=False, output_log="")
    for code in ("5", "6"):
        decision = classify_show(session, {
            "LoadState": "loaded", "InvocationID": "inv-1", "SubState": "exited",
            "Result": "success", "ExecMainCode": code, "ExecMainStatus": "0",
        })
        assert decision == ("running",), (code, decision)
    empty = SimpleNamespace(service_invocation_id="", service_stop_intent=False, output_log="")
    assert classify_show(empty, {
        "LoadState": "loaded", "InvocationID": "", "SubState": "exited",
        "Result": "success", "ExecMainCode": "0", "ExecMainStatus": "0",
    }) == ("unresolved",)
    stopped = SimpleNamespace(service_invocation_id="inv-1", service_stop_intent=True, output_log="")
    assert classify_show(stopped, {
        "LoadState": "not-found", "InvocationID": "", "SubState": "",
        "Result": "success", "ExecMainCode": "0", "ExecMainStatus": "0",
    }) == ("exit", -15, "killed", "unit_stopped")


def test_timeout_steer_and_interrupt_leave_the_same_invocation(request, monkeypatch):
    from hermes_cli.cli_process_dock import process_rows, process_status
    from tools.interrupt import request_yield
    from tools.process_registry import process_registry
    from tools.process_registry_service import _UNRESOLVED_NOTE
    from tools.process_registry_wait_policy import apply_wait_poll_policy

    with _unit(request, monkeypatch) as case:
        first = _dispatch(
            {"command": "sleep 30", "service": "await", "timeout": 1},
            case.tool_call_id, case.task_id,
        )
        assert first.get("status") == "unresolved", first
        assert first.get("status") != "timeout"
        assert first.get("exit_code") is None, first
        assert first.get("process_running") is True, first
        assert first.get("note") == _UNRESOLVED_NOTE, first
        assert case.seen["launches"] == 1
        invocation = first["service_invocation_id"]
        assert invocation
        session = _session(first["session_id"])
        assert session is not None
        assert session.id not in process_registry._completion_consumed
        echoed = apply_wait_poll_policy("wait", session.id, dict(first))
        assert echoed.get("note") == _UNRESOLVED_NOTE
        assert "do more work" not in (echoed.get("note") or "")
        entry = _list_entry(session.id)
        assert entry is not None and entry.get("attention") == "waiting", entry
        assert process_status(entry) == "waiting"
        rows = [row for row in process_rows() if row["id"] == session.id]
        assert rows and rows[0]["status"] == "waiting", rows

        request_yield(threading.get_ident())
        started = time.monotonic()
        second = _dispatch(
            {"command": "sleep 30", "service": "await", "timeout": 30},
            case.tool_call_id, case.task_id,
        )
        assert time.monotonic() - started < 8, second
        assert second.get("status") == "unresolved", second
        assert second.get("service_invocation_id") == invocation, second
        assert case.seen["launches"] == 1

        set_interrupt(True)
        started = time.monotonic()
        third = _dispatch(
            {"command": "sleep 30", "service": "await", "timeout": 30},
            case.tool_call_id, case.task_id,
        )
        assert time.monotonic() - started < 8, third
        assert third.get("status") == "unresolved", third
        assert third.get("service_invocation_id") == invocation, third
        assert _up(case.unit)
        assert case.seen["launches"] == 1


def test_orderly_stop_records_sigterm_not_success(request, monkeypatch):
    from tools.process_registry import process_registry

    with _unit(request, monkeypatch) as case:
        started = _dispatch(
            {"command": "sleep 30", "service": "notify"},
            case.tool_call_id, case.task_id,
        )
        result = process_registry.kill_process(started["session_id"])
        assert result.get("status") == "killed", result
        assert result.get("exit_code") == -15, result
        assert result.get("completion_reason") == "killed", result
        assert result.get("termination_source") == "unit_stopped", result
        assert case.seen["launches"] == 1


def test_failed_stop_intent_write_does_not_signal(request, monkeypatch):
    from tools.process_registry import process_registry

    with _unit(request, monkeypatch) as case:
        started = _dispatch(
            {"command": "sleep 30", "service": "notify"},
            case.tool_call_id, case.task_id,
        )
        session = _session(started["session_id"])
        real = process_registry._write_checkpoint

        def wrapped(*args, **kwargs):
            if kwargs.get("strict") and session.service_stop_intent:
                return False
            return real(*args, **kwargs)

        monkeypatch.setattr(process_registry, "_write_checkpoint", wrapped)
        result = process_registry.kill_process(session.id)
        assert result.get("status") == "unresolved", result
        assert session.service_stop_intent is False
        assert _up(case.unit)
        assert case.seen["launches"] == 1


def test_empty_live_invocation_is_not_a_stop(request, monkeypatch):
    import tools.process_registry_service as service_mod
    from tools.process_registry import process_registry

    with _unit(request, monkeypatch) as case:
        started = _dispatch(
            {"command": "sleep 30", "service": "notify"},
            case.tool_call_id, case.task_id,
        )
        session = _session(started["session_id"])
        real_show = service_mod.systemctl_show

        def blank(unit):
            show = real_show(unit)
            if not show:
                return show
            cloned = dict(show)
            cloned["InvocationID"] = ""
            return cloned

        monkeypatch.setattr(service_mod, "systemctl_show", blank)
        result = process_registry.kill_process(session.id)
        monkeypatch.setattr(service_mod, "systemctl_show", real_show)
        assert result.get("status") == "unresolved", result
        assert session.service_stop_intent is False
        assert _up(case.unit)


def test_post_invocation_write_failure_does_not_launch_again(request, monkeypatch):
    from tools.process_registry import process_registry

    with _unit(request, monkeypatch) as case:
        real = process_registry._write_checkpoint
        strict_calls = {"n": 0}

        def wrapped(*args, **kwargs):
            if kwargs.get("strict"):
                strict_calls["n"] += 1
                if strict_calls["n"] == 2:
                    return False
            return real(*args, **kwargs)

        monkeypatch.setattr(process_registry, "_write_checkpoint", wrapped)
        first = _dispatch(
            {"command": "sleep 30", "service": "notify"},
            case.tool_call_id, case.task_id,
        )
        assert first.get("status") == "unresolved", first
        assert first.get("service_invocation_id") in (None, ""), first
        assert "never ran" not in (first.get("note") or "").lower(), first
        assert "never ran" not in (first.get("error") or "").lower(), first
        assert case.seen["launches"] == 1
        assert strict_calls["n"] == 2
        assert _up(case.unit)
        session = _session(first["session_id"])
        assert session is not None and session.service_invocation_id == ""

        second = _dispatch(
            {"command": "sleep 30", "service": "notify"},
            case.tool_call_id, case.task_id,
        )
        assert case.seen["launches"] == 1, second
        monkeypatch.setattr(process_registry, "_write_checkpoint", real)
        stopped = process_registry.kill_process(session.id)
        assert stopped.get("status") == "killed", stopped
        assert stopped.get("exit_code") == -15, stopped
        assert stopped.get("termination_source") == "unit_stopped", stopped
        assert case.seen["launches"] == 1


def test_signal_kill_records_the_unit_signal(request, monkeypatch):
    from tools.process_registry import process_registry
    from tools.process_registry_service import refresh_service_session

    with _unit(request, monkeypatch) as case:
        started = _dispatch(
            {"command": "sleep 30", "service": "notify"},
            case.tool_call_id, case.task_id,
        )
        killed = _systemctl("kill", case.unit, "--kill-who=main", "--signal=KILL")
        assert killed.returncode == 0, (killed.returncode, killed.stderr)
        show = {}
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            show = _show(case.unit)
            if show.get("Result") == "signal":
                break
            time.sleep(0.2)
        assert show.get("Result") == "signal", show
        assert show.get("ExecMainCode") == "2", show
        assert show.get("ExecMainStatus") == "9", show
        session = _session(started["session_id"])
        refresh_service_session(process_registry, session)
        assert session.exit_code == -9, (session.exit_code, session.completion_reason, show)
        assert session.completion_reason == "killed"
        assert session.termination_source == "unit_signal"
        assert case.seen["launches"] == 1


def test_recover_reattaches_the_same_invocation_without_a_second_launch(request, monkeypatch):
    from tools.process_registry import ProcessRegistry, _checkpoint_path

    with _unit(request, monkeypatch) as case:
        started = _dispatch(
            {"command": "sleep 30", "service": "notify"},
            case.tool_call_id, case.task_id,
        )
        path = _checkpoint_path()
        entries = json.loads(path.read_text(encoding="utf-8-sig"))
        assert any(item.get("session_id") == started["session_id"] for item in entries)
        for item in entries:
            if item.get("session_id") == started["session_id"]:
                item["owner_pid"] = 2**22
        path.write_text(json.dumps(entries), encoding="utf-8")
        fresh = ProcessRegistry()
        assert fresh.recover_from_checkpoint() >= 1
        row = fresh.get(started["session_id"])
        assert row is not None
        assert row.service_invocation_id == started["service_invocation_id"]
        assert row.pid is None
        assert row.systemd_unit == ""
        assert row._reader_thread is None
        assert row.exited is False
        assert row.completion_reason != "lost"
        assert _up(case.unit)
        assert _show(case.unit).get("NRestarts") == "0"
        assert case.seen["launches"] == 1


def test_invocation_or_boot_mismatch_does_not_signal(request, monkeypatch):
    from tools.process_registry import process_registry
    from tools.process_registry_service import refresh_service_session

    with _unit(request, monkeypatch) as case:
        started = _dispatch(
            {"command": "sleep 30", "service": "notify"},
            case.tool_call_id, case.task_id,
        )
        session = _session(started["session_id"])
        session.service_invocation_id = "not-the-live-invocation"
        refresh_service_session(process_registry, session)
        assert session.exited is True
        assert session.exit_code == -1
        assert session.completion_reason == "lost"
        assert _up(case.unit)

    with _unit(request, monkeypatch) as case:
        started = _dispatch(
            {"command": "sleep 30", "service": "notify"},
            case.tool_call_id, case.task_id,
        )
        session = _session(started["session_id"])
        session.service_boot_id = "not-this-boot"
        refused = process_registry.kill_process(session.id)
        assert refused.get("status") == "unresolved", refused
        assert session.service_stop_intent is False
        assert _up(case.unit)
        refresh_service_session(process_registry, session)
        assert session.completion_reason == "lost"
        assert session.exit_code == -1
        assert _up(case.unit)
        assert case.seen["launches"] == 1


def test_pre_launch_checkpoint_failure_starts_nothing(request, monkeypatch):
    from tools.process_registry import process_registry

    with _unit(request, monkeypatch) as case:
        real = process_registry._write_checkpoint

        def wrapped(*args, **kwargs):
            if kwargs.get("strict"):
                return False
            return real(*args, **kwargs)

        monkeypatch.setattr(process_registry, "_write_checkpoint", wrapped)
        result = _dispatch(
            {"command": "printf hi", "service": "await", "timeout": 30},
            case.tool_call_id, case.task_id,
        )
        assert result.get("status") == "error", result
        assert "could not be stored" in (result.get("error") or ""), result
        assert case.seen["launches"] == 0
        assert _show(case.unit).get("LoadState") in {None, "", "not-found"}


def test_result_write_failure_keeps_the_unit_and_the_same_launch(request, monkeypatch):
    import tools.process_registry_results as results

    flag = {"fail": True}
    real = results.write_frozen_result

    def wrapped(session_id, record, *, strict=False):
        if flag["fail"] and strict:
            return False
        return real(session_id, record, strict=strict)

    monkeypatch.setattr(results, "write_frozen_result", wrapped)
    with _unit(request, monkeypatch) as case:
        first = _dispatch(
            {"command": f"printf '{_MARKER}\\n'; exit 0", "service": "await", "timeout": 2},
            case.tool_call_id, case.task_id,
        )
        assert first.get("status") == "unresolved", first
        assert first.get("exit_code") is None, first
        assert first.get("process_running") is True, first
        assert _up(case.unit)
        assert case.seen["launches"] == 1
        flag["fail"] = False
        second = _dispatch(
            {"command": f"printf '{_MARKER}\\n'; exit 0", "service": "await", "timeout": 30},
            case.tool_call_id, case.task_id,
        )
        assert second.get("exit_code") == 0, second
        assert _MARKER in (second.get("output") or ""), second
        assert case.seen["launches"] == 1


def test_empty_tool_call_id_and_pty_start_nothing(request, monkeypatch):
    with _unit(request, monkeypatch) as case:
        empty = _dispatch(
            {"command": "printf hi", "service": "await", "timeout": 30},
            "", case.task_id,
        )
        assert empty.get("status") == "error" or empty.get("error"), empty
        assert "tool call id" in (empty.get("error") or ""), empty
        assert case.seen["launches"] == 0
        assert _show(case.unit).get("LoadState") in {None, "", "not-found"}
        pty = _dispatch(
            {"command": "printf hi", "service": "await", "pty": True, "timeout": 30},
            case.tool_call_id, case.task_id,
        )
        assert "pty" in (pty.get("error") or ""), pty
        assert case.seen["launches"] == 0


def test_worker_environment_is_the_spawn_map_and_not_on_the_unit(request, monkeypatch):
    from hermes_constants import get_hermes_home
    from tools.process_registry import ProcessRegistry, process_registry

    monkeypatch.setenv("HERMES_WAIT_TEST_PROFILE", "1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "0")
    expected = ProcessRegistry._spawn_env(None)
    python = shutil.which("python3")
    assert python
    command = f'{python} -c "import json,os; print(json.dumps(dict(os.environ)))"'
    with _unit(request, monkeypatch) as case:
        result = _dispatch(
            {"command": command, "service": "notify"},
            case.tool_call_id, case.task_id,
        )
        assert result.get("status") == "running", result
        session = _session(result["session_id"])
        assert session is not None
        # Do not refresh here: a finished notify is stopped before this show.
        text = ""
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                text = Path(session.output_log).read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = ""
            if text.strip().startswith("{") or "\n{" in text:
                break
            time.sleep(0.2)
        dumped = None
        for line in reversed(text.splitlines()):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                dumped = json.loads(line)
                break
        assert dumped is not None, text[-500:]
        dumped.pop("_", None)
        assert dumped == expected, (sorted(set(dumped) ^ set(expected)), dumped.get("HERMES_WAIT_TEST_PROFILE"))
        assert dumped.get("HERMES_WAIT_TEST_PROFILE") == "1"
        assert "TELEGRAM_BOT_TOKEN" not in dumped
        assert "INVOCATION_ID" not in dumped
        env_path = get_hermes_home() / "logs" / "process-env" / f"{session.id}.env"
        script_path = get_hermes_home() / "logs" / "process-env" / f"{session.id}.sh"
        env_text = env_path.read_text(encoding="utf-8")
        assert "HERMES_WAIT_TEST_PROFILE=" in env_text
        assert "TELEGRAM_BOT_TOKEN" not in env_text
        assert stat.S_IMODE(env_path.stat().st_mode) == 0o600
        assert stat.S_IMODE(script_path.stat().st_mode) == 0o600
        shown = _systemctl("show", case.unit, "--no-pager")
        assert "TELEGRAM_BOT_TOKEN" not in shown.stdout
        assert "HERMES_WAIT_TEST_PROFILE" not in shown.stdout
        assert case.seen["launches"] == 1
        assert process_registry.get(session.id) is session

    import tools.process_registry_service as service_mod

    monkeypatch.setattr(service_mod, "_env_round_trip", lambda *_args, **_kwargs: False)
    with _unit(request, monkeypatch) as case:
        refused = _dispatch(
            {"command": "printf hi", "service": "notify"},
            case.tool_call_id, case.task_id,
        )
        assert "could not be isolated" in (refused.get("error") or ""), refused
        assert case.seen["launches"] == 0
        assert _show(case.unit).get("LoadState") in {None, "", "not-found"}


def test_lifecycle_sweeps_skip_a_session_owned_service(request, monkeypatch):
    from agent.client_lifecycle import ClientLifecycleMixin
    from tools.process_registry import process_registry
    from tools.process_registry_service import service_survives_stop

    assert service_survives_stop(SimpleNamespace(service_unit=""), "gateway_shutdown") is False
    with _unit(request, monkeypatch) as case:
        started = _dispatch(
            {"command": "sleep 30", "service": "notify"},
            case.tool_call_id, case.task_id,
        )
        session = _session(started["session_id"])
        owner = session.owner_task_id
        assert process_registry.kill_all(task_id=owner, source="gateway_shutdown") == 0
        assert _up(case.unit)
        assert process_registry.kill_all(task_id=owner, source="gateway_turn_timeout") == 0
        assert _up(case.unit)
        closed = process_registry.kill_process(session.id, source="agent_close")
        assert closed.get("status") == "running", closed
        assert _up(case.unit)

        class _Holder(ClientLifecycleMixin):
            _process_owner_task_ids = (owner,)

        _Holder()._close_task_resources(owner)
        assert _up(case.unit)
        session.owner_task_id = "sa-child-1"
        stopped = process_registry.kill_process(session.id, source="agent_close")
        assert stopped.get("status") == "killed", stopped
        assert stopped.get("exit_code") == -15, stopped
        assert stopped.get("termination_source") == "unit_stopped", stopped


def test_notify_exit_is_admitted_once_and_hidden_when_the_owner_is_empty(request, monkeypatch):
    """The owner verdict below is stubbed. The receipt and the exit come from the real unit."""
    import asyncio

    from hermes_cli.cli_process_dock import process_status
    from tools.process_registry import process_registry
    from tools.process_registry_service import attention_for

    parent = f"parent-{_real_uuid4().hex[:8]}"
    monkeypatch.setenv("HERMES_SESSION_ID", parent)
    with _unit(request, monkeypatch) as case:
        started = _dispatch(
            {"command": f"printf '{_MARKER}\\n'; exit 0", "service": "notify"},
            case.tool_call_id, case.task_id,
        )
        session = _until_exited(started["session_id"])
        assert session is not None and session.exit_code == 0, session
        assert _MARKER in (session.output_buffer or "")
        assert session.admission_pending is True
        events = _take_events(session.id)
        assert len(events) == 1, events
        assert events[0].get("started_at") == session.started_at
        from tools.process_registry_service import refresh_service_session

        refresh_service_session(process_registry, session)
        assert _take_events(session.id) == []
        entry = _list_entry(session.id)
        assert entry is not None and entry.get("attention") == "ready", entry
        assert process_status(entry) == "ready"
        from tui_gateway.methods_subagents import _live_work_owners

        assert ("background", (parent, case.task_id)) in _live_work_owners()

        process_registry._running.pop(session.id, None)
        process_registry._finished.pop(session.id, None)
        monkeypatch.delenv("HERMES_SESSION_ID", raising=False)
        hidden = _list_entry(session.id)
        from hermes_constants import get_hermes_home
        from tools.process_registry_results import load_completed_results

        receipt = get_hermes_home() / "logs" / "process-results" / f"{session.id}.json"
        # The internal list still shows the pending row. Ordinary ownerless reads do not.
        assert hidden is not None and hidden.get("attention") == "ready", hidden
        assert hidden.get("admission_pending") is True
        assert hidden.get("exit_code") == 0
        assert load_completed_results() == {}
        assert all(row["session_id"] != session.id for row in process_registry.list_sessions())
        assert all(
            row["session_id"] != session.id
            for row in process_registry.list_sessions(include_retained=True)
        )
        assert receipt.exists()
        stored = json.loads(receipt.read_text(encoding="utf-8-sig"))
        assert stored.get("exit_code") == 0
        assert _MARKER in (stored.get("output") or "")

        process_registry._finished[session.id] = session
        from gateway.config import GatewayConfig
        from gateway.run import GatewayRunner

        runner = GatewayRunner(GatewayConfig())
        evt = {
            "type": "completion", "session_id": session.id, "parent_session_id": parent,
            "session_key": case.task_id, "started_at": session.started_at,
        }

        async def _deliver(_parent, _key):
            return ("deliver", "", session.id)

        monkeypatch.setattr(runner, "_classify_completion_owner", _deliver)
        claim = asyncio.run(runner._preflight_completion_delivery(evt))
        assert claim.proceed is True
        assert session.admission_pending is True
        assert session.exit_code == 0

        async def _terminal(_parent, _key):
            return ("terminal", "", "")

        monkeypatch.setattr(runner, "_classify_completion_owner", _terminal)
        claim = asyncio.run(runner._preflight_completion_delivery(evt))
        assert claim.proceed is False
        assert session.admission_pending is False
        assert session.exit_code == 0
        stored = json.loads(receipt.read_text(encoding="utf-8-sig"))
        assert stored.get("exit_code") == 0
        assert stored.get("admission_pending") is False
        assert attention_for(session) is None
        done = _list_entry(session.id)
        assert done is not None and process_status(done) == "done"


def test_two_registries_keep_a_pidless_service_and_drop_an_ordinary_one():
    """Two registry instances share one checkpoint file. This is not two OS profiles."""
    from tools.process_registry import ProcessRegistry, ProcessSession, _checkpoint_path

    path = _checkpoint_path()
    original = path.read_bytes() if path.exists() else None
    try:
        first = ProcessRegistry()
        service = ProcessSession(
            id="proc_svcwriter01", command="true",
            service_unit="hermes-bg-proc_svcwriter01.service", service_mode="await",
            tool_call_id="tw-service", pid=None,
        )
        ordinary = ProcessSession(id="proc_ordinary01", command="true", pid=None)
        first._running[service.id] = service
        first._running[ordinary.id] = ordinary
        assert first._write_checkpoint(strict=True) is True
        second = ProcessRegistry()
        other = ProcessSession(id="proc_writerb001", command="echo", pid=4242, host_start_time=1)
        second._running[other.id] = other
        assert second._write_checkpoint(strict=True) is True
        entries = json.loads(path.read_text(encoding="utf-8-sig"))
        ids = {item.get("session_id") for item in entries}
        assert "proc_svcwriter01" in ids
        assert "proc_writerb001" in ids
        assert "proc_ordinary01" not in ids
    finally:
        if original is None:
            path.unlink(missing_ok=True)
        else:
            path.write_bytes(original)


def test_pending_service_receipts_are_extra_beyond_the_settled_cap():
    from hermes_constants import get_hermes_home
    from tools.process_registry_results import RESULT_RETENTION_SECONDS, _result_paths

    directory = get_hermes_home() / "logs" / "process-results"
    directory.mkdir(parents=True, exist_ok=True)
    created = []
    old = time.time() - RESULT_RETENTION_SECONDS - 30
    try:
        for index in range(70):
            path = directory / f"proc_settled{index:04d}.json"
            path.write_text("{}", encoding="utf-8")
            os.utime(path, (old, old))
            created.append(path)
        pending = directory / "proc_pending0001.json"
        pending.write_text(json.dumps({
            "admission_pending": True,
            "service_unit": "hermes-bg-proc_pending0001.service",
        }), encoding="utf-8")
        os.utime(pending, (old, old))
        created.append(pending)
        returned = _result_paths()
        assert pending in returned
        assert pending.exists()
        settled = [path for path in returned if path != pending]
        assert len(settled) <= 64
        assert len(returned) == len(settled) + (1 if pending in returned else 0)
    finally:
        for path in created:
            path.unlink(missing_ok=True)


def test_replay_splices_the_real_outcome_and_a_new_id_still_runs(request, monkeypatch):
    from agent.replay_cleanup import canonicalize_replay_history

    with _unit(request, monkeypatch) as case:
        result = _dispatch(
            {"command": f"printf '{_MARKER}\\n'; exit 0", "service": "await", "timeout": 60},
            case.tool_call_id, case.task_id,
        )
        assert result.get("exit_code") == 0, result
        call = {
            "id": case.tool_call_id, "type": "function",
            "function": {"name": "terminal", "arguments": "{}"},
        }
        dangling = canonicalize_replay_history([
            {"role": "user", "content": "go"},
            {"role": "assistant", "tool_calls": [call]},
        ])
        spliced = dangling[-1]
        assert spliced.get("role") == "tool"
        assert "effect_disposition" not in spliced
        assert "UNKNOWN" not in spliced.get("content", "")
        body = json.loads(spliced["content"])
        assert body.get("exit_code") == 0
        assert _MARKER in (body.get("output") or "")
        interrupted = canonicalize_replay_history([
            {"role": "user", "content": "go"},
            {"role": "assistant", "tool_calls": [call]},
            {"role": "tool", "tool_call_id": case.tool_call_id,
             "content": '{"output":"partial\\n[Command interrupted]","exit_code":130}'},
        ])
        rewritten = interrupted[-1]
        assert "effect_disposition" not in rewritten
        assert "UNKNOWN" not in rewritten.get("content", "")
        assert "[Command interrupted]" not in rewritten.get("content", "")
        body = json.loads(rewritten["content"])
        assert body.get("exit_code") == 0
        assert _MARKER in (body.get("output") or "")

        second_hex = _real_uuid4().hex[:12]
        second_unit = _pin(monkeypatch, second_hex)
        _own(request, second_unit)
        try:
            again = _dispatch(
                {"command": "printf 'HERMES_WAIT_AGAIN\\n'; exit 0", "service": "await", "timeout": 60},
                f"call-{second_hex}", f"task-{second_hex}",
            )
            assert again.get("exit_code") == 0, again
            assert "HERMES_WAIT_AGAIN" in (again.get("output") or ""), again
            assert case.seen["launches"] == 2
        finally:
            _stop_owned(second_unit)
            _release(second_unit)


def _count_stops(monkeypatch, unit: str) -> list:
    import tools.process_registry_service as service_mod

    stops = []
    real_run = service_mod._run

    def wrapped(argv, **kwargs):
        if any(part == "stop" for part in argv) and unit in argv:
            stops.append(list(argv))
        return real_run(argv, **kwargs)

    monkeypatch.setattr(service_mod, "_run", wrapped)
    return stops


def test_recovered_running_await_arms_one_watcher_and_same_process_does_not(request, monkeypatch):
    """A newly attached running await arms the existing watcher once. A live row does not."""
    from tools.process_registry import ProcessRegistry, _checkpoint_path, process_registry
    from tools.process_registry_service import _UNRESOLVED_NOTE, recover_service_entry, service_outcome_content

    with _unit(request, monkeypatch) as case:
        first = _dispatch(
            {"command": "sleep 30", "service": "await", "timeout": 1},
            case.tool_call_id, case.task_id,
        )
        assert first.get("status") == "unresolved", first
        session = _session(first["session_id"])
        assert session is not None and session.service_invocation_id
        watchers_before = [
            item for item in process_registry.pending_watchers if item.get("session_id") == session.id
        ]
        entry = next(
            item for item in json.loads(_checkpoint_path().read_text(encoding="utf-8-sig"))
            if item.get("session_id") == session.id
        )
        assert recover_service_entry(process_registry, entry) is False
        assert [
            item for item in process_registry.pending_watchers if item.get("session_id") == session.id
        ] == watchers_before
        session.notify_on_complete = False
        session.watcher_interval = 0
        assert process_registry._write_checkpoint(strict=True) is True
        process_registry._running.pop(session.id, None)
        process_registry.pending_watchers = [
            item for item in process_registry.pending_watchers if item.get("session_id") != session.id
        ]
        fresh = ProcessRegistry()
        assert fresh.recover_from_checkpoint() >= 1
        row = fresh.get(session.id)
        assert row is not None and row.exited is False
        assert row.notify_on_complete is True
        assert row._reader_thread is None
        payloads = [item for item in fresh.pending_watchers if item.get("session_id") == row.id]
        assert len(payloads) == 1 and payloads[0]["notify_on_complete"] is True, payloads
        assert case.seen["launches"] == 1
        assert recover_service_entry(fresh, entry) is False
        assert len([item for item in fresh.pending_watchers if item.get("session_id") == row.id]) == 1
        process_registry._running[row.id] = row
        try:
            body = json.loads(service_outcome_content(case.tool_call_id))
        finally:
            process_registry._running.pop(row.id, None)
        assert body["status"] == "unresolved", body
        assert body["note"] == _UNRESOLVED_NOTE
        assert body["exit_code"] is None


def test_empty_invocation_recovery_does_not_arm_notify(request, monkeypatch):
    from tools.process_registry import ProcessRegistry, _checkpoint_path, process_registry

    with _unit(request, monkeypatch) as case:
        started = _dispatch(
            {"command": "sleep 30", "service": "await", "timeout": 1},
            case.tool_call_id, case.task_id,
        )
        session = _session(started["session_id"])
        session.service_invocation_id = ""
        session.notify_on_complete = False
        session.watcher_interval = 0
        assert process_registry._write_checkpoint(strict=True) is True
        process_registry._running.pop(session.id, None)
        fresh = ProcessRegistry()
        import tools.process_registry_service as service_mod
        monkeypatch.setattr(service_mod, "systemctl_show", lambda _unit: {
            "LoadState": "loaded", "InvocationID": "live-but-not-stored", "SubState": "running",
            "Result": "success", "ExecMainCode": "0", "ExecMainStatus": "0",
        })
        assert fresh.recover_from_checkpoint() >= 1
        row = fresh.get(session.id)
        assert row is not None
        assert row.notify_on_complete is False
        assert not any(item.get("notify_on_complete") for item in fresh.pending_watchers if item.get("session_id") == row.id)
        entries = json.loads(_checkpoint_path().read_text(encoding="utf-8-sig"))
        stored = next(item for item in entries if item.get("session_id") == row.id)
        assert not stored.get("notify_on_complete")
        assert case.seen["launches"] == 1


def test_already_exited_recovery_splices_once_and_admits_nothing(request, monkeypatch):
    from tools.process_registry import ProcessRegistry, _checkpoint_path, process_registry
    from tools.process_registry_service import pending_service_events, service_outcome_content
    import tools.process_registry_service as service_mod

    with _unit(request, monkeypatch) as case:
        monkeypatch.setattr(service_mod, "_cleanup_unit_if_match", lambda _session: None)
        result = _dispatch(
            {"command": f"printf '{_MARKER}\\n'; exit 0", "service": "await", "timeout": 30},
            case.tool_call_id, case.task_id,
        )
        assert result.get("exit_code") == 0, result
        session = _session(result["session_id"])
        assert session is not None and session.notify_on_complete is False
        assert session.admission_pending is False
        fields = {
            "session_id": session.id, "command": session.command, "service_unit": session.service_unit,
            "service_invocation_id": session.service_invocation_id, "service_boot_id": session.service_boot_id,
            "service_mode": session.service_mode, "tool_call_id": session.tool_call_id,
            "notify_on_complete": False, "watcher_interval": 0, "service_stop_intent": False,
            "started_at": session.started_at, "task_id": session.task_id, "owner_task_id": session.owner_task_id,
            "session_key": session.session_key, "pid": None, "output_log": session.output_log,
        }
        process_registry._running.pop(session.id, None)
        process_registry._finished.pop(session.id, None)
        path = _checkpoint_path()
        original = path.read_bytes() if path.exists() else None
        try:
            path.write_text(json.dumps([fields]), encoding="utf-8")
            fresh = ProcessRegistry()
            assert fresh.recover_from_checkpoint() >= 1
            row = fresh.get(session.id)
            assert row is not None and row.exited is True and row.exit_code == 0, row.exit_code
            assert row.admission_pending is False and row.notify_on_complete is False
            assert [item for item in pending_service_events() if item.get("session_id") == row.id] == []
            import tools.process_registry as registry_mod
            previous = registry_mod.process_registry
            registry_mod.process_registry = fresh
            try:
                body = json.loads(service_outcome_content(case.tool_call_id))
            finally:
                registry_mod.process_registry = previous
            assert body["status"] == "exited", body
            assert body["exit_code"] == 0
            assert _MARKER in (body.get("output") or "")
            assert case.seen["launches"] == 1
        finally:
            if original is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(original)


def test_failed_stop_checkpoint_does_not_signal_or_persist_killed(request, monkeypatch):
    """Finish must not persist killed from the transient bit when the checkpoint fails."""
    import threading

    from tools.process_registry import process_registry
    from tools.process_registry_service import _finish_exit

    with _unit(request, monkeypatch) as case:
        started = _dispatch(
            {"command": "sleep 30", "service": "notify"},
            case.tool_call_id, case.task_id,
        )
        session = _session(started["session_id"])
        stops = _count_stops(monkeypatch, case.unit)
        stop_entered = threading.Event()
        finish_waiting = threading.Event()
        real_checkpoint = process_registry._write_checkpoint

        def wrapped_checkpoint(*args, **kwargs):
            if kwargs.get("strict") and session.service_stop_intent:
                stop_entered.set()
                finish_waiting.wait(5)
                return False
            return real_checkpoint(*args, **kwargs)

        monkeypatch.setattr(process_registry, "_write_checkpoint", wrapped_checkpoint)
        real_wait = threading.Condition.wait

        def wrapped_wait(self, timeout=None):
            if getattr(self, "_lock", None) is session._lock:
                finish_waiting.set()
            return real_wait(self, timeout)

        monkeypatch.setattr(threading.Condition, "wait", wrapped_wait)
        errors = []

        def stop():
            try:
                errors.append(("stop", process_registry.kill_process(session.id)))
            except Exception as exc:
                errors.append(("stop-exc", exc))

        def finish():
            try:
                assert stop_entered.wait(5)
                errors.append(("finish", _finish_exit(
                    process_registry, session, 0, "exited", "", publish=False,
                )))
            except Exception as exc:
                errors.append(("finish-exc", exc))

        stopper = threading.Thread(target=stop)
        finisher = threading.Thread(target=finish)
        stopper.start()
        finisher.start()
        stopper.join(15)
        finisher.join(15)
        assert not stopper.is_alive() and not finisher.is_alive()
        assert not any(isinstance(item[1], Exception) for item in errors), errors
        assert stops == [], stops
        assert session.service_stop_intent is False
        assert session.completion_reason != "killed"
        assert session.exit_code == 0, (session.exit_code, session.completion_reason, errors)
        from hermes_constants import get_hermes_home
        receipt = json.loads(
            (get_hermes_home() / "logs" / "process-results" / f"{session.id}.json").read_text(encoding="utf-8-sig"),
        )
        assert receipt["exit_code"] == 0
        assert receipt["completion_reason"] != "killed"
        assert _up(case.unit)
        assert case.seen["launches"] == 1


def test_completion_before_stop_is_not_signalled(request, monkeypatch):
    from tools.process_registry import process_registry
    from tools.process_registry_service import _finish_exit
    import tools.process_registry_service as service_mod

    with _unit(request, monkeypatch) as case:
        started = _dispatch(
            {"command": "sleep 30", "service": "notify"},
            case.tool_call_id, case.task_id,
        )
        session = _session(started["session_id"])
        stops = _count_stops(monkeypatch, case.unit)
        real_show = service_mod.systemctl_show

        def show(unit):
            if unit == case.unit and not session.exited:
                _finish_exit(process_registry, session, 0, "exited", "", publish=True)
            return real_show(unit)

        monkeypatch.setattr(service_mod, "systemctl_show", show)
        result = process_registry.kill_process(session.id)
        assert stops == [], stops
        assert result.get("status") != "killed", result
        assert session.exit_code == 0, session.exit_code
        assert session.completion_reason != "killed"
        from hermes_constants import get_hermes_home
        receipt = json.loads(
            (get_hermes_home() / "logs" / "process-results" / f"{session.id}.json").read_text(encoding="utf-8-sig"),
        )
        assert receipt["exit_code"] == 0
        assert receipt["completion_reason"] != "killed"
        assert _up(case.unit)


def test_durable_stop_wins_over_a_racing_success(request, monkeypatch):
    import threading

    from tools.process_registry import process_registry
    from tools.process_registry_service import _finish_exit, pending_service_events
    import tools.process_registry_service as service_mod

    with _unit(request, monkeypatch) as case:
        started = _dispatch(
            {"command": "sleep 30", "service": "notify"},
            case.tool_call_id, case.task_id,
        )
        session = _session(started["session_id"])
        durable = threading.Event()
        finish_done = threading.Event()
        real_run = service_mod._run

        def wrapped(argv, **kwargs):
            if any(part == "stop" for part in argv) and case.unit in argv:
                durable.set()
                assert finish_done.wait(5)
            return real_run(argv, **kwargs)

        monkeypatch.setattr(service_mod, "_run", wrapped)
        errors = []

        def stop():
            try:
                errors.append(("stop", process_registry.kill_process(session.id)))
            except Exception as exc:
                errors.append(("stop-exc", exc))

        def finish():
            try:
                assert durable.wait(5)
                errors.append(("finish", _finish_exit(
                    process_registry, session, 0, "exited", "", publish=False,
                )))
            finally:
                finish_done.set()

        stopper = threading.Thread(target=stop)
        finisher = threading.Thread(target=finish)
        stopper.start()
        finisher.start()
        stopper.join(15)
        finisher.join(15)
        assert not stopper.is_alive() and not finisher.is_alive()
        assert not any(isinstance(item[1], Exception) for item in errors), errors
        assert session.exit_code == -15, (session.exit_code, session.completion_reason, errors)
        assert session.completion_reason == "killed"
        from hermes_constants import get_hermes_home
        receipt = json.loads(
            (get_hermes_home() / "logs" / "process-results" / f"{session.id}.json").read_text(encoding="utf-8-sig"),
        )
        assert receipt["exit_code"] == -15
        assert receipt["completion_reason"] == "killed"
        assert not any(
            item.get("session_id") == session.id and item.get("exit_code") == 0
            for item in pending_service_events()
        )


def _write_service_checkpoint(session_id: str, **extra):
    from tools.process_registry import _checkpoint_path
    from tools.process_registry_service import read_boot_id

    entry = {
        "session_id": session_id, "command": "sleep 30", "pid": None,
        "service_unit": f"hermes-bg-{session_id}.service",
        "service_invocation_id": "inv-stale", "service_boot_id": read_boot_id(),
        "service_mode": "notify", "tool_call_id": f"call-{session_id}",
        "service_stop_intent": False, "notify_on_complete": True, "started_at": 1700000000,
        "task_id": "task-stale", "owner_task_id": "task-stale",
        "session_key": "agent:main:local:dm:stale", "watcher_interval": 0,
    }
    entry.update(extra)
    path = _checkpoint_path()
    original = path.read_bytes() if path.exists() else None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([entry]), encoding="utf-8")
    return path, original


def _write_exit_receipt(session_id: str, **extra) -> Path:
    from hermes_constants import get_hermes_home

    directory = get_hermes_home() / "logs" / "process-results"
    directory.mkdir(parents=True, exist_ok=True)
    record = {
        "id": session_id, "command": "sleep 30", "cwd": "/", "task_id": "task-stale",
        "owner_task_id": "task-stale", "session_key": "agent:main:local:dm:stale",
        "parent_session_id": "parent-stale", "started_at": 1700000000, "exit_code": 0,
        "completion_reason": "exited", "termination_source": "", "notify_on_complete": True,
        "service_unit": f"hermes-bg-{session_id}.service", "service_invocation_id": "inv-stale",
        "service_boot_id": "", "service_mode": "notify", "tool_call_id": f"call-{session_id}",
        "service_stop_intent": False, "admission_pending": True, "output": "stale-success",
    }
    record.update(extra)
    path = directory / f"{session_id}.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    return path


def test_stale_success_with_durable_stop_is_not_admitted_when_show_fails(monkeypatch):
    """Cold process: exit 0 receipt plus a not-exited stop row, and show is unavailable."""
    from tools.process_registry import ProcessRegistry
    from tools.process_registry_service import pending_service_events, refresh_service_session
    import tools.process_registry_service as service_mod

    session_id = "proc_stalesuccess1"
    path, original = _write_service_checkpoint(session_id, service_stop_intent=True)
    receipt = _write_exit_receipt(session_id)
    monkeypatch.setattr(service_mod, "systemctl_show", lambda _unit: None)
    try:
        fresh = ProcessRegistry()
        assert fresh.recover_from_checkpoint() >= 1
        assert [item for item in pending_service_events() if item.get("session_id") == session_id] == []
        row = fresh.get(session_id)
        assert row is not None and row.exited is False
        assert row.exit_code != 0
        stored = json.loads(receipt.read_text(encoding="utf-8-sig"))
        assert stored["exit_code"] == 0 and stored["admission_pending"] is True

        def matched(unit):
            return {
                "LoadState": "loaded", "InvocationID": "inv-stale", "SubState": "exited",
                "Result": "success", "ExecMainCode": "1", "ExecMainStatus": "0",
                "Id": unit, "ActiveState": "inactive", "NRestarts": "0",
            }

        monkeypatch.setattr(service_mod, "systemctl_show", matched)
        # The unit name is synthetic. Cleanup must not reach a real systemctl stop.
        monkeypatch.setattr(
            service_mod, "_run",
            lambda argv, **_kwargs: subprocess.CompletedProcess(argv, 0, "", ""),
        )
        refresh_service_session(fresh, row)
        assert row.exit_code == -15, (row.exit_code, row.completion_reason)
        assert row.completion_reason == "killed"
        assert row.termination_source == "unit_stopped"
        rewritten = json.loads(receipt.read_text(encoding="utf-8-sig"))
        assert rewritten["exit_code"] == -15
        assert rewritten["completion_reason"] == "killed"
    finally:
        receipt.unlink(missing_ok=True)
        if original is None:
            path.unlink(missing_ok=True)
        else:
            path.write_bytes(original)


def test_committed_success_without_a_checkpoint_row_is_still_admitted(monkeypatch):
    """A gone checkpoint row is the commit. The barrier must not drop that result."""
    from tools.process_registry_service import pending_service_events

    session_id = "proc_committed001"
    path, original = _write_service_checkpoint("proc_otherstale1", service_stop_intent=True)
    receipt = _write_exit_receipt(session_id)
    try:
        events = [item for item in pending_service_events() if item.get("session_id") == session_id]
        assert len(events) == 1, events
        assert events[0]["exit_code"] == 0
    finally:
        receipt.unlink(missing_ok=True)
        if original is None:
            path.unlink(missing_ok=True)
        else:
            path.write_bytes(original)


def test_lagging_checkpoint_without_stop_intent_does_not_drop_the_receipt(monkeypatch):
    """Best-effort checkpoint cleanup can lag a committed exit. That alone is not a contradiction."""
    from tools.process_registry import ProcessRegistry
    from tools.process_registry_service import pending_service_events
    import tools.process_registry_service as service_mod

    session_id = "proc_lagging0001"
    path, original = _write_service_checkpoint(session_id, service_stop_intent=False)
    receipt = _write_exit_receipt(session_id)
    monkeypatch.setattr(service_mod, "systemctl_show", lambda _unit: None)
    try:
        fresh = ProcessRegistry()
        assert fresh.recover_from_checkpoint() >= 1
        events = [item for item in pending_service_events() if item.get("session_id") == session_id]
        assert len(events) == 1 and events[0]["exit_code"] == 0, events
        row = fresh.get(session_id)
        assert row is not None and row.exited is False
    finally:
        receipt.unlink(missing_ok=True)
        if original is None:
            path.unlink(missing_ok=True)
        else:
            path.write_bytes(original)


def test_stale_exit0_writer_cannot_regress_a_committed_stop(monkeypatch):
    """One writer thread and one Stop thread share one session lock.

    The spy may set an event. It must not call Stop. A non-blocking acquire
    tells which arm this build is in. The wait, when there is one, stays
    outside the lock. A timeout means the fixture is wedged.

    section_owned: the exit-0 write already holds the session condition, so
    completion marks exit 0 and releases before Stop's first wait. Stop does
    not signal. outside: today's write is outside the condition. Stop may
    return killed, and the joined receipt must still be killed after the
    stale exit-0 write. Either arm, memory and the receipt match.
    """
    import tools.process_registry_results as results
    import tools.process_registry_service as service_mod
    from tools.process_registry import ProcessRegistry, ProcessSession
    from tools.process_registry_service import _finish_exit, pending_service_events, read_boot_id

    session_id = "proc_staleexit0w"
    unit = f"hermes-bg-{session_id}.service"
    invocation = "inv-owned-stale"
    registry = ProcessRegistry()
    session = ProcessSession(
        id=session_id, command="printf marker", task_id="task-stale-exit",
        owner_task_id="task-stale-exit", session_key="agent:main:local:dm:stale-exit",
        started_at=1700000000.0, service_unit=unit, service_invocation_id=invocation,
        service_boot_id=read_boot_id(), service_mode="await", tool_call_id="call-stale-exit",
        notify_on_complete=True, output_buffer="marker\n",
    )
    registry._running[session.id] = session
    show = {
        "LoadState": "loaded", "Id": unit, "InvocationID": invocation, "SubState": "exited",
        "Result": "success", "ExecMainCode": "1", "ExecMainStatus": "0",
        "ActiveState": "inactive", "NRestarts": "0",
    }
    monkeypatch.setattr(service_mod, "systemctl_show", lambda queried: show if queried == unit else None)
    stops = []

    def _no_systemctl(argv, **_kwargs):
        assert unit in argv, argv
        if any(part == "stop" for part in argv):
            stops.append(list(argv))
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(service_mod, "_run", _no_systemctl)
    real_write = results.write_frozen_result
    entered = threading.Event()
    release = threading.Event()
    arm = {"decided": False, "section_owned": False, "outside": False}

    def paused(session_id_arg, record, *, strict=False):
        if (
            not arm["decided"]
            and record.get("exit_code") == 0
            and record.get("completion_reason") != "killed"
        ):
            arm["decided"] = True
            # Same thread already inside the condition: Lock.acquire is false.
            if not session._lock.acquire(blocking=False):
                arm["section_owned"] = True
                entered.set()
                return real_write(session_id_arg, record, strict=strict)
            session._lock.release()
            arm["outside"] = True
            entered.set()
            if not release.wait(8):
                raise TimeoutError("stale exit-0 writer was not released")
        return real_write(session_id_arg, record, strict=strict)

    monkeypatch.setattr(results, "write_frozen_result", paused)
    errors = []
    observed_stop = {}
    stop_done = threading.Event()

    def finish():
        try:
            errors.append(("finish", _finish_exit(registry, session, 0, "exited", "", publish=True)))
        except Exception as exc:
            errors.append(("finish-exc", exc))

    def stop():
        try:
            observed_stop["result"] = registry.kill_process(session.id)
        except Exception as exc:
            errors.append(("stop-exc", exc))
        finally:
            stop_done.set()

    worker = threading.Thread(target=finish, name="stale-exit0-writer")
    stopper = threading.Thread(target=stop, name="stale-exit0-stop")
    worker.start()
    try:
        assert entered.wait(5), errors
        stopper.start()
        assert stop_done.wait(8), (errors, arm)
    finally:
        release.set()
        stopper.join(8)
        worker.join(8)
    assert not worker.is_alive() and not stopper.is_alive()
    assert not any(isinstance(item[1], Exception) for item in errors), errors
    stopped = observed_stop.get("result") or {}
    from hermes_constants import get_hermes_home
    receipt_path = get_hermes_home() / "logs" / "process-results" / f"{session.id}.json"
    stored = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
    events = [item for item in pending_service_events() if item.get("session_id") == session.id]
    observed = {
        "arm": dict(arm),
        "stop": stopped.get("status"),
        "memory_exit": session.exit_code,
        "memory_reason": session.completion_reason,
        "receipt_exit": stored.get("exit_code"),
        "receipt_reason": stored.get("completion_reason"),
        "stops": stops,
        "events": [
            {"exit_code": item.get("exit_code"), "completion_reason": item.get("completion_reason")}
            for item in events
        ],
    }
    assert session.exit_code == stored["exit_code"], observed
    assert session.completion_reason == stored["completion_reason"], observed
    try:
        if arm["section_owned"]:
            assert stops == [], observed
            assert stopped.get("status") == "already_exited", observed
            assert stored["exit_code"] == 0, observed
            assert stored["completion_reason"] == "exited", observed
            assert events, observed
            assert all(
                item.get("exit_code") == 0 and item.get("completion_reason") == "exited"
                for item in events
            ), observed
        else:
            assert arm["outside"], observed
            assert stored["exit_code"] == -15, observed
            assert stored["completion_reason"] == "killed", observed
            assert events, observed
            assert all(
                item.get("exit_code") == -15 and item.get("completion_reason") == "killed"
                for item in events
            ), observed
    finally:
        receipt_path.unlink(missing_ok=True)


def test_two_registries_adopt_the_shared_stop_outcome(monkeypatch):
    """One interpreter, two ProcessRegistry objects, one profile's files.

    Not two OS processes and not an exactly-once crash claim. B is paused
    after classify returns matching exit 0 and before its commit. A's real
    kill writes killed/-15 and removes the row. B's stale checkpoint cannot
    clear that stop bit, and after the commit it cannot put the running row
    back. B then adopts killed. Show and signal are stubs for this fake name.
    """
    import tools.process_registry_service as service_mod
    from hermes_constants import get_hermes_home
    from tools.process_registry import ProcessRegistry, ProcessSession, _checkpoint_path
    from tools.process_registry_service import (
        _checkpoint_rows, pending_service_events, read_boot_id, refresh_service_session,
    )

    session_id = "proc_shareauth01"
    unit = f"hermes-bg-{session_id}.service"
    invocation = "inv-share-auth"
    boot = read_boot_id()
    path = _checkpoint_path()
    original = path.read_bytes() if path.exists() else None
    phase = {"exit0": False}
    classified = threading.Event()
    release_b = threading.Event()
    durable = threading.Event()
    allow_stop = threading.Event()
    paused = {"finish": False, "stop": False}
    errors = []

    def show(queried):
        if queried != unit:
            return None
        sub = "exited" if phase["exit0"] else "running"
        active = "inactive" if phase["exit0"] else "active"
        code = "1" if phase["exit0"] else "0"
        return {
            "LoadState": "loaded", "Id": unit, "InvocationID": invocation, "SubState": sub,
            "Result": "success", "ExecMainCode": code, "ExecMainStatus": "0",
            "ActiveState": active, "NRestarts": "0",
        }

    def run(argv, **_kwargs):
        if unit in argv and any(part == "stop" for part in argv) and not paused["stop"]:
            paused["stop"] = True
            durable.set()
            assert allow_stop.wait(8), "stop was not released"
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(service_mod, "systemctl_show", show)
    monkeypatch.setattr(service_mod, "_run", run)
    real_finish = service_mod._finish_exit

    def wrapped_finish(registry, session, code, reason, source, *, publish=True):
        if (
            registry is registry_b
            and code == 0
            and reason == "exited"
            and not paused["finish"]
        ):
            paused["finish"] = True
            classified.set()
            assert release_b.wait(8), "registry B was not released"
        return real_finish(registry, session, code, reason, source, publish=publish)

    monkeypatch.setattr(service_mod, "_finish_exit", wrapped_finish)
    setup = ProcessRegistry()
    session = ProcessSession(
        id=session_id, command="printf marker", task_id="task-share",
        owner_task_id="task-share", session_key="agent:main:local:dm:share",
        started_at=1700000000.0, service_unit=unit, service_invocation_id=invocation,
        service_boot_id=boot, service_mode="notify", tool_call_id="call-share-auth",
        notify_on_complete=True, output_buffer="marker\n", parent_session_id="parent-share",
    )
    setup._running[session.id] = session
    assert setup._write_checkpoint(strict=True) is True
    registry_a = ProcessRegistry()
    registry_b = ProcessRegistry()
    receipt_path = get_hermes_home() / "logs" / "process-results" / f"{session_id}.json"

    def run_b():
        try:
            refresh_service_session(registry_b, registry_b.get(session_id))
        except Exception as exc:
            errors.append(("b-exc", exc))

    def run_a():
        try:
            errors.append(("a", registry_a.kill_process(session_id)))
        except Exception as exc:
            errors.append(("a-exc", exc))

    worker_b = threading.Thread(target=run_b, name="registry-b-refresh")
    worker_a = threading.Thread(target=run_a, name="registry-a-stop")
    try:
        assert registry_a.recover_from_checkpoint() >= 1
        assert registry_b.recover_from_checkpoint() >= 1
        assert registry_a.get(session_id).service_stop_intent is False
        assert registry_b.get(session_id).exited is False
        phase["exit0"] = True
        worker_b.start()
        assert classified.wait(8), errors
        worker_a.start()
        assert durable.wait(8), errors
        assert _checkpoint_rows()[session_id]["service_stop_intent"] is True
        assert registry_b._write_checkpoint(strict=True) is True
        assert _checkpoint_rows()[session_id]["service_stop_intent"] is True
        allow_stop.set()
        worker_a.join(15)
        stored = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
        assert stored["exit_code"] == -15, stored
        assert stored["completion_reason"] == "killed", stored
        assert session_id not in _checkpoint_rows(), _checkpoint_rows()
        assert registry_b._write_checkpoint(strict=True) is True
        assert session_id not in _checkpoint_rows(), _checkpoint_rows()
        kept = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
        assert kept["exit_code"] == -15 and kept["completion_reason"] == "killed", kept
        release_b.set()
        worker_b.join(8)
        assert not worker_a.is_alive() and not worker_b.is_alive()
        assert not any(isinstance(item[1], Exception) for item in errors), errors
        adopted = registry_b.get(session_id)
        final = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
        events = [item for item in pending_service_events() if item.get("session_id") == session_id]
        observed = {
            "memory_exit": adopted.exit_code,
            "memory_reason": adopted.completion_reason,
            "receipt_exit": final.get("exit_code"),
            "receipt_reason": final.get("completion_reason"),
            "events": [
                {"exit_code": item.get("exit_code"), "completion_reason": item.get("completion_reason")}
                for item in events
            ],
        }
        assert adopted.exit_code == -15, observed
        assert adopted.completion_reason == "killed", observed
        assert final["exit_code"] == -15 and final["completion_reason"] == "killed", observed
        assert all(item.get("exit_code") != 0 for item in events), observed
        assert session_id not in _checkpoint_rows()
    finally:
        allow_stop.set()
        release_b.set()
        if worker_a.is_alive() or worker_a.ident is not None:
            worker_a.join(8)
        if worker_b.is_alive() or worker_b.ident is not None:
            worker_b.join(8)
        receipt_path.unlink(missing_ok=True)
        if original is None:
            path.unlink(missing_ok=True)
        else:
            path.write_bytes(original)
