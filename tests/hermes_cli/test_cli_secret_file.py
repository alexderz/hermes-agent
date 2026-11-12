"""The classic CLI refuses ``clarify(secret_file=...)`` before prompting.

Its panel and its no-app masked prompt show only text the model wrote, so they cannot show the file's
destination apart from it; only the Webapp and desktop app's secret dialog can.
"""
from __future__ import annotations

import json
import os


def test_clarify_secret_file_refuses_on_the_cli_without_prompting(monkeypatch, tmp_path):
    from hermes_cli import callbacks
    from tests.hermes_cli.test_cli_secret_capture import _make_cli_stub
    from tools import skills_tool
    from tools.clarify_tool import clarify_tool

    monkeypatch.setattr(callbacks, "masked_secret_prompt",
                        lambda _prompt: (_ for _ in ()).throw(AssertionError("prompted on the CLI")))
    cli = _make_cli_stub()
    monkeypatch.setattr(skills_tool, "_secret_capture_callback", cli._secret_capture_callback)
    (tmp_path / "work").mkdir()

    result = json.loads(clarify_tool([{"question": "XYZ API key"}], callback=lambda _q: {},
                                     secret_file={"name": "XYZ API key", "path": str(tmp_path / "work" / "key")}))

    assert "needs the Hermes Webapp or desktop app" in result["error"]
    assert os.listdir(tmp_path / "work") == []
