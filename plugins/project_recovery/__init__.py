"""Membership bindings, handle registration, authority paths, and invocation identity.

Importing this package does no I/O, starts no thread, and reads no environment
variable. ``register`` adds no hook and no tool.
"""

from __future__ import annotations

from plugins.project_recovery.authority import (
    AuthorityClass,
    classify_authority_path,
    classify_evidence_paths,
)
from plugins.project_recovery.binding import load_binding, validate_binding
from plugins.project_recovery.handles import (
    NextDone,
    NextHandle,
    NextStopped,
    NextWait,
    finishes_closing_step,
    load_handle,
    register_handle,
    validate_handle,
)
from plugins.project_recovery.invocation import (
    LivenessObservation,
    classify_liveness,
    observe_invocation,
    observe_liveness,
)
from plugins.project_recovery.launcher import register_before_start, unit_directives
from plugins.project_recovery.mapping import (
    Err,
    Invalid,
    Ok,
    TrackerMapping,
    is_canonical_state,
    key_matches,
    label_identity,
    load_mapping,
    matches_local_assignee,
    matches_local_id,
    matches_local_label,
    member_identity,
)

__all__ = [
    "AuthorityClass",
    "Err",
    "Invalid",
    "LivenessObservation",
    "NextDone",
    "NextHandle",
    "NextStopped",
    "NextWait",
    "Ok",
    "TrackerMapping",
    "classify_authority_path",
    "classify_evidence_paths",
    "classify_liveness",
    "finishes_closing_step",
    "is_canonical_state",
    "key_matches",
    "label_identity",
    "load_binding",
    "load_handle",
    "load_mapping",
    "matches_local_assignee",
    "matches_local_id",
    "matches_local_label",
    "member_identity",
    "observe_invocation",
    "observe_liveness",
    "register",
    "register_before_start",
    "register_handle",
    "unit_directives",
    "validate_binding",
    "validate_handle",
]


def register(ctx) -> None:
    """Discovery entry. Registers no hook and no tool."""
    del ctx
