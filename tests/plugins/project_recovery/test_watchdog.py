"""Watchdog scope: registered worker handles only. Fixture checks, not live proof."""

from __future__ import annotations

import json

from hermes_yaml import safe_dump
from plugins.project_recovery.actionability import evaluate_handles
from plugins.project_recovery.binding import load_binding
from plugins.project_recovery.handles import register_handle
from plugins.project_recovery.mapping import Ok, load_mapping
from plugins.project_recovery.operational import delivery_mode, scan_scope
from plugins.project_recovery.scan import run_scan
from tests.plugins.project_recovery.support import (
    CLOSED_VERBS,
    MAPPING,
    handle_document,
    linear_document,
    workspace,
)

_UNIT = "example-architect-r1.service"
_RUNNING = {
    "LoadState": "loaded",
    "ActiveState": "active",
    "Result": "success",
    "InvocationID": "inv-1",
}
_ENDED = {
    "LoadState": "loaded",
    "ActiveState": "failed",
    "Result": "oom-kill",
    "InvocationID": "inv-1",
}
_ABSENT = {
    "LoadState": "not-found",
    "ActiveState": "inactive",
    "Result": "success",
    "InvocationID": "",
}


def _prepare(tmp_path, **kwargs):
    tmp_path.mkdir(parents=True, exist_ok=True)
    recovery, outputs = workspace(tmp_path)
    document = linear_document(outputs, **kwargs)
    raw = safe_dump(document)
    mapping = load_mapping(MAPPING)
    assert isinstance(mapping, Ok)
    loaded = load_binding(
        raw,
        closed_verbs=CLOSED_VERBS,
        mapping=mapping.value,
        recovery_dir=recovery,
    )
    assert isinstance(loaded, Ok), getattr(loaded, "error", loaded)
    (recovery / "binding.yaml").write_text(raw, encoding="utf-8")
    skill = recovery / document["tracker"]["repo_skill"]
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text(MAPPING, encoding="utf-8")
    return recovery, outputs


def _register(recovery, outputs_root, **changes):
    document = handle_document(outputs_root)
    for key, value in changes.items():
        if key in {"runtime", "outputs"} and isinstance(value, dict):
            document[key] = {**document[key], **value}
        else:
            document[key] = value
    loaded = register_handle(recovery, document, outputs_root=str(outputs_root))
    assert isinstance(loaded, Ok), getattr(loaded, "error", loaded)
    return document


def _show(monkeypatch, table):
    monkeypatch.setattr(
        "plugins.project_recovery.scan.read_unit_show",
        lambda unit: table.get(unit),
    )


def _no_tracker(monkeypatch):
    def refuse(*_args, **_kwargs):
        raise AssertionError("watchdog scope read the tracker")

    monkeypatch.setattr("plugins.project_recovery.scan.read_tracker", refuse)


def _summary(outputs):
    path = outputs / "architect.1.summary.json"
    path.write_text('{"status": "ok"}', encoding="utf-8")
    return path


def _open(recovery):
    path = recovery / "state" / "episodes.json"
    rows = json.loads(path.read_text(encoding="utf-8"))["episodes"]
    return [row for row in rows if row.get("closed_scan") is None]


def _snapshot(recovery):
    return json.loads((recovery / "state" / "snapshot.json").read_text(encoding="utf-8"))


def _lookup(_message_id):
    return {"outcome": "proven_not_found"}


def _go(capsys, recovery, **kwargs):
    kwargs.setdefault("admission_lookup", _lookup)
    code = run_scan(recovery, scope="watchdog", **kwargs)
    return code, capsys.readouterr()


def test_watchdog_reads_no_tracker(tmp_path, monkeypatch, capsys):
    recovery, outputs = _prepare(tmp_path)
    _register(recovery, outputs)
    _show(monkeypatch, {_UNIT: _RUNNING})
    _no_tracker(monkeypatch)

    code, captured = _go(capsys, recovery)

    assert code == 0
    assert captured.out.strip() == '{"wakeAgent": false}'
    assert _snapshot(recovery)["sources"]["tracker"]["scope"] == "watchdog"
    assert _snapshot(recovery)["sources"]["tracker"]["complete"] is None


