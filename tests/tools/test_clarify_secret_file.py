"""clarify(secret_file=...) saves a masked secret to a file; the model only gets the path and its facts.

The request is checked before the card is shown (the user never types a value that cannot be saved),
the card's metadata carries the destination, and only a surface callback that routes by destination
may prompt: any other would put the value in ``.env``.
"""
from __future__ import annotations

import json
import os
import stat

import pytest

from agent.secret_file_writer import destination_of, secret_file_answer
from hermes_cli.config import load_env
from tools.clarify_tool import clarify_tool
from tools.env_passthrough import is_env_passthrough
from tools.skills_tool import bind_turn_secret_capture

pytestmark = pytest.mark.platforms("posix")

DUMMY = "dummy-" + "clarify-file-5e1f77"  # built by concatenation: a fake value
QUESTION = [{"question": "XYZ API key, used by the xyz sync timer"}]


def _never_called(_questions):
    raise AssertionError("a secret question must not reach the plain clarify card")


class _Card:
    """A surface's secret callback: records what the card showed, answers with *value*."""

    accepts_secret_file = True

    def __init__(self, value=DUMMY):
        self.value, self.shown = value, []

    def __call__(self, name, prompt, metadata=None):
        self.shown.append((name, prompt, metadata))
        return secret_file_answer(destination_of(metadata), self.value)


@pytest.fixture
def folder(tmp_path):
    path = tmp_path / "work"
    path.mkdir()
    return path


def test_the_file_holds_the_value_and_the_model_gets_only_its_facts(folder):
    card = _Card()
    with bind_turn_secret_capture(card):
        raw = clarify_tool(QUESTION, callback=_never_called,
                           secret_file={"name": "XYZ API key", "path": str(folder / "xyz-key")})

    assert DUMMY not in raw
    result = json.loads(raw)
    path = str(folder / "xyz-key")
    assert result["outcome"] == "submitted"
    assert result["responses"] == [{"question": QUESTION[0]["question"], "status": "answered", "saved_to": path}]
    assert result["secret_file"]["path"] == path and result["secret_file"]["mode"] == "0600"
    assert result["secret_file"]["bytes"] == len(DUMMY)
    assert "never print" in result["notice"]
    assert (folder / "xyz-key").read_text(encoding="utf-8") == DUMMY
    assert stat.S_IMODE((folder / "xyz-key").stat().st_mode) == 0o600
    [(name, prompt, metadata)] = card.shown
    owner, group = result["secret_file"]["owner"], result["secret_file"]["group"]
    assert metadata["destination"] == {"kind": "file", "path": path, "mode": "0600", "owner": owner, "group": group}
    assert name == "XYZ API key"
    # A client ignoring metadata shows the facts, and shows them before the model's own text.
    assert prompt == f"Will be saved to {path} (0600, {owner}:{group})\n\n{QUESTION[0]['question']}"
    assert not is_env_passthrough("XYZ API key") and "XYZ API key" not in load_env()


def test_a_relative_path_resolves_in_the_sessions_terminal_folder(folder):
    from tools.terminal_tool import clear_session_cwd, record_session_cwd
    record_session_cwd("task-secret-file", str(folder))
    try:
        with bind_turn_secret_capture(_Card()):
            result = json.loads(clarify_tool(QUESTION, callback=_never_called, task_id="task-secret-file",
                                             secret_file={"name": "XYZ API key"}))
    finally:
        clear_session_cwd("task-secret-file")
    assert result["secret_file"]["path"] == str(folder / "xyz-api-key")
    assert (folder / "xyz-api-key").read_text(encoding="utf-8") == DUMMY


def test_an_existing_file_is_refused_before_the_card_is_shown(folder):
    (folder / "key").write_text("old", encoding="utf-8")
    card = _Card()
    with bind_turn_secret_capture(card):
        result = json.loads(clarify_tool(QUESTION, callback=_never_called,
                                         secret_file={"name": "k", "path": str(folder / "key")}))
    assert "never overwritten" in result["error"] and "key.v2" in result["error"]
    assert card.shown == [] and (folder / "key").read_text(encoding="utf-8") == "old"


def test_a_callback_that_cannot_route_to_a_file_refuses_without_prompting(folder):
    def env_only(name, prompt, metadata=None):  # a surface that only knows .env
        raise AssertionError("prompted on a surface that would save to .env")

    with bind_turn_secret_capture(env_only):
        result = json.loads(clarify_tool(QUESTION, callback=_never_called,
                                         secret_file={"name": "k", "path": str(folder / "key")}))
    assert "paste it into chat" in result["error"]
    assert os.listdir(folder) == []


