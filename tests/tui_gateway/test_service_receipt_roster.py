"""Cold roster visibility for one pending service receipt and no model owner."""

import json
import os
import threading
from pathlib import Path

import pytest


def _write_receipt(home: Path, session_id: str, **fields) -> Path:
    directory = home / "logs" / "process-results"
    directory.mkdir(parents=True, exist_ok=True)
    record = {
        "id": session_id,
        "command": "true",
        "cwd": str(home),
        "task_id": "task-cold",
        "owner_task_id": "",
        "session_key": "",
        "parent_session_id": "",
        "started_at": 1700000000,
        "exit_code": 0,
        "completion_reason": "exited",
        "termination_source": "",
        "notify_on_complete": True,
        "service_unit": f"hermes-bg-{session_id}.service",
        "service_invocation_id": "inv-cold",
        "service_boot_id": "boot-cold",
        "service_mode": "notify",
        "tool_call_id": f"call-{session_id}",
        "service_stop_intent": False,
        "admission_pending": True,
        "output": "cold",
    }
    record.update(fields)
    path = directory / f"{session_id}.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    os.chmod(path, 0o600)
    return path


@pytest.fixture()
def cold_roster(tmp_path, monkeypatch):
    from agent import secret_scope
    from hermes_constants import (
        get_routing_process_hermes_home,
        pin_process_hermes_home,
        process_hermes_home_is_pinned,
    )
    from persistence_assembly import open_persistence, profile_scope
    from tests.fixtures.storage_seed import seed_session
    from tools import delegate_tool_registry as reg
    from tui_gateway import launch_profile_policy, server

    launch = tmp_path / "launch-home"
    bot2 = launch / "profiles" / "bot2"
    bot2.mkdir(parents=True)
    monkeypatch.delenv("HERMES_SESSION_ID", raising=False)
    monkeypatch.delenv("HERMES_SESSION_KEY", raising=False)
    monkeypatch.delenv("HERMES_SESSION_TOKEN", raising=False)
    monkeypatch.setenv("HERMES_HOME", str(launch))
    monkeypatch.setattr(secret_scope, "_MULTIPLEX_ACTIVE", False)
    monkeypatch.setattr(secret_scope, "_AUTO_PINNED_HOME", None)
    monkeypatch.setattr(launch_profile_policy, "_snapshot", None)
    monkeypatch.setattr(server, "_hermes_home", launch)
    monkeypatch.setattr(server, "_served_profile_homes", set())
    monkeypatch.setattr(reg, "_active_subagents", {})
    monkeypatch.setattr(reg, "_active_subagents_lock", threading.RLock())

    launch_route = "agent:main:local:dm:cold-launch"
    bot2_route = "agent:bot2:telegram:dm:cold"
    launch_parent = "sa-launch-parent"
    bot2_parent = "sa-bot2-parent"
    failed_parent = "sa-failed-parent"

    launch_db = open_persistence(profile_scope(home=launch))
    seed_session(launch_db, launch_parent, "local", session_key=launch_route)
    seed_session(launch_db, failed_parent, "local", session_key="agent:main:local:dm:cold-failed")
    bot2_db = open_persistence(profile_scope(home=bot2))
    seed_session(bot2_db, bot2_parent, "telegram", session_key=bot2_route)
    # Same stored id in the other profile, so a cross-home read would be visible.
    seed_session(bot2_db, launch_parent, "telegram", session_key="agent:bot2:telegram:dm:same-id")
    bot2_db.close()
    monkeypatch.setattr(server, "_get_db", lambda: launch_db)

    launch_sid = "proc_coldlaunch01"
    bot2_sid = "proc_coldbot2001"
    _write_receipt(launch, launch_sid, parent_session_id=launch_parent, session_key=launch_route)
    _write_receipt(
        bot2, bot2_sid, parent_session_id=bot2_parent, session_key=bot2_route, service_mode="await",
    )
    _write_receipt(launch, "proc_coldmissing1", parent_session_id="", session_key=launch_route)
    _write_receipt(
        launch, "proc_coldcorrupt1", parent_session_id={"bad": True}, session_key=launch_route,
    )
    _write_receipt(
        launch, "proc_coldstranger", parent_session_id="sa-stranger",
        session_key="agent:main:local:dm:stranger",
    )
    _write_receipt(
        launch, "proc_coldfailed01", parent_session_id=failed_parent, exit_code=1,
        session_key="agent:main:local:dm:cold-failed",
    )
    broken = launch / "logs" / "process-results" / "proc_coldbroken1.json"
    broken.write_text("{", encoding="utf-8")

    was_pinned = process_hermes_home_is_pinned()
    pinned_home = get_routing_process_hermes_home() if was_pinned else None

    def roster(profile=None):
        params = {"profile": profile} if profile else {}
        resp = server.handle_request(
            {"jsonrpc": "2.0", "id": 1, "method": "subagent.roster", "params": params},
        )
        assert "result" in resp, resp
        return {row["session_id"]: row for row in resp["result"]["sessions"]}

    try:
        yield {
            "launch": launch,
            "bot2": bot2,
            "launch_db": launch_db,
            "launch_parent": launch_parent,
            "bot2_parent": bot2_parent,
            "failed_parent": failed_parent,
            "launch_route": launch_route,
            "bot2_route": bot2_route,
            "launch_sid": launch_sid,
            "bot2_sid": bot2_sid,
            "roster": roster,
        }
    finally:
        if was_pinned:
            pin_process_hermes_home(pinned_home)
        else:
            pin_process_hermes_home(None)
        launch_db.close()


