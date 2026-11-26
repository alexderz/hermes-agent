"""Scan journeys. These are fixture checks, not a live certification."""

from __future__ import annotations

import json
from pathlib import Path

from hermes_yaml import safe_dump
from plugins.project_recovery.binding import load_binding
from plugins.project_recovery.handles import register_handle
from plugins.project_recovery.mapping import Ok, load_mapping
from plugins.project_recovery.scan import run_scan
from tests.plugins.project_recovery.support import (
    CLOSED_VERBS,
    MAPPING,
    handle_document,
    linear_document,
    workspace,
    workstream,
)

_UNIT = "example-architect-r1.service"
_ABSENT = {
    "LoadState": "not-found",
    "ActiveState": "inactive",
    "Result": "success",
    "InvocationID": "",
}
_ENDED = {
    "LoadState": "loaded",
    "ActiveState": "failed",
    "Result": "oom-kill",
    "InvocationID": "inv-1",
}
_RUNNING = {
    "LoadState": "loaded",
    "ActiveState": "active",
    "Result": "success",
    "InvocationID": "inv-1",
}


def _repo_root():
    root = Path(__file__).resolve()
    while not (root / "pyproject.toml").is_file():
        if root.parent == root:
            raise AssertionError("repo root")
        root = root.parent
    return root


def test_import_origin_is_this_worktree():
    import plugins.project_recovery.scan as module

    assert Path(module.__file__).resolve().is_relative_to(_repo_root())


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


def _tracker(monkeypatch, payload):
    monkeypatch.setattr(
        "plugins.project_recovery.scan.read_tracker",
        lambda *_args, **_kwargs: payload,
    )


def _show(monkeypatch, table):
    monkeypatch.setattr(
        "plugins.project_recovery.scan.read_unit_show",
        lambda unit: table.get(unit),
    )


def _empty_tracker():
    return {
        "complete": True,
        "error": None,
        "revision": None,
        "roots": {},
        "members": {},
    }


def _members_tracker(members):
    payload = _empty_tracker()
    payload["members"] = members
    return payload


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


def _go(capsys, recovery, **kwargs):
    code = run_scan(recovery, **kwargs)
    return code, capsys.readouterr()


def _open(recovery):
    path = recovery / "state" / "episodes.json"
    rows = json.loads(path.read_text(encoding="utf-8"))["episodes"]
    return [row for row in rows if row.get("closed_scan") is None]


def _classes(recovery):
    return [row["class"] for row in _open(recovery)]


def _snapshot(recovery):
    path = recovery / "state" / "snapshot.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


def _seed_snapshot(recovery, **overrides):
    document = {
        "scan": 1,
        "at": "2026-11-22T00:00:00Z",
        "binding_revision": 7,
        "sources": {
            "tracker": {"complete": True},
            "handles": {"complete": True},
            "units": {"complete": True},
            "asks": {"complete": True},
            "owners": {},
        },
        "members": {},
        "units": {},
        "stalls": {},
    }
    document.update(overrides)
    path = recovery / "state" / "snapshot.json"
    _write_json(path, document)
    return path


def _lookup(_message_id):
    return {"outcome": "proven_not_found"}


def _found(_message_id):
    return {
        "outcome": "found",
        "admission_id": "adm-1",
        "target_session_id": "owner-session",
    }


def _quiet_stream():
    return workstream(brief="")


def test_a3_absent_registration_then_worker_lost(tmp_path, monkeypatch, capsys):
    recovery, outputs = _prepare(tmp_path, stream=_quiet_stream())
    _tracker(monkeypatch, _empty_tracker())
    _show(monkeypatch, {_UNIT: _ABSENT})
    _register(recovery, outputs)
    first, out = _go(capsys, recovery, admission_lookup=_lookup)
    assert first == 0
    assert out.out.strip() == '{"wakeAgent": false}'
    assert "worker_lost" not in _classes(recovery)
    second, again = _go(capsys, recovery, admission_lookup=_lookup)
    assert second == 0
    assert again.out.strip() == '{"wakeAgent": false}'
    assert "worker_lost" in _classes(recovery)
    assert not (recovery / "state" / "outbox.json").exists()


