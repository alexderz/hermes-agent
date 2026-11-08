"""Pure pace, eligibility, latch and on-demand logic. No I/O; every function takes ``now``.

Policy (Alex, 2026-10-24 .. 2026-11-08; vault rules.md 6-15, decisions/):
- slack = fraction left minus a straight line from 100% at window start to the reserve at reset.
- Exhausted, stale, failed or reset-pending readings are never eligible.
- A subscription inside its reserve is used only when nothing else is eligible.
- A short (5-hour) window is not paced; it is benched once less than ``short_window_min_left`` is left.
- The latch moves only when a challenger leads by ``latch_lead`` on two consecutive fresh samples.
- On-demand starts when every subscription has a fresh reading at least ``on_demand_enter`` over
  pace, and ends as soon as any eligible one is back on or under pace.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

WEEK_S = 7 * 86400

DEFAULTS: dict[str, Any] = {
    "stale_after_s": 2 * 3600,
    "reset_grace_s": 12 * 3600,
    "latch_lead": 0.10,
    "latch_samples": 2,
    "on_demand_enter": -0.10,
    "on_demand_exit": 0.0,
    "short_window_min_left": 3.0,
    "reserve": {"claude": 0.05, "supergrok": 0.05, "codex": 0.0},
}


def parse_ts(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def window_pace(used_percent: float, reset_at: datetime, now: datetime, *, period_s: int = WEEK_S,
                reserve: float = 0.0) -> dict[str, float]:
    """Slack and pace numbers for one window. ``p_points`` is slack in percentage points
    (positive = headroom, shown green; negative = over pace, shown red)."""
    start = reset_at - timedelta(seconds=period_s)
    elapsed = (now - start).total_seconds() / period_s
    u = min(1.0, max(0.0, elapsed))
    line = (1.0 - u) + u * reserve
    remaining = 1.0 - used_percent / 100.0
    slack = remaining - line
    return {
        "elapsed": round(u, 4),
        "pace_used_percent": round(100.0 * (1.0 - line), 1),
        "slack": round(slack, 4),
        "p_points": round(100.0 * slack, 1),
    }


def assess(sub: dict[str, Any], now: datetime, cfg: dict[str, Any]) -> dict[str, Any]:
    """Score one subscription reading. Returns eligibility, reason and pace numbers."""
    name = sub["id"]
    reserve = float(cfg["reserve"].get(name, 0.0))
    out: dict[str, Any] = {"id": name, "eligible": False, "reserve_only": False, "slack": None,
                           "fresh": False, "reason": ""}
    observed = parse_ts(sub.get("observed_at"))
    if sub.get("status") != "ok" or observed is None:
        out["reason"] = "no reading" if observed is None else f"reading failed ({sub.get('error') or 'unknown'})"
        if observed is None:
            return out
    age = (now - observed).total_seconds()
    out["age_s"] = int(age)
    if age > cfg["stale_after_s"]:
        out["reason"] = out["reason"] or "reading stale"
        return out
    out["fresh"] = sub.get("status") == "ok"
    if not out["fresh"]:
        return out
    week = next((w for w in sub.get("windows", []) if w.get("kind") == "week"), None)
    week_reset = parse_ts(week.get("reset_at")) if week else None
    if week is None or week.get("used_percent") is None or week_reset is None:
        prev_reset = parse_ts(sub.get("previous_week_reset_at"))
        if prev_reset and timedelta(0) <= now - prev_reset <= timedelta(seconds=cfg["reset_grace_s"]):
            out["reason"] = "new week not published yet"
        else:
            out["reason"] = "no weekly window"
        return out
    if week_reset <= now:
        out["reason"] = "new week not published yet"
        return out
    used = float(week["used_percent"])
    out.update(window_pace(used, week_reset, now, period_s=int(week.get("period_s") or WEEK_S), reserve=reserve))
    out["used_percent"] = used
    out["reset_at"] = week_reset.isoformat()
    if used >= 100.0:
        out["reason"] = "weekly limit reached"
        return out
    for w in sub.get("windows", []):
        if w.get("kind") != "short" or w.get("used_percent") is None:
            continue
        reset = parse_ts(w.get("reset_at"))
        left = 100.0 - float(w["used_percent"])
        if left < cfg["short_window_min_left"] and (reset is None or reset > now):
            out["reason"] = f"{w.get('label', 'short window')} nearly empty ({left:.0f}% left)"
            out["benched_until"] = reset.isoformat() if reset else None
            return out
    if 100.0 - used <= 100.0 * reserve:
        out["reserve_only"] = True
        out["reason"] = "in reserve"
    out["eligible"] = True
    return out


def update_latch(prev: dict[str, Any], scores: dict[str, dict[str, Any]], observed: dict[str, str],
                 cfg: dict[str, Any]) -> dict[str, Any]:
    """Advance the latch by one collector sample. ``observed`` maps id -> observed_at of this sample."""
    latch = {"incumbent": prev.get("incumbent"), "challenger": prev.get("challenger"),
             "streak": int(prev.get("streak") or 0), "seen": dict(prev.get("seen") or {}),
             "event": "held"}
    eligible = {k: s for k, s in scores.items() if s["eligible"] and not s["reserve_only"]}
    if not eligible:
        eligible = {k: s for k, s in scores.items() if s["eligible"]}
    if not eligible:
        latch.update(incumbent=None, challenger=None, streak=0, event="none eligible")
        latch["seen"].update(observed)
        return latch
    best = max(eligible, key=lambda k: eligible[k]["slack"])
    inc = latch["incumbent"]
    if inc not in eligible:
        latch.update(incumbent=best, challenger=None, streak=0,
                     event="first pick" if inc is None else f"{inc} not eligible")
    elif best != inc:
        lead = eligible[best]["slack"] - eligible[inc]["slack"]
        fresh = all(observed.get(k) and observed.get(k) != latch["seen"].get(k) for k in (best, inc))
        if lead + 1e-9 < cfg["latch_lead"]:
            latch.update(challenger=None, streak=0)
        elif fresh:
            latch["streak"] = latch["streak"] + 1 if latch["challenger"] == best else 1
            latch["challenger"] = best
            if latch["streak"] >= cfg["latch_samples"]:
                latch.update(incumbent=best, challenger=None, streak=0, event=f"moved from {inc}")
            else:
                latch["event"] = f"{best} leads by {lead:.2f} ({latch['streak']}/{cfg['latch_samples']})"
    else:
        latch.update(challenger=None, streak=0)
    latch["seen"].update(observed)
    return latch


def update_on_demand(active: bool, scores: dict[str, dict[str, Any]], cfg: dict[str, Any]) -> tuple[bool, str]:
    """Return (on_demand, reason). Missing or stale readings never start paid use."""
    paced = [s for s in scores.values() if s["fresh"] and s["slack"] is not None]
    if active:
        if any(s["eligible"] and s["slack"] >= cfg["on_demand_exit"] for s in paced):
            return False, "a subscription is back on pace"
        return True, "every subscription still over pace"
    if len(paced) == len(scores) and paced and all(s["slack"] <= cfg["on_demand_enter"] for s in paced):
        return True, "every subscription is 10 or more points over pace"
    return False, ""
