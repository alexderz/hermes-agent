"""Usage readers. Every read is a read-only quota or billing GET: no model call, no tokens spent.

Claude, ChatGPT/Codex and OpenRouter go through Hermes's own ``agent.account_usage`` fetchers (the same
path as ``hermes usage``). SuperGrok has no Hermes fetcher, so it is read from the Grok CLI billing
endpoint with Hermes's own ``xai-oauth`` login, taken from the credential pool (which refreshes it
under Hermes's lock), never from the Grok CLI's 12-hour token. Antigravity asks the official ``agy``
CLI to run ``/usage``, which that CLI handles itself outside generation.
"""
from __future__ import annotations

import json
import math
import os
import re
import subprocess
import urllib.request
from datetime import UTC, datetime, timedelta
from typing import Any, Callable, Optional

SUPERGROK_BILLING_URL = "https://cli-chat-proxy.grok.com/v1/billing?format=credits"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


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


# ``/usage`` is handled by the agy CLI itself, outside model generation. Auth stays inside that CLI.
AGY_TIMEOUT_S = 20.0
_AGY_ARGV = ("--print", "/usage", "--output-format", "json")
_AGY_MAX_BYTES = 262144
_USAGE_COUNTERS = ("input_tokens", "output_tokens", "thinking_tokens", "cache_read_tokens", "total_tokens")
_BUCKET_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,64}$")
_WINDOW = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,15}$")
_TEXT_LIMIT = 80


def _agy_executable() -> Optional[str]:
    from hermes_platform.resolver.core import locate_command
    found = locate_command("agy")
    if not found.found:
        return None
    command = found.command
    return command[0] if command else None