def test_a3_systemctl_failure_is_liveness_unknown(tmp_path, monkeypatch, capsys):
    recovery, outputs = _prepare(tmp_path, stream=_quiet_stream())
    _tracker(monkeypatch, _empty_tracker())
    _show(monkeypatch, {})
    _register(recovery, outputs)
    code, out = _go(capsys, recovery, admission_lookup=_lookup)
    assert code == 0
    assert "liveness_unknown" in out.out
    assert "worker_lost" not in _classes(recovery)
    assert "Traceback" not in out.out


def test_a13_wake_does_not_start_a_turn(tmp_path, monkeypatch, capsys):
    recovery, outputs = _prepare(tmp_path, stream=_quiet_stream())
    _tracker(monkeypatch, _empty_tracker())
    _show(monkeypatch, {_UNIT: _ENDED})

    def _forbid(*_args, **_kwargs):
        raise AssertionError("scanner spawned a process")

    monkeypatch.setattr("plugins.project_recovery.scan.subprocess.run", _forbid)
    _register(recovery, outputs)
    code, out = _go(capsys, recovery, admission_lookup=_lookup)
    assert code == 0
    assert out.out.strip() == '{"wakeAgent": false}'
    wake = next(row for row in _open(recovery) if row["class"] == "worker_lost")
    assert wake["delivery"]["state"] == "undelivered"
    assert not (recovery / "state" / "outbox.json").exists()


def test_a6_no_progress_notice_is_printed_once(tmp_path, monkeypatch, capsys):
    recovery, _outputs = _prepare(tmp_path)
    member = {
        "linear-131": {
            "key": "ABC-131",
            "type": "task",
            "state": "in_progress",
            "parent": "linear:epic-1",
            "via": ["linear:epic-1"],
            "workstream": "ws-alpha",
            "claim": {
                "label": "ws-alpha-mgr",
                "marker": "c1",
                "at": "2026-11-21T00:00:00Z",
            },
            "assignee": "self",
            "blockers": [],
            "tracker_updated": "2026-11-18T00:00:00Z",
            "visibility": "listed",
            "archived": False,
        }
    }
    _tracker(monkeypatch, _members_tracker(member))
    _show(monkeypatch, {})
    first, quiet = _go(capsys, recovery, admission_lookup=_lookup)
    assert first == 0
    assert quiet.out.strip() == '{"wakeAgent": false}'
    episodes = json.loads(
        (recovery / "state" / "episodes.json").read_text(encoding="utf-8")
    )
    for row in episodes["episodes"]:
        if row["class"] == "orphaned_owned":
            row["delivery"]["state"] = "carried"
    _write_json(recovery / "state" / "episodes.json", episodes)
    snap = _snapshot(recovery)
    snap["sources"]["owners"] = {"owner-session": {"state": "idle"}}
    _write_json(recovery / "state" / "snapshot.json", snap)
    _second, notice = _go(capsys, recovery, admission_lookup=_lookup)
    assert "no_progress" in notice.out
    assert "owner-session" not in notice.out
    _third, later = _go(capsys, recovery, admission_lookup=_lookup)
    assert later.out.strip() == '{"wakeAgent": false}'
    assert "no_progress" not in later.out


