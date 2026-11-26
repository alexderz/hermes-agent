"""Pure liveness from an already-captured ``systemctl show`` result.

This module does not call systemctl. A blank InvocationID on a live unit
after an id was stored is ``unknown``: it is not running, replaced, or
ended. ``Result=success`` with ``LoadState=not-found``, an empty
InvocationID, and no earlier running observation is systemd's placeholder
for a missing unit, not a real result, so that observation is ``absent``.
"""

from __future__ import annotations

from dataclasses import dataclass

_RUNNING = frozenset({"active", "activating", "deactivating", "reloading"})
_STOPPED = frozenset({"inactive", "failed"})


@dataclass(frozen=True)
class LivenessObservation:
    state: str
    recorded_invocation_id: str | None
    ever_running: bool


def classify_liveness(
    show,
    *,
    recorded_invocation_id: str | None = None,
    ever_running: bool = False,
    show_failed: bool = False,
) -> str:
    if show_failed or not isinstance(show, dict):
        return "unknown"
    recorded = _text_id(recorded_invocation_id)
    shown = _text_id(show.get("InvocationID"))
    active = show.get("ActiveState")
    if recorded and shown and shown != recorded:
        return "replaced"
    live = _live_state(active, recorded, shown)
    if live is not None:
        return live
    if _is_absent(show, shown, ever_running):
        return "absent"
    if _is_ended(show, shown, active, ever_running):
        return "ended"
    return "unknown"


def observe_invocation(recorded: str | None, shown: str | None) -> str | None:
    if type(recorded) is str and recorded:
        return recorded
    if type(shown) is str and shown:
        return shown
    return None


def observe_liveness(
    show,
    *,
    recorded_invocation_id: str | None = None,
    ever_running: bool = False,
    show_failed: bool = False,
) -> LivenessObservation:
    state = classify_liveness(
        show,
        recorded_invocation_id=recorded_invocation_id,
        ever_running=ever_running,
        show_failed=show_failed,
    )
    if show_failed or not isinstance(show, dict):
        return LivenessObservation(state, _kept(recorded_invocation_id), ever_running)
    shown = _text_id(show.get("InvocationID")) or None
    kept = observe_invocation(recorded_invocation_id, shown)
    return LivenessObservation(state, kept, ever_running or state == "running")


def _text_id(value) -> str:
    if type(value) is str:
        return value
    return ""


def _kept(value) -> str | None:
    if type(value) is str and value:
        return value
    return None


def _live_state(active, recorded: str, shown: str) -> str | None:
    if active not in _RUNNING:
        return None
    if not recorded or shown == recorded:
        return "running"
    return "unknown"


def _placeholder(show, shown: str, ever_running: bool) -> bool:
    return (
        show.get("LoadState") == "not-found"
        and show.get("Result") == "success"
        and shown == ""
        and not ever_running
    )


def _real_result(show, shown: str, ever_running: bool) -> bool:
    result = show.get("Result")
    if type(result) is not str or not result:
        return False
    return not _placeholder(show, shown, ever_running)


def _is_absent(show, shown: str, ever_running: bool) -> bool:
    return (
        show.get("LoadState") == "not-found"
        and not ever_running
        and not _real_result(show, shown, ever_running)
    )


def _is_ended(show, shown: str, active, ever_running: bool) -> bool:
    if _real_result(show, shown, ever_running):
        return True
    return bool(ever_running and active in _STOPPED)
