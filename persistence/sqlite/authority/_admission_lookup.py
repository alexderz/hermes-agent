"""Read-only request lookup across an expanded target set.

The caller names the targets. This read does not walk lineage, does not submit, and does not
write the admission id back.
"""

from __future__ import annotations

import sqlite3

from persistence.authority.admissions import AdmissionLookup


def lookup_admission_by_request(holder, *, principal_id: str, request_id: str, target_ids,
                                payload_digest: str | None = None) -> AdmissionLookup:
    """One finished read, or ``unavailable`` when the read itself cannot be answered."""
    ids = _target_ids(target_ids)
    if ids is None or not isinstance(principal_id, str) or not principal_id:
        return AdmissionLookup("unavailable")
    if not isinstance(request_id, str) or not request_id:
        return AdmissionLookup("unavailable")
    if payload_digest is not None and not isinstance(payload_digest, str):
        return AdmissionLookup("unavailable")
    marks = ",".join("?" * len(ids))
    sql = (
        "SELECT admission_id, target_session_id, payload_digest FROM session_admissions "
        f"WHERE principal_id=? AND request_id=? AND target_session_id IN ({marks})"
    )
    try:
        with holder._read_ctx() as conn:
            rows = conn.execute(sql, (principal_id, request_id, *ids)).fetchall()
    except (sqlite3.Error, OSError):
        return AdmissionLookup("unavailable")
    if len(rows) > 1:
        return AdmissionLookup("conflict")
    if not rows:
        return AdmissionLookup("proven_not_found")
    row = rows[0]
    stored = row["payload_digest"]
    if payload_digest is not None and stored != payload_digest:
        return AdmissionLookup("conflict")
    return AdmissionLookup("found", row["admission_id"], row["target_session_id"], stored)


def _target_ids(target_ids) -> tuple[str, ...] | None:
    if isinstance(target_ids, (str, bytes)) or target_ids is None:
        return None
    try:
        ids = tuple(target_ids)
    except TypeError:
        return None
    if not ids or any(not isinstance(item, str) or not item for item in ids):
        return None
    return ids
