"""Binding documents for hosted and local trackers.

Validation reads the document and the directory status of ``outputs.root``.
It does not open the repo skill, a profile, or a cron job. Whether the named
job is ``no_agent``, with ``attach_to_session`` unset and
``cron.mirror_delivery`` unset, is a live property checked when that job is
created.
"""

from __future__ import annotations

from dataclasses import dataclass

from plugins.project_recovery.authority import outputs_rejected
from plugins.project_recovery.mapping import (
    DEFAULT_CLOSING_STEP,
    PLAYBOOK_STEPS,
    PROJECT_STATUSES,
    WORKSTREAM_STATUSES,
    Err,
    Invalid,
    Ok,
    TrackerMapping,
    key_matches,
    matches_binding_id,
    matches_local_id,
    matches_local_label,
)

_TOP = frozenset(
    {
        "schema",
        "revision",
        "project",
        "tracker",
        "outputs",
        "roots",
        "workstreams",
        "notices",
        "scan",
    }
)
_LINEAR_ALLOWED = frozenset({"adapter", "repo_skill", "mcp_server", "read_tools"})
_LINEAR_REQUIRED = frozenset({"adapter", "repo_skill", "mcp_server"})
_LOCAL_ALLOWED = frozenset({"adapter", "repo_skill", "remote", "branch", "prefix"})
_LOCAL_ONLY = frozenset({"remote", "branch", "prefix"})
_HOSTED_ONLY = frozenset({"mcp_server", "read_tools"})
_WS_REQUIRED = frozenset(
    {"id", "status", "owner", "authority", "asks_file", "stage_results"}
)
_WS_OPTIONAL = frozenset({"closing_step"})
_ACCEPTED = frozenset({"none", "Brief", "Spec"})
_KEYED = frozenset({"kind", "id", "key", "workstream"})
_LABEL_KEYS = frozenset({"kind", "id", "name", "team", "workstream"})
_PROJECT_KEYS = frozenset({"kind", "id", "dedicated", "workstream"})


@dataclass(frozen=True)
class Project:
    id: str
    hermes_project_id: str | None
    status: str


@dataclass(frozen=True)
class TrackerBinding:
    adapter: str
    repo_skill: str
    mcp_server: str | None
    read_tools: tuple[str, ...] | None
    remote: str | None
    branch: str | None
    prefix: str | None


@dataclass(frozen=True)
class Owner:
    session: str
    claim_labels: tuple[str, ...]


@dataclass(frozen=True)
class AuthorityRef:
    brief: str
    accepted_through: str
    evidence: str


@dataclass(frozen=True)
class Workstream:
    id: str
    status: str
    closing_step: str
    owner: Owner
    authority: AuthorityRef
    asks_file: str
    stage_results: tuple[str, ...]


@dataclass(frozen=True)
class EpicRoot:
    kind: str
    id: str
    key: str
    workstream: str


@dataclass(frozen=True)
class LabelRoot:
    kind: str
    id: str
    name: str
    team: str
    workstream: str


@dataclass(frozen=True)
class ProjectRoot:
    kind: str
    id: str
    dedicated: bool
    workstream: str


@dataclass(frozen=True)
class ItemRoot:
    kind: str
    id: str
    key: str
    workstream: str


@dataclass(frozen=True)
class Binding:
    schema: str
    revision: int
    project: Project
    tracker: TrackerBinding
    outputs_root: str
    roots: tuple[EpicRoot | LabelRoot | ProjectRoot | ItemRoot, ...]
    workstreams: tuple[Workstream, ...]
    notices_deliver: str
    scan_schedule: str


def _err(reason: str, revision: int | None) -> Err[Invalid]:
    return Err(Invalid("binding_invalid", reason, revision))


def _peek_revision(data) -> int | None:
    if not isinstance(data, dict):
        return None
    revision = data.get("revision")
    if type(revision) is int:
        return revision
    return None


def validate_binding(data, *, closed_verbs, mapping, recovery_dir):
    revision = _peek_revision(data)
    propagated = _propagate_mapping(mapping, revision)
    if propagated is not None:
        return propagated
    if not isinstance(data, dict):
        return _err("unparsable", revision)
    return _document(data, revision, closed_verbs, mapping, recovery_dir)