def test_running_worker_is_quiet_at_any_age(tmp_path, monkeypatch, capsys):
    recovery, outputs = _prepare(tmp_path)
    _register(recovery, outputs, runtime={"invocation_id": "inv-1"})
    _show(monkeypatch, {_UNIT: _RUNNING})
    _no_tracker(monkeypatch)

    for _ in range(3):
        code, captured = _go(capsys, recovery)
        assert code == 0
        assert captured.out.strip() == '{"wakeAgent": false}'

    assert _open(recovery) == []


def test_unconsumed_result_without_callback_wakes_once(tmp_path, monkeypatch, capsys):
    recovery, outputs = _prepare(tmp_path)
    _register(recovery, outputs, runtime={"invocation_id": "inv-1"})
    _summary(outputs)
    _show(monkeypatch, {_UNIT: _ENDED})
    _no_tracker(monkeypatch)

    first_code, _first = _go(capsys, recovery)
    first_ids = [row["id"] for row in _open(recovery)]
    second_code, _second = _go(capsys, recovery)

    assert first_code == 0 and second_code == 0
    assert [row["class"] for row in _open(recovery)] == ["result_unprocessed"]
    assert [row["id"] for row in _open(recovery)] == first_ids
    assert _open(recovery)[0]["delivery"]["state"] != "noticed"


def test_lost_worker_wakes(tmp_path, monkeypatch, capsys):
    recovery, outputs = _prepare(tmp_path)
    _register(recovery, outputs, runtime={"invocation_id": "inv-1"})
    _show(monkeypatch, {_UNIT: _ABSENT})
    _no_tracker(monkeypatch)

    first_code, _first = _go(capsys, recovery)
    assert first_code == 0
    assert _open(recovery) == []
    code, _captured = _go(capsys, recovery)

    assert first_code == 0
    assert code == 0
    assert [row["class"] for row in _open(recovery)] == ["worker_lost"]


def test_watchdog_preserves_membership_it_never_read(tmp_path, monkeypatch, capsys):
    recovery, outputs = _prepare(tmp_path)
    _register(recovery, outputs)
    _show(monkeypatch, {_UNIT: _RUNNING})
    _no_tracker(monkeypatch)
    state = recovery / "state"
    state.mkdir(parents=True, exist_ok=True)
    members = {"ABC-100": {"status": "in_progress", "workstream": "ws-alpha"}}
    (state / "snapshot.json").write_text(
        json.dumps(
            {
                "scan": 4,
                "at": "2026-11-23T10:00:00Z",
                "binding_revision": 7,
                "sources": {"tracker": {"complete": True, "revision": None, "roots": {}}},
                "members": members,
                "units": {},
                "stalls": {},
            }
        ),
        encoding="utf-8",
    )

    code, _ = _go(capsys, recovery)

    assert code == 0
    assert _snapshot(recovery)["members"] == members


def test_started_callback_is_not_a_wake(tmp_path, monkeypatch, capsys):
    recovery, outputs = _prepare(tmp_path)
    _register(recovery, outputs, runtime={"invocation_id": "inv-1"})
    _summary(outputs)
    _show(monkeypatch, {_UNIT: _ENDED})
    _no_tracker(monkeypatch)

    def found(_message_id):
        return {
            "outcome": "found",
            "admission_id": "adm-1",
            "target_session_id": "owner-session",
        }

    receipt_path = outputs / "architect.1.delivery.json"
    receipt_path.write_text('{"message_id": "msg-1"}', encoding="utf-8")
    _go(
        capsys,
        recovery,
        admission_lookup=found,
        receipt=lambda _admission_id, session_id=None: {"status": "started"},
    )

    assert _open(recovery) == []