def test_a14_incomplete_members_stay_and_recovery_is_once(
    tmp_path, monkeypatch, capsys
):
    recovery, outputs = _prepare(tmp_path, stream=_quiet_stream())
    previous = {
        "linear-131": {
            "state": "in_progress",
            "visibility": "listed",
            "workstream": "ws-alpha",
            "first_seen_scan": 1,
        }
    }
    _seed_snapshot(recovery, members=previous)
    _show(monkeypatch, {_UNIT: _ENDED})
    _register(recovery, outputs)
    incomplete = {
        "complete": False,
        "error": "page",
        "revision": None,
        "roots": {},
        "members": None,
    }
    _tracker(monkeypatch, incomplete)
    code, out = _go(capsys, recovery, admission_lookup=_lookup)
    assert code == 0
    assert "tracker_incomplete" in out.out
    assert _snapshot(recovery)["members"] == previous
    assert "worker_lost" in _classes(recovery)
    incomplete["error"] = "timeout"
    _second, again = _go(capsys, recovery, admission_lookup=_lookup)
    assert again.out.strip() == '{"wakeAgent": false}'
    assert _snapshot(recovery)["members"] == previous
    assert _classes(recovery).count("tracker_incomplete") == 1
    _tracker(monkeypatch, _members_tracker(dict(previous)))
    _third, recovered = _go(capsys, recovery, admission_lookup=_lookup)
    assert "tracker_recovered" in recovered.out
    assert _snapshot(recovery)["members"]["linear-131"]["state"] == "in_progress"


def test_f8_membership_notice_prints_once(tmp_path, monkeypatch, capsys):
    recovery, _outputs = _prepare(tmp_path, stream=_quiet_stream())
    member = {
        "linear-131": {
            "state": "in_progress",
            "visibility": "reparented_out",
            "workstream": "ws-alpha",
            "claim": None,
            "assignee": "none",
            "blockers": [],
            "archived": False,
        }
    }
    _tracker(monkeypatch, _members_tracker(member))
    _show(monkeypatch, {})
    code, out = _go(capsys, recovery, admission_lookup=_lookup)
    assert code == 0
    assert "membership_change" in out.out
    assert "owner-session" not in out.out
    assert "/" not in out.out
    _second, later = _go(capsys, recovery, admission_lookup=_lookup)
    assert later.out.strip() == '{"wakeAgent": false}'


def test_f8_reason_codes_are_the_whole_stdout(tmp_path, monkeypatch, capsys):
    recovery, _outputs = _prepare(tmp_path, stream=_quiet_stream())
    (recovery / "binding.yaml").unlink()
    code, out = _go(capsys, recovery)
    assert code == 1
    assert out.out == "binding_invalid\n"
    assert out.err == ""

    recovery, _outputs = _prepare(tmp_path / "second", stream=_quiet_stream())
    path = _seed_snapshot(recovery)
    path.write_text("{", encoding="utf-8")
    before = path.read_bytes()
    code, out = _go(capsys, recovery)
    assert code == 1
    assert out.out == "state_unreadable\n"
    assert path.read_bytes() == before

    recovery, _outputs = _prepare(tmp_path / "third", stream=_quiet_stream())

    def _boom(*_args, **_kwargs):
        raise RuntimeError("ghp_abcdefghijklmnopqrstuvwxyz /home/someone/keys")

    monkeypatch.setattr("plugins.project_recovery.scan.read_tracker", _boom)
    code, out = _go(capsys, recovery, admission_lookup=_lookup)
    assert code == 1
    assert out.out == "internal\n"
    assert "ghp_" not in out.out
    assert "/home/" not in out.out
    assert "Traceback" not in out.out
    assert "Traceback" not in out.err


def test_project_pause_does_not_rewrite_state(tmp_path, monkeypatch, capsys):
    recovery, _outputs = _prepare(
        tmp_path, status="paused", roots=[], stream=_quiet_stream()
    )
    path = _seed_snapshot(recovery)
    before = path.read_bytes()
    _tracker(monkeypatch, _empty_tracker())
    code, out = _go(capsys, recovery)
    assert code == 0
    assert out.out.strip() == '{"wakeAgent": false}'
    assert path.read_bytes() == before
    assert not (recovery / "state" / "episodes.json").exists()
    assert not (recovery / "state" / "aliases.json").exists()