def load_binding(text, *, closed_verbs, mapping, recovery_dir):
    loaded = _load_yaml(text)
    if isinstance(loaded, Err):
        return loaded
    if not isinstance(loaded, dict):
        return _err("unparsable", None)
    return validate_binding(
        loaded,
        closed_verbs=closed_verbs,
        mapping=mapping,
        recovery_dir=recovery_dir,
    )


def _propagate_mapping(mapping, revision):
    if isinstance(mapping, Err):
        reason = getattr(mapping.error, "reason", "mapping_unparsable")
        return _err(reason, revision)
    if not isinstance(mapping, TrackerMapping):
        return _err("mapping_unparsable", revision)
    return None


def _load_yaml(text):
    if type(text) is not str:
        return _err("unparsable", None)
    try:
        from hermes_yaml import safe_load

        return safe_load(text)
    except Exception as exc:
        if not _yaml_error(exc):
            raise
        return _err("unparsable", None)


def _yaml_error(exc: BaseException) -> bool:
    return any(cls.__name__ == "YAMLError" for cls in type(exc).__mro__)


def _document(data, revision, closed_verbs, mapping, recovery_dir):
    if set(data) != _TOP or data.get("schema") != "project-recovery-binding/1":
        return _err("schema", revision)
    if type(data.get("revision")) is not int:
        return _err("schema", revision)
    project = _project(data["project"], revision)
    if isinstance(project, Err):
        return project
    tracker = _tracker(data["tracker"], closed_verbs, revision)
    if isinstance(tracker, Err):
        return tracker
    return _document_rest(
        data, revision, mapping, recovery_dir, project.value, tracker.value
    )


def _document_rest(data, revision, mapping, recovery_dir, project, tracker):
    outputs = _outputs(data["outputs"], recovery_dir, revision)
    if isinstance(outputs, Err):
        return outputs
    notices = _notices(data["notices"], revision)
    if isinstance(notices, Err):
        return notices
    schedule = _schedule(data["scan"], revision)
    if isinstance(schedule, Err):
        return schedule
    streams = _workstreams(data["workstreams"], revision)
    if isinstance(streams, Err):
        return streams
    ids = {stream.id for stream in streams.value}
    roots = _roots(data["roots"], ids, tracker, mapping, revision)
    if isinstance(roots, Err):
        return roots
    return Ok(
        Binding(
            "project-recovery-binding/1",
            data["revision"],
            project,
            tracker,
            outputs.value,
            roots.value,
            streams.value,
            notices.value,
            schedule.value,
        )
    )


def _project(raw, revision):
    if not isinstance(raw, dict) or set(raw) != {"id", "hermes_project_id", "status"}:
        return _err("schema", revision)
    status = raw["status"]
    if (
        not matches_binding_id(raw["id"])
        or type(status) is not str
        or status not in PROJECT_STATUSES
    ):
        return _err("schema", revision)
    hermes = raw["hermes_project_id"]
    if hermes is not None and not matches_binding_id(hermes):
        return _err("schema", revision)
    return Ok(Project(raw["id"], hermes, raw["status"]))


def _tracker(raw, closed_verbs, revision):
    if not isinstance(raw, dict):
        return _err("adapter", revision)
    adapter = raw.get("adapter")
    if type(adapter) is not str:
        return _err("adapter", revision)
    builder = _ADAPTERS.get(adapter)
    if builder is None:
        return _err("adapter", revision)
    return builder(raw, closed_verbs, revision)


def _linear_tracker(raw, closed_verbs, revision):
    keys = set(raw)
    if keys & _LOCAL_ONLY or not _LINEAR_REQUIRED <= keys <= _LINEAR_ALLOWED:
        return _err("adapter", revision)
    skill = _plain_text(raw.get("repo_skill"))
    server = _plain_text(raw.get("mcp_server"))
    if skill is None or server is None:
        return _err("schema", revision)
    tools = _read_tools(raw, closed_verbs, revision)
    if isinstance(tools, Err):
        return tools
    return Ok(TrackerBinding("linear", skill, server, tools.value, None, None, None))


def _local_tracker(raw, closed_verbs, revision):
    del closed_verbs
    keys = set(raw)
    if keys & _HOSTED_ONLY or keys != _LOCAL_ALLOWED:
        return _err("adapter", revision)
    prefix = raw.get("prefix")
    if type(prefix) is not str or not matches_local_id(prefix, prefix + "-a1b2"):
        return _err("schema", revision)
    remote = _plain_text(raw.get("remote"))
    branch = _plain_text(raw.get("branch"))
    skill = _plain_text(raw.get("repo_skill"))
    if remote is None or branch is None or skill is None:
        return _err("schema", revision)
    return Ok(TrackerBinding("local", skill, None, None, remote, branch, prefix))


