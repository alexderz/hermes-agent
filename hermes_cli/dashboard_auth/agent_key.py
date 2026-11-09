"""Local agent key: a machine credential for the operator's own automation on the dashboard host.

A gated dashboard (OAuth / password) has no non-interactive login for local scripts, so an
automation that wants to *start a turn inside the dashboard* (so phones and browsers attached to
that dashboard can open and steer the chat while it runs, and the turn survives the script
exiting) had to borrow a human's session. The agent key fills that gap without widening the
network surface:

* The key lives in a file (default ``<HERMES_HOME>/dashboard-agent.key``, override
  ``dashboard.agent_key.file``) that must be owner-only (no group/other bits) and >= 43 chars.
  The file is re-read when it changes; deleting it revokes the key immediately.
* It is accepted ONLY from a direct local connection: loopback peer AND no proxy forwarding
  header (``X-Forwarded-For`` / ``Forwarded`` / ``X-Real-IP``). A reverse proxy on the same host
  always adds one, so a request that arrives through the public edge never matches, even though
  its TCP peer is loopback.
* It plugs into the one verifier shared by the REST bearer leg and the gateway WebSocket
  ``?token=`` leg (``middleware._verify_access_token``), yielding a ``Session`` whose provider is
  ``agent-key``. It is never offered on the login page and never mints cookies.
"""
from __future__ import annotations

import hmac
import logging
import os
import stat
import threading
import time
from pathlib import Path
from typing import Any, Optional

from hermes_cli.dashboard_auth.base import Session

_log = logging.getLogger(__name__)

PROVIDER_NAME = "agent-key"
DEFAULT_FILENAME = "dashboard-agent.key"
MIN_KEY_CHARS = 43  # secrets.token_urlsafe(32)
_FORWARDING_HEADERS = ("x-forwarded-for", "forwarded", "x-real-ip")
_LOCAL_PEERS = frozenset({"127.0.0.1", "::1", "localhost"})

_lock = threading.Lock()
_cache: dict[str, Any] = {"path": None, "sig": None, "key": ""}


def key_path() -> Path:
    """Configured key file, or ``<HERMES_HOME>/dashboard-agent.key``."""
    raw = ""
    try:
        from hermes_cli.config import cfg_get, load_config

        raw = str(cfg_get(load_config(), "dashboard", "agent_key", "file", default="") or "").strip()
    except Exception:
        raw = ""
    if raw:
        return Path(os.path.expanduser(raw))
    from hermes_constants import get_hermes_home

    return get_hermes_home() / DEFAULT_FILENAME


def _load_key(path: Path) -> str:
    """The key, or ``""`` when absent, group/other-accessible, or too short (fail closed).
    Cached on (inode, mtime, size) so verification does one ``stat`` per request."""
    try:
        st = path.stat()
    except OSError:
        return ""
    sig = (st.st_ino, st.st_mtime_ns, st.st_size)
    with _lock:
        if _cache["path"] == str(path) and _cache["sig"] == sig:
            return _cache["key"]
    key = ""
    if st.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        _log.warning("dashboard agent key %s ignored: it must be owner-only (chmod 600)", path)
    else:
        try:
            key = path.read_text(encoding="utf-8").strip()
        except OSError:
            key = ""
        if key and len(key) < MIN_KEY_CHARS:
            _log.warning("dashboard agent key %s ignored: shorter than %d chars", path, MIN_KEY_CHARS)
            key = ""
    with _lock:
        _cache.update(path=str(path), sig=sig, key=key)
    return key


def request_is_direct_local(request: Any) -> bool:
    """Loopback TCP peer and no proxy forwarding header: a process on this host talking to the
    dashboard directly, not a client relayed through a local reverse proxy."""
    client = getattr(request, "client", None)
    if not client or (getattr(client, "host", "") or "") not in _LOCAL_PEERS:
        return False
    headers = getattr(request, "headers", None) or {}
    return not any(headers.get(h) for h in _FORWARDING_HEADERS)


def verify_agent_key(request: Any, token: str) -> Optional[Session]:
    """``Session`` for the local agent when ``token`` is the agent key on a direct local request,
    else ``None`` (callers fall through to the normal providers)."""
    if not token or not request_is_direct_local(request):
        return None
    key = _load_key(key_path())
    if not key or not hmac.compare_digest(token.encode("utf-8"), key.encode("utf-8")):
        return None
    return Session(
        user_id="agent:local", email="", display_name="Local agent", org_id="",
        provider=PROVIDER_NAME, expires_at=int(time.time()) + 300, access_token="", refresh_token="")


def _reset_cache_for_tests() -> None:
    with _lock:
        _cache.update(path=None, sig=None, key="")
