"""Operator notice lines and the append-only notice log.

A line names the project, the episode, the class, and a subject id.
It does not include a session id, a path, or a credential.
"""

from __future__ import annotations

import json
from pathlib import Path

from plugins.project_recovery.snapshot import atomic_write


def format_notice(project_id, episode) -> str:
    subject = episode.get("subject") or {}
    label = subject.get("id") if isinstance(subject, dict) else "notice"
    return f"recovery {project_id}: {episode['id']} {episode['class']} {label}"


def load_notices(path: Path):
    if not path.exists():
        return ""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        return "state_unreadable"
    if text and not _lines_are_json(text):
        return "state_unreadable"
    return text


def append_notices(path: Path, records) -> None:
    previous = load_notices(path)
    if previous == "state_unreadable":
        raise ValueError("notices")
    if previous and not previous.endswith("\n"):
        previous += "\n"
    body = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
    atomic_write(path, previous + body)


def _lines_are_json(text: str) -> bool:
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            json.loads(line)
        except json.JSONDecodeError:
            return False
    return True


def notice_record(episode, scan, at):
    subject = episode.get("subject") or {}
    return {
        "scan": scan,
        "at": at,
        "id": episode.get("id"),
        "class": episode.get("class"),
        "subject": subject.get("id") if isinstance(subject, dict) else None,
    }