def test_workstream_pause_keeps_delivery(tmp_path, monkeypatch, capsys):
    recovery, _outputs = _prepare(
        tmp_path,
        stream=workstream(status="paused", brief=""),
    )
    _seed_snapshot(recovery)
    _write_json(
        recovery / "state" / "episodes.json",
        {
            "episodes": [
                {
                    "id": "E-1-1",
                    "class": "orphaned_owned",
                    "subject": {"kind": "member", "id": "linear-131"},
                    "workstream": "ws-alpha",
                    "owner": "owner-session",
                    "evidence": {},
                    "delivery": {"state": "undelivered"},
                    "notice": {"no_progress": None},
                    "closed_scan": None,
                }
            ]
        },
    )
    _tracker(monkeypatch, _empty_tracker())
    _show(monkeypatch, {})
    code, _out = _go(capsys, recovery, admission_lookup=_lookup)
    assert code == 0
    row = json.loads(
        (recovery / "state" / "episodes.json").read_text(encoding="utf-8")
    )["episodes"][0]
    assert row["delivery"]["state"] == "undelivered"
    assert row["closed_scan"] is None


def test_closed_project_and_workstream_close_episodes(tmp_path, monkeypatch, capsys):
    recovery, _outputs = _prepare(tmp_path, status="closed", stream=_quiet_stream())
    _write_json(
        recovery / "state" / "episodes.json",
        {
            "episodes": [
                {
                    "id": "E-1-1",
                    "class": "orphaned_owned",
                    "subject": {"kind": "member", "id": "linear-131"},
                    "workstream": "ws-alpha",
                    "owner": "",
                    "evidence": {},
                    "delivery": {"state": "undelivered"},
                    "notice": {},
                    "closed_scan": None,
                }
            ]
        },
    )
    _tracker(monkeypatch, _empty_tracker())
    code, _out = _go(capsys, recovery, admission_lookup=_lookup)
    assert code == 0
    row = json.loads(
        (recovery / "state" / "episodes.json").read_text(encoding="utf-8")
    )["episodes"][0]
    assert row["closed_scan"] == 1

    recovery, _outputs = _prepare(
        tmp_path / "ws",
        stream=workstream(status="closed", brief=""),
    )
    _write_json(
        recovery / "state" / "episodes.json",
        {
            "episodes": [
                {
                    "id": "E-1-1",
                    "class": "orphaned_owned",
                    "subject": {"kind": "member", "id": "linear-131"},
                    "workstream": "ws-alpha",
                    "owner": "",
                    "evidence": {},
                    "delivery": {"state": "undelivered"},
                    "notice": {},
                    "closed_scan": None,
                }
            ]
        },
    )
    _tracker(monkeypatch, _empty_tracker())
    code, _out = _go(capsys, recovery, admission_lookup=_lookup)
    assert code == 0
    row = json.loads(
        (recovery / "state" / "episodes.json").read_text(encoding="utf-8")
    )["episodes"][0]
    assert row["closed_scan"] == 1


def test_g7_done_workstream_closes_finished_member_episode(
    tmp_path, monkeypatch, capsys
):
    recovery, _outputs = _prepare(
        tmp_path,
        stream=workstream(
            status="done", accepted_through="Spec", brief="/briefs/brief.md"
        ),
    )
    _write_json(
        recovery / "state" / "episodes.json",
        {
            "episodes": [
                {
                    "id": "E-1-1",
                    "class": "orphaned_owned",
                    "subject": {"kind": "member", "id": "linear-100"},
                    "workstream": "ws-alpha",
                    "owner": "",
                    "evidence": {"state": "in_progress"},
                    "delivery": {"state": "undelivered"},
                    "notice": {},
                    "closed_scan": None,
                }
            ]
        },
    )
    members = {
        "linear-100": {
            "state": "done",
            "visibility": "listed",
            "workstream": "ws-alpha",
            "claim": None,
            "assignee": "none",
            "blockers": [],
            "archived": False,
        },
        "linear-150": {
            "state": "ready",
            "visibility": "listed",
            "workstream": "ws-alpha",
            "claim": None,
            "assignee": "none",
            "blockers": [],
            "archived": False,
        },
    }
    _tracker(monkeypatch, _members_tracker(members))
    _show(monkeypatch, {})
    code, out = _go(capsys, recovery, admission_lookup=_lookup)
    assert code == 0
    assert out.out.strip() == '{"wakeAgent": false}'
    rows = json.loads(
        (recovery / "state" / "episodes.json").read_text(encoding="utf-8")
    )["episodes"]
    finished = next(row for row in rows if row["subject"]["id"] == "linear-100")
    opened = [row for row in rows if row["class"] == "ready_authorized"]
    assert finished["closed_scan"] is not None
    assert len(opened) == 1
    assert "stalled_workstream" not in [
        row["class"] for row in rows if row.get("closed_scan") is None
    ]


