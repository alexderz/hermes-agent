"""One recovery outbox file per logical owner.

``state/outbox/recovery.<project>.<owner>.json``. A null receipt is the
in-flight intent and is not replaced. Adoption writes the admission id
into that same record. Only a receipted record may be replaced.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from plugins.project_recovery.mapping import Err, Ok, matches_binding_id

SCHEMA = "project-recovery-outbox/1"


def outbox_path(state_dir: Path, project: str, owner: str) -> Path:
    """File for one ``recovery.<project>.<owner>`` key. Ids are binding ids."""
    return Path(state_dir) / "outbox" / f"recovery.{project}.{owner}.json"


def recovery_key(project: str, owner: str) -> str:
    return f"recovery:{project}:{owner}"


def recovery_label(project: str) -> str:
    return f"recovery-{project}"


def load_outbox(state_dir: Path, project: str, owner: str) -> dict | Err | None:
    """The stored record. None when the file is absent.

    An unreadable file, or one that is not an outbox record, is an error. The
    bytes stay where they are. A missing file is not that error.
    """
    path = outbox_path(state_dir, project, owner)
    if not path.is_file():
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError):
        return Err("unreadable")
    except json.JSONDecodeError:
        return Err("invalid")
    if not _valid_record(loaded):
        return Err("invalid")
    return loaded


def write_intent(
    state_dir: Path,
    *,
    project: str,
    owner: str,
    scan: int,
    intent_at: float,
    episodes: list[str],
) -> Ok | Err:
    """Write a new intent. An unreceipted file is left untouched."""
    refusal = _ids_refusal(project, owner, episodes)
    if refusal is not None:
        return refusal
    current = load_outbox(state_dir, project, owner)
    if isinstance(current, Err):
        return current
    if isinstance(current, dict) and current.get("receipt") is None:
        return Err("unreceipted")
    record = _record(
        project=project, owner=owner, scan=scan, intent_at=intent_at,
        episodes=list(episodes), message=None, receipt=None,
    )
    _store(state_dir, project, owner, record)
    return Ok(record)


def remember_message(
    state_dir: Path, project: str, owner: str, message_id: str,
) -> Ok | Err:
    """Store the plugin message id on the unreceipted intent. Receipt stays null."""
    if not matches_binding_id(message_id):
        return Err("binding_invalid")
    current = load_outbox(state_dir, project, owner)
    if isinstance(current, Err):
        return current
    if current is None:
        return Err("missing")
    if current.get("receipt") is not None:
        return Err("already_receipted")
    updated = dict(current)
    updated["message"] = message_id
    _store(state_dir, project, owner, updated)
    return Ok(updated)


def adopt_receipt(
    state_dir: Path, project: str, owner: str, admission_id: str,
) -> Ok | Err:
    """Write the admission id into the existing record. Does not mint a new file."""
    if not matches_binding_id(admission_id):
        return Err("binding_invalid")
    current = load_outbox(state_dir, project, owner)
    if isinstance(current, Err):
        return current
    if current is None:
        return Err("missing")
    updated = dict(current)
    updated["receipt"] = admission_id
    _store(state_dir, project, owner, updated)
    return Ok(updated)


def atomic_write(destination: Path, payload: str) -> None:
    """Temp file, fsync, then rename. The previous file stays until the rename."""
    directory = destination.parent
    directory.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=directory,
    )
    try:
        _write_temp(descriptor, temporary, destination, payload)
    except Exception:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise
    _fsync_directory(directory)


def _valid_record(loaded) -> bool:
    """An outbox record: string key, null or string receipt, binding-id episodes.

    ``schema`` is not required. A file that fails this is not an intent.
    """
    if not isinstance(loaded, dict):
        return False
    key = loaded.get("key")
    if not isinstance(key, str) or not key:
        return False
    if "receipt" in loaded and loaded["receipt"] is not None and not isinstance(loaded["receipt"], str):
        return False
    episodes = loaded.get("episodes")
    if not isinstance(episodes, list):
        return False
    return all(isinstance(item, str) and matches_binding_id(item) for item in episodes)


def _ids_refusal(project: str, owner: str, episodes: list[str]) -> Err | None:
    if not matches_binding_id(project) or not matches_binding_id(owner):
        return Err("binding_invalid")
    if any(not matches_binding_id(episode) for episode in episodes):
        return Err("binding_invalid")
    return None


def _record(*, project, owner, scan, intent_at, episodes, message, receipt) -> dict:
    return {
        "schema": SCHEMA,
        "owner": owner,
        "scan": scan,
        "intent_at": intent_at,
        "episodes": list(episodes),
        "label": recovery_label(project),
        "key": recovery_key(project, owner),
        "message": message,
        "receipt": receipt,
    }


def _store(state_dir: Path, project: str, owner: str, record: dict) -> None:
    payload = json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    atomic_write(outbox_path(state_dir, project, owner), payload)


def _write_temp(descriptor: int, temporary: str, destination: Path, payload: str) -> None:
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
