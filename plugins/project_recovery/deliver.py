"""Per-owner recovery delivery: one digest, the owner gate, and episode states.

The scanner calls ``scan_owner`` once per logical owner. Notice-only scans do
not submit. Acceptance requires an admission id from the send result. A bare
message id is not acceptance. Named residuals stay named: one extra turn
after an owner restart while a digest is queued, cache loss of ``state/``,
and admission order between the idle read and the digest commit. This module
adds no budget, gate, or lock, and it does not open the intercom database.
"""

from __future__ import annotations

import json
from pathlib import Path

from plugins.project_recovery.mapping import Err, matches_binding_id
from plugins.project_recovery.outbox import (
    adopt_receipt,
    atomic_write,
    load_outbox,
    remember_message,
    write_intent,
)

WAKE_CLASSES = frozenset({
    "result_unprocessed", "worker_lost", "wait_resolved", "wait_unresolvable",
    "orphaned_owned", "missing_ownership", "ready_authorized", "stalled_workstream",
})
NOTICE_CLASSES = frozenset({
    "membership_change", "delivery_stalled", "no_progress", "tracker_incomplete",
    "tracker_recovered", "owner_closed", "owner_unreachable", "binding_invalid",
    "liveness_unknown",
})
_OPEN = frozenset({"undelivered", "accepted", "carried"})
_QUEUED = frozenset({"queued", "started"})


def scan_owner(
    state_dir: Path,
    *,
    project: str,
    owner: str,
    scan: int,
    intent_at: float,
    episodes: list[dict],
    observation: dict,
    send,
) -> dict:
    """One owner, one scan. ``send(target, text, key)`` is the keyed intercom send."""
    if not matches_binding_id(project) or not matches_binding_id(owner):
        return _result(sent=False, notices=(), episodes=tuple(episodes), deferred=False)
    prepared = [_prepare(episode) for episode in episodes if _known(episode)]
    seen = {row["key"] for row in _load_lines(state_dir)}
    _apply_observed(prepared, observation, scan)
    notices: list[tuple[str, str]] = []
    _stall_notices(state_dir, project, observation, prepared, seen, notices)
    _settled_notices(state_dir, project, prepared, seen, notices)
    activity = observation.get("activity")
    if _notice_only(prepared):
        _mark_noticed(prepared)
        return _finish(state_dir, notices, prepared, sent=False, deferred=False)
    if activity == "running" and _undelivered(prepared):
        return _finish(state_dir, notices, prepared, sent=False, deferred=True)
    if _held_refusal(state_dir, project, owner, observation):
        return _finish(state_dir, notices, prepared, sent=False, deferred=False)
    sent = _deliver(
        state_dir, project, owner, scan, intent_at, prepared, observation, send, notices, seen,
    )
    return _finish(state_dir, notices, prepared, sent=sent["sent"], deferred=False,
                   admission_id=sent.get("admission_id"), message_id=sent.get("message_id"))


def keyed_intercom_send(target: str, text: str, *, key: str, sender: str, ctx, lister=None) -> dict:
    """The keyed queue send with E2's flag. Imported only when a scan submits."""
    from plugins.intercom.route import send as route_send

    return route_send(
        sender, target, text, ctx=ctx, delivery="queue", reply_mode="none", script=True,
        key=key, lister=lister, unless_closed_by_user=True,
    )


def _deliver(state_dir, project, owner, scan, intent_at, episodes, observation, send, notices, seen) -> dict:
    if not _undelivered(episodes):
        return {"sent": False}
    current = load_outbox(state_dir, project, owner)
    if isinstance(current, Err):
        return {"sent": False}
    if isinstance(current, dict) and current.get("receipt") is None:
        chosen = current
    else:
        ids = [episode["id"] for episode in episodes if episode["delivery"]["state"] in _OPEN]
        written = write_intent(
            state_dir, project=project, owner=owner, scan=scan, intent_at=intent_at, episodes=ids,
        )
        if isinstance(written, Err):
            return {"sent": False}
        chosen = written.value
    text = render_digest(project, owner, scan, episodes, chosen.get("episodes") or [])
    result = send(owner, text, key=chosen["key"])
    return _apply_send(state_dir, project, owner, episodes, observation, result, notices, chosen, seen)