def test_board_episode_survives_a_watchdog_scan(tmp_path, monkeypatch, capsys):
    recovery, outputs = _prepare(tmp_path)
    _register(recovery, outputs)
    _show(monkeypatch, {_UNIT: _RUNNING})
    _no_tracker(monkeypatch)
    state = recovery / "state"
    state.mkdir(parents=True, exist_ok=True)
    board_episode = {
        "id": "E-9-1",
        "class": "orphaned_owned",
        "subject": {"kind": "member", "id": "ABC-9"},
        "workstream": "ws-alpha",
        "evidence": {"state": "in_progress"},
        "opened_scan": 9,
        "closed_scan": None,
        "delivery": {"state": "carried"},
        "notice": {},
    }
    (state / "episodes.json").write_text(
        json.dumps({"schema": "project-recovery-episodes/1", "episodes": [board_episode]}),
        encoding="utf-8",
    )
    (state / "snapshot.json").write_text(
        json.dumps(
            {
                "scan": 9,
                "at": "2026-11-23T10:00:00Z",
                "binding_revision": 7,
                "sources": {
                    "tracker": {"complete": False, "revision": None, "roots": {}},
                    "owners": {"owner-session": {"state": "idle"}},
                },
                "members": {},
                "units": {},
                "stalls": {},
            }
        ),
        encoding="utf-8",
    )

    code, _ = _go(capsys, recovery)

    assert code == 0
    rows = json.loads((state / "episodes.json").read_text(encoding="utf-8"))["episodes"]
    kept = next(row for row in rows if row["id"] == "E-9-1")
    assert kept["closed_scan"] is None
    assert kept["delivery"]["state"] == "carried"
    assert kept["notice"] == {}


def test_watchdog_scan_does_not_lose_a_tracker_outage(tmp_path, monkeypatch, capsys):
    recovery, outputs = _prepare(tmp_path)
    _register(recovery, outputs)
    _show(monkeypatch, {_UNIT: _RUNNING})
    _no_tracker(monkeypatch)
    state = recovery / "state"
    state.mkdir(parents=True, exist_ok=True)
    outage = {
        "id": "E-9-2",
        "class": "tracker_incomplete",
        "subject": {"kind": "source", "id": "tracker"},
        "workstream": "",
        "evidence": {"source": "tracker", "revision": 7},
        "opened_scan": 9,
        "closed_scan": None,
        "delivery": {"state": "noticed"},
        "notice": {},
    }
    (state / "episodes.json").write_text(
        json.dumps({"schema": "project-recovery-episodes/1", "episodes": [outage]}),
        encoding="utf-8",
    )
    (state / "snapshot.json").write_text(
        json.dumps(
            {
                "scan": 9,
                "at": "2026-11-23T10:00:00Z",
                "binding_revision": 7,
                "sources": {"tracker": {"complete": False, "revision": None, "roots": {}}},
                "members": {},
                "units": {},
                "stalls": {},
            }
        ),
        encoding="utf-8",
    )

    code, _ = _go(capsys, recovery)

    assert code == 0
    rows = json.loads((state / "episodes.json").read_text(encoding="utf-8"))["episodes"]
    assert [row["id"] for row in rows if row["closed_scan"] is None] == ["E-9-2"]


def test_blocker_wait_is_retained_and_ask_wait_is_managed():
    from plugins.project_recovery.scan import _split_board_episodes

    blocker = {
        "id": "E-1",
        "class": "wait_resolved",
        "evidence": {"wait": "blocker", "ref": "ABC-9", "status": "done"},
        "closed_scan": None,
    }
    ask = {
        "id": "E-2",
        "class": "wait_resolved",
        "evidence": {"wait": "ask", "ref": "asks.md#q1", "status": "answered"},
        "closed_scan": None,
    }
    orphan = {
        "id": "E-3",
        "class": "orphaned_owned",
        "evidence": {"state": "in_progress"},
        "closed_scan": None,
    }
    result = {
        "id": "E-4",
        "class": "result_unprocessed",
        "evidence": {"callback": "absent"},
        "closed_scan": None,
    }

    managed, retained = _split_board_episodes([blocker, ask, orphan, result])

    assert [row["id"] for row in retained] == ["E-1", "E-3"]
    assert [row["id"] for row in managed] == ["E-2", "E-4"]