def test_rejected_summary_is_h5_and_a_real_summary_is_h4(tmp_path, monkeypatch, capsys):
    recovery, outputs = _prepare(tmp_path, stream=_quiet_stream())
    _tracker(monkeypatch, _empty_tracker())
    _show(monkeypatch, {_UNIT: _ENDED})
    document = _register(recovery, outputs)
    summary = Path(document["outputs"]["summary"])
    summary.symlink_to(outputs / "not-a-summary")
    code, _out = _go(
        capsys,
        recovery,
        admission_lookup=_found,
        receipt=lambda admission_id, session_id=None: {"status": "terminal"},
    )
    assert code == 0
    assert "worker_lost" in _classes(recovery)
    assert "result_unprocessed" not in _classes(recovery)

    recovery, outputs = _prepare(tmp_path / "valid", stream=_quiet_stream())
    _tracker(monkeypatch, _empty_tracker())
    _show(monkeypatch, {_UNIT: _ENDED})
    document = _register(recovery, outputs)
    Path(document["outputs"]["summary"]).write_text("{}\n", encoding="utf-8")
    Path(document["outputs"]["callback_receipt"]).write_text(
        json.dumps({"message_id": "msg-1"}),
        encoding="utf-8",
    )
    code, out = _go(
        capsys,
        recovery,
        admission_lookup=_found,
        receipt=lambda admission_id, session_id=None: {"status": "terminal"},
    )
    assert code == 0
    assert out.out.strip() == '{"wakeAgent": false}'
    assert "result_unprocessed" in _classes(recovery)
    assert "owner-session" not in out.out


def test_bad_stage_status_is_h5_and_pass_is_h4(tmp_path, monkeypatch, capsys):
    recovery, outputs = _prepare(tmp_path, stream=_quiet_stream())
    stage = outputs / "stage.json"
    stage.write_text(json.dumps({"status": "nope"}), encoding="utf-8")
    _tracker(monkeypatch, _empty_tracker())
    _show(monkeypatch, {_UNIT: _ENDED})
    document = _register(recovery, outputs, outputs={"stage_result": str(stage)})
    Path(document["outputs"]["summary"]).unlink(missing_ok=True)
    _go(
        capsys,
        recovery,
        admission_lookup=_found,
        receipt=lambda admission_id, session_id=None: {"status": "terminal"},
    )
    assert "worker_lost" in _classes(recovery)
    assert "result_unprocessed" not in _classes(recovery)

    recovery, outputs = _prepare(tmp_path / "pass", stream=_quiet_stream())
    stage = outputs / "stage.json"
    stage.write_text(json.dumps({"status": "pass"}), encoding="utf-8")
    _tracker(monkeypatch, _empty_tracker())
    _show(monkeypatch, {_UNIT: _ENDED})
    _register(recovery, outputs, outputs={"stage_result": str(stage)})
    _go(
        capsys,
        recovery,
        admission_lookup=_found,
        receipt=lambda admission_id, session_id=None: {"status": "terminal"},
    )
    assert "result_unprocessed" in _classes(recovery)


