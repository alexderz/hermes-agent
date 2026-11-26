"""Handle documents, consumption, and register-before-start writes."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from plugins.project_recovery import (
    Err,
    NextDone,
    NextHandle,
    NextStopped,
    NextWait,
    Ok,
    finishes_closing_step,
    load_handle,
    register_handle,
    validate_handle,
)
from tests.plugins.project_recovery.support import handle_document, workspace

CONSUMED_AT = "2026-11-22T11:02:00Z"


def _consumed(nxt):
    return {"at": CONSUMED_AT, "next": nxt}


@pytest.mark.parametrize(
    ("nxt", "kind", "fields"),
    [
        ({"handle": "h-0008"}, NextHandle, {"handle": "h-0008"}),
        (
            {"wait": {"kind": "ask", "ref": "/asks/asks.md#Q1"}},
            NextWait,
            {"kind": "ask", "ref": "/asks/asks.md#Q1", "resume_after": None},
        ),
        (
            {"wait": {"kind": "blocker", "ref": "linear:blocker-1"}},
            NextWait,
            {"kind": "blocker", "ref": "linear:blocker-1", "resume_after": None},
        ),
        (
            {"wait": {"kind": "quota", "resume_after": "2026-11-22T12:00:00Z"}},
            NextWait,
            {"kind": "quota", "ref": None, "resume_after": "2026-11-22T12:00:00Z"},
        ),
        (
            {"wait": {"kind": "operator", "ref": "/asks/asks.md#Q2"}},
            NextWait,
            {"kind": "operator", "ref": "/asks/asks.md#Q2", "resume_after": None},
        ),
        ({"done": "Build"}, NextDone, {"step": "Build"}),
        ({"done": "Changelog"}, NextDone, {"step": "Changelog"}),
        ({"stopped": "operator"}, NextStopped, {"reason": "operator"}),
    ],
)
def test_consumed_next_round_trips(tmp_path, nxt, kind, fields):
    recovery, outputs = workspace(tmp_path)
    document = handle_document(outputs, consumed=_consumed(nxt))
    validated = validate_handle(document, outputs_root=outputs)
    written = register_handle(recovery, document, outputs_root=outputs)
    loaded = load_handle(recovery / "handles" / "h-0007.json", outputs_root=outputs)

    assert isinstance(validated, Ok)
    assert isinstance(written, Ok)
    assert isinstance(loaded, Ok)
    for handle in (validated.value, written.value, loaded.value):
        assert isinstance(handle.consumed.next, kind)
        for name, expected in fields.items():
            assert getattr(handle.consumed.next, name) == expected
        assert handle.runtime.invocation_id is None
    stored = json.loads((recovery / "handles" / "h-0007.json").read_text(encoding="utf-8"))
    assert stored["consumed"]["next"] == nxt
    assert stored["schema"] == "project-recovery-handle/1"


def test_unconsumed_handle_round_trips_with_null_outputs(tmp_path):
    recovery, outputs = workspace(tmp_path)
    document = handle_document(outputs, consumed=None, stage_result=None)
    result = register_handle(recovery, document, outputs_root=outputs)

    assert isinstance(result, Ok)
    assert result.value.consumed is None
    assert result.value.outputs.stage_result is None
    stored = json.loads((recovery / "handles" / "h-0007.json").read_text(encoding="utf-8"))
    assert stored["consumed"] is None
    assert stored["outputs"]["stage_result"] is None


def test_done_finishes_the_workstream_only_when_it_equals_closing_step():
    assert finishes_closing_step(NextDone("Changelog"), "Changelog") is True
    assert finishes_closing_step(NextDone("Build"), "Changelog") is False
    assert finishes_closing_step(NextStopped("operator"), "Changelog") is False
    assert finishes_closing_step(NextHandle("h-0008"), "Changelog") is False
    assert (
        finishes_closing_step(
            NextWait("ask", ref="/asks/asks.md#Q1"),
            "Changelog",
        )
        is False
    )


@pytest.mark.parametrize(
    "nxt",
    [
        {"handle": "h-0008", "done": "Build"},
        {"stopped": "user"},
        {"done": "Ship"},
        {"wait": {"kind": "quota"}},
        {"wait": {"kind": "ask"}},
        {"wait": {"kind": "sleep", "ref": "x"}},
        {},
        "operator",
        {"stopped": "operator", "handle": "h-0008"},
    ],
)
def test_bad_next_is_an_error_and_writes_nothing(tmp_path, nxt):
    recovery, outputs = workspace(tmp_path)
    document = handle_document(outputs, consumed=_consumed(nxt))
    result = register_handle(recovery, document, outputs_root=outputs)

    assert isinstance(result, Err)
    assert result.error.code == "handle_invalid"
    assert result.error.reason == "handle_next"
    assert not (recovery / "handles").exists()


def test_register_writes_one_complete_file_by_replace_in_the_same_directory(
    tmp_path, monkeypatch
):
    recovery, outputs = workspace(tmp_path)
    calls = []
    real_replace = os.replace

    def spy(src, dst):
        calls.append((str(src), str(dst)))
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", spy)
    document = handle_document(outputs)
    result = register_handle(recovery, document, outputs_root=outputs)

    assert isinstance(result, Ok)
    assert calls
    src, dst = calls[-1]
    assert Path(src).parent == Path(dst).parent
    assert Path(dst) == recovery / "handles" / "h-0007.json"
    assert Path(src).name != Path(dst).name
    names = sorted(path.name for path in (recovery / "handles").iterdir())
    assert names == ["h-0007.json"]
    parsed = json.loads(Path(dst).read_text(encoding="utf-8"))
    assert parsed["handle"] == "h-0007"
    assert parsed["runtime"]["invocation_id"] is None


def test_missing_output_files_are_accepted_and_not_created(tmp_path):
    recovery, outputs = workspace(tmp_path)
    document = handle_document(outputs)
    result = register_handle(recovery, document, outputs_root=outputs)

    assert isinstance(result, Ok)
    for name in (
        "architect.1.summary.json",
        "architect.1.report.md",
        "architect.1.delivery.json",
        "architect.session",
    ):
        assert not (outputs / name).exists()


def test_output_path_outside_the_root_is_rejected(tmp_path):
    recovery, outputs = workspace(tmp_path)
    outside = tmp_path / "elsewhere" / "summary.json"
    document = handle_document(outputs, summary=str(outside))
    result = register_handle(recovery, document, outputs_root=outputs)

    assert isinstance(result, Err)
    assert result.error.code == "handle_invalid"
    assert result.error.reason == "outside_root"
    assert not (recovery / "handles").exists()


def test_dotdot_output_path_is_rejected(tmp_path):
    recovery, outputs = workspace(tmp_path)
    escaped = outputs / ".." / "outputs" / "architect.1.summary.json"
    document = handle_document(outputs, summary=str(escaped))
    result = register_handle(recovery, document, outputs_root=outputs)

    assert isinstance(result, Err)
    assert result.error.reason == "lexical_escape"
    assert not (recovery / "handles").exists()


@pytest.mark.platforms("posix")
def test_existing_non_regular_output_does_not_block_registration(tmp_path):
    recovery, outputs = workspace(tmp_path)
    pipe = outputs / "architect.1.summary.json"
    os.mkfifo(pipe)
    document = handle_document(outputs, summary=str(pipe))
    result = register_handle(recovery, document, outputs_root=outputs)

    assert isinstance(result, Ok)
    stored = json.loads((recovery / "handles" / "h-0007.json").read_text(encoding="utf-8"))
    assert stored["outputs"]["summary"] == str(pipe)


def test_handle_file_stays_under_recovery_handles(tmp_path):
    recovery, outputs = workspace(tmp_path)
    result = register_handle(recovery, handle_document(outputs), outputs_root=outputs)
    written = recovery / "handles" / "h-0007.json"

    assert isinstance(result, Ok)
    assert written.is_file()
    assert written.parent.parent == recovery
    assert outputs not in written.parents


def test_invalid_update_does_not_replace_a_registered_handle(tmp_path):
    recovery, outputs = workspace(tmp_path)
    first = register_handle(recovery, handle_document(outputs), outputs_root=outputs)
    assert isinstance(first, Ok)
    original = (recovery / "handles" / "h-0007.json").read_text(encoding="utf-8")
    bad = handle_document(outputs, consumed=_consumed({"done": "Ship"}))
    second = register_handle(recovery, bad, outputs_root=outputs)

    assert isinstance(second, Err)
    assert (recovery / "handles" / "h-0007.json").read_text(encoding="utf-8") == original
    names = sorted(path.name for path in (recovery / "handles").iterdir())
    assert names == ["h-0007.json"]


def test_handle_id_cannot_escape_the_handles_directory(tmp_path):
    recovery, outputs = workspace(tmp_path)
    document = handle_document(outputs)
    document["handle"] = "../h-0007"
    result = register_handle(recovery, document, outputs_root=outputs)

    assert isinstance(result, Err)
    assert result.error.reason == "handle_id"
    assert not (recovery / "h-0007.json").exists()
    assert not (tmp_path / "h-0007.json").exists()


def test_member_subject_round_trips(tmp_path):
    recovery, outputs = workspace(tmp_path)
    document = handle_document(outputs)
    document["subject"] = {"kind": "member", "id": "linear:item-1"}
    result = register_handle(recovery, document, outputs_root=outputs)

    assert isinstance(result, Ok)
    assert result.value.subject.kind == "member"
    assert result.value.subject.id == "linear:item-1"


def test_consumption_can_be_recorded_when_evidence_files_are_absent(tmp_path):
    recovery, outputs = workspace(tmp_path)
    registered = register_handle(recovery, handle_document(outputs), outputs_root=outputs)
    assert isinstance(registered, Ok)
    updated = handle_document(outputs, consumed=_consumed({"stopped": "operator"}))
    result = register_handle(recovery, updated, outputs_root=outputs)

    assert isinstance(result, Ok)
    assert isinstance(result.value.consumed.next, NextStopped)
    assert not (outputs / "architect.1.summary.json").exists()


def test_list_valued_wait_kind_is_a_typed_error(tmp_path):
    _recovery, outputs = workspace(tmp_path)
    document = handle_document(
        outputs,
        consumed={
            "at": CONSUMED_AT,
            "next": {"wait": {"kind": [], "ref": "synthetic"}},
        },
    )
    result = validate_handle(document, outputs_root=outputs)

    assert isinstance(result, Err)
    assert result.error.code == "handle_invalid"
    assert result.error.reason == "handle_next"


def test_invalid_utf8_handle_is_unreadable(tmp_path):
    _recovery, outputs = workspace(tmp_path)
    path = tmp_path / "bad-handle.json"
    path.write_bytes(bytes([255]))
    result = load_handle(path, outputs_root=outputs)

    assert isinstance(result, Err)
    assert result.error.code == "handle_invalid"
    assert result.error.reason == "unreadable"
