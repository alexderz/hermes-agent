"""Snapshot merge and temp-and-rename writes."""

from __future__ import annotations

import json
from pathlib import Path

from plugins.project_recovery.snapshot import (
    members_after,
    snapshot_document,
    write_json,
)


def _repo_root():
    root = Path(__file__).resolve()
    while not (root / "pyproject.toml").is_file():
        if root.parent == root:
            raise AssertionError("repo root")
        root = root.parent
    return root


def test_import_origin_is_this_worktree():
    import plugins.project_recovery.snapshot as module

    assert Path(module.__file__).resolve().is_relative_to(_repo_root())


def test_incomplete_read_keeps_previous_members():
    previous = {"linear-131": {"state": "ready", "visibility": "listed"}}
    read = {"complete": False, "members": {"linear-131": {"state": "done"}}}
    assert members_after(previous, read, 4) is previous


def test_complete_read_stamps_seen_scans_and_keeps_omitted_ids():
    previous = {
        "linear-131": {"state": "ready", "first_seen_scan": 2},
        "linear-100": {"state": "done", "first_seen_scan": 1},
    }
    read = {"complete": True, "members": {"linear-131": {"state": "in_progress"}}}
    stamped = members_after(previous, read, 5)
    assert stamped["linear-131"]["first_seen_scan"] == 2
    assert stamped["linear-131"]["last_seen_scan"] == 5
    assert stamped["linear-131"]["state"] == "in_progress"
    assert stamped["linear-100"]["state"] == "done"


def test_atomic_write_roundtrip_is_complete_json(tmp_path):
    path = tmp_path / "state" / "snapshot.json"
    write_json(path, {"scan": 1, "members": {}})
    assert json.loads(path.read_text(encoding="utf-8"))["scan"] == 1
    assert list(path.parent.glob(".snapshot.json.*.tmp")) == []


def test_callback_message_id_is_stored_on_the_unit():
    document = snapshot_document(
        scan=1,
        at="2026-11-22T00:00:00Z",
        binding_revision=7,
        tracker={"complete": True},
        handles_complete=True,
        units_complete=True,
        asks_complete=True,
        owners={},
        members={},
        units={"h-0007": {"callback_message_id": "msg-1", "callback": "terminal"}},
        stalls={},
    )
    assert document["units"]["h-0007"]["callback_message_id"] == "msg-1"
