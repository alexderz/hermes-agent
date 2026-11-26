"""Episode identity, once-only reconcile, and persistence.

``result_unprocessed`` ignores the callback field for identity. Outage
episodes ignore the error string. Notice delivery moves to ``noticed``
only when the scanner prints the line.
"""

from __future__ import annotations

from plugins.project_recovery.snapshot import load_document, write_json

_UNCHANGED = object()


def load_episodes(path):
    loaded = load_document(path)
    if loaded is None:
        return []
    if loaded == "state_unreadable" or not isinstance(loaded, dict):
        return "state_unreadable"
    rows = loaded.get("episodes")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        return "state_unreadable"
    return rows


def write_episodes(path, episodes) -> None:
    write_json(path, {"episodes": episodes})


def identity_of(episode) -> tuple:
    evidence = dict(episode.get("evidence") or {})
    if episode.get("class") == "result_unprocessed":
        evidence.pop("callback", None)
    evidence.pop("error", None)
    return (episode.get("class"), _freeze(episode.get("subject")), _freeze(evidence))


def reconcile(
    existing,
    intents,
    *,
    scan,
    suppress,
    hold,
    close_workstreams,
    close_all,
    skip_workstreams,
):
    skipped = []
    pool = []
    for episode in existing:
        workstream = episode.get("workstream") or ""
        if workstream in skip_workstreams and not close_all:
            skipped.append(episode)
            continue
        pool.append(episode)
    closed = [episode for episode in pool if episode.get("closed_scan") is not None]
    open_rows = [episode for episode in pool if episode.get("closed_scan") is None]
    if close_all:
        return skipped + closed + [_close(episode, scan) for episode in open_rows]
    by_identity = {}
    for episode in open_rows:
        by_identity.setdefault(identity_of(episode), episode)
    kept_ids = set()
    produced = []
    for intent in intents:
        produced.append(_adopt(intent, by_identity, kept_ids, existing, produced, scan))
    for episode in open_rows:
        if id(episode) in kept_ids:
            continue
        if _retained(episode, suppress, hold):
            produced.append(episode)
            continue
        if (episode.get("workstream") or "") in close_workstreams:
            produced.append(_close(episode, scan))
            continue
        produced.append(_close(episode, scan))
    return skipped + closed + produced


def notice_lines(project_id, episodes, scan):
    """Printable lines. Does not mark noticed; the scanner does that after flush."""
    from plugins.project_recovery.notices import format_notice

    lines = []
    fresh = []
    for episode in episodes:
        if episode.get("closed_scan") is not None or not _notice_class(episode):
            continue
        delivery = episode.setdefault("delivery", {})
        if delivery.get("state") == "noticed":
            continue
        lines.append(format_notice(project_id, episode))
        fresh.append(episode.get("id"))
        episode["opened_scan"] = episode.get("opened_scan") or scan
    return lines, fresh


def _notice_class(episode) -> bool:
    delivery = episode.get("delivery") or {}
    if delivery.get("state") not in {None, "undelivered", "noticed"}:
        return False
    return episode.get("class") in _NOTICE


_NOTICE = frozenset(
    {
        "membership_change",
        "delivery_stalled",
        "no_progress",
        "tracker_incomplete",
        "tracker_recovered",
        "owner_closed",
        "owner_unreachable",
        "binding_invalid",
        "liveness_unknown",
        "receipt_outage",
    }
)


def _adopt(intent, by_identity, kept_ids, existing, produced, scan):
    draft = _draft(intent, scan, existing, produced)
    current = by_identity.get(identity_of(draft))
    if current is None:
        return draft
    kept_ids.add(id(current))
    if intent.class_name == "result_unprocessed":
        evidence = current.setdefault("evidence", {})
        evidence["callback"] = intent.evidence.get("callback")
    return current


def _draft(intent, scan, existing, produced):
    number = _next_number(scan, existing, produced)
    return {
        "id": f"E-{scan}-{number}",
        "class": intent.class_name,
        "subject": intent.subject,
        "workstream": intent.workstream,
        "owner": intent.owner,
        "evidence": dict(intent.evidence),
        "opened_scan": scan,
        "delivery": {
            "state": "undelivered",
            "message": None,
            "admission": None,
            "carried_in_turn": None,
            "settled_scan": None,
        },
        "notice": {"no_progress": None, "undeliverable": None},
        "closed_scan": None,
    }


def _next_number(scan, existing, produced) -> int:
    taken = {episode.get("id") for episode in list(existing) + list(produced)}
    number = 1
    while f"E-{scan}-{number}" in taken:
        number += 1
    return number


def _retained(episode, suppress, hold) -> bool:
    subject = episode.get("subject") or {}
    if subject.get("kind") != "handle":
        return False
    ident = subject.get("id")
    if episode.get("class") == "result_unprocessed" and ident in suppress:
        return True
    return ident in hold


def _close(episode, scan):
    if episode.get("closed_scan") is None:
        episode["closed_scan"] = scan
    return episode


def _freeze(value):
    if isinstance(value, dict):
        return tuple(sorted((key, _freeze(item)) for key, item in value.items()))
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def apply_no_progress(episodes, *, scan, owner_idle):
    """One notice after a carried wake has settled. Does not wake it again."""
    if owner_idle is not True:
        return []
    opened = []
    for episode in episodes:
        if episode.get("closed_scan") is not None:
            continue
        if episode.get("class") in _NOTICE or episode.get("class") == "no_progress":
            continue
        delivery = episode.get("delivery") or {}
        notice = episode.setdefault("notice", {})
        if delivery.get("state") != "carried":
            continue
        if notice.get("no_progress") is not None:
            continue
        notice["no_progress"] = scan
        opened.append(_progress_intent(episode))
    return opened


def _progress_intent(episode):
    from plugins.project_recovery.actionability import Intent

    return Intent(
        "no_progress",
        {"kind": "episode", "id": episode.get("id")},
        episode.get("workstream") or "",
        {"episode": episode.get("id"), "class": episode.get("class")},
        True,
        "",
    )
