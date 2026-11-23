"""Cold projection of pending service receipts with no model owner.

The sidebar count, the internal service-receipt list, and the bound session's
process list all see the same unconsumed outcome. A failed or lost receipt stays
visible until settlement. Ordinary ownerless reads stay empty.
"""

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
    lost_parent = "sa-lost-parent"
    failed_route = "agent:main:local:dm:cold-failed"
    lost_route = "agent:main:local:dm:cold-lost"

    launch_db = open_persistence(profile_scope(home=launch))
    seed_session(launch_db, launch_parent, "local", session_key=launch_route)
    seed_session(launch_db, failed_parent, "local", session_key=failed_route)
    seed_session(launch_db, lost_parent, "local", session_key=lost_route)
    bot2_db = open_persistence(profile_scope(home=bot2))
    seed_session(bot2_db, bot2_parent, "telegram", session_key=bot2_route)
    # Same stored id in the other profile, so a cross-home read would be visible.
    seed_session(bot2_db, launch_parent, "telegram", session_key=launch_route)
    bot2_db.close()
    monkeypatch.setattr(server, "_get_db", lambda: launch_db)

    launch_sid = "proc_coldlaunch01"
    bot2_sid = "proc_coldbot2001"
    failed_sid = "proc_coldfailed01"
    lost_sid = "proc_coldlost0001"
    missing_sid = "proc_coldmissing1"
    corrupt_sid = "proc_coldcorrupt1"
    stranger_sid = "proc_coldstranger"
    collide_sid = "proc_coldcollide1"
    _write_receipt(
        launch, launch_sid, parent_session_id=launch_parent, session_key=launch_route,
        command="ready-cold-cmd", output="ready-cold-out",
    )
    _write_receipt(
        bot2, bot2_sid, parent_session_id=bot2_parent, session_key=bot2_route,
        service_mode="await", command="bot2-secret-cmd", output="bot2-secret-out",
    )
    _write_receipt(
        launch, missing_sid, parent_session_id="", session_key=launch_route,
        command="missing-parent-cmd", output="missing-parent-out",
    )
    _write_receipt(
        launch, corrupt_sid, parent_session_id={"bad": True}, session_key=launch_route,
        command="corrupt-parent-cmd", output="corrupt-parent-out",
    )
    _write_receipt(
        launch, stranger_sid, parent_session_id="sa-stranger",
        session_key="agent:main:local:dm:stranger",
        command="stranger-cold-cmd", output="stranger-cold-out",
    )
    _write_receipt(
        launch, failed_sid, parent_session_id=failed_parent, exit_code=1,
        session_key=failed_route, command="failed-cold-cmd", output="failed-cold-out",
    )
    _write_receipt(
        launch, lost_sid, parent_session_id=lost_parent, exit_code=None,
        completion_reason="lost", session_key=lost_route,
        command="lost-cold-cmd", output="lost-cold-out",
    )
    # Same route as the launch receipt, stored only under bot2.
    _write_receipt(
        bot2, collide_sid, parent_session_id="sa-collide-unstored",
        session_key=launch_route, command="collide-secret-cmd", output="collide-secret-out",
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
            "lost_parent": lost_parent,
            "failed_route": failed_route,
            "lost_route": lost_route,
            "launch_route": launch_route,
            "bot2_route": bot2_route,
            "launch_sid": launch_sid,
            "bot2_sid": bot2_sid,
            "failed_sid": failed_sid,
            "lost_sid": lost_sid,
            "missing_sid": missing_sid,
            "corrupt_sid": corrupt_sid,
            "stranger_sid": stranger_sid,
            "collide_sid": collide_sid,
            "roster": roster,
        }
    finally:
        if was_pinned:
            pin_process_hermes_home(pinned_home)
        else:
            pin_process_hermes_home(None)
        launch_db.close()


def _by_id(rows):
    return {row.get("session_id") or row.get("id"): row for row in rows}


def _blob(rows):
    return json.dumps(list(rows))


