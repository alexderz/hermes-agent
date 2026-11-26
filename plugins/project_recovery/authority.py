"""Read-time classification of worker evidence paths.

Classification is not a lock. A writer can replace a path after this check
and before a later read, so the resolved path is not an immutable property
of the file. No mount policy is added. This module does not call systemctl
and does not write a unit file.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import PurePosixPath, Path


@dataclass(frozen=True)
class AuthorityClass:
    evidence: bool
    reason: str
    resolved: str | None = None


def lexical_escape(path: str) -> bool:
    if type(path) is not str:
        return False
    return ".." in PurePosixPath(path).parts


def lexical_normal(path: str) -> str:
    pieces = [part for part in PurePosixPath(path).parts if part not in {"/", "."}]
    if path.startswith("/"):
        return "/" + "/".join(pieces)
    return "/".join(pieces)


def lexically_contained(path: str, root: str) -> bool:
    """True when ``path`` is ``root`` or a lexical child, without resolving links."""
    if lexical_escape(path) or lexical_escape(root):
        return False
    child = lexical_normal(path)
    parent = lexical_normal(root)
    if child == parent:
        return True
    # "/" + "/" is "//", which matches no absolute child. Every other parent
    # keeps the separator so "/var" does not contain "/var2".
    if parent == "/":
        return child.startswith("/")
    return child.startswith(parent + "/")


def lexically_within(path: str, root: str) -> bool:
    if not lexically_contained(path, root):
        return False
    return lexical_normal(path) != lexical_normal(root)


def output_path_reason(path, outputs_root) -> str | None:
    """Lexical registration check. ``None`` means the name may be recorded."""
    if type(path) is not str:
        return "outside_root"
    if lexical_escape(path):
        return "lexical_escape"
    root = os.fspath(outputs_root)
    if not PurePosixPath(path).is_absolute() or not PurePosixPath(root).is_absolute():
        return "outside_root"
    if not lexically_within(path, root):
        return "outside_root"
    return None


def outputs_rejected(root: str, recovery) -> bool:
    """True when ``outputs.root`` is not an absolute directory outside recovery."""
    if type(root) is not str or not PurePosixPath(root).is_absolute():
        return True
    if lexical_escape(root):
        return True
    recovery_text = os.fspath(recovery)
    if lexically_contained(root, recovery_text):
        return True
    path = Path(root)
    if not path.is_dir():
        return True
    return _resolves_inside(path, Path(recovery_text))


def _resolves_inside(path: Path, parent: Path) -> bool:
    try:
        resolved = path.resolve()
        parent_resolved = parent.resolve()
    except OSError:
        return True
    return resolved == parent_resolved or parent_resolved in resolved.parents


def classify_authority_path(path, outputs_root) -> AuthorityClass:
    if type(path) is not str:
        return AuthorityClass(False, "unspecified", None)
    root = os.fspath(outputs_root)
    lexical = _lexical_reason(path, root)
    if lexical is not None:
        return AuthorityClass(False, lexical, None)
    return _classify_existing(path, root)


def classify_evidence_paths(paths, outputs_root) -> dict[str, AuthorityClass]:
    return {
        name: classify_authority_path(one, outputs_root) for name, one in paths.items()
    }


def _lexical_reason(path: str, root: str) -> str | None:
    if lexical_escape(path):
        return "lexical_escape"
    if not PurePosixPath(path).is_absolute() or not PurePosixPath(root).is_absolute():
        return "outside_root"
    if not lexically_within(path, root):
        return "outside_root"
    return None


def _classify_existing(path: str, root: str) -> AuthorityClass:
    relative = PurePosixPath(lexical_normal(path)).relative_to(lexical_normal(root))
    walked = Path(lexical_normal(root))
    parts = relative.parts
    for index, part in enumerate(parts):
        walked = walked / part
        kind = _lstat_kind(walked)
        final = index == len(parts) - 1
        classified = _kind_class(kind, final)
        if classified is not None:
            return classified
    resolved = Path(path).resolve()
    if not _resolves_inside(Path(path), Path(root)) or resolved == Path(root).resolve():
        return AuthorityClass(False, "outside_root", None)
    return AuthorityClass(True, "evidence", str(resolved))


def _kind_class(kind: str, final: bool) -> AuthorityClass | None:
    if kind == "missing":
        return AuthorityClass(False, "missing", None)
    if kind == "symlink":
        return AuthorityClass(False, "symlink", None)
    if kind == "error":
        return AuthorityClass(False, "not_regular", None)
    if not final and kind != "directory":
        return AuthorityClass(False, _file_reason(kind), None)
    if final and kind != "regular":
        return AuthorityClass(False, _file_reason(kind), None)
    return None


def _file_reason(kind: str) -> str:
    if kind in {"directory", "fifo", "device", "symlink"}:
        return kind
    return "not_regular"


def _lstat_kind(path: Path) -> str:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return "missing"
    except OSError:
        return "error"
    return _mode_kind(mode)


def _mode_kind(mode: int) -> str:
    if stat.S_ISLNK(mode):
        return "symlink"
    if stat.S_ISREG(mode):
        return "regular"
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISFIFO(mode):
        return "fifo"
    if stat.S_ISCHR(mode) or stat.S_ISBLK(mode):
        return "device"
    return "other"
