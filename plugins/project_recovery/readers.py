"""Tracker readers for the linear and local adapters.

Linear calls go through the published read-only MCP function. Local git
commands set the hook-off environment on every invocation, including
fetch, and never run the write recipe. State names are read through
``TrackerMapping.state_aliases``.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

from ruamel.yaml.error import YAMLError

from hermes_yaml import safe_load
from plugins.project_recovery.mapping import (
    key_matches,
    matches_local_assignee,
    matches_local_id,
    matches_local_label,
    member_identity,
)
from tools.mcp_readonly import call_mcp_tool_readonly

_REFUSALS = frozenset(
    {
        "verb_refused",
        "args_refused",
        "scope_refused",
        "hint_refused",
        "trust_refused",
    }
)
_IN_FLIGHT = frozenset({"in_progress", "in_review"})
_BLOCKED = frozenset({"ready", "in_progress", "in_review"})
_CLAIM = re.compile(
    r"^(Claimed|Released) by ([a-z0-9][a-z0-9-]{0,31}) "
    r"([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z)"
    r"(?: \(per orchestrator [a-z0-9][a-z0-9-]{0,31}/[^()/\n]+\))?$"
)
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,64}$")
_SHA = re.compile(r"^[0-9a-fA-F]{7,64}$")
_WRITE = frozenset(
    {
        "add",
        "am",
        "checkout",
        "cherry-pick",
        "clean",
        "commit",
        "merge",
        "push",
        "rebase",
        "reset",
        "revert",
        "worktree",
    }
)


def read_tracker(recovery_dir, binding, mapping, previous_members):
    """Return a tracker read. ``members`` is None when the source is incomplete."""
    previous = previous_members if isinstance(previous_members, dict) else {}
    if binding.tracker.adapter == "local":
        return _read_local(recovery_dir, binding, mapping, previous)
    if binding.tracker.adapter == "linear":
        return _read_linear(recovery_dir, binding, mapping, previous)
    return _incomplete({}, "adapter", None)


def _incomplete(roots, error, revision):
    return {
        "complete": False,
        "error": error,
        "revision": revision,
        "roots": roots,
        "members": None,
    }


def _complete(roots, members, revision):
    return {
        "complete": True,
        "error": None,
        "revision": revision,
        "roots": roots,
        "members": members,
    }


def _allows(binding, verb) -> bool:
    tools = binding.tracker.read_tools
    return tools is None or verb in tools


def _e1(recovery, server, verb, args):
    previous = os.getcwd()
    os.chdir(recovery)
    try:
        return call_mcp_tool_readonly(server, verb, args)
    finally:
        os.chdir(previous)


def _decode(text):
    if text in _REFUSALS or type(text) is not str:
        return None, text if type(text) is str else "unreadable"
    try:
        body = json.loads(text)
    except json.JSONDecodeError:
        return None, "unreadable"
    if (
        isinstance(body, dict)
        and set(body) == {"result"}
        and type(body["result"]) is str
    ):
        try:
            return json.loads(body["result"]), None
        except json.JSONDecodeError:
            return None, "unreadable"
    if (
        isinstance(body, dict)
        and "error" in body
        and "issues" not in body
        and "id" not in body
    ):
        return None, "error"
    return body, None


def _code(payload):
    if isinstance(payload, dict):
        code = payload.get("code")
        if code in {"not_found", "not_permitted"}:
            return code
    return None


def _state_of(mapping, raw):
    if not isinstance(raw, dict):
        return None
    status = raw.get("status")
    if type(status) is not str:
        status = raw.get("state")
    if type(status) is not str:
        return None
    for canonical, aliases in mapping.state_aliases.items():
        if status in aliases:
            return canonical
    return None


def _read_linear(recovery, binding, mapping, previous):
    server = binding.tracker.mcp_server
    me = _linear_me(recovery, binding, server)
    found = {}
    roots = {}
    for root in binding.roots:
        batch, error = _enumerate_root(recovery, binding, server, root)
        if error:
            roots[root.id] = "incomplete"
            return _incomplete(roots, error, None)
        roots[root.id] = "complete"
        for raw in batch:
            built = _from_linear(raw, root, mapping)
            if built is None:
                return _incomplete(roots, "status", None)
            _merge(found, built)
    me_id = me
    classified, error = _classify_missing(
        recovery, binding, mapping, server, previous, found
    )
    if error:
        return _incomplete(roots, error, None)
    found.update(classified)
    error = _fill_linear(recovery, binding, mapping, server, found, me_id)
    if error:
        return _incomplete(roots, error, None)
    return _complete(roots, found, None)


def _linear_me(recovery, binding, server):
    if not _allows(binding, "get_user"):
        return None
    payload, err = _decode(_e1(recovery, server, "get_user", {"query": "me"}))
    if err or not isinstance(payload, dict) or type(payload.get("id")) is not str:
        return None
    return payload["id"]


def _enumerate_root(recovery, binding, server, root):
    if root.kind == "epic":
        return _enumerate_epic(recovery, binding, server, root)
    if root.kind == "label":
        return _enumerate_label(recovery, binding, server, root)
    if root.kind == "project":
        return _enumerate_project(recovery, binding, server, root)
    if root.kind == "item":
        return _enumerate_item(recovery, binding, server, root)
    return None, "root"


def _enumerate_epic(recovery, binding, server, root):
    if not _allows(binding, "list_issues"):
        return None, "verbs"
    rows = _pages(recovery, server, {"parentId": root.id})
    if rows is None:
        return None, "pagination"
    epic, error = _optional_epic(recovery, binding, server, root.id)
    if error:
        return None, error
    if epic is not None:
        rows.append(epic)
    return rows, None


def _optional_epic(recovery, binding, server, ident):
    if not _allows(binding, "get_issue"):
        return None, "verbs"
    payload, err = _decode(_e1(recovery, server, "get_issue", {"id": ident}))
    if err:
        return None, "read"
    if _code(payload) == "not_found":
        return None, None
    if _code(payload) == "not_permitted" or not isinstance(payload, dict):
        return None, "read"
    if payload.get("id") != ident:
        return None, "read"
    return payload, None


def _enumerate_label(recovery, binding, server, root):
    if not _allows(binding, "list_issue_labels") or not _allows(binding, "list_issues"):
        return None, "verbs"
    payload, err = _decode(
        _e1(recovery, server, "list_issue_labels", {"team": root.team})
    )
    if (
        err
        or not isinstance(payload, dict)
        or not isinstance(payload.get("labels"), list)
    ):
        return None, "unresolved"
    if not any(
        isinstance(item, dict) and item.get("id") == root.id
        for item in payload["labels"]
    ):
        return None, "unresolved"
    rows = _pages(recovery, server, {"label": root.id, "team": root.team})
    if rows is None:
        return None, "pagination"
    return rows, None


def _enumerate_project(recovery, binding, server, root):
    if not root.dedicated or not _allows(binding, "list_issues"):
        return None, "verbs"
    rows = _pages(recovery, server, {"project": root.id})
    if rows is None:
        return None, "pagination"
    return rows, None


def _enumerate_item(recovery, binding, server, root):
    if not _allows(binding, "get_issue"):
        return None, "verbs"
    payload, err = _decode(_e1(recovery, server, "get_issue", {"id": root.id}))
    if err:
        return None, "read"
    code = _code(payload)
    if code == "not_found":
        return [{"id": root.id, "code": "not_found"}], None
    if code == "not_permitted":
        return [{"id": root.id, "code": "not_permitted"}], None
    if not isinstance(payload, dict) or payload.get("id") != root.id:
        return None, "read"
    return [payload], None


def _pages(recovery, server, selector):
    cursor = None
    seen = set()
    rows = []
    while True:
        args = dict(selector)
        if cursor:
            args["cursor"] = cursor
        payload, err = _decode(_e1(recovery, server, "list_issues", args))
        if (
            err
            or not isinstance(payload, dict)
            or not isinstance(payload.get("issues"), list)
        ):
            return None
        rows.extend(payload["issues"])
        if not payload.get("hasNextPage"):
            return rows
        cursor = payload.get("cursor")
        if type(cursor) is not str or not cursor or cursor in seen:
            return None
        seen.add(cursor)


def _from_linear(raw, root, mapping):
    if not isinstance(raw, dict):
        return None
    if raw.get("code") in {"not_found", "not_permitted"}:
        ident = member_identity(raw.get("id"), title=raw.get("title"))
        if type(ident) is not str:
            return None
        return _shell(ident, root, "inaccessible", "backlog")
    state = _state_of(mapping, raw)
    if state is None:
        return None
    ident = member_identity(
        raw.get("id"),
        key=raw.get("key") if type(raw.get("key")) is str else None,
        title=raw.get("title"),
        state=state,
    )
    if type(ident) is not str:
        return None
    record = _record(ident, raw, root, mapping, state)
    record["visibility"] = "listed"
    record["_assignee_id"] = raw.get("assigneeId")
    return record


def _record(ident, raw, root, mapping, state):
    key = raw.get("key")
    parent = raw.get("parentId", raw.get("parent"))
    updated = raw.get("updatedAt", raw.get("updated"))
    kind = raw.get("type")
    return {
        "key": key if type(key) is str and key_matches(mapping, key) else None,
        "type": kind if type(kind) is str and kind else "task",
        "state": state,
        "parent": parent if type(parent) is str else None,
        "via": [root.id],
        "workstream": root.workstream,
        "claim": None,
        "assignee": "unknown",
        "blockers": [],
        "tracker_updated": updated if type(updated) is str else "",
        "visibility": "listed",
        "archived": raw.get("archived") is True,
        "_id": ident,
    }


def _shell(ident, root, visibility, state):
    return {
        "key": None,
        "type": "task",
        "state": state,
        "parent": None,
        "via": [root.id],
        "workstream": root.workstream,
        "claim": None,
        "assignee": "unknown",
        "blockers": [],
        "tracker_updated": "",
        "visibility": visibility,
        "archived": False,
        "_id": ident,
    }


def _merge(found, record):
    ident = record.pop("_id")
    current = found.get(ident)
    if current is None:
        found[ident] = record
        return
    for item in record["via"]:
        if item not in current["via"]:
            current["via"].append(item)


def _classify_missing(recovery, binding, mapping, server, previous, found):
    roots = {root.id: root for root in binding.roots}
    classified = {}
    for ident, prior in previous.items():
        if ident in found:
            continue
        record, error = _one_missing(
            recovery, binding, mapping, server, ident, prior, roots
        )
        if error:
            return None, error
        classified[ident] = record
    return classified, None


def _one_missing(recovery, binding, mapping, server, ident, prior, roots):
    via = _via(prior)
    if via and all(item not in roots for item in via):
        return _with_visibility(prior, "unbound"), None
    if not _allows(binding, "get_issue"):
        return None, "read"
    payload, err = _decode(_e1(recovery, server, "get_issue", {"id": ident}))
    if err:
        return None, "read"
    code = _code(payload)
    if code in {"not_found", "not_permitted"}:
        return _with_visibility(prior, "inaccessible"), None
    if not isinstance(payload, dict):
        return None, "read"
    relation = _relation(payload, via, roots)
    if relation == "match":
        root = roots[via[0]]
        built = _from_linear(payload, root, mapping)
        if built is None:
            return None, "status"
        built["visibility"] = "listed"
        built.pop("_id", None)
        return built, None
    if relation == "different":
        updated = _with_visibility(prior, "reparented_out")
        parent = payload.get("parentId")
        if type(parent) is str:
            updated["parent"] = parent
        return updated, None
    return None, "read"


def _via(prior):
    raw = prior.get("via") if isinstance(prior, dict) else None
    if type(raw) is str:
        return [raw]
    if isinstance(raw, list):
        return [item for item in raw if type(item) is str]
    return []


def _with_visibility(prior, visibility):
    body = {key: value for key, value in prior.items() if not key.startswith("_")}
    body["visibility"] = visibility
    return body


def _relation(payload, via, roots):
    if not via:
        return "unknown"
    unknown = False
    for ident in via:
        root = roots.get(ident)
        if root is None:
            unknown = True
            continue
        verdict = _one_relation(payload, root)
        if verdict == "match":
            return "match"
        if verdict == "unknown":
            unknown = True
    return "unknown" if unknown else "different"


def _one_relation(payload, root):
    if root.kind == "epic":
        return _id_relation(
            payload.get("parentId"), root.id, payload.get("id") == root.id
        )
    if root.kind == "label":
        labels = payload.get("labelIds")
        if not isinstance(labels, list):
            return "unknown"
        return "match" if root.id in labels else "different"
    if root.kind == "project":
        return _id_relation(payload.get("projectId"), root.id, False)
    if payload.get("id") == root.id:
        return "match"
    return "different"


def _id_relation(value, expected, also):
    if also or value == expected:
        return "match"
    if type(value) is str:
        return "different"
    return "unknown"


def _fill_linear(recovery, binding, mapping, server, found, me):
    for record in found.values():
        record.pop("_id", None)
        if "_assignee_id" not in record:
            continue
        assignee_id = record.pop("_assignee_id")
        record["assignee"] = _linear_assignee(me, assignee_id, record["visibility"])
    for ident, record in found.items():
        if record["visibility"] != "listed":
            continue
        if record["state"] in _IN_FLIGHT:
            claim, error = _linear_claims(recovery, binding, server, ident)
            if error:
                return error
            record["claim"] = claim
        if record["state"] in _BLOCKED:
            blockers, error = _linear_blockers(
                recovery, binding, mapping, server, ident, found
            )
            if error:
                return error
            record["blockers"] = blockers
    return None


def _linear_assignee(me, assignee_id, visibility):
    if visibility != "listed":
        return "unknown"
    if me is None:
        return "unknown"
    if assignee_id is None or assignee_id == "":
        return "none"
    if assignee_id == me:
        return "self"
    return "other"


def _linear_claims(recovery, binding, server, ident):
    if not _allows(binding, "list_comments"):
        return None, "verbs"
    cursor = None
    seen = set()
    pages = []
    while True:
        args = {"issueId": ident, "orderBy": "createdAt"}
        if cursor:
            args["cursor"] = cursor
        payload, err = _decode(_e1(recovery, server, "list_comments", args))
        if (
            err
            or not isinstance(payload, dict)
            or not isinstance(payload.get("comments"), list)
        ):
            return None, "read"
        pages.extend(payload["comments"])
        if not payload.get("hasNextPage"):
            break
        cursor = payload.get("cursor")
        if type(cursor) is not str or not cursor or cursor in seen:
            return None, "pagination"
        seen.add(cursor)
    return _earliest_claim(list(reversed(pages))), None


def _earliest_claim(oldest):
    live = []
    for comment in oldest:
        if not isinstance(comment, dict):
            continue
        if comment.get("parentId") is not None or comment.get("quotedText") is not None:
            continue
        body = comment.get("body")
        if type(body) is not str:
            continue
        match = _CLAIM.fullmatch(body)
        if match is None:
            continue
        kind, label, at = match.group(1), match.group(2), match.group(3)
        if kind == "Released":
            live = [item for item in live if item["label"] != label]
            continue
        marker = comment.get("id")
        live.append(
            {
                "label": label,
                "marker": marker if type(marker) is str else label,
                "at": at,
            }
        )
    if not live:
        return None
    return live[0]


def _linear_blockers(recovery, binding, mapping, server, ident, found):
    if not _allows(binding, "get_issue"):
        return None, "verbs"
    payload, err = _decode(
        _e1(recovery, server, "get_issue", {"id": ident, "includeRelations": True})
    )
    if err or not isinstance(payload, dict) or _code(payload):
        return None, "read"
    relations = (
        payload.get("relations") if isinstance(payload.get("relations"), dict) else {}
    )
    blocked = relations.get("blockedBy", relations.get("blocked_by"))
    if blocked is None:
        return [], None
    if not isinstance(blocked, list):
        return None, "read"
    rows = []
    for item in blocked:
        mapped, error = _one_blocker(recovery, binding, mapping, server, item, found)
        if error:
            return None, error
        rows.append(mapped)
    return rows, None


def _one_blocker(recovery, binding, mapping, server, item, found):
    if not isinstance(item, dict) or type(item.get("id")) is not str:
        return None, "read"
    status = item.get("status", item.get("state"))
    if type(status) is str:
        state = _state_of(mapping, {"status": status})
        if state is None:
            return None, "status"
        return {"id": item["id"], "state": state}, None
    if item["id"] not in found and not _known_root(binding, item["id"]):
        return None, "read"
    payload, err = _decode(_e1(recovery, server, "get_issue", {"id": item["id"]}))
    if err or _code(payload):
        return None, "read"
    state = _state_of(mapping, payload if isinstance(payload, dict) else {})
    if state is None:
        return None, "status"
    return {"id": item["id"], "state": state}, None


def _known_root(binding, ident) -> bool:
    return any(root.id == ident for root in binding.roots)


def _read_local(recovery, binding, mapping, previous):
    tracker = binding.tracker
    if not _REF.fullmatch(tracker.remote or "") or not _REF.fullmatch(
        tracker.branch or ""
    ):
        return _incomplete({}, "pattern", None)
    repo = _repo_root(recovery, tracker.repo_skill)
    if repo is None:
        return _incomplete({}, "repo", None)
    fetched = _git(repo, ["fetch", tracker.remote, tracker.branch])
    if fetched.returncode != 0:
        return _incomplete({}, "fetch", None)
    parsed = _git(repo, ["rev-parse", f"{tracker.remote}/{tracker.branch}"])
    sha = parsed.stdout.strip()
    if parsed.returncode != 0 or _SHA.fullmatch(sha) is None:
        return _incomplete({}, "fetch", None)
    listed = _git(repo, ["ls-tree", sha, "tickets/"])
    if listed.returncode != 0:
        return _incomplete({}, "read", sha)
    idents, bad = _tree_ids(listed.stdout, tracker.prefix)
    if bad:
        return _incomplete({}, "pattern", sha)
    docs, error = _local_docs(repo, sha, idents, mapping, tracker.prefix)
    if error:
        return _incomplete({}, error, sha)
    roots = {}
    found = {}
    for root in binding.roots:
        roots[root.id] = "complete"
        for ident in _selected(docs, root):
            built = _from_local(ident, docs[ident], root, mapping, binding)
            if built is None:
                return _incomplete(roots, "pattern", sha)
            _merge(found, built)
    error = _local_missing(previous, found, binding, docs)
    if error:
        return _incomplete(roots, error, sha)
    _local_blockers(found, docs, mapping)
    if _local_blocker_error(found):
        return _incomplete(roots, "pattern", sha)
    return _complete(roots, found, sha)


def _repo_root(recovery, skill):
    path = Path(skill)
    if not path.is_absolute():
        path = Path(recovery) / skill
    probe = path if path.is_dir() else path.parent
    for parent in [probe, *probe.parents]:
        if (parent / ".git").exists():
            return parent
    return None


def _git_env():
    env = {
        "LC_ALL": "C",
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "core.hooksPath",
        "GIT_CONFIG_VALUE_0": "/dev/null",
    }
    for name in (
        "PATH",
        "SYSTEMROOT",
        "PATHEXT",
        "WINDIR",
        "COMSPEC",
        "TMP",
        "TEMP",
        "TMPDIR",
    ):
        value = os.environ.get(name)
        if type(value) is str and value:
            env[name] = value
    return env


def _git(repo, args):
    if args and args[0] in _WRITE:
        raise RuntimeError("write recipe")
    return subprocess.run(
        ["git", "-C", os.fspath(repo), *args],
        env=_git_env(),
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def _tree_ids(text, prefix):
    idents = []
    bad = False
    for line in text.splitlines():
        if not line or "\t" not in line:
            continue
        meta, name = line.split("\t", 1)
        if not meta.startswith("100644"):
            continue
        base = Path(name).name
        if not base.endswith(".md"):
            bad = True
            continue
        ident = base[: -len(".md")]
        if not matches_local_id(prefix, ident):
            bad = True
            continue
        idents.append(ident)
    return idents, bad


def _local_docs(repo, sha, idents, mapping, prefix):
    docs = {}
    for ident in idents:
        if not matches_local_id(prefix, ident):
            return None, "pattern"
        shown = _git(repo, ["show", f"{sha}:tickets/{ident}.md"])
        if shown.returncode != 0:
            return None, "read"
        front = _front_matter(shown.stdout)
        if front is None or front.get("id") != ident:
            return None, "front_matter"
        if _state_of(mapping, front) is None:
            return None, "status"
        if _bad_local_fields(front, prefix):
            return None, "pattern"
        docs[ident] = front
    return docs, None


def _front_matter(text):
    if type(text) is not str or not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    try:
        loaded = safe_load(parts[1])
    except YAMLError:
        return None
    if not isinstance(loaded, dict):
        return None
    return loaded


def _bad_local_fields(front, prefix) -> bool:
    parent = front.get("parent", "")
    if parent not in ("", None) and not matches_local_id(prefix, parent):
        return True
    labels = front.get("labels", [])
    if not isinstance(labels, list):
        return True
    for label in labels:
        if type(label) is not str or not _label_ok(prefix, label):
            return True
    blocked = front.get("blocked_by", [])
    if not isinstance(blocked, list):
        return True
    return any(
        type(item) is not str or not matches_local_id(prefix, item) for item in blocked
    )


def _label_ok(prefix, label) -> bool:
    return matches_local_label(label) or matches_local_id(prefix, label)


def _selected(docs, root):
    if root.kind == "item":
        return [root.id] if root.id in docs else []
    if root.kind == "epic":
        chosen = [root.id] if root.id in docs else []
        chosen.extend(
            ident for ident, doc in docs.items() if doc.get("parent") == root.id
        )
        return chosen
    if root.kind == "label":
        return [
            ident
            for ident, doc in docs.items()
            if root.id in (doc.get("labels") or [])
            or root.name in (doc.get("labels") or [])
        ]
    if root.kind == "project":
        return [ident for ident in docs if _reaches(docs, ident, root.id, set(), 0)]
    return []


def _reaches(docs, ident, root_id, seen, hops) -> bool:
    if hops > 5 or ident in seen:
        return False
    if ident == root_id:
        return True
    parent = docs.get(ident, {}).get("parent")
    if parent == root_id:
        return True
    if type(parent) is not str or parent not in docs:
        return False
    return _reaches(docs, parent, root_id, seen | {ident}, hops + 1)


def _from_local(ident, front, root, mapping, binding):
    state = _state_of(mapping, front)
    if state is None:
        return None
    native = member_identity(ident, title=front.get("title"), state=state)
    labels = _claim_labels(binding, root.workstream)
    assignee, claim = _local_claim(front, labels)
    if assignee is None:
        return None
    record = _record(native, front, root, mapping, state)
    record["assignee"] = assignee
    record["claim"] = claim
    record["visibility"] = "listed"
    record["_blocked"] = list(front.get("blocked_by") or [])
    return record


def _claim_labels(binding, workstream):
    for item in binding.workstreams:
        if item.id == workstream:
            return set(item.owner.claim_labels)
    return set()


def _local_claim(front, labels):
    raw = front.get("assignee", "")
    if raw is None:
        raw = ""
    if type(raw) is not str:
        return None, None
    if raw == "":
        return "none", None
    if not matches_local_assignee(raw):
        return None, None
    updated = front.get("updated", front.get("updated_at", ""))
    claim = {
        "label": raw,
        "marker": raw,
        "at": updated if type(updated) is str else "",
    }
    return ("self" if raw in labels else "other"), claim


def _local_missing(previous, found, binding, docs):
    roots = {root.id: root for root in binding.roots}
    for ident, prior in previous.items():
        if ident in found:
            continue
        error = _one_local_missing(ident, prior, roots, docs, found)
        if error:
            return error
    return None


def _one_local_missing(ident, prior, roots, docs, found):
    via = _via(prior)
    if via and all(item not in roots for item in via):
        found[ident] = _with_visibility(prior, "unbound")
        return None
    front = docs.get(ident)
    if not isinstance(front, dict):
        found[ident] = _with_visibility(prior, "inaccessible")
        return None
    if _local_relation(front, via, roots, docs) != "different":
        return "read"
    found[ident] = _reparented_local(prior, front)
    return None


def _reparented_local(prior, front):
    updated = _with_visibility(prior, "reparented_out")
    parent = front.get("parent")
    if type(parent) is str:
        updated["parent"] = parent
    return updated


def _local_relation(front, via, roots, docs):
    if not via:
        return "unknown"
    unknown = False
    for ident in via:
        root = roots.get(ident)
        if root is None:
            unknown = True
            continue
        verdict = _local_one_relation(front, root, docs)
        if verdict == "match":
            return "match"
        if verdict == "unknown":
            unknown = True
    return "unknown" if unknown else "different"


def _local_one_relation(front, root, docs):
    if root.kind == "epic":
        return _id_relation(
            front.get("parent"), root.id, front.get("id") == root.id
        )
    if root.kind == "label":
        return _local_label_relation(front, root)
    if root.kind == "project":
        return _project_relation(docs, front.get("id"), root.id)
    if front.get("id") == root.id:
        return "match"
    return "different"


def _local_label_relation(front, root):
    labels = front.get("labels")
    if not isinstance(labels, list):
        return "unknown"
    if root.id in labels or root.name in labels:
        return "match"
    return "different"


def _project_relation(docs, ident, root_id):
    if type(ident) is not str:
        return "unknown"
    if _reaches(docs, ident, root_id, set(), 0):
        return "match"
    return _project_chain(docs, ident, root_id)


def _project_chain(docs, ident, root_id):
    seen = set()
    current = ident
    for _hop in range(6):
        if current in seen:
            return "unknown"
        seen.add(current)
        front = docs.get(current)
        if not isinstance(front, dict):
            return "unknown"
        parent = front.get("parent")
        if parent == root_id:
            return "match"
        if parent in ("", None):
            return "different"
        if type(parent) is not str or parent not in docs:
            return "unknown"
        current = parent
    return "unknown"


def _local_blockers(found, docs, mapping):
    for record in found.values():
        blocked = record.pop("_blocked", None)
        record.pop("_id", None)
        if blocked is None or record["visibility"] != "listed":
            record.setdefault("blockers", record.get("blockers") or [])
            continue
        if record["state"] not in _BLOCKED:
            record["blockers"] = []
            continue
        rows = []
        for ident in blocked:
            front = docs.get(ident)
            if front is None:
                rows.append({"id": ident, "state": "missing"})
                continue
            state = _state_of(mapping, front)
            if state is None:
                record["_blocker_error"] = True
                return
            rows.append({"id": ident, "state": state})
        record["blockers"] = rows


def _local_blocker_error(found) -> bool:
    return any(record.pop("_blocker_error", False) for record in found.values())