def _fraction(value: Any) -> Optional[float]:
    """A quota fraction in ``[0, 1]``. Booleans and non-finite numbers stay unknown."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, int) and not 0 <= value <= 1:
        return None
    try:
        number = float(value)
    except OverflowError:
        return None
    if not math.isfinite(number) or number < 0 or number > 1:
        return None
    return number


def _short_text(value: Any, limit: int = _TEXT_LIMIT) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    if not text:
        return None
    return text[:limit]


def _reset_at(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return text


def _zero_inference(payload: dict[str, Any]) -> bool:
    if payload.get("status") != "SUCCESS" or payload.get("conversation_id") != "":
        return False
    turns = payload.get("num_turns")
    if isinstance(turns, bool) or turns != 0:
        return False
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return False
    for key in _USAGE_COUNTERS:
        value = usage.get(key)
        if isinstance(value, bool) or value != 0:
            return False
    command = payload.get("command")
    return isinstance(command, dict) and command.get("name") == "usage"


def _bucket(item: Any) -> Optional[dict[str, Any]]:
    if not isinstance(item, dict):
        return None
    ident = item.get("id")
    if not isinstance(ident, str) or _BUCKET_ID.fullmatch(ident) is None:
        return None
    window = item.get("window")
    if not isinstance(window, str) or _WINDOW.fullmatch(window) is None:
        window = None
    return {"id": ident, "name": _short_text(item.get("name")), "window": window,
            "remaining_fraction": _fraction(item.get("remaining_fraction")),
            "reset_at": _reset_at(item.get("reset_time"))}


def _group(item: Any) -> Optional[dict[str, Any]]:
    if not isinstance(item, dict):
        return None
    name = _short_text(item.get("name"))
    buckets = item.get("buckets")
    if not name or not isinstance(buckets, list):
        return None
    return {"name": name, "buckets": [bucket for item in buckets if (bucket := _bucket(item))]}


def parse_agy_usage(payload: Any) -> dict[str, Any]:
    """Normalize one ``/usage`` payload. The error string never includes the body."""
    if not isinstance(payload, dict):
        return {"ok": False, "error": "agy usage returned malformed data"}
    if not _zero_inference(payload):
        return {"ok": False, "error": "agy usage did not return a quota result"}
    command = payload.get("command")
    data = command.get("data") if isinstance(command, dict) else None
    raw_groups = data.get("groups") if isinstance(data, dict) else None
    if not isinstance(raw_groups, list):
        return {"ok": False, "error": "agy usage returned malformed data"}
    if not raw_groups:
        return {"ok": False, "error": "agy usage returned no quota data"}
    parsed = [group for item in raw_groups if (group := _group(item))]
    if not parsed:
        return {"ok": False, "error": "agy usage returned no quota data"}
    return {"ok": True, "groups": parsed}


def _stdout_bytes(completed: Any) -> Optional[bytes]:
    stdout = getattr(completed, "stdout", None)
    if isinstance(stdout, str):
        return stdout.encode("utf-8", "replace")
    if isinstance(stdout, bytes):
        return stdout
    return None


def read_agy() -> dict[str, Any]:
    """Read Antigravity quota. A failure carries a fixed reason, never command output."""
    try:
        executable = _agy_executable()
    except Exception:
        return _failed("agy", "agy not found")
    if not executable:
        return _failed("agy", "agy not found")
    try:
        completed = subprocess.run(  # noqa: UP022 - stdin stays closed while both streams are captured
            [executable, *_AGY_ARGV], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=AGY_TIMEOUT_S, check=False)
    except subprocess.TimeoutExpired:
        return _failed("agy", "agy usage timed out")
    except OSError:
        return _failed("agy", "agy usage unavailable")
    except Exception:
        return _failed("agy", "agy usage unavailable")
    if getattr(completed, "returncode", None) != 0:
        return _failed("agy", "agy usage failed")
    raw = _stdout_bytes(completed)
    if not raw or len(raw) > _AGY_MAX_BYTES:
        return _failed("agy", "agy usage returned malformed data")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _failed("agy", "agy usage returned malformed data")
    parsed = parse_agy_usage(payload)
    if not parsed["ok"]:
        return _failed("agy", str(parsed["error"]))
    return {"id": "agy", "status": "ok", "attempted_at": _now_iso(), "observed_at": _now_iso(),
            "groups": parsed["groups"]}


READERS: dict[str, Callable[[], dict[str, Any]]] = {
    "claude": read_claude, "codex": read_codex, "supergrok": read_supergrok, "agy": read_agy,
}


# ---------------------------------------------------------- Cheaper Inference rates
#
# Pay-per-use prices, not a quota: the catalog the account pays, filtered to the models this
# Hermes is configured to use through ``custom:cheaperinference``. One read-only GET, no tokens.

CHEAPER_MODELS_URL = "https://api.cheaperinference.com/v1/models"
CHEAPER_USAGE_URL = "https://api.cheaperinference.com/v1/usage/daily"
CHEAPER_BALANCE_URL = "https://api.cheaperinference.com/v1/account/balance"
CHEAPER_MAX_BYTES = 8 * 1024 * 1024
CHEAPER_TIMEOUT_S = 20.0
_CHEAPER_KEY_ENVS = ("CHEAPERINFERENCE_API_KEY", "CI_MCP_BEARER_TOKEN")


def _cheaper_token() -> Optional[str]:
    for name in _CHEAPER_KEY_ENVS:
        value = os.environ.get(name)
        if value and value.strip():
            return value.strip()
    return None


def cheaper_configured_models(cfg: Optional[dict[str, Any]] = None) -> list[str]:
    """The model ids this Hermes routes through Cheaper Inference, in config order."""
    if cfg is None:
        try:
            from hermes_cli.config import load_config
            cfg = load_config() or {}
        except Exception:
            cfg = {}
    entry = ((cfg or {}).get("providers") or {}).get("cheaperinference") or {}
    models = [m for m in entry.get("models") or [] if isinstance(m, str) and m.strip()]
    default = (cfg or {}).get("model") or {}
    default_model = default.get("default") if isinstance(default, dict) else None
    if isinstance(default_model, str) and default_model and default_model not in models:
        models.append(default_model)
    return models


def cheaper_active_model(cfg: Optional[dict[str, Any]] = None) -> Optional[str]:
    """The configured default model, when it runs through Cheaper Inference."""
    if cfg is None:
        try:
            from hermes_cli.config import load_config
            cfg = load_config() or {}
        except Exception:
            cfg = {}
    default = (cfg or {}).get("model") or {}
    model = default.get("default") if isinstance(default, dict) else None
    provider = default.get("provider") if isinstance(default, dict) else None
    if isinstance(model, str) and model in cheaper_configured_models(cfg) and isinstance(provider, str) \
            and "cheaperinference" in provider:
        return model
    return None


def _price(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value.bit_length() > 1024:
        return None  # 2**1024 and larger cannot become a finite float
    try:
        if isinstance(value, (int, float)) or (isinstance(value, str) and value.strip()):
            number = float(value)
        else:
            return None
    except (OverflowError, ValueError):
        return None
    return number if math.isfinite(number) and number >= 0 else None


def _provider_name(value: Any) -> str:
    return value if isinstance(value, str) else ""


def parse_cheaper_models(payload: Any, wanted: list[str]) -> list[dict[str, Any]]:
    """Rows for the configured models, in config order. Unknown or unpriced models are skipped."""
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        return []
    by_id: dict[str, dict[str, Any]] = {}
    for item in payload["data"]:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            continue
        pricing = item.get("pricing")
        if not isinstance(pricing, dict):
            continue
        input_price = _price(pricing.get("input_per_million"))
        output_price = _price(pricing.get("output_per_million"))
        if input_price is None or output_price is None:
            continue
        row = {
            "id": item["id"],
            "provider": _provider_name(item.get("provider")) or _provider_name(item.get("owned_by")),
            "input": input_price,
            "output": output_price,
            "list_input": _price(pricing.get("list_input_per_million")),
            "list_output": _price(pricing.get("list_output_per_million")),
            "discount": _price(pricing.get("discount_percent")),
            "free": bool(item.get("is_free")),
        }
        by_id[item["id"]] = row
    rows = []
    for model_id in wanted:
        row = by_id.get(model_id)
        if row is not None:
            rows.append(row)
    return rows


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse redirects: the bearer token must never follow a Location to another host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_CHEAPER_OPENER = urllib.request.build_opener(_NoRedirect)


def _cheaper_urlopen(req, timeout: float) -> bytes:
    with _CHEAPER_OPENER.open(req, timeout=timeout) as resp:
        return resp.read(CHEAPER_MAX_BYTES + 1)


def parse_cheaper_spend(payload: Any, now: datetime) -> Optional[dict[str, Any]]:
    """UTC week/day/month spend from the daily feed, the same shape OpenRouter reports.

    Balance needs ``account:read`` on the key; without it the balance stays unknown, never zero.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get("daily_spend"), list):
        return None
    by_day: dict[str, float] = {}
    for row in payload["daily_spend"]:
        if not isinstance(row, dict):
            continue
        date = row.get("date")
        amount = _price(row.get("spend_usd"))
        if isinstance(date, str) and len(date) == 10 and amount is not None:
            by_day[date] = amount
    if not by_day:
        return None
    day = now.astimezone(UTC).date()
    monday = day - timedelta(days=day.weekday())
    first = day.replace(day=1)
    week = round(sum(v for d, v in by_day.items() if d >= monday.isoformat()), 6)
    month = round(sum(v for d, v in by_day.items() if d >= first.isoformat()), 6)
    return {"today": by_day.get(day.isoformat(), 0.0), "week": week, "month": month, "balance": None}


