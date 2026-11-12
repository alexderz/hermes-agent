"""A classic CLI attached to a gateway session neither shows nor answers a ``clarify(secret_file=...)`` card.

The gateway sends the card to every viewer of the session and the first answer settles it for all, so a
skip from this terminal would cancel it on the Webapp or desktop app too, the surfaces that draw the
file's destination. The CLI sends no response frame, prints where to answer it, and never claims the value
went to ``.env``.
"""
from __future__ import annotations

import pytest

from hermes_cli.gateway_agent import GatewayAgent

DUMMY = "dummy-" + "cli-viewer-6d02"  # built by concatenation: a fake value


class _Connection:
    def __init__(self):
        self.replies = []

    def reply(self, rid, result):
        self.replies.append((rid, result))


@pytest.fixture
def attached_cli(monkeypatch):
    """A gateway-attached classic CLI with no full-screen app: its masked prompt types *DUMMY*."""
    from hermes_cli import callbacks
    from tests.hermes_cli.test_cli_secret_capture import _make_cli_stub
    from tools import skills_tool

    typed = []
    monkeypatch.setattr(callbacks, "masked_secret_prompt", lambda prompt: typed.append(prompt) or DUMMY)
    monkeypatch.setattr(skills_tool, "_secret_capture_callback", _make_cli_stub()._secret_capture_callback)
    agent = GatewayAgent.__new__(GatewayAgent)
    agent.connection, agent._open_request = _Connection(), None
    return agent, typed


def _card(metadata):
    return {"jsonrpc": "2.0", "id": "srv-1", "method": "secret",
            "params": {"session_id": "local-1", "env_var": "XYZ API key", "metadata": metadata,
                       "prompt": "Will be saved to /srv/example/xyz-key (0600, hermes:hermes)\n\nXYZ API key"}}


def test_a_file_card_gets_no_answer_and_no_env_claim(attached_cli, capsys):
    agent, typed = attached_cli

    agent._answer_request(_card({"source": "agent", "destination": {
        "kind": "file", "path": "/srv/example/xyz-key", "mode": "0600", "owner": "hermes", "group": "hermes"}}))

    out = capsys.readouterr().out
    assert agent.connection.replies == []  # not even a skip: the Webapp or desktop app answers it
    assert typed == []  # the masked prompt never opened
    assert "/srv/example/xyz-key" in out and "Webapp or desktop app" in out
    assert ".env" not in out


def test_an_env_card_is_still_answered_with_the_typed_value(attached_cli):
    agent, typed = attached_cli

    agent._answer_request(_card({"source": "agent"}))

    assert agent.connection.replies == [("srv-1", {"value": DUMMY})]
    assert len(typed) == 1
