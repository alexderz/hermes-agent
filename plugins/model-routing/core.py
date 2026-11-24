"""Collector, state file and status rendering for model-routing.

State lives in ``<HERMES_HOME>/plugin-data/model-routing/state.json`` (written atomically, 0600) with a
small ``history.jsonl`` beside it (one line per sample, no prompt text, capped at ~2 MB).
"""
from __future__ import annotations

import json
import math
import os
import re
import tempfile
from datetime import UTC, datetime
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

# Antigravity reset times move forward even when a bucket is unused, so a pace line would be
# invented. The meter shows the reading; the latch, pick and on-demand tier never see it.
DISPLAY_ONLY = frozenset({"agy"})
DISPLAY_NAMES = {"agy": "Antigravity"}


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
            read_openrouter: Optional[Callable[[], dict]] = None,
            read_cheaper: Optional[Callable[[], dict]] = None,
            path: Optional[Path] = None,
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
    try:
        cheaper = (read_cheaper or readers.read_cheaper_inference)()
    except Exception as exc:  # the collector always writes state, even if a reader escapes
        cheaper = {"id": "cheaperinference", "status": "failed",
                   "attempted_at": datetime.now(UTC).isoformat(), "error": type(exc).__name__}
    if cheaper.get("status") != "ok" and (prev.get("cheaperinference") or {}).get("observed_at"):
        cheaper = {**prev["cheaperinference"], "status": "failed", "error": cheaper.get("error")}
    now = now or datetime.now(UTC)
    scored = {k: v for k, v in subs.items() if k not in DISPLAY_ONLY}
    scores = {k: pace.assess(v, now, cfg) for k, v in scored.items()}
    observed = {k: v.get("observed_at") for k, v in scored.items() if v.get("status") == "ok"}
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
             "openrouter": orr, "cheaperinference": cheaper, "latch": latch, "pick": pick,
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


def _remaining_percent(fraction: Any) -> Optional[float]:
    """Percent remaining. Rounding must not turn a positive fraction into zero."""
    if isinstance(fraction, bool) or not isinstance(fraction, (int, float)):
        return None
    # 2**1024 and larger cannot become a finite float. Reject them before conversion.
    if isinstance(fraction, int) and fraction.bit_length() > 1024:
        return None
    try:
        number = float(fraction)
    except OverflowError:
        return None
    if not math.isfinite(number):
        return None
    percent = number * 100.0
    if not math.isfinite(percent):
        return None
    if percent > 0.0 and round(percent, 6) == 0.0:
        return percent
    return round(percent, 6)


def agy_group_tag(name: str) -> str:
    """Compact chip tag for one model group. Argon is checked before Gemini."""
    low = name.casefold()
    if "argon" in low:
        return "Ar"
    if "claude" in low or "gpt" in low:
        return "CG"
    if "gemini" in low:
        return "G"
    parts = [part for part in re.split(r"[^A-Za-z0-9]+", name) if part]
    if len(parts) >= 2:
        return "".join(part[0] for part in parts[:3]).upper()
    if parts:
        return parts[0][:2]
    return "?"


def _window_word(window: Any) -> str:
    if window == "weekly":
        return "weekly"
    if window == "5h":
        return "5-hour"
    if isinstance(window, str) and window:
        return window
    return "window"


def format_remaining(percent: Any) -> str:
    if isinstance(percent, bool) or not isinstance(percent, (int, float)):
        return "–"
    number = float(percent)
    if not math.isfinite(number):
        return "–"
    if 0 < number < 1:
        return "<1%"
    return f"{round(number):.0f}%"


def _agy_bucket_card(bucket: dict[str, Any]) -> dict[str, Any]:
    reset_at = bucket.get("reset_at")
    return {"id": bucket.get("id"), "name": bucket.get("name"), "window": bucket.get("window"),
            "remaining_percent": _remaining_percent(bucket.get("remaining_fraction")),
            "reset_at": reset_at, "reset_label": _fmt_reset(reset_at) if reset_at else "?"}