def test_o5_stall_notice_for_queued_and_unknown(tmp_path, monkeypatch, capsys):
    recovery, outputs = _prepare(tmp_path, stream=_quiet_stream())
    _seed_snapshot(
        recovery,
        sources={
            "tracker": {"complete": True},
            "handles": {"complete": True},
            "units": {"complete": True},
            "asks": {"complete": True},
            "owners": {"owner-session": {"state": "idle"}},
        },
    )
    _tracker(monkeypatch, _empty_tracker())
    _show(monkeypatch, {_UNIT: _ENDED})
    document = _register(recovery, outputs)
    Path(document["outputs"]["callback_receipt"]).write_text(
        json.dumps({"message_id": "msg-1"}),
        encoding="utf-8",
    )
    seen = []

    def _queued(_admission_id, session_id=None):
        seen.append(session_id)
        return {"status": "queued"}

    code, first = _go(capsys, recovery, admission_lookup=_found, receipt=_queued)
    assert code == 0
    assert "delivery_stalled" not in first.out
    assert seen == ["owner-session"]
    assert "owner-session" not in first.out
    _second, notice = _go(capsys, recovery, admission_lookup=_found, receipt=_queued)
    assert "delivery_stalled" in notice.out
    assert "adm-1" in notice.out
    assert "owner-session" not in notice.out

    recovery, outputs = _prepare(tmp_path / "unknown", stream=_quiet_stream())
    _tracker(monkeypatch, _empty_tracker())
    _show(monkeypatch, {_UNIT: _ENDED})
    document = _register(recovery, outputs)
    Path(document["outputs"]["callback_receipt"]).write_text(
        json.dumps({"message_id": "msg-1"}),
        encoding="utf-8",
    )
    code, out = _go(
        capsys,
        recovery,
        admission_lookup=_found,
        receipt=lambda admission_id, session_id=None: {"status": "unknown"},
    )
    assert code == 0
    assert "delivery_stalled" in out.out


def test_missing_lookup_does_not_open_h4(tmp_path, monkeypatch, capsys):
    recovery, outputs = _prepare(tmp_path, stream=_quiet_stream())
    _tracker(monkeypatch, _empty_tracker())
    _show(monkeypatch, {_UNIT: _ENDED})
    document = _register(recovery, outputs)
    Path(document["outputs"]["summary"]).write_text("{}\n", encoding="utf-8")
    code, out = _go(capsys, recovery)
    assert code == 0
    assert "receipt_outage" in out.out
    assert "result_unprocessed" not in _classes(recovery)

    recovery, _outputs = _prepare(tmp_path / "empty", stream=_quiet_stream())
    _tracker(monkeypatch, _empty_tracker())
    _show(monkeypatch, {})
    code, out = _go(capsys, recovery)
    assert code == 0
    assert out.out.strip() == '{"wakeAgent": false}'
    assert not (recovery / "state" / "episodes.json").exists() or (
        "receipt_outage" not in _classes(recovery)
    )


def test_h3_scan_does_not_carry_or_submit(tmp_path, monkeypatch, capsys):
    recovery, outputs = _prepare(tmp_path, stream=_quiet_stream())
    _seed_snapshot(recovery)
    _write_json(
        recovery / "state" / "episodes.json",
        {
            "episodes": [
                {
                    "id": "E-1-1",
                    "class": "result_unprocessed",
                    "subject": {"kind": "handle", "id": "h-0007"},
                    "workstream": "ws-alpha",
                    "owner": "",
                    "evidence": {"callback": "terminal"},
                    "delivery": {"state": "undelivered"},
                    "notice": {"no_progress": None},
                    "closed_scan": None,
                }
            ]
        },
    )
    _tracker(monkeypatch, _empty_tracker())
    _show(monkeypatch, {_UNIT: _ENDED})
    document = _register(recovery, outputs)
    Path(document["outputs"]["callback_receipt"]).write_text(
        json.dumps({"message_id": "msg-1"}),
        encoding="utf-8",
    )
    code, out = _go(
        capsys,
        recovery,
        admission_lookup=_found,
        receipt=lambda admission_id, session_id=None: {"status": "queued"},
    )
    assert code == 0
    assert out.out.strip() == '{"wakeAgent": false}'
    rows = [
        row
        for row in json.loads(
            (recovery / "state" / "episodes.json").read_text(encoding="utf-8")
        )["episodes"]
        if row["class"] == "result_unprocessed" and row.get("closed_scan") is None
    ]
    assert len(rows) == 1
    assert rows[0]["id"] == "E-1-1"
    assert rows[0]["delivery"]["state"] == "undelivered"
    assert not (recovery / "state" / "outbox.json").exists()