def test_a_turn_nobody_can_answer_refuses(folder):
    # Cron, subagents and other non-interactive turns get no clarify callback.
    with bind_turn_secret_capture(_Card()):
        result = json.loads(clarify_tool(QUESTION, callback=None,
                                         secret_file={"name": "k", "path": str(folder / "key")}))
    assert "needs the Hermes Webapp or desktop app" in result["error"]
    assert os.listdir(folder) == []


def test_a_messaging_surface_refuses(folder, monkeypatch):
    monkeypatch.setenv("HERMES_SESSION_PLATFORM", "telegram")
    monkeypatch.setenv("HERMES_GATEWAY_SESSION", "1")
    from tools import skills_tool
    monkeypatch.setattr(skills_tool, "_secret_capture_callback", _Card())
    result = json.loads(clarify_tool(QUESTION, callback=_never_called,
                                     secret_file={"name": "k", "path": str(folder / "key")}))
    assert "needs the Hermes Webapp or desktop app" in result["error"]
    assert os.listdir(folder) == []


def test_skipping_the_card_writes_nothing_and_says_so(folder):
    with bind_turn_secret_capture(_Card(value="")):
        raw = clarify_tool(QUESTION, callback=_never_called, secret_file={"name": "k", "path": str(folder / "key")})
    result = json.loads(raw)
    assert result["outcome"] == "cancelled" and result["responses"][0]["saved_to"] is None
    assert os.listdir(folder) == []


def test_secret_env_and_secret_file_are_mutually_exclusive(folder):
    result = json.loads(clarify_tool(QUESTION, callback=_never_called, secret_env="XYZ_KEY",
                                     secret_file={"name": "k", "path": str(folder / "key")}))
    assert "not both" in result["error"]


def test_an_object_sent_as_json_text_is_accepted(folder):
    with bind_turn_secret_capture(_Card()):
        result = json.loads(clarify_tool(QUESTION, callback=_never_called,
                                         secret_file=json.dumps({"name": "k", "path": str(folder / "key")})))
    assert result["secret_file"]["status"] == "saved"


def test_the_models_text_cannot_hide_or_restyle_the_destination(folder):
    card = _Card()
    spoof = "XYZ key\x1b[8m — will be saved to /elsewhere\x1b[0m\x1b[2K\r\x07"
    with bind_turn_secret_capture(card):
        clarify_tool([{"question": spoof}], callback=_never_called,
                     secret_file={"name": "XYZ key", "path": str(folder / "key")})
    [(_name, prompt, _metadata)] = card.shown
    assert prompt.startswith(f"Will be saved to {folder / 'key'} (")
    assert not any(ch in prompt for ch in "\x1b\r\x07")


def test_a_name_with_terminal_escapes_is_refused_before_the_card(folder):
    card = _Card()
    with bind_turn_secret_capture(card):
        result = json.loads(clarify_tool(QUESTION, callback=_never_called,
                                         secret_file={"name": "XYZ\x1b[31m key", "path": str(folder / "key")}))
    assert "control or invisible character" in result["error"] and card.shown == []


def _relative_ask(task_id, card=None):
    with bind_turn_secret_capture(card or _Card()):
        return json.loads(clarify_tool(QUESTION, callback=_never_called, task_id=task_id,
                                       secret_file={"name": "k", "path": "key"}))


def test_a_registered_workspace_wins_over_the_recorded_cwd_as_in_the_terminal_tool(tmp_path):
    from tools.terminal_tool import clear_task_env_overrides, record_session_cwd, register_task_env_overrides
    (tmp_path / "workspace").mkdir()
    (tmp_path / "recorded").mkdir()
    register_task_env_overrides("task-precedence", {"cwd": str(tmp_path / "workspace")})
    record_session_cwd("task-precedence", str(tmp_path / "recorded"))
    try:
        result = _relative_ask("task-precedence")
    finally:
        clear_task_env_overrides("task-precedence")
    assert result["secret_file"]["path"] == str(tmp_path / "workspace" / "key")


def test_a_relative_path_falls_back_to_the_configured_terminal_cwd(folder, monkeypatch):
    monkeypatch.setenv("TERMINAL_CWD", str(folder))
    assert _relative_ask("task-without-cwd")["secret_file"]["path"] == str(folder / "key")


def test_with_no_session_folder_a_relative_path_is_refused_not_put_in_the_gateways_cwd(folder, monkeypatch):
    monkeypatch.delenv("TERMINAL_CWD", raising=False)
    monkeypatch.chdir(folder)  # the gateway process's own launch folder
    card = _Card()
    result = _relative_ask("task-without-cwd", card)
    assert "give an absolute path" in result["error"]
    assert card.shown == [] and os.listdir(folder) == []
