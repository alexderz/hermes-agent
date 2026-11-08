"""model-routing dashboard backend, mounted at /api/plugins/model-routing/. Read-only."""
from __future__ import annotations

import asyncio
import importlib.util
import sys
import threading
import time
from pathlib import Path

from fastapi import APIRouter

router = APIRouter()
_ROOT = Path(__file__).resolve().parent.parent


def _core():
    """Load the plugin directory as a private package so core.py's relative imports work."""
    pkg = "_model_routing_dashboard_pkg"
    if pkg not in sys.modules:
        spec = importlib.util.spec_from_file_location(pkg, _ROOT / "__init__.py",
                                                      submodule_search_locations=[str(_ROOT)])
        m = importlib.util.module_from_spec(spec)
        sys.modules[pkg] = m
        spec.loader.exec_module(m)
    return importlib.import_module(pkg + ".core")


_REFRESH_LOCK = threading.Lock()
_REFRESH_MIN_S = 60.0
_last_refresh = 0.0


def _payload(core, s):
    od = s.get("on_demand") or {}
    return {
        "written_at": s.get("written_at"),
        "cards": core.cards(s) if s else [],
        "openrouter": (s.get("openrouter") or {}).get("spend"),
        "pick": s.get("pick"),
        "latch_event": (s.get("latch") or {}).get("event"),
        "on_demand": od,
        "warning": s.get("warning"),
        "text": core.render_text(s),
    }


@router.get("/state")
async def state():
    core = _core()
    return _payload(core, core.load_state())


def _collect_once():
    global _last_refresh
    core = _core()
    with _REFRESH_LOCK:
        if time.monotonic() - _last_refresh >= _REFRESH_MIN_S:
            core.collect()
            _last_refresh = time.monotonic()
        return _payload(core, core.load_state())


@router.post("/refresh")
async def refresh():
    """Read every provider now (read-only quota GETs, no tokens); at most once a minute."""
    return await asyncio.to_thread(_collect_once)