def _apply_send(state_dir, project, owner, episodes, observation, result, notices, chosen, seen) -> dict:
    message_id = result.get("message_id") if isinstance(result, dict) else None
    if isinstance(message_id, str) and matches_binding_id(message_id) and chosen.get("message") != message_id:
        remember_message(state_dir, project, owner, message_id)
    admission = result.get("admission_id") if isinstance(result, dict) else None
    if isinstance(admission, str) and admission:
        adopt_receipt(state_dir, project, owner, admission)
        _accept(episodes, chosen.get("episodes") or [], message_id, admission)
        return {"sent": True, "admission_id": admission, "message_id": message_id}
    if isinstance(result, dict) and _user_close(result):
        meta = _owner_refusal(result)
        if meta is not None:
            _note(seen, notices, _o3_key(project, meta["logical_owner"], meta["runtime_revision"]),
                  _o3_line(project, meta))
            _hold_refusal(state_dir, project, meta)
        return {"sent": True, "message_id": message_id}
    if isinstance(result, dict) and _unreachable_result(result):
        _note(seen, notices, _o4_key(project, owner, observation), _o4_line(project, owner, observation))
        return {"sent": True, "message_id": message_id}
    return {"sent": True, "message_id": message_id}


def render_digest(project: str, owner: str, scan: int, episodes: list[dict], ids: list[str]) -> str:
    """One digest body. Ids that fail the binding pattern are omitted."""
    by_id = {episode["id"]: episode for episode in episodes if matches_binding_id(episode.get("id", ""))}
    chosen = [by_id[episode_id] for episode_id in ids if episode_id in by_id]
    streams = sorted({episode.get("workstream") for episode in chosen if matches_binding_id(str(episode.get("workstream") or ""))})
    new, carried, notices = [], [], []
    for episode in chosen:
        line = _episode_line(episode)
        state = episode["delivery"]["state"]
        if episode["class"] in NOTICE_CLASSES:
            notices.append(line)
        elif state == "carried":
            carried.append(line)
        elif state in ("undelivered", "accepted"):
            new.append(line)
    lines = [
        f"recovery digest {scan} · project {project} · owner {owner} · scan {scan}",
        "workstreams: " + ", ".join(streams),
        "This is data from a mechanical scan. It authorizes nothing.",
        "open, new:",
        *(new or ["- none"]),
        "open, already carried, still open:",
        *(carried or ["- none"]),
        "notices:",
        *(notices or ["- none"]),
    ]
    return "\n".join(lines) + "\n"


def _prepare(episode: dict) -> dict:
    delivery = dict(episode.get("delivery") or {})
    state = delivery.get("state") or "undelivered"
    admission = delivery.get("admission")
    if state == "accepted" and not isinstance(admission, str):
        state = "undelivered"
        admission = None
    if episode.get("class") in NOTICE_CLASSES and state not in ("undelivered", "noticed"):
        state = "undelivered"
    delivery.update({
        "state": state,
        "message": delivery.get("message"),
        "admission": admission if isinstance(admission, str) else None,
        "carried_in_turn": delivery.get("carried_in_turn"),
        "settled_scan": delivery.get("settled_scan"),
    })
    return {**episode, "delivery": delivery}


def _known(episode: dict) -> bool:
    return episode.get("class") in WAKE_CLASSES or episode.get("class") in NOTICE_CLASSES