def test_cached_message_id_survives_a_rejected_receipt_path(
    tmp_path, monkeypatch, capsys
):
    recovery, outputs = _prepare(tmp_path, stream=_quiet_stream())
    _tracker(monkeypatch, _empty_tracker())
    _show(monkeypatch, {_UNIT: _ENDED})
    document = _register(recovery, outputs)
    outside = tmp_path / "outside.json"
    outside.write_text(
        json.dumps({"message_id": "msg-other"}),
        encoding="utf-8",
    )
    Path(document["outputs"]["callback_receipt"]).symlink_to(outside)
    _seed_snapshot(
        recovery,
        units={
            "h-0007": {
                "callback_message_id": "msg-cached",
                "callback": "terminal",
                "invocation_id": "inv-1",
                "ever_running": True,
            }
        },
    )
    seen = []

    def lookup(message_id):
        seen.append(message_id)
        return {
            "outcome": "found",
            "admission_id": "adm-9",
            "target_session_id": "owner-session",
        }

    code, out = _go(
        capsys,
        recovery,
        admission_lookup=lookup,
        receipt=lambda admission_id, session_id=None: {"status": "queued"},
    )
    assert code == 0
    unit = _snapshot(recovery)["units"]["h-0007"]
    assert seen == ["msg-cached"]
    assert unit["callback"] == "queued"
    assert unit["callback_message_id"] == "msg-cached"
    assert "msg-other" not in out.out
    assert "owner-session" not in out.out


def _owned_member():
    return {
        "linear-131": {
            "key": "ABC-131",
            "type": "task",
            "state": "in_progress",
            "parent": "linear:epic-1",
            "via": ["linear:epic-1"],
            "workstream": "ws-alpha",
            "claim": {
                "label": "ws-alpha-mgr",
                "marker": "c1",
                "at": "2026-11-21T00:00:00Z",
            },
            "assignee": "self",
            "blockers": [],
            "tracker_updated": "2026-11-18T00:00:00Z",
            "visibility": "listed",
            "archived": False,
        }
    }


def _reparented(ident):
    return {
        "state": "in_progress",
        "visibility": "reparented_out",
        "workstream": "ws-alpha",
        "claim": None,
        "assignee": "none",
        "blockers": [],
        "archived": False,
        "parent": "elsewhere",
        "via": ["linear:epic-1"],
    }


def _episodes(recovery):
    path = recovery / "state" / "episodes.json"
    return json.loads(path.read_text(encoding="utf-8"))["episodes"]


def test_correction_scan_writes_alias_cache_before_enumeration(
    tmp_path, monkeypatch, capsys
):
    recovery, _outputs = _prepare(tmp_path, stream=_quiet_stream())
    seen = {}

    def _read(*_args, **_kwargs):
        path = recovery / "state" / "aliases.json"
        seen["during"] = json.loads(path.read_text(encoding="utf-8"))
        return _empty_tracker()

    monkeypatch.setattr("plugins.project_recovery.scan.read_tracker", _read)
    _show(monkeypatch, {})
    code, _out = _go(capsys, recovery, admission_lookup=_lookup)
    assert code == 0
    body = seen["during"]
    assert body["schema"] == "project-recovery-aliases/1"
    assert type(body["binding_revision"]) is int
    assert body["binding_revision"] == 7
    assert body["state_aliases"]["in_progress"] == ["In Progress"]
    assert body["state_aliases"]["canceled"] == ["Canceled"]