def _plain_text(value) -> str | None:
    if type(value) is not str or not value.strip():
        return None
    return value


def _read_tools(raw, closed_verbs, revision):
    if "read_tools" not in raw:
        return Ok(None)
    tools = raw["read_tools"]
    if not isinstance(tools, list) or any(type(item) is not str for item in tools):
        return _err("read_tools", revision)
    if len(set(tools)) != len(tools):
        return _err("read_tools", revision)
    allowed = set(closed_verbs)
    if any(item not in allowed for item in tools):
        return _err("read_tools", revision)
    return Ok(tuple(tools))


def _outputs(raw, recovery_dir, revision):
    if not isinstance(raw, dict) or set(raw) != {"root"}:
        return _err("outputs_root", revision)
    root = raw["root"]
    if outputs_rejected(root, recovery_dir):
        return _err("outputs_root", revision)
    return Ok(root)


def _notices(raw, revision):
    if not isinstance(raw, dict) or set(raw) != {"deliver"}:
        return _err("notices_deliver", revision)
    deliver = raw["deliver"]
    if type(deliver) is not str or _bad_deliver(deliver):
        return _err("notices_deliver", revision)
    return Ok(deliver)


def _bad_deliver(deliver: str) -> bool:
    return (
        deliver == "bot-chat"
        or deliver.startswith("bot-chat:")
        or deliver.startswith("room:")
    )


def _schedule(raw, revision):
    if not isinstance(raw, dict) or set(raw) != {"schedule"}:
        return _err("schema", revision)
    schedule = raw["schedule"]
    if type(schedule) is not str or not schedule.strip():
        return _err("schema", revision)
    return Ok(schedule)


def _workstreams(raw, revision):
    if not isinstance(raw, list):
        return _err("schema", revision)
    built = []
    seen: set[str] = set()
    for item in raw:
        one = _workstream(item, revision)
        if isinstance(one, Err):
            return one
        if one.value.id in seen:
            return _err("schema", revision)
        seen.add(one.value.id)
        built.append(one.value)
    return Ok(tuple(built))


def _workstream(raw, revision):
    if not isinstance(raw, dict):
        return _err("schema", revision)
    keys = set(raw)
    if not _WS_REQUIRED <= keys <= _WS_REQUIRED | _WS_OPTIONAL:
        return _err("schema", revision)
    status = raw["status"]
    if (
        not matches_binding_id(raw["id"])
        or type(status) is not str
        or status not in WORKSTREAM_STATUSES
    ):
        return _err("schema", revision)
    closing = _closing(raw, revision)
    if isinstance(closing, Err):
        return closing
    owner = _owner(raw["owner"], revision)
    if isinstance(owner, Err):
        return owner
    authority = _authority(raw["authority"], revision)
    if isinstance(authority, Err):
        return authority
    stages = _string_tuple(raw["stage_results"])
    if type(raw["asks_file"]) is not str or stages is None:
        return _err("schema", revision)
    return Ok(
        Workstream(
            raw["id"],
            raw["status"],
            closing.value,
            owner.value,
            authority.value,
            raw["asks_file"],
            stages,
        )
    )


def _closing(raw, revision):
    if "closing_step" not in raw:
        return Ok(DEFAULT_CLOSING_STEP)
    if raw["closing_step"] not in PLAYBOOK_STEPS:
        return _err("closing_step", revision)
    return Ok(raw["closing_step"])


def _owner(raw, revision):
    if not isinstance(raw, dict) or set(raw) != {"session", "claim_labels"}:
        return _err("schema", revision)
    if not matches_binding_id(raw["session"]):
        return _err("schema", revision)
    labels = raw["claim_labels"]
    if not isinstance(labels, list) or any(not _claim_ok(item) for item in labels):
        return _err("claim_label", revision)
    return Ok(Owner(raw["session"], tuple(labels)))


def _claim_ok(value) -> bool:
    return type(value) is str and matches_local_label(value)