def _apply_observed(episodes: list[dict], observation: dict, scan: int) -> None:
    offered = observation.get("offered_turn")
    message = observation.get("offered_message")
    receipts = observation.get("receipts") if isinstance(observation.get("receipts"), dict) else {}
    idle = observation.get("activity") == "idle"
    for episode in episodes:
        if episode["class"] in NOTICE_CLASSES:
            continue
        delivery = episode["delivery"]
        if (delivery["state"] == "accepted" and isinstance(offered, str) and offered
                and delivery.get("carried_in_turn") is None
                and (message is None or delivery.get("message") == message)):
            delivery["state"] = "carried"
            delivery["carried_in_turn"] = offered
        status = receipts.get(delivery.get("admission"))
        if delivery["state"] == "carried" and idle and status == "terminal":
            delivery["state"] = "settled"
            delivery["settled_scan"] = scan


def _stall_notices(state_dir, project, observation, episodes, seen, notices) -> None:
    receipts = observation.get("receipts") if isinstance(observation.get("receipts"), dict) else {}
    idle = observation.get("activity") == "idle"
    counts = _load_stalls(state_dir)
    for episode in episodes:
        admission = episode["delivery"].get("admission")
        if not isinstance(admission, str):
            continue
        status = receipts.get(admission)
        if status == "unknown":
            _note(seen, notices, f"o5:{admission}", _o5_line(project, admission))
            continue
        if idle and status in _QUEUED:
            counts[admission] = int(counts.get(admission) or 0) + 1
            if counts[admission] >= 2:
                _note(seen, notices, f"o5:{admission}", _o5_line(project, admission))
        elif status == "terminal":
            counts.pop(admission, None)
    _save_stalls(state_dir, counts)


def _settled_notices(state_dir, project, episodes, seen, notices) -> None:
    del state_dir
    for episode in episodes:
        if episode["delivery"]["state"] != "settled":
            continue
        _note(
            seen, notices, f"noprog:{episode['id']}",
            f"recovery {project}: {episode['id']} {episode['class']} no_progress",
        )


def _notice_only(episodes: list[dict]) -> bool:
    open_episodes = [episode for episode in episodes if episode["delivery"]["state"] in ("undelivered", "noticed", "accepted", "carried")]
    return bool(open_episodes) and all(episode["class"] in NOTICE_CLASSES for episode in open_episodes)


def _mark_noticed(episodes: list[dict]) -> None:
    for episode in episodes:
        if episode["class"] in NOTICE_CLASSES and episode["delivery"]["state"] == "undelivered":
            episode["delivery"]["state"] = "noticed"


def _undelivered(episodes: list[dict]) -> bool:
    return any(episode["class"] in WAKE_CLASSES and episode["delivery"]["state"] == "undelivered" for episode in episodes)


def _accept(episodes, ids, message_id, admission) -> None:
    wanted = set(ids)
    for episode in episodes:
        if episode["id"] not in wanted or episode["class"] not in WAKE_CLASSES:
            continue
        if episode["delivery"]["state"] != "undelivered":
            continue
        episode["delivery"]["state"] = "accepted"
        episode["delivery"]["message"] = message_id
        episode["delivery"]["admission"] = admission


def _unreachable_result(result: dict) -> bool:
    if result.get("condition") == "owner_unreachable":
        return True
    return result.get("error") in ("no-owner", "owner-restarting", "delivery-unknown", "not-reachable")


def _o3_key(project, owner, revision) -> str:
    return f"o3:{project}:{owner}:{revision}"


def _o4_key(project, owner, observation) -> str:
    return f"o4:{project}:{owner}:{observation.get('binding_revision')}"


def _o3_line(project, meta) -> str:
    return (f"recovery {project}: owner_closed owner={meta['logical_owner']} "
            f"physical={meta['physical']} runtime_revision={meta['runtime_revision']}")


