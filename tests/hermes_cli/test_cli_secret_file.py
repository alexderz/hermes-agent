"""The classic CLI's secret panel saves a ``clarify(secret_file=...)`` answer to the file, not ``.env``."""
from __future__ import annotations

import os
import stat
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.platforms("posix")

DUMMY = "dummy-" + "cli-file-91d2b4"  # built by concatenation: a fake value


def test_cli_secret_file_answer_is_written_to_the_file_not_the_env(monkeypatch, tmp_path):
    from agent.secret_file_writer import plan_secret_file
    from hermes_cli import callbacks

    monkeypatch.setattr(callbacks, "masked_secret_prompt", lambda _prompt: DUMMY + "\n")
    monkeypatch.setattr(callbacks, "save_env_value_secure",
                        lambda *a: (_ for _ in ()).throw(AssertionError("a file secret went to .env")))
    (tmp_path / "work").mkdir()
    dest = plan_secret_file({"name": "k", "path": str(tmp_path / "work" / "key")}, base_dir=None)

    result = callbacks.prompt_for_secret(SimpleNamespace(), "k", "prompt", {"source": "agent", "destination": dest})

    assert result["secret_file"]["bytes"] == len(DUMMY)
    assert (tmp_path / "work" / "key").read_text(encoding="utf-8") == DUMMY
    assert stat.S_IMODE(os.stat(tmp_path / "work" / "key").st_mode) == 0o600


def test_clarify_secret_file_through_the_real_cli_callback(monkeypatch, tmp_path):
    import json

    from hermes_cli import callbacks
    from tests.hermes_cli.test_cli_secret_capture import _make_cli_stub
    from tools import skills_tool
    from tools.clarify_tool import clarify_tool

    monkeypatch.setattr(callbacks, "masked_secret_prompt", lambda _prompt: DUMMY)
    monkeypatch.setattr(callbacks, "save_env_value_secure",
                        lambda *a: (_ for _ in ()).throw(AssertionError("a file secret went to .env")))
    cli = _make_cli_stub()
    monkeypatch.setattr(skills_tool, "_secret_capture_callback", cli._secret_capture_callback)
    (tmp_path / "work").mkdir()

    raw = clarify_tool([{"question": "XYZ API key"}], callback=lambda _q: {},
                       secret_file={"name": "XYZ API key", "path": str(tmp_path / "work" / "key")})

    assert DUMMY not in raw
    assert json.loads(raw)["secret_file"]["status"] == "saved"
    assert (tmp_path / "work" / "key").read_text(encoding="utf-8") == DUMMY