def test_disk_only_pending_receipt_stays_in_the_roster_without_an_owner(cold_roster):
    """A retained ready receipt still counts after restart when no model owner is set.

    The ordinary loader stays empty. A foreign profile stays out of the response.
    A missing or non-string parent is not replaced with the route. Settlement clears
    the same background count and does not schedule another model turn.
    """
    from tools.process_registry import process_registry
    from tools.process_registry_results import load_completed_results
    from tui_gateway.methods_subagents import _live_work_owners

    case = cold_roster
    launch_parent = case["launch_parent"]
    bot2_parent = case["bot2_parent"]
    launch_sid = case["launch_sid"]
    bot2_sid = case["bot2_sid"]
    roster = case["roster"]
    ready = {"session_id": launch_parent, "subagents": 0, "background": 1}

    assert os.environ.get("HERMES_SESSION_ID", "") == ""
    assert process_registry.get(launch_sid) is None
    assert process_registry.get(bot2_sid) is None
    assert launch_sid not in process_registry._running
    assert launch_sid not in process_registry._finished
    assert load_completed_results() == {}
    listed_ids = {
        row.get("session_id")
        for row in process_registry.list_sessions(include_service_receipts=True)
    }
    assert launch_sid not in listed_ids
    assert bot2_sid not in listed_ids

    queue_before = process_registry.completion_queue.qsize()
    admissions_before = case["launch_db"].admissions.list(
        session_id=launch_parent, pending_only=False,
    )

    assert ("background", (launch_parent, case["launch_route"])) in _live_work_owners()
    first = roster()
    assert first == {launch_parent: ready}
    assert roster() == first
    assert ("background", (bot2_parent, case["bot2_route"])) in _live_work_owners(case["bot2"])
    foreign = roster("bot2")
    assert foreign == {
        bot2_parent: {"session_id": bot2_parent, "subagents": 0, "background": 1},
    }
    assert launch_parent not in foreign
    assert case["failed_parent"] not in first

    assert process_registry.completion_queue.qsize() == queue_before
    assert case["launch_db"].admissions.list(
        session_id=launch_parent, pending_only=False,
    ) == admissions_before
    assert process_registry.get(launch_sid) is None
    assert load_completed_results() == {}
    assert os.environ.get("HERMES_SESSION_ID", "") == ""

    from tools.process_registry_service import clear_service_admission

    assert clear_service_admission(launch_sid) is True
    stored = json.loads(
        (case["launch"] / "logs" / "process-results" / f"{launch_sid}.json").read_text(encoding="utf-8"),
    )
    assert stored["admission_pending"] is False
    assert stored["exit_code"] == 0
    assert launch_parent not in roster()
    assert ("background", (launch_parent, case["launch_route"])) not in _live_work_owners(case["launch"])
    assert roster("bot2") == foreign