def _authority(raw, revision):
    if not isinstance(raw, dict) or set(raw) != {"brief", "accepted_through", "evidence"}:
        return _err("schema", revision)
    accepted = raw["accepted_through"]
    if type(accepted) is not str or accepted not in _ACCEPTED:
        return _err("schema", revision)
    if type(raw["brief"]) is not str or type(raw["evidence"]) is not str:
        return _err("schema", revision)
    return Ok(AuthorityRef(raw["brief"], raw["accepted_through"], raw["evidence"]))


def _string_tuple(value) -> tuple[str, ...] | None:
    if not isinstance(value, list) or any(type(item) is not str for item in value):
        return None
    return tuple(value)


def _roots(raw, workstream_ids, tracker, mapping, revision):
    if not isinstance(raw, list):
        return _err("schema", revision)
    built = []
    for item in raw:
        one = _root(item, workstream_ids, tracker, mapping, revision)
        if isinstance(one, Err):
            return one
        built.append(one.value)
    return Ok(tuple(built))


def _root(raw, workstream_ids, tracker, mapping, revision):
    if not isinstance(raw, dict):
        return _err("schema", revision)
    kind = raw.get("kind")
    if type(kind) is not str:
        return _err("schema", revision)
    builder = _ROOTS.get(kind)
    if builder is None:
        return _err("schema", revision)
    return builder(raw, workstream_ids, tracker, mapping, revision)


def _keyed_root(raw, kind, cls, workstream_ids, tracker, mapping, revision):
    if set(raw) != _KEYED:
        return _err("schema", revision)
    ident = _member_id(raw.get("id"), tracker, revision)
    if isinstance(ident, Err):
        return ident
    key = _display_key(raw.get("key"), mapping, revision)
    if isinstance(key, Err):
        return key
    link = _linked(raw.get("workstream"), workstream_ids, revision)
    if isinstance(link, Err):
        return link
    return Ok(cls(kind, ident.value, key.value, link.value))


def _epic_root(raw, workstream_ids, tracker, mapping, revision):
    return _keyed_root(
        raw, "epic", EpicRoot, workstream_ids, tracker, mapping, revision
    )


def _item_root(raw, workstream_ids, tracker, mapping, revision):
    return _keyed_root(
        raw, "item", ItemRoot, workstream_ids, tracker, mapping, revision
    )


def _label_root(raw, workstream_ids, tracker, mapping, revision):
    del mapping
    if set(raw) != _LABEL_KEYS:
        return _err("schema", revision)
    ident = _member_id(raw.get("id"), tracker, revision)
    if isinstance(ident, Err):
        return ident
    name = _adapter_name(raw.get("name"), tracker, revision)
    if isinstance(name, Err):
        return name
    team = _adapter_name(raw.get("team"), tracker, revision)
    if isinstance(team, Err):
        return team
    link = _linked(raw.get("workstream"), workstream_ids, revision)
    if isinstance(link, Err):
        return link
    return Ok(LabelRoot("label", ident.value, name.value, team.value, link.value))


def _project_root(raw, workstream_ids, tracker, mapping, revision):
    del mapping
    if not isinstance(raw, dict) or raw.get("dedicated") is not True:
        return _err("dedicated", revision)
    if set(raw) != _PROJECT_KEYS:
        return _err("schema", revision)
    ident = _member_id(raw.get("id"), tracker, revision)
    if isinstance(ident, Err):
        return ident
    link = _linked(raw.get("workstream"), workstream_ids, revision)
    if isinstance(link, Err):
        return link
    return Ok(ProjectRoot("project", ident.value, True, link.value))


def _member_id(ident, tracker, revision):
    if type(ident) is not str or not ident:
        return _err("schema", revision)
    if tracker.adapter == "local" and not matches_local_id(tracker.prefix, ident):
        return _err("local_id", revision)
    return Ok(ident)


def _display_key(key, mapping, revision):
    if not key_matches(mapping, key):
        return _err("key_pattern", revision)
    return Ok(key)


def _adapter_name(value, tracker, revision):
    if type(value) is not str or not value:
        return _err("schema", revision)
    if tracker.adapter == "local" and not matches_local_label(value):
        return _err("local_label", revision)
    return Ok(value)


def _linked(workstream, workstream_ids, revision):
    if type(workstream) is not str or workstream not in workstream_ids:
        return _err("schema", revision)
    return Ok(workstream)


_ADAPTERS = {
    "linear": _linear_tracker,
    "local": _local_tracker,
}
_ROOTS = {
    "epic": _epic_root,
    "item": _item_root,
    "label": _label_root,
    "project": _project_root,
}