def _cheaper_get(url: str, token: str, timeout: float) -> Any:
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token, "Accept": "application/json"})
    raw = _cheaper_urlopen(req, timeout)
    if not raw or len(raw) > CHEAPER_MAX_BYTES:
        raise ValueError("payload rejected")
    return json.loads(raw.decode("utf-8"))


_BALANCE_KEYS = ("balance_usd", "available_usd", "wallet_balance_usd", "credits_usd", "balance")


def _find_balance(payload: Any, depth: int = 0) -> Optional[float]:
    """The wallet balance from an account payload; None when the shape is unknown."""
    if depth > 3:
        return None
    if isinstance(payload, dict):
        for key in _BALANCE_KEYS:
            if key in payload:
                amount = _price(payload[key])
                if amount is not None:
                    return amount
        for key in ("wallet", "account", "data"):
            if isinstance(payload.get(key), (dict, list)):
                found = _find_balance(payload[key], depth + 1)
                if found is not None:
                    return found
    elif isinstance(payload, list):
        for item in payload:
            found = _find_balance(item, depth + 1)
            if found is not None:
                return found
    return None


def read_cheaper_balance(token: str, timeout: float) -> Optional[float]:
    """Wallet balance, when the key carries ``account:read``. A missing scope stays unknown."""
    try:
        return _find_balance(_cheaper_get(CHEAPER_BALANCE_URL, token, timeout))
    except Exception:
        return None


def read_cheaper_inference(token_fn: Callable[[], Optional[str]] = _cheaper_token,
                           timeout: float = CHEAPER_TIMEOUT_S,
                           models_fn: Callable[[], list[str]] = cheaper_configured_models,
                           now: Optional[datetime] = None) -> dict[str, Any]:
    """Read Cheaper Inference spend and the rates for the models this Hermes uses.

    Total by design: any failure becomes a failed reading so the collector still writes state.
    Spend is the primary figure; the rate rows are detail that may be absent.
    """
    try:
        token = token_fn()
    except Exception:
        return _failed("cheaperinference", "key lookup failed")
    if not token:
        return _failed("cheaperinference", "no Cheaper Inference key")
    try:
        wanted = list(dict.fromkeys(models_fn()))
    except Exception:
        wanted = []
    moment = now or datetime.now(UTC)
    spend = None
    spend_error = None
    try:
        spend = parse_cheaper_spend(_cheaper_get(CHEAPER_USAGE_URL, token, timeout), moment)
        if spend is None:
            spend_error = "usage returned no daily spend"
        else:
            spend["balance"] = read_cheaper_balance(token, timeout)
    except Exception as exc:
        spend_error = f"usage unreadable ({type(exc).__name__})"
    rows: list[dict[str, Any]] = []
    active = None
    try:
        payload = _cheaper_get(CHEAPER_MODELS_URL, token, timeout) if wanted else None
        rows = parse_cheaper_models(payload, wanted) if payload is not None else []
        active = cheaper_active_model() if rows else None
    except Exception:
        rows, active = [], None
    if spend is None and not rows:
        return _failed("cheaperinference", spend_error or "no rates or spend")
    return {"id": "cheaperinference", "status": "ok", "attempted_at": _now_iso(), "observed_at": _now_iso(),
            "spend": spend, "spend_error": spend_error, "active_model": active, "models": rows}
