"""Read-only MCP call for a non-model scanner.

Scope comes from ``binding.yaml``, the previous ``state/snapshot.json``,
and ids this process's ``list_issues`` returned. The signature takes no
allowlist. Refusals happen before any RPC. The plugin is not imported.
list_comments eligibility reads canonical snapshot state, or maps a status
this process just enumerated through ``state/aliases.json``. That file is
a versioned projection of aliases the scanner already parsed. This module
does not parse Mapping markdown.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from ruamel.yaml.error import YAMLError

_CLOSED = (
    "list_issues",
    "get_issue",
    "list_comments",
    "list_issue_labels",
    "get_user",
)
_REFUSALS = frozenset(
    {
        "verb_refused",
        "args_refused",
        "scope_refused",
        "hint_refused",
        "trust_refused",
    }
)
_ELIGIBLE = frozenset({"ready", "in_progress", "in_review"})
_CANONICAL = (
    "backlog",
    "ready",
    "in_progress",
    "in_review",
    "done",
    "canceled",
)
_ALIAS_SCHEMA = "project-recovery-aliases/1"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._-]{0,200}$")
_SECRET = re.compile(
    r"https?://\S+|file://\S+|ghp_[A-Za-z0-9_]+|sk-[A-Za-z0-9_\-]+"
    r"|lin_api_\S+|Bearer\s+\S+",
    re.IGNORECASE,
)
_HOME_PATH = re.compile(r"/home/\S*|/Users/\S*")

_ENUM: dict[tuple, dict[str, str]] = {}
_USER_ONCE: set[tuple] = set()


@dataclass
class _Scope:
    server: str
    revision: int
    scan: int
    verbs: frozenset
    wider: bool
    roots: tuple
    members: dict
    binding_path: str
    aliases: dict
    alias_cache: bool

    def key(self):
        return (self.binding_path, self.server, self.revision, self.scan)


def call_mcp_tool_readonly(server, verb, args, timeout=30):
    """Return rendered tool text, or a refusal code. No RPC on refusal."""
    if _bad_call(server, verb, args, timeout):
        return "args_refused" if type(verb) is str else "verb_refused"
    loaded = _load_scope()
    if isinstance(loaded, str):
        return loaded
    if server != loaded.server:
        return "scope_refused"
    refused = _refuse_verb(loaded, verb)
    if refused:
        return refused
    outgoing = _outgoing(loaded, verb, args)
    if isinstance(outgoing, str):
        return outgoing
    try:
        return _invoke(loaded, verb, outgoing, float(timeout))
    except Exception as exc:  # health: allow BLE001 -- sanitized, not logged
        return _public_error(exc)


call_mcp_tool_readonly.closed_verbs = _CLOSED


def _bad_call(server, verb, args, timeout) -> bool:
    if type(server) is not str or not server or type(args) is not dict:
        return True
    if type(verb) is not str:
        return True
    if type(timeout) is bool or type(timeout) not in (int, float) or timeout <= 0:
        return True
    return False


def _load_scope():
    workdir = Path.cwd()
    binding_path = workdir / "binding.yaml"
    try:
        text = binding_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        return "scope_refused"
    try:
        from hermes_yaml import safe_load

        data = safe_load(text)
    except YAMLError:
        return "scope_refused"
    parsed = _parse_binding(data)
    if parsed is None:
        return "scope_refused"
    snap = _parse_snapshot(workdir / "state" / "snapshot.json")
    if isinstance(snap, str):
        return snap
    scan, members = snap
    aliases, fresh = _load_aliases(workdir, parsed["revision"])
    scope = _Scope(
        parsed["server"],
        parsed["revision"],
        scan,
        parsed["verbs"],
        parsed["wider"],
        parsed["roots"],
        members,
        str(binding_path.resolve()),
        aliases,
        fresh,
    )
    return scope


def _parse_binding(data):
    if not isinstance(data, dict):
        return None
    if data.get("schema") != "project-recovery-binding/1":
        return None
    revision = data.get("revision")
    if type(revision) is not int or type(revision) is bool:
        return None
    tracker = data.get("tracker")
    if not isinstance(tracker, dict) or tracker.get("adapter") != "linear":
        return None
    server = tracker.get("mcp_server")
    skill = tracker.get("repo_skill")
    if type(server) is not str or not server or type(skill) is not str:
        return None
    verbs, wider = _verbs(tracker.get("read_tools", None), "read_tools" in tracker)
    if verbs is None:
        return None
    roots = _roots(data.get("roots"))
    if roots is None:
        return None
    return {
        "server": server,
        "revision": revision,
        "skill": skill,
        "verbs": verbs,
        "wider": wider,
        "roots": roots,
    }


def _verbs(raw, present):
    if not present:
        return frozenset(_CLOSED), False
    if not isinstance(raw, list) or any(type(item) is not str for item in raw):
        return None, False
    if len(set(raw)) != len(raw):
        return None, False
    closed = set(_CLOSED)
    if any(item not in closed for item in raw):
        return frozenset(), True
    return frozenset(raw), False


def _roots(raw):
    if not isinstance(raw, list):
        return None
    roots = []
    for item in raw:
        root = _one_root(item)
        if root is None:
            return None
        roots.append(root)
    return tuple(roots)


def _one_root(item):
    if not isinstance(item, dict):
        return None
    kind = item.get("kind")
    ident = item.get("id")
    if kind not in {"epic", "label", "project", "item"} or not _valid_id(ident):
        return None
    root = {"kind": kind, "id": ident, "team": None, "dedicated": False}
    if kind == "label":
        team = item.get("team")
        if type(team) is not str or not team:
            return None
        root["team"] = team
    if kind == "project":
        root["dedicated"] = item.get("dedicated") is True
    return root


def _parse_snapshot(path: Path):
    if not path.is_file():
        return 0, {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return "scope_refused"
    if not isinstance(data, dict):
        return "scope_refused"
    scan = data.get("scan", 0)
    if type(scan) is not int or type(scan) is bool or scan < 0:
        return "scope_refused"
    raw_members = data.get("members", {})
    if not isinstance(raw_members, dict):
        return "scope_refused"
    members = {}
    for ident, body in raw_members.items():
        if not _valid_id(ident):
            return "scope_refused"
        state = body.get("state") if isinstance(body, dict) else None
        members[ident] = state if type(state) is str else None
    return scan, members


def _load_aliases(workdir: Path, revision: int):
    loaded = _read_alias_cache(workdir / "state" / "aliases.json")
    if not _alias_document(loaded, revision):
        return {}, False
    projected = _project_aliases(loaded.get("state_aliases"))
    if projected is None:
        return {}, False
    return projected, True


def _read_alias_cache(path: Path):
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None


def _alias_document(loaded, revision: int) -> bool:
    if not isinstance(loaded, dict) or loaded.get("schema") != _ALIAS_SCHEMA:
        return False
    cached = loaded.get("binding_revision")
    return type(cached) is int and cached == revision


def _project_aliases(raw):
    if not isinstance(raw, dict) or set(raw) != set(_CANONICAL):
        return None
    projected = {}
    for name in _CANONICAL:
        values = raw[name]
        if not _native_names(values):
            return None
        projected[name] = tuple(values)
    return projected


def _native_names(values) -> bool:
    if type(values) is not list or not values:
        return False
    return all(type(item) is str and item != "" for item in values)


def _refuse_verb(scope: _Scope, verb: str):
    if scope.wider or verb not in _CLOSED or verb not in scope.verbs:
        return "verb_refused"
    return None


def _outgoing(scope: _Scope, verb: str, args: dict):
    checker = _CHECKS.get(verb)
    if checker is None:
        return "verb_refused"
    return checker(scope, args)


def _check_list(scope: _Scope, args: dict):
    cursor, rest = _cursor(args)
    if cursor == "args_refused":
        return "args_refused"
    mode = _list_mode(rest, args)
    if isinstance(mode, str):
        return mode
    kind, ident = mode
    if not _root_allows(scope, kind, ident, args):
        return "scope_refused"
    outgoing = dict(rest)
    if cursor:
        outgoing["cursor"] = cursor
    outgoing["limit"] = 250
    outgoing["includeArchived"] = True
    return outgoing


def _cursor(args: dict):
    if "cursor" not in args:
        return None, args
    cursor = args["cursor"]
    if type(cursor) is not str or not cursor:
        return "args_refused", None
    rest = {key: value for key, value in args.items() if key != "cursor"}
    return cursor, rest


def _list_mode(rest, args):
    keys = set(rest)
    if keys == {"parentId"}:
        return _ident_mode("epic", args.get("parentId"))
    if keys == {"label", "team"}:
        return _ident_mode("label", args.get("label"))
    if keys == {"project"}:
        return _ident_mode("project", args.get("project"))
    return "args_refused"


def _ident_mode(kind, ident):
    if not _valid_id(ident):
        return "args_refused"
    return kind, ident


def _root_allows(scope: _Scope, kind: str, ident: str, args: dict) -> bool:
    if kind == "label":
        team = args.get("team")
        if type(team) is not str:
            return False
        return any(
            root["kind"] == "label" and root["id"] == ident and root["team"] == team
            for root in scope.roots
        )
    if kind == "project":
        return any(
            root["kind"] == "project" and root["id"] == ident and root["dedicated"]
            for root in scope.roots
        )
    return any(root["kind"] == kind and root["id"] == ident for root in scope.roots)


def _check_issue(scope: _Scope, args: dict):
    keys = set(args)
    if "includeRelations" in keys:
        if type(args["includeRelations"]) is not bool:
            return "args_refused"
        keys.discard("includeRelations")
    if keys != {"id"} or not _valid_id(args.get("id")):
        return "args_refused"
    if not _in_scope(scope, args["id"]):
        return "scope_refused"
    outgoing = {"id": args["id"]}
    if "includeRelations" in args:
        outgoing["includeRelations"] = args["includeRelations"]
    return outgoing


def _check_comments(scope: _Scope, args: dict):
    cursor, rest = _cursor(args)
    if cursor == "args_refused" or set(rest) != {"issueId", "orderBy"}:
        return "args_refused"
    if rest.get("orderBy") != "createdAt" or not _valid_id(rest.get("issueId")):
        return "args_refused"
    ident = rest["issueId"]
    if not _in_scope(scope, ident) or _member_state(scope, ident) not in _ELIGIBLE:
        return "scope_refused"
    outgoing = {"issueId": ident, "orderBy": "createdAt", "limit": 250}
    if cursor:
        outgoing["cursor"] = cursor
    return outgoing


def _check_labels(scope: _Scope, args: dict):
    if set(args) != {"team"} or type(args.get("team")) is not str or not args["team"]:
        return "args_refused"
    team = args["team"]
    if not any(
        root["kind"] == "label" and root["team"] == team for root in scope.roots
    ):
        return "scope_refused"
    return {"team": team}


def _check_user(scope: _Scope, args: dict):
    if args != {"query": "me"}:
        return "args_refused"
    if scope.key() in _USER_ONCE:
        return "args_refused"
    return {"query": "me"}


_CHECKS = {
    "list_issues": _check_list,
    "get_issue": _check_issue,
    "list_comments": _check_comments,
    "list_issue_labels": _check_labels,
    "get_user": _check_user,
}


def _valid_id(ident) -> bool:
    return type(ident) is str and _ID.fullmatch(ident) is not None


def _in_scope(scope: _Scope, ident: str) -> bool:
    if any(root["id"] == ident for root in scope.roots):
        return True
    if ident in scope.members:
        return True
    return ident in _ENUM.get(scope.key(), {})


def _member_state(scope: _Scope, ident: str):
    enumerated = _ENUM.get(scope.key(), {})
    if ident in enumerated:
        if not scope.alias_cache:
            return None
        return _canonical(scope, enumerated[ident])
    state = scope.members.get(ident)
    if state in _CANONICAL:
        return state
    return None


def _canonical(scope: _Scope, raw: str):
    for name, aliases in scope.aliases.items():
        if raw in aliases:
            return name
    return None


def _invoke(scope: _Scope, verb: str, outgoing: dict, timeout: float):
    from tools import mcp_tool
    from tools.mcp_tool_discovery import _get_connected_server_for_call
    from tools.mcp_tool_handlers import _render_call_tool_result, _trust_gate_check
    from tools.mcp_tool_loop import _run_on_mcp_loop
    from tools.mcp_tool_scope import _resolve_server_key

    error = _trust_gate_check(scope.server, verb, [], outgoing)
    if error is not None:
        return "trust_refused"
    server = _get_connected_server_for_call(scope.server)
    if server is None or getattr(server, "session", None) is None:
        return _sanitize("server unavailable")
    hint_key = _resolve_server_key(scope.server)

    async def _call():
        lock = getattr(server, "_rpc_lock", None)
        if lock is None:
            return "hint_refused"
        async with lock:
            hints = mcp_tool._tool_read_only_hints.get(hint_key, {})
            if hints.get(verb) is not True:
                return "hint_refused"
            if verb == "get_user":
                _USER_ONCE.add(scope.key())
            return await server.session.call_tool(verb, arguments=outgoing)

    result = _run_on_mcp_loop(_call, timeout=timeout)
    if type(result) is str and result in _REFUSALS:
        return result
    _remember(scope, verb, result)
    if _coded(result) is not None:
        return _sanitize(json.dumps(_coded(result), ensure_ascii=False))
    return _sanitize(_render_call_tool_result(result, scope.server))


def _coded(result):
    payload = _payload(result)
    if not isinstance(payload, dict):
        return None
    code = payload.get("code")
    if code in {"not_found", "not_permitted"}:
        return {"code": code}
    return None


def _remember(scope: _Scope, verb: str, result) -> None:
    if verb != "list_issues":
        return
    payload = _payload(result)
    issues = payload.get("issues") if isinstance(payload, dict) else None
    if not isinstance(issues, list):
        return
    bucket = _ENUM.setdefault(scope.key(), {})
    for issue in issues:
        if not isinstance(issue, dict) or not _valid_id(issue.get("id")):
            continue
        status = issue.get("status", issue.get("state"))
        bucket[issue["id"]] = status if type(status) is str else ""


def _payload(result):
    content = getattr(result, "content", None) or []
    chunks = []
    for block in content:
        text = getattr(block, "text", None)
        if type(text) is str:
            chunks.append(text)
    raw = "\n".join(chunks).strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _public_error(exc: BaseException) -> str:
    return _sanitize(str(exc)) or "[redacted]"


def _sanitize(text: str) -> str:
    home = str(Path.home())
    if home and home not in {"/", ""}:
        text = text.replace(home, "[redacted]")
    text = _HOME_PATH.sub("[redacted]", text)
    text = _SECRET.sub("[redacted]", text)
    return text
