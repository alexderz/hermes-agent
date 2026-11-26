"""Behavior of the read-only MCP call: closed verbs, scope, hint, no secrets."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tools import mcp_readonly

_ID = "linear:not-in-scope"
_ROOT = "linear:epic-1"


def _binding_text(tools=None, roots=None, revision=7):
    if tools is None:
        tools = list(mcp_readonly.call_mcp_tool_readonly.closed_verbs)
    if roots is None:
        roots = [{"kind": "epic", "id": _ROOT}]
    lines = [
        "schema: project-recovery-binding/1",
        f"revision: {revision}",
        "tracker:",
        "  adapter: linear",
        "  mcp_server: linear",
        "  repo_skill: SKILL.md",
        "  read_tools:",
    ]
    for tool in tools:
        lines.append(f"    - {tool}")
    lines.append("roots:")
    for root in roots:
        lines.append(f"  - kind: {root['kind']}")
        lines.append(f"    id: {root['id']}")
        if "team" in root:
            lines.append(f"    team: {root['team']}")
        if "dedicated" in root:
            lines.append(f"    dedicated: {str(root['dedicated']).lower()}")
    return "\n".join(lines) + "\n"


def _plant(tmp_path, *, tools=None, roots=None, revision=7, snapshot=None, skill=None):
    (tmp_path / "binding.yaml").write_text(
        _binding_text(tools, roots, revision), encoding="utf-8"
    )
    if snapshot is not None:
        state = tmp_path / "state"
        state.mkdir()
        (state / "snapshot.json").write_text(snapshot, encoding="utf-8")
    if skill is not None:
        (tmp_path / "SKILL.md").write_text(skill, encoding="utf-8")


class _Block:
    def __init__(self, text):
        self.text = text
        self.type = "text"


class _Result:
    def __init__(self, text, is_error=False):
        self.content = [_Block(text)]
        self.isError = is_error
        self.structuredContent = None


def _run_loop(coro_or_factory, timeout=30):
    del timeout
    coro = coro_or_factory() if callable(coro_or_factory) else coro_or_factory
    loop = asyncio.new_event_loop()
    try:

        async def _go():
            from tools import mcp_tool

            for srv in list(mcp_tool._servers.values()):
                if getattr(srv, "_rpc_lock", None) is None:
                    srv._rpc_lock = asyncio.Lock()
            return await coro

        return loop.run_until_complete(_go())
    finally:
        loop.close()


@pytest.fixture
def mcp_session():
    session = MagicMock()
    session.call_tool = AsyncMock(return_value=_Result('{"ok": true}'))
    server = SimpleNamespace(session=session, _rpc_lock=None)
    from tools import mcp_tool

    with (
        patch.dict(mcp_tool._servers, {"linear": server}, clear=False),
        patch.dict(mcp_tool._server_trust_levels, {}, clear=True),
        patch.dict(mcp_tool._tool_read_only_hints, {}, clear=True),
        patch("tools.mcp_tool_loop._run_on_mcp_loop", side_effect=_run_loop),
        patch.object(mcp_tool, "_mcp_registry_scope", lambda: None),
    ):
        yield session


def _allow(server_name, verb):
    from tools import mcp_tool

    mcp_tool._server_trust_levels[server_name] = "full"
    mcp_tool._tool_read_only_hints[server_name] = {verb: True}


def test_import_origin_is_this_worktree():
    root = Path(__file__).resolve().parents[2]
    assert Path(mcp_readonly.__file__).resolve().is_relative_to(root)


def test_scope_refused_for_mapping_valid_id_outside_loaded_scope(
    tmp_path, monkeypatch, mcp_session
):
    """A valid id outside root, history, and enumeration is refused with no RPC."""
    monkeypatch.chdir(tmp_path)
    _plant(tmp_path)
    _allow("linear", "get_issue")
    result = mcp_readonly.call_mcp_tool_readonly("linear", "get_issue", {"id": _ID})
    assert result == "scope_refused"
    mcp_session.call_tool.assert_not_awaited()


@pytest.fixture(autouse=True)
def _clear_process_scope():
    mcp_readonly._ENUM.clear()
    mcp_readonly._USER_ONCE.clear()
    yield
    mcp_readonly._ENUM.clear()
    mcp_readonly._USER_ONCE.clear()


class _Flip:
    """Sets the hint false only after the call has entered the RPC lock."""

    def __init__(self, server_name, verb):
        self._inner = asyncio.Lock()
        self._server_name = server_name
        self._verb = verb

    async def __aenter__(self):
        await self._inner.acquire()
        from tools import mcp_tool

        hints = mcp_tool._tool_read_only_hints[self._server_name]
        hints[self._verb] = False
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self._inner.release()
        return False


def _hints(*verbs):
    from tools import mcp_tool

    mcp_tool._server_trust_levels["linear"] = "full"
    mcp_tool._tool_read_only_hints["linear"] = {verb: True for verb in verbs}


def _skill():
    return (
        "# Tracker\n\n"
        "Contract: tracker-sdlc v2\n\n"
        "## Mapping\n\n"
        "| Canonical | Example |\n"
        "| --- | --- |\n"
        "| backlog | Backlog |\n"
        "| ready | Ready |\n"
        "| in_progress | In Progress |\n"
        "| in_review | In Review |\n"
        "| done | Done |\n"
        "| canceled | `Canceled` `Duplicate` |\n"
    )


def test_closed_list_issues_reaches_call_tool_once(tmp_path, monkeypatch, mcp_session):
    """Positive control: one closed call, limit 250, archived, no state filter."""
    monkeypatch.chdir(tmp_path)
    _plant(tmp_path)
    _hints("list_issues")
    payload = json.dumps({"issues": [], "hasNextPage": False})
    mcp_session.call_tool.return_value = _Result(payload)
    result = mcp_readonly.call_mcp_tool_readonly(
        "linear", "list_issues", {"parentId": _ROOT}
    )
    mcp_session.call_tool.assert_awaited_once_with(
        "list_issues",
        arguments={"parentId": _ROOT, "limit": 250, "includeArchived": True},
    )
    assert json.loads(json.loads(result)["result"])["hasNextPage"] is False


def test_hint_recheck_inside_the_lock_refuses_full_trust(
    tmp_path, monkeypatch, mcp_session
):
    monkeypatch.chdir(tmp_path)
    _plant(tmp_path)
    _hints("get_issue")
    from tools import mcp_tool

    mcp_tool._servers["linear"]._rpc_lock = _Flip("linear", "get_issue")
    result = mcp_readonly.call_mcp_tool_readonly("linear", "get_issue", {"id": _ROOT})
    assert result == "hint_refused"
    mcp_session.call_tool.assert_not_awaited()


def test_false_hint_on_full_trust_is_hint_refused(tmp_path, monkeypatch, mcp_session):
    monkeypatch.chdir(tmp_path)
    _plant(tmp_path)
    from tools import mcp_tool

    mcp_tool._server_trust_levels["linear"] = "full"
    mcp_tool._tool_read_only_hints["linear"] = {"get_issue": False}
    result = mcp_readonly.call_mcp_tool_readonly("linear", "get_issue", {"id": _ROOT})
    assert result == "hint_refused"
    mcp_session.call_tool.assert_not_awaited()


def test_untrusted_exact_true_hint_reaches_call_tool(
    tmp_path, monkeypatch, mcp_session
):
    monkeypatch.chdir(tmp_path)
    _plant(tmp_path)
    from tools import mcp_tool

    mcp_tool._server_trust_levels["linear"] = "untrusted"
    mcp_tool._tool_read_only_hints["linear"] = {"get_issue": True}
    result = mcp_readonly.call_mcp_tool_readonly("linear", "get_issue", {"id": _ROOT})
    assert result != "hint_refused"
    mcp_session.call_tool.assert_awaited_once()


def test_untrusted_false_hint_is_trust_refused_without_rpc(
    tmp_path, monkeypatch, mcp_session
):
    monkeypatch.chdir(tmp_path)
    _plant(tmp_path)
    from tools import mcp_tool

    mcp_tool._server_trust_levels["linear"] = "untrusted"
    mcp_tool._tool_read_only_hints["linear"] = {"get_issue": False}
    with patch(
        "tools.approval_prompt.request_elicitation_consent", return_value="decline"
    ):
        result = mcp_readonly.call_mcp_tool_readonly(
            "linear", "get_issue", {"id": _ROOT}
        )
    assert result == "trust_refused"
    mcp_session.call_tool.assert_not_awaited()


def test_missing_trust_consults_configured_default(tmp_path, monkeypatch, mcp_session):
    monkeypatch.chdir(tmp_path)
    _plant(tmp_path)
    from tools import mcp_tool

    seen = []

    def _configured(server_name, key):
        seen.append(server_name)
        return "full"

    monkeypatch.setattr("tools.mcp_tool_handlers._configured_trust", _configured)
    mcp_tool._tool_read_only_hints["linear"] = {"get_issue": True}
    result = mcp_readonly.call_mcp_tool_readonly("linear", "get_issue", {"id": _ROOT})
    assert result != "trust_refused"
    assert seen == ["linear"]
    assert "linear" not in mcp_tool._server_trust_levels
    mcp_session.call_tool.assert_awaited_once()


def test_errors_omit_token_url_and_home(tmp_path, monkeypatch, mcp_session, caplog):
    monkeypatch.chdir(tmp_path)
    _plant(tmp_path)
    _hints("get_issue")
    secret = "ghp_abcdefghijklmnopqrstuvwxyz"
    url = "https://example.test/secret"
    home = "/home/someone/keys"
    mcp_session.call_tool.side_effect = RuntimeError(f"{secret} {url} {home}")
    result = mcp_readonly.call_mcp_tool_readonly("linear", "get_issue", {"id": _ROOT})
    for banned in (secret, url, home, "someone"):
        assert banned not in result
        assert banned not in caplog.text


def test_get_user_accepts_only_me_once(tmp_path, monkeypatch, mcp_session):
    monkeypatch.chdir(tmp_path)
    _plant(tmp_path)
    _hints("get_user")
    mcp_session.call_tool.return_value = _Result('{"id": "user-1"}')
    refused = mcp_readonly.call_mcp_tool_readonly(
        "linear", "get_user", {"query": "other"}
    )
    assert refused == "args_refused"
    mcp_session.call_tool.assert_not_awaited()
    first = mcp_readonly.call_mcp_tool_readonly("linear", "get_user", {"query": "me"})
    assert "user-1" in first
    second = mcp_readonly.call_mcp_tool_readonly("linear", "get_user", {"query": "me"})
    assert second == "args_refused"
    mcp_session.call_tool.assert_awaited_once()


def test_wider_verb_set_is_verb_refused(tmp_path, monkeypatch, mcp_session):
    monkeypatch.chdir(tmp_path)
    _plant(tmp_path, tools=["list_issues", "create_issue"])
    _hints("list_issues")
    result = mcp_readonly.call_mcp_tool_readonly(
        "linear", "list_issues", {"parentId": _ROOT}
    )
    assert result == "verb_refused"
    mcp_session.call_tool.assert_not_awaited()


def test_state_filter_and_unknown_key_are_args_refused(
    tmp_path, monkeypatch, mcp_session
):
    monkeypatch.chdir(tmp_path)
    _plant(tmp_path)
    _hints("list_issues", "get_issue")
    state = mcp_readonly.call_mcp_tool_readonly(
        "linear", "list_issues", {"parentId": _ROOT, "state": "Done"}
    )
    archived = mcp_readonly.call_mcp_tool_readonly(
        "linear", "list_issues", {"parentId": _ROOT, "includeArchived": True}
    )
    extra = mcp_readonly.call_mcp_tool_readonly(
        "linear", "get_issue", {"id": _ROOT, "allowlist": ["get_issue"]}
    )
    assert state == "args_refused"
    assert archived == "args_refused"
    assert extra == "args_refused"
    mcp_session.call_tool.assert_not_awaited()


def test_structurally_invalid_id_is_args_refused(tmp_path, monkeypatch, mcp_session):
    monkeypatch.chdir(tmp_path)
    _plant(tmp_path)
    _hints("get_issue")
    result = mcp_readonly.call_mcp_tool_readonly(
        "linear", "get_issue", {"id": "bad id"}
    )
    assert result == "args_refused"
    mcp_session.call_tool.assert_not_awaited()


def test_corrupt_snapshot_is_scope_refused(tmp_path, monkeypatch, mcp_session):
    monkeypatch.chdir(tmp_path)
    _plant(tmp_path, snapshot="{")
    _hints("list_issues")
    result = mcp_readonly.call_mcp_tool_readonly(
        "linear", "list_issues", {"parentId": _ROOT}
    )
    assert result == "scope_refused"
    mcp_session.call_tool.assert_not_awaited()


def test_snapshot_member_and_enumerated_id_are_in_scope(
    tmp_path, monkeypatch, mcp_session
):
    monkeypatch.chdir(tmp_path)
    _plant(
        tmp_path,
        snapshot=json.dumps({"scan": 2, "members": {_ID: {"state": "ready"}}}),
    )
    _hints("get_issue", "list_issues")
    historical = mcp_readonly.call_mcp_tool_readonly("linear", "get_issue", {"id": _ID})
    assert historical != "scope_refused"
    fresh = "linear:fresh-1"
    mcp_session.call_tool.return_value = _Result(
        json.dumps({"issues": [{"id": fresh, "status": "Ready"}], "hasNextPage": False})
    )
    listed = mcp_readonly.call_mcp_tool_readonly(
        "linear", "list_issues", {"parentId": _ROOT}
    )
    assert listed != "scope_refused"
    mcp_session.call_tool.return_value = _Result(json.dumps({"id": fresh}))
    fetched = mcp_readonly.call_mcp_tool_readonly("linear", "get_issue", {"id": fresh})
    assert fetched != "scope_refused"
    assert mcp_session.call_tool.await_count == 3


def test_comments_follow_enumerated_aliases(tmp_path, monkeypatch, mcp_session):
    monkeypatch.chdir(tmp_path)
    _plant(tmp_path, skill=_skill_closed())
    _write_aliases(tmp_path, _aliases())
    _hints("list_issues", "list_comments")

    def _answer(verb, arguments):
        if verb == "list_issues":
            body = {
                "issues": [
                    {"id": "linear:prog-1", "status": "In Progress"},
                    {"id": "linear:dup-1", "status": "Duplicate"},
                ],
                "hasNextPage": False,
            }
            return _Result(json.dumps(body))
        return _Result('{"comments": [], "hasNextPage": false}')

    mcp_session.call_tool.side_effect = _answer
    listed = mcp_readonly.call_mcp_tool_readonly(
        "linear", "list_issues", {"parentId": _ROOT}
    )
    assert listed != "scope_refused"
    allowed = mcp_readonly.call_mcp_tool_readonly(
        "linear",
        "list_comments",
        {"issueId": "linear:prog-1", "orderBy": "createdAt"},
    )
    refused = mcp_readonly.call_mcp_tool_readonly(
        "linear",
        "list_comments",
        {"issueId": "linear:dup-1", "orderBy": "createdAt"},
    )
    assert "comments" in allowed
    assert refused == "scope_refused"
    assert mcp_session.call_tool.await_count == 2


def test_backlog_snapshot_state_refuses_comments(tmp_path, monkeypatch, mcp_session):
    monkeypatch.chdir(tmp_path)
    _plant(
        tmp_path,
        snapshot=json.dumps({"scan": 1, "members": {_ID: {"state": "backlog"}}}),
    )
    _hints("list_comments")
    result = mcp_readonly.call_mcp_tool_readonly(
        "linear",
        "list_comments",
        {"issueId": _ID, "orderBy": "createdAt"},
    )
    assert result == "scope_refused"
    mcp_session.call_tool.assert_not_awaited()


def test_non_string_verb_is_verb_refused(tmp_path, monkeypatch, mcp_session):
    monkeypatch.chdir(tmp_path)
    _plant(tmp_path)
    result = mcp_readonly.call_mcp_tool_readonly("linear", None, {"id": _ROOT})
    assert result == "verb_refused"
    mcp_session.call_tool.assert_not_awaited()


def _skill_closed():
    """Mapping markdown that does not grant In Progress or Duplicate."""
    return (
        "# Tracker\n\n"
        "Contract: tracker-sdlc v2\n\n"
        "## Mapping\n\n"
        "| Canonical | Example |\n"
        "| --- | --- |\n"
        "| backlog | Backlog |\n"
        "| ready | Ready |\n"
        "| in_progress | Waiting |\n"
        "| in_review | In Review |\n"
        "| done | Done |\n"
        "| canceled | Canceled |\n"
    )


def _skill_sneaky():
    """Mapping markdown that would widen in_progress with an extra native name."""
    return (
        "# Tracker\n\n"
        "Contract: tracker-sdlc v2\n\n"
        "## Mapping\n\n"
        "| Canonical | Example |\n"
        "| --- | --- |\n"
        "| backlog | Backlog |\n"
        "| ready | Ready |\n"
        "| in_progress | `In Progress` `Sneaky` |\n"
        "| in_review | In Review |\n"
        "| done | Done |\n"
        "| canceled | Canceled |\n"
    )


def _aliases(revision=7, **replacements):
    states = {
        "backlog": ["Backlog"],
        "ready": ["Ready"],
        "in_progress": ["In Progress"],
        "in_review": ["In Review"],
        "done": ["Done"],
        "canceled": ["Canceled", "Duplicate"],
    }
    states.update(replacements)
    return json.dumps(
        {
            "schema": "project-recovery-aliases/1",
            "binding_revision": revision,
            "state_aliases": states,
        }
    )


def _write_aliases(tmp_path, text):
    state = tmp_path / "state"
    state.mkdir(exist_ok=True)
    (state / "aliases.json").write_text(text, encoding="utf-8")


def _enumerate(session, issues):
    def _answer(verb, arguments):
        del arguments
        if verb == "list_issues":
            body = {"issues": issues, "hasNextPage": False}
            return _Result(json.dumps(body))
        return _Result('{"comments": [], "hasNextPage": false}')

    session.call_tool.side_effect = _answer


def _comments(issue_id):
    return mcp_readonly.call_mcp_tool_readonly(
        "linear",
        "list_comments",
        {"issueId": issue_id, "orderBy": "createdAt"},
    )


def test_correction_real_sdk_list_issues_renders_envelope_and_stays_in_scope(
    tmp_path, monkeypatch, mcp_session
):
    """A real SDK result is rendered and remembered, not rejected as unhashable."""
    from mcp.types import CallToolResult, TextContent

    monkeypatch.chdir(tmp_path)
    _plant(tmp_path)
    _hints("list_issues", "get_issue")
    fresh = "linear:sdk-1"
    payload = json.dumps(
        {"issues": [{"id": fresh, "status": "Ready"}], "hasNextPage": False}
    )
    mcp_session.call_tool.return_value = CallToolResult(
        content=[TextContent(type="text", text=payload)]
    )
    listed = mcp_readonly.call_mcp_tool_readonly(
        "linear", "list_issues", {"parentId": _ROOT}
    )
    mcp_session.call_tool.assert_awaited_once()
    decoded = json.loads(json.loads(listed)["result"])
    assert decoded["issues"][0]["id"] == fresh
    assert decoded["hasNextPage"] is False
    mcp_session.call_tool.return_value = CallToolResult(
        content=[TextContent(type="text", text=json.dumps({"id": fresh}))]
    )
    fetched = mcp_readonly.call_mcp_tool_readonly("linear", "get_issue", {"id": fresh})
    assert fetched != "scope_refused"
    assert "unhashable" not in fetched
    inner = json.loads(json.loads(fetched)["result"])
    assert inner["id"] == fresh
    assert mcp_session.call_tool.await_count == 2


def test_correction_alias_cache_grants_in_progress_and_cancels_duplicate(
    tmp_path, monkeypatch, mcp_session
):
    """Structured aliases decide eligibility. Duplicate stays canceled."""
    monkeypatch.chdir(tmp_path)
    _plant(tmp_path, skill=_skill_closed())
    _write_aliases(tmp_path, _aliases())
    _hints("list_issues", "list_comments")
    _enumerate(
        mcp_session,
        [
            {"id": "linear:prog-1", "status": "In Progress"},
            {"id": "linear:dup-1", "status": "Duplicate"},
        ],
    )
    listed = mcp_readonly.call_mcp_tool_readonly(
        "linear", "list_issues", {"parentId": _ROOT}
    )
    assert listed != "scope_refused"
    allowed = _comments("linear:prog-1")
    refused = _comments("linear:dup-1")
    assert "comments" in allowed
    assert refused == "scope_refused"


def test_correction_skill_markdown_alone_cannot_widen_comments(
    tmp_path, monkeypatch, mcp_session
):
    monkeypatch.chdir(tmp_path)
    _plant(tmp_path, skill=_skill_sneaky())
    _hints("list_issues", "list_comments")
    _enumerate(mcp_session, [{"id": "linear:snek-1", "status": "Sneaky"}])
    listed = mcp_readonly.call_mcp_tool_readonly(
        "linear", "list_issues", {"parentId": _ROOT}
    )
    assert listed != "scope_refused"
    assert _comments("linear:snek-1") == "scope_refused"


def test_correction_stale_alias_cache_cannot_widen_comments(
    tmp_path, monkeypatch, mcp_session
):
    monkeypatch.chdir(tmp_path)
    _plant(tmp_path, revision=8, skill=_skill_sneaky())
    _write_aliases(
        tmp_path,
        _aliases(revision=7, in_progress=["In Progress", "Sneaky"]),
    )
    _hints("list_issues", "list_comments")
    _enumerate(mcp_session, [{"id": "linear:snek-1", "status": "Sneaky"}])
    listed = mcp_readonly.call_mcp_tool_readonly(
        "linear", "list_issues", {"parentId": _ROOT}
    )
    assert listed != "scope_refused"
    assert _comments("linear:snek-1") == "scope_refused"


def test_correction_fresh_status_does_not_reuse_snapshot_without_cache(
    tmp_path, monkeypatch, mcp_session
):
    monkeypatch.chdir(tmp_path)
    _plant(
        tmp_path,
        skill=_skill_closed(),
        snapshot=json.dumps(
            {"scan": 2, "members": {"linear:prog-1": {"state": "in_progress"}}}
        ),
    )
    _hints("list_issues", "list_comments")
    _enumerate(mcp_session, [{"id": "linear:prog-1", "status": "In Progress"}])
    listed = mcp_readonly.call_mcp_tool_readonly(
        "linear", "list_issues", {"parentId": _ROOT}
    )
    assert listed != "scope_refused"
    assert _comments("linear:prog-1") == "scope_refused"