def _agy_group_cards(sub: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for group in sub.get("groups") or []:
        if not isinstance(group, dict) or not group.get("name"):
            continue
        buckets = [_agy_bucket_card(bucket) for bucket in group.get("buckets") or [] if isinstance(bucket, dict)]
        out.append({"name": group["name"], "tag": agy_group_tag(str(group["name"])), "buckets": buckets})
    return out


def _lowest_weekly(groups: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    best: Optional[dict[str, Any]] = None
    for group in groups:
        for bucket in group["buckets"]:
            if bucket.get("window") != "weekly":
                continue
            percent = bucket.get("remaining_percent")
            if percent is None:
                continue
            if best is None or percent < best["remaining_percent"]:
                best = {"group_name": group["name"], "tag": group["tag"], "window": "weekly",
                        "bucket_id": bucket.get("id"), "remaining_percent": percent,
                        "reset_at": bucket.get("reset_at"), "reset_label": bucket.get("reset_label")}
    return best


def _agy_fresh(sub: Optional[dict[str, Any]], now: datetime, cfg: dict[str, Any]) -> tuple[bool, str]:
    if not sub:
        return False, "no reading"
    observed = pace.parse_ts(sub.get("observed_at"))
    if observed is None:
        return False, "no reading"
    if sub.get("status") != "ok":
        return False, "reading failed"
    if (now - observed).total_seconds() > cfg["stale_after_s"]:
        return False, "reading stale"
    return True, ""


def agy_view(sub: Optional[dict[str, Any]], now: datetime, cfg: dict[str, Any]) -> dict[str, Any]:
    """One display card. Stale and failed readings keep no percentage on the card."""
    fresh, reason = _agy_fresh(sub, now, cfg)
    groups = _agy_group_cards(sub) if fresh and sub else []
    return {"id": "agy", "name": DISPLAY_NAMES["agy"], "plan": None, "display_only": True,
            "used_percent": None, "pace_delta": None, "pace_used_percent": None, "reset_at": None,
            "reset_label": None, "eligible": False, "fresh": fresh, "reason": reason,
            "short_used_percent": None, "observed_at": sub.get("observed_at") if sub else None,
            "picked": False, "summary": _lowest_weekly(groups) if groups else None, "groups": groups}


def _render_agy(card: dict[str, Any]) -> list[str]:
    if not card.get("fresh") or not card.get("groups"):
        return [f"  Antigravity: {card.get('reason') or 'no reading'}"]
    lines = ["  Antigravity (separate model groups, not paced):"]
    for group in card["groups"]:
        for bucket in group.get("buckets") or []:
            lines.append(f"    {group['name']} {_window_word(bucket.get('window'))}: "
                         f"{format_remaining(bucket.get('remaining_percent'))} remaining, "
                         f"resets {bucket.get('reset_label') or '?'}")
    summary = card.get("summary")
    if summary:
        lines.append(f"    Lowest weekly: {summary['group_name']} ({summary['tag']}) "
                     f"{format_remaining(summary['remaining_percent'])} remaining. Other groups are separate.")
    else:
        lines.append("    No weekly group reading. Other groups are separate.")
    return lines


def cards(state: dict[str, Any], now: Optional[datetime] = None) -> list[dict[str, Any]]:
    """Paced subscriptions first, then the display-only Antigravity card when state has readings."""
    out = []
    for sub_id, s in (state.get("scores") or {}).items():
        if sub_id in DISPLAY_ONLY:
            continue
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
    if "scores" in state or "subscriptions" in state:
        moment = now or datetime.now(UTC)
        out.append(agy_view((state.get("subscriptions") or {}).get("agy"), moment, pace.DEFAULTS))
    return out


def render_text(state: dict[str, Any], now: Optional[datetime] = None) -> str:
    if not state:
        return "Model routing: no usage collected yet (the collector runs every 15 minutes)."
    lines = ["Subscription usage (weekly), most over pace first:"]
    for c in cards(state, now):
        if c.get("display_only"):
            lines.extend(_render_agy(c))
            continue
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
    ci = state.get("cheaperinference") or {}
    if ci.get("status") == "ok":
        spend = ci.get("spend") or {}
        if spend:
            lines.append(f"  Cheaper Inference (pay per use): ${spend.get('today') or 0:.2f} today, "
                         f"${spend.get('week') or 0:.2f} this week, ${spend.get('month') or 0:.2f} this month")
        elif ci.get("spend_error"):
            lines.append(f"  Cheaper Inference (pay per use): spend unavailable ({ci['spend_error']})")
        if ci.get("models"):
            lines.append("    Model rates ($/M tokens in / out):")
            for row in ci["models"]:
                off = f", {row['discount']:.0f}% off list" if row.get("discount") else ""
                mark = "  <- current model" if ci.get("active_model") == row.get("id") else ""
                lines.append(f"      {row['id']}: ${row['input']:.4g} in / ${row['output']:.4g} out{off}{mark}")
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
