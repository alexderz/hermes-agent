"""Collector, state file and status rendering for model-routing.

State lives in ``<HERMES_HOME>/plugin-data/model-routing/state.json`` (written atomically, 0600) with a
small ``history.jsonl`` beside it (one line per sample, no prompt text, capped at ~2 MB).
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

try:  # loaded as a Hermes plugin package
    from . import pace, readers
except ImportError:  # loaded flat (tests)
    import pace  # type: ignore
    import readers  # type: ignore

SCHEMA = 1
HISTORY_MAX_BYTES = 2 * 1024 * 1024

SUBSCRIPTIONS: dict[str, dict[str, str]] = {
    "claude": {"name": "Claude", "plan": "Max 20x", "provider": "claude-subscription-directsdk-experimental",
               "model": "claude-opus-5-5"},
    "codex": {"name": "ChatGPT", "plan": "Pro Lite", "provider": "openai-codex", "model": "gpt-6.1-sol"},
    "supergrok": {"name": "SuperGrok", "plan": "Heavy", "provider": "xai-oauth", "model": "grok-4.7"},
}


def data_dir() -> Path:
    try:
        from hermes_constants import get_hermes_home
        home = Path(get_hermes_home())
    except Exception:
        home = Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")
    d = home / "plugin-data" / "model-routing"
    d.mkdir(parents=True, exist_ok=True, mode=0o700)
    return d


def load_state(path: Optional[Path] = None) -> dict[str, Any]:
    path = path or data_dir() / "state.json"
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def _write_atomic(path: Path, data: dict[str, Any]) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".state-", suffix=".json")
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(data, fh, indent=1, sort_keys=True)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _merge_reading(prev: Optional[dict[str, Any]], new: dict[str, Any]) -> dict[str, Any]:
    """Keep the last good reading when a read fails; remember the previous week's reset for grace."""
    if new.get("status") == "ok":
        merged = dict(new)
        prev_week = next((w for w in (prev or {}).get("windows", []) if w.get("kind") == "week"), None)
        new_week = next((w for w in new.get("windows", []) if w.get("kind") == "week"), None)
        if prev_week and not new_week:
            merged["previous_week_reset_at"] = prev_week.get("reset_at")
        elif prev:
            merged["previous_week_reset_at"] = (prev or {}).get("previous_week_reset_at")
        return merged
    if prev and prev.get("observed_at"):
        kept = dict(prev)
        kept.update(status="failed", error=new.get("error"), attempted_at=new.get("attempted_at"))
        return kept
    return new


