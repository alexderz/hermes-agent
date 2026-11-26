"""The two unit directives and register-before-start. No unit is started."""

from __future__ import annotations

import json
import os

from plugins.project_recovery import Err, Ok, register_before_start, unit_directives
from tests.plugins.project_recovery.support import handle_document, workspace


def _forbid_spawn(monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("spawned")

    monkeypatch.setattr("subprocess.Popen", boom)
    monkeypatch.setattr("subprocess.run", boom)
    monkeypatch.setattr("os.system", boom)


def test_unit_directives_are_only_the_two_approved_strings(tmp_path, monkeypatch):
    recovery, outputs = workspace(tmp_path)
    _forbid_spawn(monkeypatch)
    result = unit_directives(recovery, outputs)

    assert isinstance(result, Ok)
    assert result.value == (
        f"ReadOnlyPaths={recovery.resolve()}",
        f"ReadWritePaths={outputs.resolve()}",
    )


def test_relative_directive_paths_are_rejected(tmp_path):
    _recovery, outputs = workspace(tmp_path)
    result = unit_directives("recovery", outputs)

    assert isinstance(result, Err)
    assert result.error.reason == "not_absolute"


def test_directives_reject_an_outputs_root_inside_recovery(tmp_path):
    recovery, _outputs = workspace(tmp_path)
    nested = recovery / "outputs"
    nested.mkdir()
    result = unit_directives(recovery, nested)

    assert isinstance(result, Err)
    assert result.error.reason == "outputs_root"


def test_register_before_start_writes_the_handle_and_returns_directives(
    tmp_path, monkeypatch
):
    recovery, outputs = workspace(tmp_path)
    _forbid_spawn(monkeypatch)
    result = register_before_start(
        recovery, handle_document(outputs), outputs_root=outputs
    )

    assert isinstance(result, Ok)
    plan = result.value
    assert plan.directives == (
        f"ReadOnlyPaths={recovery.resolve()}",
        f"ReadWritePaths={outputs.resolve()}",
    )
    assert plan.path == str(recovery / "handles" / "h-0007.json")
    stored = json.loads(open(plan.path, encoding="utf-8").read())
    assert stored["handle"] == "h-0007"
    assert stored["runtime"]["invocation_id"] is None
    assert stored["outputs"]["summary"].endswith("architect.1.summary.json")
    assert list(recovery.rglob("*.service")) == []
    assert not (outputs / "architect.1.summary.json").exists()
    assert os.listdir(outputs) == []
