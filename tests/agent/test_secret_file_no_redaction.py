"""File intake keeps values out of its response, not in a global output-censor registry."""
import json

import pytest

import agent.redact as redact
from agent.secret_file_writer import plan_secret_file, secret_file_answer

pytestmark = pytest.mark.platforms("posix")


@pytest.mark.parametrize("value", ["x", "ok", "dummy-file-token-0123456789", "界"])
def test_file_intake_does_not_register_global_redaction(tmp_path, monkeypatch, value):
    monkeypatch.setattr(redact, "_VAULT_REDACTION_VALUES", {})
    destination = plan_secret_file({"name": "Sample", "path": str(tmp_path / "sample")}, base_dir=None)
    result = secret_file_answer(destination, value)
    assert result["success"]
    assert (tmp_path / "sample").read_text() == value
    assert redact._VAULT_REDACTION_VALUES == {}
    text = f"ordinary output includes {value} without global replacement"
    assert redact.redact_registered_vault_values(text) == text
    if len(value) > 2:
        assert value not in json.dumps(result)


def test_file_intake_preserves_existing_vault_registrations(tmp_path, monkeypatch):
    monkeypatch.setattr(redact, "_VAULT_REDACTION_VALUES", {})
    existing = "existing-browser-vault-password-012345"
    redact.register_vault_redaction_value(existing)
    before = {scope: dict(values) for scope, values in redact._VAULT_REDACTION_VALUES.items()}
    destination = plan_secret_file({"name": "Sample", "path": str(tmp_path / "sample")}, base_dir=None)
    assert secret_file_answer(destination, "x")["success"]
    assert redact._VAULT_REDACTION_VALUES == before
    assert existing not in redact.redact_registered_vault_values(existing)