def _snapshot(profile_dir, session_id, route):
    from types import SimpleNamespace

    from gateway.session_ancillary import process_snapshot

    authority = SimpleNamespace(
        sessions={session_id: SimpleNamespace(route=route, source=None)},
        persistence=SimpleNamespace(scope=SimpleNamespace(profile_dir=profile_dir)),
    )
    return process_snapshot(authority, SimpleNamespace(session_id=session_id), None, [])


def _processes(session_key, profile_home):
    from tui_gateway.server import _session_processes

    return _session_processes({"session_key": session_key, "profile_home": profile_home})


def _assert_unresolved_parent(row, launch_parent):
    assert row.get("parent_session_id") in (None, "")
    assert row.get("parent_session_id") != launch_parent
    assert not isinstance(row.get("parent_session_id"), dict)


def test_disk_only_pending_receipt_stays_in_the_roster_without_an_owner(cold_roster):
    """Ready, failed, and lost receipts stay visible with no model owner.

    The ordinary loader and the agent tool stay empty. A foreign profile's
    command and output stay out, even when the stored id and the route coincide.
    A missing or non-string parent is not replaced with the route. Settlement
    clears the same rows and does not schedule another model turn.
    """
    from hermes_cli.cli_process_dock import process_rows, process_status
    from tools.process_registry import _handle_process, _list_processes, process_registry
    from tools.process_registry_results import load_completed_results
    from tui_gateway import server
    from tui_gateway.methods_subagents import _live_work_owners

    case = cold_roster
    launch_parent = case["launch_parent"]
    bot2_parent = case["bot2_parent"]
    failed_parent = case["failed_parent"]
    lost_parent = case["lost_parent"]
    launch_sid = case["launch_sid"]
    bot2_sid = case["bot2_sid"]
    failed_sid = case["failed_sid"]
    lost_sid = case["lost_sid"]
    missing_sid = case["missing_sid"]
    corrupt_sid = case["corrupt_sid"]
    stranger_sid = case["stranger_sid"]
    collide_sid = case["collide_sid"]
    launch_route = case["launch_route"]
    roster = case["roster"]
    one = {"subagents": 0, "background": 1}

    assert os.environ.get("HERMES_SESSION_ID", "") == ""
    for sid in (launch_sid, bot2_sid, failed_sid, lost_sid, collide_sid):
        assert process_registry.get(sid) is None
        assert sid not in process_registry._running
        assert sid not in process_registry._finished
    assert load_completed_results() == {}

    queue_before = process_registry.completion_queue.qsize()
    admissions_before = case["launch_db"].admissions.list(
        session_id=launch_parent, pending_only=False,
    )

    flagged = _by_id(process_registry.list_sessions(include_service_receipts=True))
    assert flagged[launch_sid]["attention"] == "ready"
    assert flagged[launch_sid]["exit_code"] == 0
    assert flagged[launch_sid]["admission_pending"] is True
    assert flagged[launch_sid]["command"] == "ready-cold-cmd"
    assert "ready-cold-out" in (flagged[launch_sid].get("output_preview") or "")
    assert flagged[failed_sid]["attention"] == "failed"
    assert flagged[failed_sid]["exit_code"] == 1
    assert flagged[failed_sid]["attention"] != "ready"
    assert flagged[lost_sid]["attention"] == "lost"
    assert process_status(flagged[launch_sid]) == "ready"
    assert process_status(flagged[failed_sid]) == "failed"
    assert process_status(flagged[lost_sid]) == "lost"
    assert bot2_sid not in flagged
    assert collide_sid not in flagged
    secret = _blob(flagged.values())
    assert "bot2-secret-cmd" not in secret
    assert "bot2-secret-out" not in secret
    assert "collide-secret-cmd" not in secret
    assert "collide-secret-out" not in secret
    _assert_unresolved_parent(flagged[missing_sid], launch_parent)
    _assert_unresolved_parent(flagged[corrupt_sid], launch_parent)

    plain_ids = {row["session_id"] for row in process_registry.list_sessions()}
    retained_ids = {
        row["session_id"] for row in process_registry.list_sessions(include_retained=True)
    }
    tool_ids = {
        row["session_id"] for row in _list_processes("task-cold")["processes"]
    }
    sneaky = json.loads(_handle_process(
        {"action": "list", "include_service_receipts": True}, task_id="task-cold",
    ))
    sneaky_ids = {row["session_id"] for row in sneaky["processes"]}
    agents = server.handle_request(
        {"jsonrpc": "2.0", "id": 2, "method": "agents.list", "params": {}},
    )
    agent_ids = {row["session_id"] for row in agents["result"]["processes"]}
    hidden = {launch_sid, failed_sid, lost_sid, bot2_sid, collide_sid, stranger_sid}
    assert hidden.isdisjoint(plain_ids)
    assert hidden.isdisjoint(retained_ids)
    assert hidden.isdisjoint(tool_ids)
    assert hidden.isdisjoint(sneaky_ids)
    assert hidden.isdisjoint(agent_ids)
    assert load_completed_results() == {}

    painted = _by_id(process_rows())
    assert launch_sid in painted
    assert painted[launch_sid]["command"] == "ready-cold-cmd"
    assert bot2_sid not in painted
    assert collide_sid not in painted
    paint_blob = _blob(painted.values())
    assert "bot2-secret" not in paint_blob
    assert "collide-secret" not in paint_blob

    assert ("background", (launch_parent, launch_route)) in _live_work_owners()
    assert ("background", (failed_parent, case["failed_route"])) in _live_work_owners()
    assert ("background", (lost_parent, case["lost_route"])) in _live_work_owners()
    first = roster()
    assert first[launch_parent] == {"session_id": launch_parent, **one}
    assert first[failed_parent] == {"session_id": failed_parent, **one}
    assert first[lost_parent] == {"session_id": lost_parent, **one}
    assert roster() == first
    assert "sa-stranger" not in first
    assert ("background", (bot2_parent, case["bot2_route"])) in _live_work_owners(case["bot2"])
    foreign = roster("bot2")
    assert foreign == {bot2_parent: {"session_id": bot2_parent, **one}}
    assert launch_parent not in foreign
    assert failed_parent not in foreign

    launch_rows = _by_id(_processes(launch_route, str(case["launch"])))
    assert launch_rows[launch_sid]["attention"] == "ready"
    assert launch_rows[launch_sid]["admission_pending"] is True
    assert "ready-cold-out" in (launch_rows[launch_sid].get("output_tail") or "")
    assert failed_sid not in launch_rows
    assert lost_sid not in launch_rows
    assert stranger_sid not in launch_rows
    assert bot2_sid not in launch_rows
    assert collide_sid not in launch_rows
    _assert_unresolved_parent(launch_rows[missing_sid], launch_parent)
    _assert_unresolved_parent(launch_rows[corrupt_sid], launch_parent)
    assert "bot2-secret" not in _blob(launch_rows.values())
    assert "collide-secret" not in _blob(launch_rows.values())

    default_home = _by_id(_processes(launch_route, None))
    assert launch_sid in default_home
    assert bot2_sid not in default_home
    assert collide_sid not in default_home

    failed_rows = _by_id(_processes(case["failed_route"], str(case["launch"])))
    assert failed_rows[failed_sid]["attention"] == "failed"
    assert failed_rows[failed_sid]["exit_code"] == 1
    assert failed_rows[failed_sid]["attention"] != "ready"
    assert launch_sid not in failed_rows

    lost_rows = _by_id(_processes(case["lost_route"], str(case["launch"])))
    assert lost_rows[lost_sid]["attention"] == "lost"
    assert lost_rows[lost_sid]["attention"] != "ready"

    bot2_rows = _by_id(_processes(case["bot2_route"], str(case["bot2"])))
    assert bot2_rows[bot2_sid]["command"] == "bot2-secret-cmd"
    assert "bot2-secret-out" in (bot2_rows[bot2_sid].get("output_tail") or "")
    assert launch_sid not in bot2_rows
    assert "ready-cold" not in _blob(bot2_rows.values())

    collide_rows = _by_id(_processes(launch_route, str(case["bot2"])))
    assert collide_sid in collide_rows
    assert launch_sid not in collide_rows
    assert "ready-cold-cmd" not in _blob(collide_rows.values())
    assert "ready-cold-out" not in _blob(collide_rows.values())

    launch_snap = _by_id(_snapshot(case["launch"], launch_parent, launch_route))
    assert launch_snap[launch_sid]["attention"] == "ready"
    assert launch_snap[launch_sid]["exit_code"] == 0
    assert "ready-cold-out" in (launch_snap[launch_sid].get("output_tail") or "")
    assert failed_sid not in launch_snap
    assert stranger_sid not in launch_snap
    assert bot2_sid not in launch_snap
    assert collide_sid not in launch_snap
    _assert_unresolved_parent(launch_snap[missing_sid], launch_parent)
    _assert_unresolved_parent(launch_snap[corrupt_sid], launch_parent)
    assert "bot2-secret" not in _blob(launch_snap.values())
    assert "collide-secret" not in _blob(launch_snap.values())

    failed_snap = _by_id(_snapshot(case["launch"], failed_parent, case["failed_route"]))
    assert failed_snap[failed_sid]["attention"] == "failed"
    assert failed_snap[failed_sid]["exit_code"] == 1
    assert launch_sid not in failed_snap

    lost_snap = _by_id(_snapshot(case["launch"], lost_parent, case["lost_route"]))
    assert lost_snap[lost_sid]["attention"] == "lost"
    assert lost_snap[lost_sid]["attention"] != "ready"

    foreign_snap = _by_id(_snapshot(case["bot2"], launch_parent, launch_route))
    assert collide_sid in foreign_snap
    assert launch_sid not in foreign_snap
    assert failed_sid not in foreign_snap
    assert "ready-cold-cmd" not in _blob(foreign_snap.values())
    assert "ready-cold-out" not in _blob(foreign_snap.values())
    assert "failed-cold" not in _blob(foreign_snap.values())

    assert process_registry.completion_queue.qsize() == queue_before
    assert case["launch_db"].admissions.list(
        session_id=launch_parent, pending_only=False,
    ) == admissions_before
    for sid in (launch_sid, failed_sid, lost_sid, bot2_sid):
        assert process_registry.get(sid) is None
        assert sid not in process_registry._running
        assert sid not in process_registry._finished
    assert load_completed_results() == {}
    assert os.environ.get("HERMES_SESSION_ID", "") == ""

    from tools.process_registry_service import clear_service_admission

    assert clear_service_admission(launch_sid) is True
    assert clear_service_admission(failed_sid) is True
    assert clear_service_admission(lost_sid) is True
    for sid, code in ((launch_sid, 0), (failed_sid, 1), (lost_sid, None)):
        stored = json.loads(
            (case["launch"] / "logs" / "process-results" / f"{sid}.json").read_text(encoding="utf-8"),
        )
        assert stored["admission_pending"] is False
        assert stored["exit_code"] == code
    settled = roster()
    assert launch_parent not in settled
    assert failed_parent not in settled
    assert lost_parent not in settled
    assert ("background", (launch_parent, launch_route)) not in _live_work_owners(case["launch"])
    assert ("background", (failed_parent, case["failed_route"])) not in _live_work_owners()
    assert ("background", (lost_parent, case["lost_route"])) not in _live_work_owners()
    assert roster("bot2") == foreign
    settled_flag = _by_id(process_registry.list_sessions(include_service_receipts=True))
    assert launch_sid not in settled_flag
    assert failed_sid not in settled_flag
    assert lost_sid not in settled_flag
    assert launch_sid not in _by_id(_processes(launch_route, str(case["launch"])))
    assert failed_sid not in _by_id(_processes(case["failed_route"], str(case["launch"])))
    assert lost_sid not in _by_id(_processes(case["lost_route"], str(case["launch"])))
    assert launch_sid not in _by_id(_snapshot(case["launch"], launch_parent, launch_route))
    assert failed_sid not in _by_id(_snapshot(case["launch"], failed_parent, case["failed_route"]))
    assert lost_sid not in _by_id(_snapshot(case["launch"], lost_parent, case["lost_route"]))
    assert process_registry.completion_queue.qsize() == queue_before
    missing = json.loads(
        (case["launch"] / "logs" / "process-results" / f"{missing_sid}.json").read_text(encoding="utf-8"),
    )
    assert missing["admission_pending"] is True
    assert missing["parent_session_id"] == ""
