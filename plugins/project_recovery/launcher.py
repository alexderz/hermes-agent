"""Register-before-start data for a later disposable unit.

The two directive strings are not OS isolation. Same-UID writers are not
isolated until a future unit actually carries these directives. This module
does not call systemctl, does not write a unit file, and does not change a
live unit.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import PurePosixPath, Path

from plugins.project_recovery.authority import lexical_escape, lexically_contained
from plugins.project_recovery.handles import Handle, register_handle
from plugins.project_recovery.mapping import Err, Invalid, Ok


@dataclass(frozen=True)
class LaunchPlan:
    handle: Handle
    path: str
    directives: tuple[str, str]


def unit_directives(recovery_dir, outputs_root):
    recovery = _absolute(recovery_dir)
    outputs = _absolute(outputs_root)
    if recovery is None or outputs is None:
        return Err(Invalid("binding_invalid", "not_absolute", None))
    if _outputs_inside_recovery(outputs, recovery):
        return Err(Invalid("binding_invalid", "outputs_root", None))
    return Ok(
        (
            f"ReadOnlyPaths={Path(recovery).resolve()}",
            f"ReadWritePaths={Path(outputs).resolve()}",
        )
    )


def register_before_start(recovery_dir, document, *, outputs_root):
    registered = register_handle(recovery_dir, document, outputs_root=outputs_root)
    if isinstance(registered, Err):
        return registered
    directives = unit_directives(recovery_dir, outputs_root)
    if isinstance(directives, Err):
        return directives
    handle = registered.value
    path = str(Path(recovery_dir) / "handles" / f"{handle.handle}.json")
    return Ok(LaunchPlan(handle, path, directives.value))


def _absolute(value) -> str | None:
    text = os.fspath(value)
    if type(text) is not str or not PurePosixPath(text).is_absolute():
        return None
    if lexical_escape(text):
        return None
    return text


def _outputs_inside_recovery(outputs: str, recovery: str) -> bool:
    if lexically_contained(outputs, recovery):
        return True
    try:
        child = Path(outputs).resolve()
        parent = Path(recovery).resolve()
    except OSError:
        return True
    return child == parent or parent in child.parents