def collect(*, now: Optional[datetime] = None, read: Optional[dict[str, Callable[[], dict]]] = None,
            read_openrouter: Optional[Callable[[], dict]] = None, path: Optional[Path] = None,
            cfg: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Read every subscription once, score, advance the latch and write the state file."""
    cfg = {**pace.DEFAULTS, **(cfg or {})}
    path = path or data_dir() / "state.json"
    prev = load_state(path)
    read = read or readers.READERS
    subs: dict[str, Any] = {}
    for sub_id, fn in read.items():
        subs[sub_id] = _merge_reading((prev.get("subscriptions") or {}).get(sub_id), fn())
    orr = (read_openrouter or readers.read_openrouter)()
    if orr.get("status") != "ok" and (prev.get("openrouter") or {}).get("observed_at"):
        orr = {**prev["openrouter"], "status": "failed", "error": orr.get("error")}
    now = now or datetime.now(timezone.utc)
    scores = {k: pace.assess(v, now, cfg) for k, v in subs.items()}
    observed = {k: v.get("observed_at") for k, v in subs.items() if v.get("status") == "ok"}
    latch = pace.update_latch(prev.get("latch") or {}, scores, observed, cfg)
    on_demand, od_reason = pace.update_on_demand(bool((prev.get("on_demand") or {}).get("active")), scores, cfg)
    unavailable = sorted(k for k, s in scores.items() if not s["fresh"])
    prev_warn = prev.get("warning") or {}
    warning = {"active": bool(unavailable), "subscriptions": unavailable,
               "since": prev_warn.get("since") if prev_warn.get("active") and unavailable else
               (now.isoformat() if unavailable else None)}
    transition = None
    if warning["active"] and not prev_warn.get("active"):
        transition = "usage data unavailable"
    elif prev_warn.get("active") and not warning["active"]:
        transition = "usage data back to normal"
    pick = None
    if on_demand:
        pick = {"subscription": "on-demand", "provider": "openrouter", "model": None}
    elif latch.get("incumbent"):
        t = SUBSCRIPTIONS.get(latch["incumbent"], {})
        pick = {"subscription": latch["incumbent"], "provider": t.get("provider"), "model": t.get("model")}
    state = {"schema": SCHEMA, "written_at": now.isoformat(), "subscriptions": subs, "scores": scores,
             "openrouter": orr, "latch": latch, "pick": pick,
             "on_demand": {"active": on_demand, "reason": od_reason}, "warning": warning,
             "last_transition": transition or prev.get("last_transition")}
    _write_atomic(path, state)
    _append_history(path.parent / "history.jsonl", {
        "ts": now.isoformat(), "pick": (pick or {}).get("subscription"), "event": latch.get("event"),
        "on_demand": on_demand, "transition": transition,
        "slack": {k: s.get("slack") for k, s in scores.items()},
        "used": {k: s.get("used_percent") for k, s in scores.items()},
        "fresh": {k: s["fresh"] for k, s in scores.items()}})
    return state


def _append_history(path: Path, row: dict[str, Any]) -> None:
    try:
        if path.exists() and path.stat().st_size > HISTORY_MAX_BYTES:
            path.replace(path.with_suffix(".jsonl.1"))
        with open(path, "a") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
        os.chmod(path, 0o600)
    except OSError:
        pass


# ---------------------------------------------------------------- rendering

def _fmt_reset(iso: Optional[str]) -> str:
    dt = pace.parse_ts(iso)
    if not dt:
        return "?"
    try:
        from zoneinfo import ZoneInfo
        dt = dt.astimezone(ZoneInfo("America/Chicago"))
    except Exception:
        pass
    return dt.strftime("%a %-I:%M %p")


def cards(state: dict[str, Any]) -> list[dict[str, Any]]:
    """One card per subscription, most over pace first (sorted by used minus pace)."""
    out = []
    for sub_id, s in (state.get("scores") or {}).items():
        meta = SUBSCRIPTIONS.get(sub_id, {"name": sub_id, "plan": ""})
        reading = (state.get("subscriptions") or {}).get(sub_id) or {}
        short = next((w for w in reading.get("windows", []) if w.get("kind") == "short"), None)
        # Alex's format "98%  P: -47%": the sign is headroom against pace (minus = over pace, red).
        delta = s.get("p_points")
        out.append({
            "id": sub_id, "name": meta["name"], "plan": meta.get("plan"), "used_percent": s.get("used_percent"),
            "pace_delta": delta, "pace_used_percent": s.get("pace_used_percent"), "reset_at": s.get("reset_at"),
            "reset_label": _fmt_reset(s.get("reset_at")), "eligible": s["eligible"], "fresh": s["fresh"],
            "reason": s.get("reason") or ("in use" if (state.get("pick") or {}).get("subscription") == sub_id else "ok"),
            "short_used_percent": short.get("used_percent") if short else None,
            "observed_at": reading.get("observed_at"),
            "picked": (state.get("pick") or {}).get("subscription") == sub_id,
        })
    out.sort(key=lambda c: (c["pace_delta"] is None, c["pace_delta"] or 0))
    return out


def render_text(state: dict[str, Any]) -> str:
    if not state:
        return "Model routing: no usage collected yet (the collector runs every 15 minutes)."
    lines = ["Subscription usage (weekly), most over pace first:"]
    for c in cards(state):
        if c["used_percent"] is None:
            lines.append(f"  {c['name']} {c['plan']}: no reading ({c['reason']})")
            continue
        sign = "+" if c["pace_delta"] > 0 else ""
        status = "over pace" if c["pace_delta"] < 0 else "under pace"
        short = f", 5-hour {c['short_used_percent']:.0f}%" if c["short_used_percent"] is not None else ""
        mark = "  <- current pick" if c["picked"] else ""
        lines.append(f"  {c['name']} {c['plan']}: {c['used_percent']:.0f}%  P: {sign}{c['pace_delta']:.0f}% "
                     f"({status}{short}), resets {c['reset_label']}"
                     f"{'' if c['eligible'] else ' - not eligible: ' + c['reason']}{mark}")
    o = (state.get("openrouter") or {}).get("spend") or {}
    if o:
        lines.append(f"  OpenRouter (pay per use): ${o.get('today') or 0:.2f} today, ${o.get('week') or 0:.2f} this week, "
                     f"${o.get('month') or 0:.2f} this month; balance ${o.get('balance') or 0:.2f}")
    pick = state.get("pick")
    od = state.get("on_demand") or {}
    if od.get("active"):
        lines.append(f"Routing would use on-demand OpenRouter: {od.get('reason')}.")
    elif pick:
        lines.append(f"Routing would pick: {SUBSCRIPTIONS.get(pick['subscription'], {}).get('name', pick['subscription'])} "
                     f"({pick['provider']} / {pick['model']}); latch: {(state.get('latch') or {}).get('event')}.")
    else:
        lines.append("Routing has no pick (no eligible subscription).")
    if (state.get("warning") or {}).get("active"):
        lines.append("Warning: usage data unavailable for " + ", ".join(state["warning"]["subscriptions"]) + ".")
    lines.append(f"Read at {_fmt_reset(state.get('written_at'))} Central. Advisory only: routing does not move work yet.")
    return "\n".join(lines)
