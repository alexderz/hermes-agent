"""Linear and local tracker reads. Fixtures are synthetic."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

from hermes_yaml import safe_dump
from plugins.project_recovery.actionability import evaluate
from plugins.project_recovery.binding import load_binding
from plugins.project_recovery.mapping import Ok, load_mapping
from plugins.project_recovery.readers import read_tracker
from tests.plugins.project_recovery.support import (
    CLOSED_VERBS,
    MAPPING,
    linear_document,
    local_document,
    workspace,
    workstream,
)

_EPIC = {
    "kind": "epic",
    "id": "linear:epic-1",
    "key": "ABC-100",
    "workstream": "ws-alpha",
}
_LABEL = {
    "kind": "label",
    "id": "linear-label:7c1d",
    "name": "Recovery X",
    "team": "ABC",
    "workstream": "ws-alpha",
}
_ITEM = {
    "kind": "item",
    "id": "linear:item-1",
    "key": "ABC-131",
    "workstream": "ws-alpha",
}
_PROJECT = {
    "kind": "project",
    "id": "linear:project-1",
    "dedicated": True,
    "workstream": "ws-alpha",
}


def _repo_root():
    root = Path(__file__).resolve()
    while not (root / "pyproject.toml").is_file():
        if root.parent == root:
            raise AssertionError("repo root")
        root = root.parent
    return root


def test_import_origin_is_this_worktree():
    import plugins.project_recovery.readers as module

    assert Path(module.__file__).resolve().is_relative_to(_repo_root())


def _bind(tmp_path, builder, mapping_text=None):
    recovery, outputs = workspace(tmp_path)
    document = builder(outputs)
    text = mapping_text or MAPPING
    mapping = load_mapping(text)
    assert isinstance(mapping, Ok)
    raw = safe_dump(document)
    loaded = load_binding(
        raw,
        closed_verbs=CLOSED_VERBS,
        mapping=mapping.value,
        recovery_dir=recovery,
    )
    assert isinstance(loaded, Ok), getattr(loaded, "error", loaded)
    skill = recovery / document["tracker"]["repo_skill"]
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text(text, encoding="utf-8")
    (recovery / "binding.yaml").write_text(raw, encoding="utf-8")
    return recovery, loaded.value, mapping.value


def _issue(ident, status, **extra):
    body = {
        "id": ident,
        "key": ident,
        "status": status,
        "parentId": "linear:epic-1",
        "archived": False,
        "assigneeId": None,
        "updatedAt": "2026-11-22T00:00:00Z",
        "type": "task",
    }
    body.update(extra)
    return body


def _wrapped(payload):
    return json.dumps({"result": json.dumps(payload)})


class _Board:
    def __init__(self):
        self.calls = []
        self.issues = []
        self.comments = {}
        self.user = {"id": "user-me"}
        self.user_error = None
        self.labels = [{"id": "linear-label:7c1d", "name": "Recovery X"}]
        self.pages = None
        self.page_index = 0
        self.by_id = {}

    def __call__(self, server, verb, args):
        self.calls.append((server, verb, dict(args)))
        if verb == "get_user":
            if self.user_error:
                return self.user_error
            return _wrapped(self.user)
        if verb == "list_issues":
            if self.pages is not None:
                payload = self.pages[self.page_index]
                self.page_index += 1
                return _wrapped(payload)
            return _wrapped({"issues": self.issues, "hasNextPage": False})
        if verb == "list_comments":
            comments = self.comments.get(args.get("issueId"), [])
            return _wrapped({"comments": comments, "hasNextPage": False})
        if verb == "list_issue_labels":
            return _wrapped({"labels": self.labels})
        if verb == "get_issue":
            ident = args.get("id")
            if args.get("includeRelations"):
                body = dict(self.by_id.get(ident, {"id": ident}))
                body["relations"] = {"blockedBy": []}
                return _wrapped(body)
            if ident in self.by_id:
                return _wrapped(self.by_id[ident])
            return json.dumps({"code": "not_found"})
        return "verb_refused"


def _install(monkeypatch, board):
    monkeypatch.setattr(
        "plugins.project_recovery.readers.call_mcp_tool_readonly",
        board,
    )


def _selectors(board):
    return [args for _server, verb, args in board.calls if verb == "list_issues"]


def test_a16_enumeration_uses_only_bound_roots(tmp_path, monkeypatch):
    recovery, binding, mapping = _bind(
        tmp_path,
        lambda outputs: linear_document(outputs, roots=[_EPIC, _LABEL]),
    )
    board = _Board()
    board.issues = [_issue("ABC-131", "Done", archived=True)]
    _install(monkeypatch, board)
    result = read_tracker(recovery, binding, mapping, {})
    assert _selectors(board) == [
        {"parentId": "linear:epic-1"},
        {"label": "linear-label:7c1d", "team": "ABC"},
    ]
    assert all(
        "state" not in args and "project" not in args for args in _selectors(board)
    )
    member = result["members"]["ABC-131"]
    assert result["complete"] is True
    assert member["visibility"] == "listed"
    assert member["archived"] is True
    assert member["state"] == "done"


def test_a15_reparent_archive_and_label_history(tmp_path, monkeypatch):
    recovery, binding, mapping = _bind(
        tmp_path,
        lambda outputs: linear_document(outputs, roots=[_EPIC, _LABEL]),
    )
    board = _Board()
    board.by_id["ABC-131"] = {
        "id": "ABC-131",
        "key": "ABC-131",
        "status": "In Progress",
        "parentId": "linear:other",
        "labelIds": [],
    }
    board.by_id["ABC-132"] = {
        "id": "ABC-132",
        "key": "ABC-132",
        "status": "Done",
        "parentId": None,
        "labelIds": ["linear-label:7c1d"],
    }
    previous = {
        "ABC-131": {
            "state": "in_progress",
            "visibility": "listed",
            "via": ["linear:epic-1"],
            "workstream": "ws-alpha",
            "assignee": "self",
            "claim": None,
            "blockers": [],
            "archived": False,
        },
        "ABC-132": {
            "state": "done",
            "visibility": "listed",
            "via": ["linear-label:7c1d"],
            "workstream": "ws-alpha",
            "assignee": "none",
            "claim": None,
            "blockers": [],
            "archived": False,
        },
    }
    _install(monkeypatch, board)
    result = read_tracker(recovery, binding, mapping, previous)
    assert result["complete"] is True
    assert result["members"]["ABC-131"]["visibility"] == "reparented_out"
    assert result["members"]["ABC-131"]["assignee"] == "self"
    assert result["members"]["ABC-132"]["visibility"] == "listed"
    assert result["members"]["ABC-132"]["state"] == "done"


def test_a15_unresolved_label_is_incomplete_not_empty(tmp_path, monkeypatch):
    recovery, binding, mapping = _bind(
        tmp_path, lambda outputs: linear_document(outputs, roots=[_LABEL])
    )
    board = _Board()
    board.labels = []
    _install(monkeypatch, board)
    result = read_tracker(recovery, binding, mapping, {"ABC-131": {"state": "done"}})
    assert result["complete"] is False
    assert result["members"] is None


def test_a15_item_not_found_is_inaccessible(tmp_path, monkeypatch):
    recovery, binding, mapping = _bind(
        tmp_path, lambda outputs: linear_document(outputs, roots=[_ITEM])
    )
    board = _Board()
    _install(monkeypatch, board)
    result = read_tracker(recovery, binding, mapping, {})
    assert result["complete"] is True
    assert result["members"]["linear:item-1"]["visibility"] == "inaccessible"


def test_dedicated_project_root_lists_by_project_id(tmp_path, monkeypatch):
    recovery, binding, mapping = _bind(
        tmp_path, lambda outputs: linear_document(outputs, roots=[_PROJECT])
    )
    board = _Board()
    board.issues = [_issue("ABC-131", "Done", projectId="linear:project-1")]
    _install(monkeypatch, board)
    result = read_tracker(recovery, binding, mapping, {})
    assert _selectors(board) == [{"project": "linear:project-1"}]
    assert result["members"]["ABC-131"]["visibility"] == "listed"


def test_undedicated_project_root_stays_incomplete(tmp_path, monkeypatch):
    root = SimpleNamespace(
        kind="project",
        id="linear:project-1",
        dedicated=False,
        workstream="ws-alpha",
        team=None,
    )
    tracker = SimpleNamespace(
        adapter="linear",
        mcp_server="linear",
        read_tools=CLOSED_VERBS,
        repo_skill="SKILL.md",
    )
    binding = SimpleNamespace(tracker=tracker, roots=(root,), workstreams=())
    mapping = load_mapping(MAPPING)
    assert isinstance(mapping, Ok)
    board = _Board()
    _install(monkeypatch, board)
    result = read_tracker(tmp_path, binding, mapping.value, {})
    assert result["complete"] is False
    assert result["members"] is None


def test_partial_pagination_leaves_the_source_incomplete(tmp_path, monkeypatch):
    recovery, binding, mapping = _bind(
        tmp_path, lambda outputs: linear_document(outputs, roots=[_EPIC])
    )
    board = _Board()
    board.pages = [
        {
            "issues": [_issue("ABC-131", "Done")],
            "hasNextPage": True,
            "cursor": "page-2",
        },
        {"issues": [], "hasNextPage": True, "cursor": "page-2"},
    ]
    _install(monkeypatch, board)
    result = read_tracker(recovery, binding, mapping, {})
    assert result["complete"] is False
    assert result["members"] is None


def test_narrowed_verbs_do_not_drop_ids(tmp_path, monkeypatch):
    recovery, binding, mapping = _bind(
        tmp_path,
        lambda outputs: linear_document(
            outputs,
            roots=[_EPIC],
            read_tools=["get_user", "get_issue"],
        ),
    )
    board = _Board()
    _install(monkeypatch, board)
    result = read_tracker(
        recovery, binding, mapping, {"ABC-131": {"via": ["linear:epic-1"]}}
    )
    assert result["complete"] is False
    assert result["members"] is None
    assert _selectors(board) == []


def test_unknown_status_makes_the_source_incomplete(tmp_path, monkeypatch):
    recovery, binding, mapping = _bind(
        tmp_path, lambda outputs: linear_document(outputs, roots=[_EPIC])
    )
    board = _Board()
    board.issues = [_issue("ABC-131", "Weird")]
    _install(monkeypatch, board)
    result = read_tracker(recovery, binding, mapping, {})
    assert result["complete"] is False
    assert result["members"] is None


def test_a17_assignee_and_missing_claim(tmp_path, monkeypatch):
    recovery, binding, mapping = _bind(
        tmp_path,
        lambda outputs: linear_document(
            outputs,
            roots=[_EPIC],
            stream=workstream(accepted_through="Spec"),
        ),
    )
    board = _Board()
    board.issues = [
        _issue("ABC-160", "In Progress"),
        _issue("ABC-161", "Ready", assigneeId="user-me"),
        _issue("ABC-162", "Ready", assigneeId="user-other"),
        _issue("ABC-163", "Ready", assigneeId=None),
    ]
    _install(monkeypatch, board)
    result = read_tracker(recovery, binding, mapping, {})
    members = result["members"]
    assert members["ABC-160"]["claim"] is None
    assert members["ABC-161"]["assignee"] == "self"
    assert members["ABC-162"]["assignee"] == "other"
    assert members["ABC-163"]["assignee"] == "none"
    names = _classes(_world_from(members, accepted="Spec"))
    assert "missing_ownership" in names
    assert names.count("ready_authorized") == 2
    board.user_error = "trust_refused"
    board.calls.clear()
    failed = read_tracker(recovery, binding, mapping, {})
    assert failed["members"]["ABC-161"]["assignee"] == "unknown"
    failed_names = _classes(_world_from(failed["members"], accepted="Spec"))
    assert "ready_authorized" not in failed_names


def test_claims_are_oldest_first_and_reread(tmp_path, monkeypatch):
    recovery, binding, mapping = _bind(
        tmp_path, lambda outputs: linear_document(outputs, roots=[_EPIC])
    )
    board = _Board()
    board.issues = [_issue("ABC-160", "In Progress")]
    board.comments["ABC-160"] = [
        _comment("c-new", "Claimed by ws-alpha-mgr 2026-11-22T02:00:00Z"),
        _comment("c-old", "Claimed by ws-alpha-mgr 2026-11-22T01:00:00Z"),
        _comment(
            "c-reply",
            "Claimed by other-mgr 2026-11-22T00:00:00Z",
            parent_id="c-old",
        ),
    ]
    _install(monkeypatch, board)
    first = read_tracker(recovery, binding, mapping, {})
    second = read_tracker(recovery, binding, mapping, {})
    assert first["members"]["ABC-160"]["claim"]["marker"] == "c-old"
    assert second["members"]["ABC-160"]["claim"]["marker"] == "c-old"
    assert [verb for _server, verb, _args in board.calls].count("list_comments") == 2


def test_equal_claim_timestamps_keep_reversed_order(tmp_path, monkeypatch):
    recovery, binding, mapping = _bind(
        tmp_path, lambda outputs: linear_document(outputs, roots=[_EPIC])
    )
    board = _Board()
    board.issues = [_issue("ABC-160", "In Progress")]
    stamp = "Claimed by ws-alpha-mgr 2026-11-22T01:00:00Z"
    board.comments["ABC-160"] = [_comment("c-a", stamp), _comment("c-b", stamp)]
    _install(monkeypatch, board)
    result = read_tracker(recovery, binding, mapping, {})
    assert result["members"]["ABC-160"]["claim"]["marker"] == "c-b"


def _comment(ident, body, parent_id=None):
    return {
        "id": ident,
        "body": body,
        "parentId": parent_id,
        "quotedText": None,
        "createdAt": "2026-11-22T00:00:00Z",
    }


def _classes(world):
    return [item.class_name for item in evaluate(world).intents]


def _world_from(members, accepted):
    rows = []
    for ident, record in members.items():
        body = dict(record)
        body["id"] = ident
        rows.append(body)
    return {
        "project_status": "open",
        "binding_revision": 7,
        "tracker_complete": True,
        "asks_complete": True,
        "asks": {},
        "now": "2026-11-22T12:00:00Z",
        "handles": [],
        "members": rows,
        "workstreams": [
            {
                "id": "ws-alpha",
                "status": "open",
                "closing_step": "Changelog",
                "claim_labels": ["ws-alpha-mgr"],
                "brief": "",
                "accepted_through": accepted,
                "owner": "owner-session",
            }
        ],
        "receipt_outage": False,
    }


def _git(repo, *args):
    return subprocess.run(
        ["git", "-C", os.fspath(repo), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def _author(monkeypatch):
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Test")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "test@example.com")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Test")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "test@example.com")


def _page(ident, **fields):
    body = {
        "id": ident,
        "state": "Ready",
        "parent": "",
        "labels": [],
        "blocked_by": [],
        "assignee": "",
        "updated": "2026-11-22T00:00:00Z",
        "title": "ignored",
    }
    body.update(fields)
    return "---\n" + safe_dump(body) + "---\nsecret body stays out\n"


def _commit(origin, files, message):
    for relative, content in files.items():
        path = Path(origin) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        _git(origin, "add", "--", relative)
    committed = _git(origin, "commit", "-m", message)
    assert committed.returncode == 0, committed.stderr


def _local(tmp_path, monkeypatch, mapping_text=None):
    _author(monkeypatch)
    recovery, outputs = workspace(tmp_path)
    origin = tmp_path / "origin"
    clone = recovery / "repo"
    origin.mkdir()
    assert _git(origin, "init", "-b", "tickets").returncode == 0
    document = local_document(outputs)
    text = mapping_text or MAPPING
    mapping = load_mapping(text)
    assert isinstance(mapping, Ok)
    raw = safe_dump(document)
    loaded = load_binding(
        raw,
        closed_verbs=CLOSED_VERBS,
        mapping=mapping.value,
        recovery_dir=recovery,
    )
    assert isinstance(loaded, Ok), getattr(loaded, "error", loaded)
    (recovery / "binding.yaml").write_text(raw, encoding="utf-8")
    return recovery, origin, clone, loaded.value, mapping.value


def test_f16_fetch_disables_hooks_and_pins_one_commit(tmp_path, monkeypatch):
    recovery, origin, clone, binding, mapping = _local(tmp_path, monkeypatch)
    _commit(origin, {"tickets/abc-a1b2.md": _page("abc-a1b2")}, "A")
    cloned = subprocess.run(
        ["git", "clone", os.fspath(origin), os.fspath(clone)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert cloned.returncode == 0, cloned.stderr
    hookdir = tmp_path / "hooks"
    hookdir.mkdir()
    marker = tmp_path / "hook-marker"
    hook = hookdir / "reference-transaction"
    hook.write_text(
        '#!/bin/sh\ntouch "' + os.fspath(marker) + '"\n',
        encoding="utf-8",
    )
    hook.chmod(0o755)
    assert _git(clone, "config", "core.hooksPath", os.fspath(hookdir)).returncode == 0
    _commit(origin, {"tickets/abc-a1b2.md": _page("abc-a1b2", state="Backlog")}, "B")
    raw = subprocess.run(
        ["git", "-C", os.fspath(clone), "fetch", "origin", "tickets"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert raw.returncode == 0, raw.stderr
    assert marker.is_file()
    _commit(
        origin, {"tickets/abc-a1b2.md": _page("abc-a1b2", state="In Progress")}, "C"
    )
    marker.unlink()
    head = _git(clone, "rev-parse", "HEAD").stdout
    count = _git(clone, "rev-list", "--count", "HEAD").stdout
    calls = []
    real = subprocess.run

    def _spy(argv, **kwargs):
        env = kwargs.get("env")
        calls.append((list(argv), None if env is None else dict(env)))
        return real(argv, **kwargs)

    monkeypatch.setattr("plugins.project_recovery.readers.subprocess.run", _spy)
    (clone / "tickets").mkdir(exist_ok=True)
    (clone / "tickets" / "abc-ffff.md").write_text(_page("abc-ffff"), encoding="utf-8")
    result = read_tracker(recovery, binding, mapping, {})
    monkeypatch.setattr("plugins.project_recovery.readers.subprocess.run", real)
    pinned = _git(clone, "rev-parse", "origin/tickets").stdout.strip()
    assert result["complete"] is True
    assert result["revision"] == pinned
    assert "abc-ffff" not in result["members"]
    assert "secret body stays out" not in json.dumps(result["members"])
    assert result["members"]["abc-a1b2"]["state"] == "in_progress"
    assert not marker.exists()
    assert _git(clone, "rev-parse", "HEAD").stdout == head
    assert _git(clone, "rev-list", "--count", "HEAD").stdout == count
    commands = []
    for argv, env in calls:
        assert argv[0] == "git"
        overlay = {
            "LC_ALL": None if env is None else env.get("LC_ALL"),
            "GIT_CONFIG_COUNT": None if env is None else env.get("GIT_CONFIG_COUNT"),
            "GIT_CONFIG_KEY_0": None if env is None else env.get("GIT_CONFIG_KEY_0"),
            "GIT_CONFIG_VALUE_0": None
            if env is None
            else env.get("GIT_CONFIG_VALUE_0"),
        }
        assert overlay == {
            "LC_ALL": "C",
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "core.hooksPath",
            "GIT_CONFIG_VALUE_0": "/dev/null",
        }, (argv, overlay)
        commands.append(argv[3])
    assert commands
    assert set(commands) <= {"fetch", "rev-parse", "ls-tree", "show"}


def test_bad_front_matter_omits_the_id_and_is_incomplete(tmp_path, monkeypatch):
    recovery, origin, clone, binding, mapping = _local(tmp_path, monkeypatch)
    _commit(
        origin,
        {
            "tickets/abc-a1b2.md": _page("abc-a1b2"),
            "tickets/abc-c3d4.md": _page("abc-zzzz"),
        },
        "bad",
    )
    assert (
        subprocess.run(
            ["git", "clone", os.fspath(origin), os.fspath(clone)],
            check=False,
            capture_output=True,
            text=True,
        ).returncode
        == 0
    )
    result = read_tracker(recovery, binding, mapping, {})
    assert result["complete"] is False
    assert result["members"] is None


def test_failed_fetch_leaves_the_source_incomplete(tmp_path, monkeypatch):
    recovery, origin, clone, binding, mapping = _local(tmp_path, monkeypatch)
    _commit(origin, {"tickets/abc-a1b2.md": _page("abc-a1b2")}, "A")
    assert (
        subprocess.run(
            ["git", "clone", os.fspath(origin), os.fspath(clone)],
            check=False,
            capture_output=True,
            text=True,
        ).returncode
        == 0
    )
    assert _git(clone, "remote", "remove", "origin").returncode == 0
    result = read_tracker(recovery, binding, mapping, {})
    assert result["complete"] is False
    assert result["members"] is None


def test_duplicate_alias_reads_as_canceled(tmp_path, monkeypatch):
    alias = MAPPING.replace(
        "| canceled | Canceled |",
        "| canceled | `Canceled` `Duplicate` |",
    )
    recovery, origin, clone, binding, mapping = _local(tmp_path, monkeypatch, alias)
    _commit(origin, {"tickets/abc-a1b2.md": _page("abc-a1b2", state="Duplicate")}, "A")
    assert (
        subprocess.run(
            ["git", "clone", os.fspath(origin), os.fspath(clone)],
            check=False,
            capture_output=True,
            text=True,
        ).returncode
        == 0
    )
    result = read_tracker(recovery, binding, mapping, {})
    assert result["complete"] is True
    assert result["members"]["abc-a1b2"]["state"] == "canceled"


def test_local_assignee_claim_and_missing_blocker(tmp_path, monkeypatch):
    recovery, origin, clone, binding, mapping = _local(tmp_path, monkeypatch)
    _commit(
        origin,
        {
            "tickets/abc-a1b2.md": _page(
                "abc-a1b2",
                state="Ready",
                assignee="ws-alpha-mgr",
                blocked_by=["abc-9999"],
            ),
            "tickets/abc-c3d4.md": _page(
                "abc-c3d4", assignee="other-mgr", parent="abc-a1b2"
            ),
        },
        "A",
    )
    assert (
        subprocess.run(
            ["git", "clone", os.fspath(origin), os.fspath(clone)],
            check=False,
            capture_output=True,
            text=True,
        ).returncode
        == 0
    )
    result = read_tracker(recovery, binding, mapping, {})
    assert result["complete"] is True
    ours = result["members"]["abc-a1b2"]
    other = result["members"]["abc-c3d4"]
    assert ours["assignee"] == "self"
    assert ours["claim"]["label"] == "ws-alpha-mgr"
    assert ours["blockers"] == [{"id": "abc-9999", "state": "missing"}]
    assert other["assignee"] == "other"
    assert other["claim"]["marker"] == "other-mgr"


def _clone(origin, clone):
    cloned = subprocess.run(
        ["git", "clone", os.fspath(origin), os.fspath(clone)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert cloned.returncode == 0, cloned.stderr


def test_correction_local_reparent_and_deleted_follow_membership(
    tmp_path, monkeypatch
):
    """A live file with a different epic parent is reparented; a deleted file is not."""
    recovery, origin, clone, binding, mapping = _local(tmp_path, monkeypatch)
    _commit(
        origin,
        {
            "tickets/abc-a1b2.md": _page("abc-a1b2"),
            "tickets/abc-m0v1.md": _page("abc-m0v1", parent="abc-o9o9"),
        },
        "A",
    )
    _clone(origin, clone)
    previous = {
        "abc-m0v1": {
            "state": "in_progress",
            "visibility": "listed",
            "via": ["abc-a1b2"],
            "parent": "abc-a1b2",
        },
        "abc-g0n1": {
            "state": "ready",
            "visibility": "listed",
            "via": ["abc-a1b2"],
            "parent": "abc-a1b2",
        },
    }
    result = read_tracker(recovery, binding, mapping, previous)
    assert result["complete"] is True
    moved = result["members"]["abc-m0v1"]
    deleted = result["members"]["abc-g0n1"]
    assert moved["visibility"] == "reparented_out"
    assert moved["parent"] == "abc-o9o9"
    assert deleted["visibility"] == "inaccessible"


def test_correction_local_unproven_project_chain_is_incomplete(tmp_path, monkeypatch):
    recovery, origin, clone, binding, mapping = _local(tmp_path, monkeypatch)
    _commit(
        origin,
        {"tickets/abc-d4n9.md": _page("abc-d4n9", parent="abc-m1ss", state="Ready")},
        "A",
    )
    _clone(origin, clone)
    previous = {
        "abc-d4n9": {
            "state": "ready",
            "visibility": "listed",
            "via": ["abc-f7a8"],
            "parent": "abc-f7a8",
        }
    }
    result = read_tracker(recovery, binding, mapping, previous)
    assert result["complete"] is False
    assert result["members"] is None