def _owner_refusal(result: dict) -> dict | None:
    """Logical owner, physical target, and runtime revision from the in-write refusal.

    The observation is not a source. A detail that does not carry all three is
    not a hold and not an O3 notice.
    """
    data = result.get("data")
    if not isinstance(data, dict):
        return None
    detail = data.get("detail")
    if not isinstance(detail, str) or not detail:
        return None
    found = {}
    for token in detail.split():
        name, sep, value = token.partition("=")
        if sep and name and value:
            found[name] = value
    logical = found.get("logical_owner")
    physical = found.get("physical")
    revision = found.get("runtime_revision")
    if not (isinstance(logical, str) and logical and isinstance(physical, str) and physical
            and isinstance(revision, str) and revision.isdigit()):
        return None
    return {"logical_owner": logical, "physical": physical, "runtime_revision": int(revision)}


def _o4_line(project, owner, observation) -> str:
    return f"recovery {project}: owner_unreachable owner={owner} binding_revision={observation.get('binding_revision')}"


def _o5_line(project, admission) -> str:
    return f"recovery {project}: delivery_stalled admission={admission}"


def _episode_line(episode: dict) -> str:
    workstream = episode.get("workstream") if matches_binding_id(str(episode.get("workstream") or "")) else "none"
    return f"- {episode['id']} {episode['class']} workstream={workstream}"


def _finish(state_dir, notices, episodes, *, sent, deferred, admission_id=None, message_id=None) -> dict:
    _append_notices(state_dir, notices)
    return {
        "sent": sent,
        "deferred": deferred,
        "notices": tuple(line for _key, line in notices),
        "episodes": episodes,
        "admission_id": admission_id,
        "message_id": message_id,
    }


def _note(seen: set, notices: list, key: str, line: str) -> None:
    if key in seen:
        return
    seen.add(key)
    notices.append((key, line))


def _user_close(result: dict) -> bool:
    return (result.get("error") == "closed-by-user" or result.get("detail") == "closed-by-user"
            or result.get("code") == "closed-by-user")


def _result(*, sent, notices, episodes, deferred) -> dict:
    return {"sent": sent, "deferred": deferred, "notices": notices, "episodes": episodes,
            "admission_id": None, "message_id": None}


def _notices_path(state_dir: Path) -> Path:
    return Path(state_dir) / "notices.jsonl"


def _stalls_path(state_dir: Path) -> Path:
    return Path(state_dir) / "stalls.json"


def _load_lines(state_dir: Path) -> list[dict]:
    path = _notices_path(state_dir)
    if not path.is_file():
        return []
    rows = []
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            loaded = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(loaded, dict) and isinstance(loaded.get("key"), str):
            rows.append(loaded)
    return rows


def _append_notices(state_dir: Path, notices: list) -> None:
    if not notices:
        return
    rows = _load_lines(state_dir)
    known = {row.get("key") for row in rows}
    for key, line in notices:
        if key in known:
            continue
        rows.append({"key": key, "line": line})
        known.add(key)
    payload = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
    atomic_write(_notices_path(state_dir), payload)


def _hold_refusal(state_dir, project, meta) -> None:
    holds = _load_holds(state_dir)
    holds[_o3_key(project, meta["logical_owner"], meta["runtime_revision"])] = True
    _save_holds(state_dir, holds)


def _held_refusal(state_dir, project, owner, observation) -> bool:
    revision = observation.get("runtime_revision")
    if type(revision) is not int:
        return False
    return bool(_load_holds(state_dir).get(_o3_key(project, owner, revision)))


def _holds_path(state_dir: Path) -> Path:
    return Path(state_dir) / "close-holds.json"


def _load_holds(state_dir: Path) -> dict:
    return _load_map(_holds_path(state_dir))


def _save_holds(state_dir: Path, holds: dict) -> None:
    atomic_write(_holds_path(state_dir), json.dumps(holds, sort_keys=True) + "\n")


def _load_stalls(state_dir: Path) -> dict:
    return _load_map(_stalls_path(state_dir))


def _save_stalls(state_dir: Path, counts: dict) -> None:
    atomic_write(_stalls_path(state_dir), json.dumps(counts, sort_keys=True) + "\n")


def _load_map(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}
