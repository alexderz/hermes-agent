"""Local dashboard agent key: direct-loopback-only machine credential (dashboard_auth/agent_key.py)."""
from __future__ import annotations

import os
import secrets
from types import SimpleNamespace

import pytest

from hermes_cli.dashboard_auth import agent_key as ak


def _req(host="127.0.0.1", headers=None):
    return SimpleNamespace(client=SimpleNamespace(host=host), headers=headers or {})


def _write(path, value, mode=0o600):
    path.write_bytes(value if isinstance(value, bytes) else value.encode())
    os.chmod(path, mode)


@pytest.fixture
def key(tmp_path, monkeypatch):
    path = tmp_path / "dashboard-agent.key"
    value = secrets.token_urlsafe(32)
    _write(path, value + "\n")
    monkeypatch.setattr(ak, "key_path", lambda: path)
    ak._reset_cache_for_tests()
    yield path, value
    ak._reset_cache_for_tests()


def test_direct_loopback_accepts_key(key):
    _, value = key
    s = ak.verify_agent_key(_req(), value)
    assert s is not None and s.provider == "agent-key" and s.user_id == "agent:local"
    assert ak.verify_agent_key(_req("::1"), value) is not None


def test_wrong_key_rejected(key):
    assert ak.verify_agent_key(_req(), "x" * 43) is None
    assert ak.verify_agent_key(_req(), "") is None


@pytest.mark.parametrize("hdr", ["x-forwarded-for", "forwarded", "x-real-ip", "via", "cf-connecting-ip"])
@pytest.mark.parametrize("val", ["10.69.0.50", ""])
def test_proxied_request_rejected_even_from_loopback_even_empty(key, hdr, val):
    _, value = key
    assert ak.verify_agent_key(_req(headers={hdr: val}), value) is None


def test_remote_peer_rejected(key):
    _, value = key
    assert ak.verify_agent_key(_req("10.69.0.50"), value) is None
    assert ak.verify_agent_key(_req("localhost"), value) is None
    assert ak.verify_agent_key(SimpleNamespace(client=None, headers={}), value) is None


def test_group_readable_file_ignored(key):
    path, value = key
    os.chmod(path, 0o640)
    assert ak.verify_agent_key(_req(), value) is None


def test_chmod_after_load_is_rechecked(key):
    path, value = key
    assert ak.verify_agent_key(_req(), value) is not None
    os.chmod(path, 0o644)
    assert ak.verify_agent_key(_req(), value) is None
    os.chmod(path, 0o600)
    assert ak.verify_agent_key(_req(), value) is not None


def test_symlink_refused(key, tmp_path, monkeypatch):
    path, value = key
    link = tmp_path / "link.key"
    link.symlink_to(path)
    monkeypatch.setattr(ak, "key_path", lambda: link)
    ak._reset_cache_for_tests()
    assert ak.verify_agent_key(_req(), value) is None


def test_non_utf8_file_fails_closed_without_raising(key):
    path, _ = key
    _write(path, b"\xff\xfe" + b"a" * 60)
    assert ak.verify_agent_key(_req(), "a" * 60) is None


def test_short_key_ignored(key):
    path, _ = key
    _write(path, "short-key")
    assert ak.verify_agent_key(_req(), "short-key") is None


def test_deleting_file_revokes_and_rotation_applies(key):
    path, value = key
    assert ak.verify_agent_key(_req(), value) is not None
    new = secrets.token_urlsafe(32)
    _write(path, new)
    assert ak.verify_agent_key(_req(), value) is None
    assert ak.verify_agent_key(_req(), new) is not None
    path.unlink()
    assert ak.verify_agent_key(_req(), new) is None


def test_config_overrides_file_and_identity(tmp_path, monkeypatch):
    path = tmp_path / "elsewhere.key"
    value = secrets.token_urlsafe(32)
    _write(path, value)
    monkeypatch.setattr(ak, "_section", lambda: {"file": str(path), "user_id": "basic:alex"})
    ak._reset_cache_for_tests()
    assert ak.key_path() == path
    assert ak.verify_agent_key(_req(), value).user_id == "basic:alex"


def test_default_path_under_hermes_home(monkeypatch, tmp_path):
    monkeypatch.setattr(ak, "_section", lambda: {})
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    assert ak.key_path() == tmp_path / "dashboard-agent.key"


def test_verifier_only_honours_key_when_asked(key, monkeypatch):
    from hermes_cli.dashboard_auth import middleware

    _, value = key
    monkeypatch.setattr(middleware, "scan_session_providers", lambda *a, **k: None)
    v = middleware._verify_access_token
    assert v(_req(), access_token=value, audit=False, allow_agent_key=True).provider == "agent-key"
    assert v(_req(), access_token=value, audit=False) is None  # cookie leg default
    assert v(_req(headers={"x-forwarded-for": "1.2.3.4"}), access_token=value, audit=False,
             allow_agent_key=True) is None


# ---- end to end through the real gated app ---------------------------------------------------


@pytest.fixture
def gated(key):
    from starlette.testclient import TestClient

    from hermes_cli import web_server
    from hermes_cli.dashboard_auth.registry import clear_providers

    clear_providers()
    state = web_server.app.state
    prev = {k: getattr(state, k, None) for k in ("bound_host", "bound_port", "auth_required")}
    state.bound_host, state.bound_port, state.auth_required = "127.0.0.1", 9119, True
    local = TestClient(web_server.app, base_url="http://127.0.0.1:9119", client=("127.0.0.1", 50000))
    remote = TestClient(web_server.app, base_url="http://127.0.0.1:9119", client=("10.69.0.50", 50000))
    yield key[1], local, remote
    clear_providers()
    for k, v in prev.items():
        setattr(state, k, v)


def test_e2e_bearer_from_loopback_passes_gate(gated):
    value, local, _ = gated
    r = local.get("/api/auth/me", headers={"Authorization": f"Bearer {value}"})
    assert r.status_code == 200 and r.json()["provider"] == "agent-key"


def test_e2e_bearer_via_proxy_or_remote_rejected(gated):
    value, local, remote = gated
    assert local.get("/api/auth/me", headers={"Authorization": f"Bearer {value}",
                                               "X-Forwarded-For": "10.69.0.50"}).status_code == 401
    assert remote.get("/api/auth/me", headers={"Authorization": f"Bearer {value}"}).status_code == 401


def test_e2e_key_in_cookie_is_not_a_login(gated):
    value, local, _ = gated
    from hermes_cli.dashboard_auth.cookies import SESSION_AT_COOKIE as ACCESS_COOKIE_NAME

    local.cookies.set(ACCESS_COOKIE_NAME, value)
    assert local.get("/api/auth/me").status_code == 401


def test_e2e_agent_key_cannot_mint_ws_ticket(gated):
    value, local, _ = gated
    r = local.post("/api/auth/ws-ticket", headers={"Authorization": f"Bearer {value}"})
    assert r.status_code == 403