def test_correction_carried_episode_notices_without_receipt_status(
    tmp_path, monkeypatch, capsys
):
    recovery, _outputs = _prepare(tmp_path)
    _tracker(monkeypatch, _members_tracker(_owned_member()))
    _show(monkeypatch, {})
    first, quiet = _go(capsys, recovery, admission_lookup=_lookup)
    assert first == 0
    assert quiet.out.strip() == '{"wakeAgent": false}'
    snap = _snapshot(recovery)
    snap["sources"]["owners"] = {"owner-session": {"state": "idle"}}
    _write_json(recovery / "state" / "snapshot.json", snap)
    _held, still = _go(capsys, recovery, admission_lookup=_lookup)
    assert "no_progress" not in still.out
    document = {"episodes": _episodes(recovery)}
    for row in document["episodes"]:
        if row["class"] == "orphaned_owned":
            row["delivery"]["state"] = "carried"
            assert "receipt_status" not in row["delivery"]
    _write_json(recovery / "state" / "episodes.json", document)
    _second, notice = _go(capsys, recovery, admission_lookup=_lookup)
    assert "no_progress" in notice.out
    assert "owner-session" not in notice.out
    _third, later = _go(capsys, recovery, admission_lookup=_lookup)
    assert later.out.strip() == '{"wakeAgent": false}'
    assert "no_progress" not in later.out


def test_correction_failed_notice_print_stays_retryable(tmp_path, monkeypatch, capsys):
    import builtins

    recovery, _outputs = _prepare(tmp_path, stream=_quiet_stream())
    _tracker(monkeypatch, _members_tracker({"linear-131": _reparented("linear-131")}))
    _show(monkeypatch, {})
    real_print = builtins.print

    def _boom(*_args, **_kwargs):
        raise OSError("stdout")

    monkeypatch.setattr(builtins, "print", _boom)
    try:
        run_scan(recovery, admission_lookup=_lookup)
    except OSError:
        pass
    else:
        raise AssertionError("print failure did not surface")
    monkeypatch.setattr(builtins, "print", real_print)
    rows = [row for row in _episodes(recovery) if row["class"] == "membership_change"]
    assert len(rows) == 1
    assert rows[0]["delivery"]["state"] != "noticed"
    log = recovery / "state" / "notices.jsonl"
    if log.is_file():
        assert "membership_change" not in log.read_text(encoding="utf-8")
    code, out = _go(capsys, recovery, admission_lookup=_lookup)
    assert code == 0
    assert "membership_change" in out.out
    _again, later = _go(capsys, recovery, admission_lookup=_lookup)
    assert later.out.strip() == '{"wakeAgent": false}'


def test_correction_partial_notice_flush_marks_only_printed(
    tmp_path, monkeypatch, capsys
):
    import builtins

    recovery, _outputs = _prepare(tmp_path, stream=_quiet_stream())
    members = {
        "linear-131": _reparented("linear-131"),
        "linear-132": _reparented("linear-132"),
    }
    _tracker(monkeypatch, _members_tracker(members))
    _show(monkeypatch, {})
    printed = []
    real_print = builtins.print

    def _print(*args, **_kwargs):
        if printed:
            raise OSError("stdout")
        printed.append(args[0] if args else "")

    monkeypatch.setattr(builtins, "print", _print)
    try:
        run_scan(recovery, admission_lookup=_lookup)
    except OSError:
        pass
    else:
        raise AssertionError("second notice did not fail")
    monkeypatch.setattr(builtins, "print", real_print)
    flushed_subject = printed[0].split()[-1]
    rows = [row for row in _episodes(recovery) if row["class"] == "membership_change"]
    flushed = [row for row in rows if row["subject"]["id"] == flushed_subject]
    pending = [row for row in rows if row["subject"]["id"] != flushed_subject]
    assert len(flushed) == 1
    assert flushed[0]["delivery"]["state"] == "noticed"
    assert len(pending) == 1
    assert pending[0]["delivery"]["state"] != "noticed"
    log = (recovery / "state" / "notices.jsonl").read_text(encoding="utf-8")
    assert flushed_subject in log
    assert pending[0]["subject"]["id"] not in log
    _code, out = _go(capsys, recovery, admission_lookup=_lookup)
    assert pending[0]["subject"]["id"] in out.out
    assert flushed_subject not in out.out
