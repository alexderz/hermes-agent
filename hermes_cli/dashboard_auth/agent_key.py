"""Local agent key: a machine credential for the operator's own automation on the dashboard host.

A gated dashboard (OAuth / password) has no non-interactive login for local scripts, so an
automation that wants to *start a turn inside the dashboard* (so phones and browsers attached to
that dashboard can open and steer the chat while it runs, and the turn survives the script
exiting) had to borrow a human's session. The agent key fills that gap without widening the
network surface:

* The key lives in a file (default ``<HERMES_HOME>/dashboard-agent.key``, override
  ``dashboard.agent_key.file``) that must be a regular file owned by the dashboard's user with no
  group/other bits, holding >= 43 chars. It is re-read when the file changes (content, mode or
  owner); deleting it revokes the key immediately.
* It is accepted only on the bearer (``Authorization``) and gateway WebSocket ``?token=`` legs,
  never from a cookie, and only on a request whose TCP peer is loopback and which carries no
  proxy forwarding header. An HTTP reverse proxy on the same host (caddy here) adds
  ``X-Forwarded-For``, so traffic through the public edge never matches. Loopback alone does not
  prove a local process (SSH ``-L`` tunnels and L4 proxies also arrive as loopback): the key
  itself is the secret, and it grants what the dashboard's own user can do, including the
  terminal (``/api/pty``).
* It cannot be exchanged for credentials that work elsewhere: ``/api/auth/ws-ticket`` refuses an
  agent-key session.
* The session's identity is ``dashboard.agent_key.user_id`` (default ``agent:local``). Sessions
  created with the key record it as their auth user, which memory providers see as the runtime
  user; set it to the operator's id to share their memory peer.
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
DEFAULT_USER_ID = "agent:local"
MIN_KEY_CHARS = 43  # secrets.token_urlsafe(32)
# Any of these means "relayed by a proxy". Presence, not value, is what counts.
_FORWARDING_HEADERS = (
    "x-forwarded-for", "forwarded", "x-real-ip", "via", "x-forwarded-host", "x-forwarded-proto",
    "cf-connecting-ip", "true-client-ip")
_LOCAL_PEERS = frozenset({"127.0.0.1", "::1"})

_lock = threading.Lock()
_cache: dict[str, Any] = {"path": None, "sig": None, "key": ""}


def _section() -> dict:
    try:
        from hermes_cli.config import cfg_get, load_config_readonly

        section = cfg_get(load_config_readonly(), "dashboard", "agent_key", default=None)
    except Exception:
        return {}
    return section if isinstance(section, dict) else {}


def key_path() -> Path:
    """Configured key file, or ``<HERMES_HOME>/dashboard-agent.key``."""
    raw = str(_section().get("file") or "").strip()
    if raw:
        return Path(os.path.expanduser(raw))
    from hermes_constants import get_hermes_home

    return get_hermes_home() / DEFAULT_FILENAME


def _read_owner_only(path: Path) -> str:
    """File content when it is a regular, owner-only file of this process's user; else ``""``.
    Opened with ``O_NOFOLLOW`` and checked on the opened descriptor (no stat/open race)."""
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            _log.warning("dashboard agent key %s ignored: not a regular file", path)
            return ""
        if hasattr(os, "geteuid") and st.st_uid != os.geteuid():
            _log.warning("dashboard agent key %s ignored: not owned by the dashboard's user", path)
            return ""
        if st.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
            _log.warning("dashboard agent key %s ignored: it must be owner-only (chmod 600)", path)
            return ""
        return os.read(fd, 4096).decode("utf-8").strip()
    finally:
        os.close(fd)


def _load_key(path: Path) -> str:
    """The key, or ``""`` (absent, unsafe, unreadable, undecodable or too short: fail closed).
    Cached on the file's identity, content stamps, mode and owner, so ``chmod``/``chown`` and a
    same-size rewrite all force a re-check; verification costs one ``lstat`` per request."""
    try:
        st = os.lstat(path)
    except OSError:
        return ""
    sig = (st.st_ino, st.st_dev, st.st_mtime_ns, st.st_ctime_ns, st.st_size, st.st_mode, st.st_uid)
    with _lock:
        if _cache["path"] == str(path) and _cache["sig"] == sig:
            return _cache["key"]
    try:
        key = _read_owner_only(path)
    except (OSError, ValueError) as exc:  # ValueError covers UnicodeDecodeError
        _log.warning("dashboard agent key %s unreadable: %s", path, type(exc).__name__)
        key = ""
    if key and len(key) < MIN_KEY_CHARS:
        _log.warning("dashboard agent key %s ignored: shorter than %d chars", path, MIN_KEY_CHARS)
        key = ""
    with _lock:
        _cache.update(path=str(path), sig=sig, key=key)
    return key


def request_is_direct_local(request: Any) -> bool:
    """Loopback TCP peer and no proxy forwarding header (even an empty one)."""
    client = getattr(request, "client", None)
    if not client or (getattr(client, "host", "") or "") not in _LOCAL_PEERS:
        return False
    headers = getattr(request, "headers", None) or {}
    return not any(h in headers for h in _FORWARDING_HEADERS)


def verify_agent_key(request: Any, token: str) -> Optional[Session]:
    """``Session`` for the local agent when ``token`` is the agent key on a direct local request,
    else ``None`` (callers fall through to the normal providers). Never raises."""
    try:
        if not token or not request_is_direct_local(request):
            return None
        key = _load_key(key_path())
        if not key or not hmac.compare_digest(token.encode("utf-8"), key.encode("utf-8")):
            return None
        user_id = str(_section().get("user_id") or "").strip() or DEFAULT_USER_ID
        return Session(
            user_id=user_id, email="", display_name="Local agent", org_id="",
            provider=PROVIDER_NAME, expires_at=int(time.time()) + 300, access_token="",
            refresh_token="")
    except Exception:
        _log.warning("dashboard agent key verification failed; refusing", exc_info=True)
        return None


def _reset_cache_for_tests() -> None:
    with _lock:
        _cache.update(path=None, sig=None, key="")
