"""Usage readers. Every read is a read-only quota or billing GET: no model call, no tokens spent.

Claude, ChatGPT/Codex and OpenRouter go through Hermes's own ``agent.account_usage`` fetchers (the same
path as ``hermes usage``). SuperGrok has no Hermes fetcher, so it is read from the Grok CLI billing
endpoint with Hermes's own ``xai-oauth`` login, taken from the credential pool (which refreshes it
under Hermes's lock), never from the Grok CLI's 12-hour token.
"""
from __future__ import annotations

import json
import re
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable, Optional

SUPERGROK_BILLING_URL = "https://cli-chat-proxy.grok.com/v1/billing?format=credits"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _failed(sub_id: str, error: str) -> dict[str, Any]:
    return {"id": sub_id, "status": "failed", "attempted_at": _now_iso(), "error": error[:200]}


def _from_snapshot(sub_id: str, snapshot, classify: Callable[[str], Optional[str]]) -> dict[str, Any]:
    if snapshot is None:
        return _failed(sub_id, "no usage returned")
    if getattr(snapshot, "unavailable_reason", None):
        return _failed(sub_id, str(snapshot.unavailable_reason))
    windows = []
    for w in snapshot.windows:
        kind = classify(w.label or "")
        if kind is None:
            continue
        windows.append({"kind": kind, "label": w.label, "used_percent": w.used_percent, "reset_at": _iso(w.reset_at)})
    return {"id": sub_id, "status": "ok", "attempted_at": _now_iso(),
            "observed_at": snapshot.fetched_at.isoformat(), "plan": snapshot.plan,
            "windows": windows, "details": list(snapshot.details)}


def _classify_claude(label: str) -> Optional[str]:
    low = label.lower()
    if low == "current week":
        return "week"
    if low == "current session":
        return "short"
    return None  # model-specific weeks (Fable, Opus) are shown by Hermes but not paced


def _classify_codex(label: str) -> Optional[str]:
    low = label.lower()
    if "week" in low:
        return "week"
    if "5h" in low or "5-hour" in low or "hour" in low or "session" in low:
        return "short"
    return None


def read_claude(provider: str = "claude-subscription-directsdk-experimental") -> dict[str, Any]:
    from agent.account_usage import fetch_account_usage
    try:
        return _from_snapshot("claude", fetch_account_usage(provider), _classify_claude)
    except Exception as exc:  # a reader never breaks the collector
        return _failed("claude", f"{type(exc).__name__}: {exc}")


def read_codex() -> dict[str, Any]:
    from agent.account_usage import fetch_account_usage
    try:
        return _from_snapshot("codex", fetch_account_usage("openai-codex"), _classify_codex)
    except Exception as exc:
        return _failed("codex", f"{type(exc).__name__}: {exc}")


_MONEY = r"\$([0-9][0-9,]*\.?[0-9]*)"


def parse_openrouter_details(details: list[str]) -> dict[str, Optional[float]]:
    out: dict[str, Optional[float]] = {"balance": None, "today": None, "week": None, "month": None}
    text = " ".join(details)
    m = re.search(r"Credits balance:\s*" + _MONEY, text)
    if m:
        out["balance"] = float(m.group(1).replace(",", ""))
    for key, word in (("today", "today"), ("week", "this week"), ("month", "this month")):
        m = re.search(_MONEY + r"\s+" + word, text)
        if m:
            out[key] = float(m.group(1).replace(",", ""))
    return out


def read_openrouter() -> dict[str, Any]:
    from agent.account_usage import fetch_account_usage
    try:
        snap = fetch_account_usage("openrouter")
    except Exception as exc:
        return _failed("openrouter", f"{type(exc).__name__}: {exc}")
    if snap is None or getattr(snap, "unavailable_reason", None):
        return _failed("openrouter", str(getattr(snap, "unavailable_reason", None) or "no usage returned"))
    return {"id": "openrouter", "status": "ok", "attempted_at": _now_iso(),
            "observed_at": snap.fetched_at.isoformat(), "spend": parse_openrouter_details(list(snap.details))}


def parse_supergrok_billing(body: dict[str, Any]) -> dict[str, Any]:
    cfg = body.get("config") if isinstance(body.get("config"), dict) else {}
    period = cfg.get("currentPeriod") if isinstance(cfg.get("currentPeriod"), dict) else {}
    used = cfg.get("creditUsagePercent")
    windows = []
    if isinstance(used, (int, float)) and period.get("end"):
        windows.append({"kind": "week", "label": "Week", "used_percent": float(used), "reset_at": period.get("end"),
                        "start_at": period.get("start")})
    products = [{"product": p.get("product"), "used_percent": p.get("usagePercent")}
                for p in cfg.get("productUsage") or [] if isinstance(p, dict)]
    return {"windows": windows, "products": products}


def _xai_token() -> str:
    from agent.credential_pool import load_pool
    entry = load_pool("xai-oauth").select()
    if entry is None:
        raise RuntimeError("no xai-oauth login in the credential pool")
    return entry.runtime_api_key


def read_supergrok(token_fn: Callable[[], str] = _xai_token, timeout: float = 20.0) -> dict[str, Any]:
    try:
        token = token_fn()
        req = urllib.request.Request(SUPERGROK_BILLING_URL, headers={
            "Authorization": "Bearer " + token, "Accept": "application/json", "X-XAI-Token-Auth": "xai-grok-cli"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode())
    except Exception as exc:
        code = getattr(exc, "code", None)
        return _failed("supergrok", f"HTTP {code}" if code else f"{type(exc).__name__}: {exc}")
    parsed = parse_supergrok_billing(body)
    return {"id": "supergrok", "status": "ok", "attempted_at": _now_iso(), "observed_at": _now_iso(),
            "plan": None, **parsed}


READERS: dict[str, Callable[[], dict[str, Any]]] = {
    "claude": read_claude, "codex": read_codex, "supergrok": read_supergrok,
}