def test_board_scan_recovers_a_watchdog_retained_outage(tmp_path, monkeypatch, capsys):
    recovery, outputs = _prepare(tmp_path)
    _register(recovery, outputs)
    _show(monkeypatch, {_UNIT: _RUNNING})
    _no_tracker(monkeypatch)
    state = recovery / "state"
    state.mkdir(parents=True, exist_ok=True)
    outage = {
        "id": "E-9-2",
        "class": "tracker_incomplete",
        "subject": {"kind": "source", "id": "tracker"},
        "workstream": "",
        "evidence": {"source": "tracker", "revision": 7},
        "opened_scan": 9,
        "closed_scan": None,
        "delivery": {"state": "noticed"},
        "notice": {},
    }
    (state / "episodes.json").write_text(
        json.dumps({"schema": "project-recovery-episodes/1", "episodes": [outage]}),
        encoding="utf-8",
    )
    (state / "snapshot.json").write_text(
        json.dumps(
            {
                "scan": 9,
                "at": "2026-11-23T10:00:00Z",
                "binding_revision": 7,
                "sources": {"tracker": {"complete": False, "revision": None, "roots": {}}},
                "members": {},
                "units": {},
                "stalls": {},
            }
        ),
        encoding="utf-8",
    )
    _go(capsys, recovery)
    complete = {
        "complete": True,
        "error": None,
        "revision": None,
        "roots": {},
        "members": {},
    }
    monkeypatch.setattr("plugins.project_recovery.scan.read_tracker", lambda *a, **k: complete)

    first_code = run_scan(recovery, scope="board", admission_lookup=_lookup)
    first = capsys.readouterr()
    second_code = run_scan(recovery, scope="board", admission_lookup=_lookup)
    second = capsys.readouterr()

    assert first_code == 0 and second_code == 0
    assert first.out.count("tracker_recovered") == 1
    assert second.out.count("tracker_recovered") == 0
    assert _open(recovery) == []


def test_healthy_board_emits_no_recovery(tmp_path, monkeypatch, capsys):
    recovery, outputs = _prepare(tmp_path)
    _register(recovery, outputs)
    _show(monkeypatch, {_UNIT: _RUNNING})
    complete = {
        "complete": True,
        "error": None,
        "revision": None,
        "roots": {},
        "members": {},
    }
    monkeypatch.setattr("plugins.project_recovery.scan.read_tracker", lambda *a, **k: complete)

    code = run_scan(recovery, scope="board", admission_lookup=_lookup)

    assert code == 0
    assert "tracker_recovered" not in capsys.readouterr().out


def test_evaluate_handles_ignores_board_rules():
    running = {"id": "h-1", "liveness": "running", "consumed": None, "callback": "absent"}
    queued = {
        "id": "h-2",
        "liveness": "ended",
        "consumed": None,
        "callback": "queued",
        "summary_ok": True,
    }
    waiting = {
        "id": "h-3",
        "liveness": "ended",
        "consumed": {"next": {"wait": {"kind": "blocker", "ref": "ABC-9"}}},
        "callback": "absent",
    }
    started = {
        "id": "h-4",
        "liveness": "replaced",
        "consumed": None,
        "callback": "started",
        "summary_ok": True,
    }
    world = {
        "project_status": "open",
        "binding_revision": 7,
        "tracker_complete": False,
        "receipt_outage": False,
        "handles": [running, queued, waiting, started],
        "members": [],
        "workstreams": [{"id": "ws-alpha", "status": "open"}],
        "asks": {},
        "asks_complete": True,
        "now": "2026-11-23T10:00:00Z",
    }

    result = evaluate_handles(world)

    assert result.intents == ()
    assert result.suppress == frozenset({"h-2", "h-4"})


def test_scope_selection_defaults_to_watchdog():
    assert scan_scope({}) == "watchdog"
    assert scan_scope({"PROJECT_RECOVERY_SCOPE": ""}) == "watchdog"
    assert scan_scope({"PROJECT_RECOVERY_SCOPE": "board"}) == "board"
    assert scan_scope({"PROJECT_RECOVERY_SCOPE": "everything"}) == "refused"
    assert delivery_mode({}) == "notice-only"


def test_unknown_scope_is_refused(tmp_path, capsys):
    recovery, _ = _prepare(tmp_path)

    code = run_scan(recovery, scope="everything")

    assert code == 1
    assert capsys.readouterr().out.strip() == "scope_invalid"


def test_board_scope_still_reads_the_tracker(tmp_path, monkeypatch, capsys):
    recovery, outputs = _prepare(tmp_path)
    _register(recovery, outputs)
    _show(monkeypatch, {_UNIT: _RUNNING})
    calls = []

    def tracker(*_args, **_kwargs):
        calls.append(1)
        return {"complete": True, "error": None, "revision": None, "roots": {}, "members": {}}

    monkeypatch.setattr("plugins.project_recovery.scan.read_tracker", tracker)

    code = run_scan(recovery, scope="board")

    assert code == 0
    assert calls
    assert "scope" not in _snapshot(recovery)["sources"]["tracker"]
