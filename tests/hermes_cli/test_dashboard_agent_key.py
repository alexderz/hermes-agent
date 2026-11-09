"""Local dashboard agent key: direct-loopback-only machine credential (dashboard_auth/agent_key.py)."""
from __future__ import annotations

import os
import secrets
from types import SimpleNamespace

import pytest

from hermes_cli.dashboard_auth import agent_key as ak


def _req(host="127.0.0.1", headers=None):
    return SimpleNamespace(client=SimpleNamespace(host=host), headers=headers or {})


@pytest.fixture
def key(tmp_path, monkeypatch):
    path = tmp_path / "dashboard-agent.key"
    value = secrets.token_urlsafe(32)
    path.write_text(value + "\n", encoding="utf-8")
    os.chmod(path, 0o600)
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


@pytest.mark.parametrize("hdr", ["x-forwarded-for", "forwarded", "x-real-ip"])
def test_proxied_request_rejected_even_from_loopback(key, hdr):
    _, value = key
    assert ak.verify_agent_key(_req(headers={hdr: "10.69.0.50"}), value) is None


def test_remote_peer_rejected(key):
    _, value = key
    assert ak.verify_agent_key(_req("10.69.0.50"), value) is None
    assert ak.verify_agent_key(SimpleNamespace(client=None, headers={}), value) is None


def test_group_readable_file_ignored(key):
    path, value = key
    os.chmod(path, 0o640)
    assert ak.verify_agent_key(_req(), value) is None


def test_short_key_ignored(key):
    path, _ = key
    path.write_text("short-key", encoding="utf-8")
    os.chmod(path, 0o600)
    assert ak.verify_agent_key(_req(), "short-key") is None


def test_deleting_file_revokes_and_rotation_applies(key):
    path, value = key
    assert ak.verify_agent_key(_req(), value) is not None
    new = secrets.token_urlsafe(32)
    path.write_text(new, encoding="utf-8")
    os.chmod(path, 0o600)
    assert ak.verify_agent_key(_req(), value) is None
    assert ak.verify_agent_key(_req(), new) is not None
    path.unlink()
    assert ak.verify_agent_key(_req(), new) is None


def test_middleware_verifier_honours_key_before_providers(key, monkeypatch):
    from hermes_cli.dashboard_auth import middleware

    _, value = key
    monkeypatch.setattr(middleware, "scan_session_providers", lambda *a, **k: None)
    assert middleware._verify_access_token(_req(), access_token=value, audit=False).provider == "agent-key"
    assert middleware._verify_access_token(
        _req(headers={"x-forwarded-for": "1.2.3.4"}), access_token=value, audit=False) is None


def test_default_path_under_hermes_home(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    assert ak.key_path().name == "dashboard-agent.key"
