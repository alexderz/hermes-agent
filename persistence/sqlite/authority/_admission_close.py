"""User-close check for one new admit, on the connection the admit write already holds.

The physical row is the one ``_closed_by_user`` loads: the local receipt's current
target, otherwise the compression tip. A recoverable end reason is not a user close.
The check does not reopen the row.
"""

from __future__ import annotations

import json

from persistence.conversation.sessions import RECOVERABLE_END_REASONS
from persistence.core.errors import AuthorityRefusal
from persistence.sqlite.conversation._store.compression import _compression_tip_on
from persistence.sqlite.conversation._store.local import POLICY_PREFIX


def physical_target_on(holder, conn, logical_owner: str) -> str:
    """Receipt current target, else the compression tip, read on ``conn``."""
    try:
        saved = conn.execute(
            "SELECT value FROM state_meta WHERE key=?",
            (POLICY_PREFIX + logical_owner,),
        ).fetchone()
        if saved is None:
            raise KeyError(logical_owner)
        value = json.loads(saved[0])
        if not isinstance(value, dict):
            raise TypeError("receipt")
        entry = value["entry"]
        if not isinstance(entry, dict):
            raise KeyError("entry")
        target = entry.get("session_id")
        if not isinstance(target, str) or not target:
            raise TypeError("target")
        return target
    except (KeyError, TypeError, ValueError):
        return _compression_tip_on(holder, conn, logical_owner)


def refuse_user_close(holder, conn, check) -> None:
    """Raise ``closed-by-user`` when ``check`` names a user-closed physical row."""
    if check is None:
        return
    logical_owner = getattr(check, "logical_owner", None)
    if not isinstance(logical_owner, str) or not logical_owner:
        raise AuthorityRefusal("invalid_params", field="session")
    physical = physical_target_on(holder, conn, logical_owner)
    row = conn.execute(
        "SELECT ended_at, end_reason, runtime_revision FROM sessions WHERE id=?",
        (physical,),
    ).fetchone()
    if row is None or not row["ended_at"]:
        return
    if row["end_reason"] in RECOVERABLE_END_REASONS:
        return
    detail = (
        f"logical_owner={logical_owner} physical={physical} "
        f"runtime_revision={row['runtime_revision']}"
    )
    raise AuthorityRefusal("closed-by-user", field="session", detail=detail)
