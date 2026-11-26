"""Read-time worker-evidence classification."""

from __future__ import annotations

import os

import pytest

from plugins.project_recovery import classify_authority_path, classify_evidence_paths
from plugins.project_recovery.authority import (
    lexically_contained,
    lexically_within,
    output_path_reason,
)


def test_regular_file_inside_the_root_is_evidence(tmp_path):
    root = tmp_path / "outputs"
    root.mkdir()
    summary = root / "summary.json"
    summary.write_text("{}\n", encoding="utf-8")
    result = classify_authority_path(str(summary), str(root))

    assert result.evidence is True
    assert result.reason == "evidence"
    assert result.resolved == str(summary.resolve())


def test_dotdot_segment_is_not_evidence_even_when_it_lands_inside(tmp_path):
    root = tmp_path / "outputs"
    root.mkdir()
    summary = root / "summary.json"
    summary.write_text("{}\n", encoding="utf-8")
    escaped = root / ".." / "outputs" / "summary.json"
    result = classify_authority_path(str(escaped), str(root))

    assert result.evidence is False
    assert result.reason == "lexical_escape"


def test_path_outside_the_root_is_not_evidence(tmp_path):
    root = tmp_path / "outputs"
    root.mkdir()
    other = tmp_path / "summary.json"
    other.write_text("{}\n", encoding="utf-8")
    result = classify_authority_path(str(other), str(root))

    assert result.evidence is False
    assert result.reason == "outside_root"


def test_missing_file_is_not_evidence_and_not_an_exception(tmp_path):
    root = tmp_path / "outputs"
    root.mkdir()
    result = classify_authority_path(str(root / "soon.json"), str(root))

    assert result.evidence is False
    assert result.reason == "missing"
    assert result.resolved is None


@pytest.mark.platforms("posix")
def test_symlink_whose_target_leaves_the_root_is_not_evidence(tmp_path):
    root = tmp_path / "outputs"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    secret = outside / "secret.json"
    secret.write_text("{}\n", encoding="utf-8")
    link = root / "secret.json"
    link.symlink_to(secret)
    result = classify_authority_path(str(link), str(root))

    assert result.evidence is False
    assert result.reason == "symlink"


@pytest.mark.platforms("posix")
def test_symlink_to_a_regular_file_inside_the_root_is_not_evidence(tmp_path):
    root = tmp_path / "outputs"
    root.mkdir()
    real = root / "summary.json"
    real.write_text("{}\n", encoding="utf-8")
    link = root / "alias.json"
    link.symlink_to(real)
    result = classify_authority_path(str(link), str(root))
    direct = classify_authority_path(str(real), str(root))

    assert result.evidence is False
    assert result.reason == "symlink"
    assert direct.evidence is True


@pytest.mark.platforms("posix")
def test_intermediate_symlink_that_leaves_the_root_is_not_evidence(tmp_path):
    root = tmp_path / "outputs"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    secret = outside / "secret.json"
    secret.write_text("{}\n", encoding="utf-8")
    link = root / "link"
    link.symlink_to(outside, target_is_directory=True)
    result = classify_authority_path(str(root / "link" / "secret.json"), str(root))

    assert result.evidence is False
    assert result.reason == "symlink"


def test_directory_is_not_evidence(tmp_path):
    root = tmp_path / "outputs"
    folder = root / "stage"
    folder.mkdir(parents=True)
    result = classify_authority_path(str(folder), str(root))

    assert result.evidence is False
    assert result.reason == "directory"


@pytest.mark.platforms("posix")
def test_fifo_is_not_evidence(tmp_path):
    root = tmp_path / "outputs"
    root.mkdir()
    pipe = root / "receipt"
    os.mkfifo(pipe)
    result = classify_authority_path(str(pipe), str(root))

    assert result.evidence is False
    assert result.reason == "fifo"


@pytest.mark.platforms("linux")
def test_device_node_is_not_evidence():
    result = classify_authority_path("/dev/null", "/dev")

    assert result.evidence is False
    assert result.reason == "device"


def test_a_failing_path_leaves_a_sibling_path_valid(tmp_path):
    root = tmp_path / "outputs"
    root.mkdir()
    summary = root / "summary.json"
    summary.write_text("{}\n", encoding="utf-8")
    folder = root / "stage"
    folder.mkdir()
    classes = classify_evidence_paths(
        {
            "summary": str(summary),
            "stage_result": str(folder),
            "callback_receipt": None,
            "report": str(root / "missing.md"),
        },
        str(root),
    )

    assert classes["summary"].evidence is True
    assert classes["stage_result"].evidence is False
    assert classes["stage_result"].reason == "directory"
    assert classes["callback_receipt"].evidence is False
    assert classes["report"].reason == "missing"


def test_manager_brief_outside_the_root_is_not_worker_evidence(tmp_path):
    root = tmp_path / "outputs"
    root.mkdir()
    brief = tmp_path / "authority.brief"
    brief.write_text("brief\n", encoding="utf-8")
    summary = root / "summary.json"
    summary.write_text("{}\n", encoding="utf-8")
    classes = classify_evidence_paths(
        {"authority.brief": str(brief), "summary": str(summary)},
        str(root),
    )

    assert classes["authority.brief"].evidence is False
    assert classes["authority.brief"].reason == "outside_root"
    assert classes["summary"].evidence is True


def test_filesystem_root_contains_an_absolute_child():
    assert lexically_contained("/child/file", "/")
    assert lexically_contained("/", "/")
    assert lexically_within("/child/file", "/")
    assert not lexically_within("/", "/")
    assert output_path_reason("/child/file", "/") is None


def test_non_root_directory_does_not_contain_a_sibling_prefix():
    assert lexically_contained("/var/child", "/var")
    assert lexically_contained("/var", "/var")
    assert not lexically_contained("/var2", "/var")
    assert not lexically_within("/var", "/var")
    assert output_path_reason("/var2/file", "/var") == "outside_root"
