"""Pure InvocationID observation and the liveness table."""

from __future__ import annotations

import json

import pytest

from plugins.project_recovery import (
    Ok,
    classify_liveness,
    observe_invocation,
    observe_liveness,
    register_handle,
)
from tests.plugins.project_recovery.support import handle_document, workspace


def _show(active, invocation="", load="loaded", result="success"):
    return {
        "LoadState": load,
        "ActiveState": active,
        "Result": result,
        "InvocationID": invocation,
    }


@pytest.mark.parametrize(
    ("show", "recorded", "ever", "failed", "expected"),
    [
        (_show("active", "id-1"), "id-1", True, False, "running"),
        (_show("activating", "id-1"), None, False, False, "running"),
        (_show("deactivating", "id-1"), "id-1", True, False, "running"),
        (_show("reloading", "id-1"), "id-1", True, False, "running"),
        (_show("active", "id-1"), None, False, False, "running"),
        (_show("active", "id-2"), "id-1", True, False, "replaced"),
        (_show("inactive", "id-2"), "id-1", True, False, "replaced"),
        (_show("inactive", "", "loaded", "success"), "id-1", False, False, "ended"),
        (_show("inactive", "", "loaded", "exit-code"), None, False, False, "ended"),
        (_show("inactive", "", "loaded", "signal"), None, False, False, "ended"),
        (_show("inactive", "", "loaded", "oom-kill"), None, False, False, "ended"),
        (_show("inactive", "", "loaded", "timeout"), None, False, False, "ended"),
        (_show("inactive", "", "loaded", "core-dump"), None, False, False, "ended"),
        (_show("failed", "", "loaded", ""), "id-1", True, False, "ended"),
        (_show("inactive", "", "not-found", "success"), None, False, False, "absent"),
        (_show("inactive", "", "not-found", "success"), None, True, False, "ended"),
        (_show("active", "id-1"), "id-1", True, True, "unknown"),
        (None, None, False, False, "unknown"),
    ],
)
def test_liveness_table(show, recorded, ever, failed, expected):
    assert (
        classify_liveness(
            show,
            recorded_invocation_id=recorded,
            ever_running=ever,
            show_failed=failed,
        )
        == expected
    )


def test_replaced_is_not_running():
    state = classify_liveness(
        _show("active", "id-2"),
        recorded_invocation_id="id-1",
        ever_running=True,
    )

    assert state == "replaced"
    assert state != "running"


def test_absent_is_not_ended():
    state = classify_liveness(
        _show("inactive", "", "not-found", "success"),
        recorded_invocation_id=None,
        ever_running=False,
    )

    assert state == "absent"
    assert state != "ended"


def test_classify_liveness_does_not_spawn(monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("spawned")

    monkeypatch.setattr("subprocess.Popen", boom)
    monkeypatch.setattr("subprocess.run", boom)
    monkeypatch.setattr("os.system", boom)
    state = classify_liveness(
        _show("inactive", "", "not-found", "success"),
        recorded_invocation_id=None,
        ever_running=False,
    )

    assert state == "absent"


def test_first_nonempty_invocation_id_is_kept():
    assert observe_invocation(None, None) is None
    assert observe_invocation(None, "") is None
    assert observe_invocation("", "inv-1") == "inv-1"
    assert observe_invocation("inv-1", "inv-2") == "inv-1"
    assert observe_invocation("inv-1", "") == "inv-1"
    assert observe_invocation("inv-1", None) == "inv-1"


def test_first_id_is_retained_before_the_handle_copy(tmp_path):
    recovery, outputs = workspace(tmp_path)
    registered = register_handle(recovery, handle_document(outputs), outputs_root=outputs)
    assert isinstance(registered, Ok)
    path = recovery / "handles" / "h-0007.json"
    first = observe_liveness(
        _show("active", "inv-1"),
        recorded_invocation_id=None,
        ever_running=False,
    )
    assert first.state == "running"
    assert first.recorded_invocation_id == "inv-1"
    assert first.ever_running is True
    assert json.loads(path.read_text(encoding="utf-8"))["runtime"]["invocation_id"] is None

    second = observe_liveness(
        _show("active", "inv-2"),
        recorded_invocation_id=first.recorded_invocation_id,
        ever_running=first.ever_running,
    )
    assert second.state == "replaced"
    assert second.recorded_invocation_id == "inv-1"
    assert json.loads(path.read_text(encoding="utf-8"))["runtime"]["invocation_id"] is None


def test_failed_show_does_not_replace_the_recorded_id():
    observed = observe_liveness(
        _show("active", "inv-2"),
        recorded_invocation_id="inv-1",
        ever_running=True,
        show_failed=True,
    )

    assert observed.state == "unknown"
    assert observed.recorded_invocation_id == "inv-1"
    assert observed.ever_running is True


def test_blank_id_on_a_live_unit_does_not_count_as_replaced():
    state = classify_liveness(
        _show("active", ""),
        recorded_invocation_id="inv-1",
        ever_running=True,
    )

    assert state == "unknown"
