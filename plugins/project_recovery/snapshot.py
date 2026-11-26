"""Snapshot load, member merge, and temp-and-rename writes.

An incomplete tracker read keeps the previous member map. Members already
recorded are not deleted. ``callback_message_id`` is copied forward when
this scan does not refresh it from a file that passed the authority check.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def atomic_write(destination: Path, payload: str) -> None:
    directory = destination.parent
    directory.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=directory,
    )
    try:
        _write_temp(descriptor, temporary, destination, payload)
    except Exception:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise
    _fsync_directory(directory)


def _write_temp(
    descriptor: int, temporary: str, destination: Path, payload: str
) -> None:
    with os.fdopen(descriptor, "w", encoding="utf-8") as sink:
        sink.write(payload)
        sink.flush()
        os.fsync(sink.fileno())
    os.replace(temporary, destination)


def _fsync_directory(directory: Path) -> None:
    try:
        dir_fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def load_document(path: Path):
    """Return the JSON value, None when the file is absent, or ``state_unreadable``."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return "state_unreadable"


def members_after(previous, read, scan: int):
    prior = previous if isinstance(previous, dict) else {}
    if not read.get("complete") or read.get("members") is None:
        return prior
    return _stamp(prior, read["members"], scan)


def _stamp(previous, members, scan: int):
    stamped = {}
    for ident, record in members.items():
        body = {
            key: value for key, value in record.items() if not str(key).startswith("_")
        }
        prior = previous.get(ident)
        seen = prior.get("first_seen_scan") if isinstance(prior, dict) else None
        body["first_seen_scan"] = seen if type(seen) is int else scan
        body["last_seen_scan"] = scan
        stamped[ident] = body
    for ident, prior in previous.items():
        if ident not in stamped and isinstance(prior, dict):
            stamped[ident] = prior
    return stamped


def snapshot_document(
    *,
    scan,
    at,
    binding_revision,
    tracker,
    handles_complete,
    units_complete,
    asks_complete,
    owners,
    members,
    units,
    stalls,
):
    return {
        "scan": scan,
        "at": at,
        "binding_revision": binding_revision,
        "sources": {
            "tracker": tracker,
            "handles": {"complete": handles_complete},
            "units": {"complete": units_complete},
            "asks": {"complete": asks_complete},
            "owners": owners if isinstance(owners, dict) else {},
        },
        "members": members,
        "units": units,
        "stalls": stalls if isinstance(stalls, dict) else {},
    }


def write_json(path: Path, document) -> None:
    atomic_write(path, json.dumps(document, ensure_ascii=False, indent=2) + "\n")


def carried_owners(previous):
    if not isinstance(previous, dict):
        return {}
    sources = previous.get("sources")
    if not isinstance(sources, dict):
        return {}
    owners = sources.get("owners")
    return owners if isinstance(owners, dict) else {}


def carried_stalls(previous):
    if not isinstance(previous, dict):
        return {}
    stalls = previous.get("stalls")
    return stalls if isinstance(stalls, dict) else {}


def tracker_was_incomplete(previous) -> bool:
    if not isinstance(previous, dict):
        return False
    sources = previous.get("sources")
    if not isinstance(sources, dict):
        return False
    tracker = sources.get("tracker")
    if not isinstance(tracker, dict) or "complete" not in tracker:
        return False
    return tracker.get("complete") is False
