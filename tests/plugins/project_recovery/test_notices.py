"""Notice lines and the temp-and-rename notice log."""

from __future__ import annotations

import json
from pathlib import Path

from plugins.project_recovery.notices import (
    append_notices,
    format_notice,
    load_notices,
)


def _repo_root():
    root = Path(__file__).resolve()
    while not (root / "pyproject.toml").is_file():
        if root.parent == root:
            raise AssertionError("repo root")
        root = root.parent
    return root


def test_import_origin_is_this_worktree():
    import plugins.project_recovery.notices as module

    assert Path(module.__file__).resolve().is_relative_to(_repo_root())


def test_notice_line_names_project_episode_class_and_subject():
    episode = {
        "id": "E-2-1",
        "class": "membership_change",
        "subject": {"kind": "member", "id": "linear-131"},
        "owner": "owner-session",
    }
    line = format_notice("proj-example", episode)
    assert line == "recovery proj-example: E-2-1 membership_change linear-131"
    assert "owner-session" not in line
    assert "/" not in line


def test_append_rewrites_the_whole_file_by_rename(tmp_path):
    path = tmp_path / "notices.jsonl"
    append_notices(path, [{"id": "E-1-1", "class": "membership_change"}])
    append_notices(path, [{"id": "E-2-1", "class": "tracker_recovered"}])
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [row["id"] for row in rows] == ["E-1-1", "E-2-1"]
    assert list(path.parent.glob(".notices.jsonl.*.tmp")) == []


def test_corrupt_notice_log_is_state_unreadable(tmp_path):
    path = tmp_path / "notices.jsonl"
    path.write_text("not-json\n", encoding="utf-8")
    assert load_notices(path) == "state_unreadable"


def test_missing_notice_log_is_empty(tmp_path):
    assert load_notices(tmp_path / "notices.jsonl") == ""
