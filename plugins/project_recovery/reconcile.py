"""Manager writes for a recovery folder.

Binding and handle files are validated with the membership schemas, then
replaced by a temp file in the same directory. Scanner state is not written.
A receipt, a marker, and worker files are not consumption.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from hermes_yaml import safe_dump, safe_load
from plugins.project_recovery.authority import classify_authority_path
from plugins.project_recovery.binding import validate_binding
from plugins.project_recovery.handles import (
    NextDone,
    finishes_closing_step,
    load_handle,
    register_handle,
)
from plugins.project_recovery.invocation import observe_invocation
from plugins.project_recovery.mapping import (
    PLAYBOOK_STEPS,
    Err,
    Invalid,
    matches_binding_id,
)


def write_binding(recovery_dir, document, *, closed_verbs, mapping):
    """Validate ``document`` and replace ``binding.yaml`` in ``recovery_dir``."""
    validated = validate_binding(
        document,
        closed_verbs=closed_verbs,
        mapping=mapping,
        recovery_dir=recovery_dir,
    )
    if isinstance(validated, Err):
        return validated
    _atomic_write(Path(recovery_dir) / "binding.yaml", _yaml(document))
    return validated


def _yaml(document) -> str:
    payload = safe_dump(document)
    if payload.endswith("\n"):
        return payload
    return payload + "\n"


def _atomic_write(destination: Path, payload: str) -> None:
    directory = destination.parent
    directory.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=directory,
    )
    try:
        _write_temp(descriptor, temporary, destination, payload)
    except Exception:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise
    _fsync_directory(directory)


def _write_temp(
    descriptor: int, temporary: str, destination: Path, payload: str
) -> None:
    with os.fdopen(descriptor, "w", encoding="utf-8") as sink:
        sink.write(payload)
        sink.flush()
        os.fsync(sink.fileno())
    os.replace(temporary, destination)


def _fsync_directory(directory: Path) -> None:
    try:
        dir_fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def write_handle(recovery_dir, document, *, outputs_root):
    """Validate and replace one handle file. Output names need not exist yet."""
    return register_handle(recovery_dir, document, outputs_root=outputs_root)


def record_consumption(recovery_dir, handle_id, consumed, *, outputs_root):
    """Store ``consumed`` on an existing handle. Receipts are not an argument."""
    if not matches_binding_id(handle_id) or not isinstance(consumed, dict):
        return _handle_err("schema")
    loaded = _load_handle(recovery_dir, handle_id, outputs_root)
    if isinstance(loaded, Err):
        return loaded
    document = loaded.document()
    document["consumed"] = consumed
    return register_handle(recovery_dir, document, outputs_root=outputs_root)


def read_worker_evidence(handle, *, outputs_root):
    """Classify worker paths. A failure is omitted and is not read."""
    trusted = {}
    rejected = {}
    for name, path in _evidence_paths(handle):
        if path is None:
            continue
        classified = classify_authority_path(path, outputs_root)
        if classified.evidence and classified.resolved:
            trusted[name] = classified.resolved
        else:
            rejected[name] = classified.reason
    return EvidenceView(trusted, rejected)


def copy_invocation(recovery_dir, handle_id, invocation_id, *, outputs_root):
    """Keep the first non-empty recorded id. An empty id does not write."""
    if not matches_binding_id(handle_id):
        return _handle_err("handle_id")
    if type(invocation_id) is not str or not invocation_id:
        return _handle_err("schema")
    loaded = _load_handle(recovery_dir, handle_id, outputs_root)
    if isinstance(loaded, Err):
        return loaded
    document = loaded.document()
    recorded = document["runtime"].get("invocation_id")
    if type(recorded) is not str:
        recorded = None
    document["runtime"]["invocation_id"] = observe_invocation(
        recorded, invocation_id
    )
    return register_handle(recovery_dir, document, outputs_root=outputs_root)


class EvidenceView:
    """Trusted resolved paths, and the reason each other path was rejected."""

    def __init__(self, trusted, rejected):
        self.trusted = trusted
        self.rejected = rejected

    def __repr__(self) -> str:
        return f"EvidenceView(trusted={list(self.trusted)}, rejected={self.rejected!r})"


def _evidence_paths(handle):
    outputs = handle.outputs
    return (
        ("summary", outputs.summary),
        ("report", outputs.report),
        ("stage_result", outputs.stage_result),
        ("callback_receipt", outputs.callback_receipt),
        ("resume", handle.resume.ref),
    )


def _load_handle(recovery_dir, handle_id, outputs_root):
    path = Path(recovery_dir) / "handles" / f"{handle_id}.json"
    loaded = load_handle(path, outputs_root=outputs_root)
    if isinstance(loaded, Err):
        return loaded
    if loaded.value.handle != handle_id:
        return _handle_err("handle_id")
    return loaded.value


def _handle_err(reason: str):
    return Err(Invalid("handle_invalid", reason, None))


def workstream_finished(nxt, closing_step) -> bool:
    """True only when ``next.done`` is the workstream closing step."""
    if not isinstance(nxt, dict) or set(nxt) != {"done"}:
        return False
    step = nxt.get("done")
    if type(step) is not str or step not in PLAYBOOK_STEPS:
        return False
    if type(closing_step) is not str:
        return False
    return finishes_closing_step(NextDone(step), closing_step)


def set_accepted_through(
    recovery_dir, workstream_id, *, move, evidence, closed_verbs, mapping
):
    """Update one workstream when the caller supplies both move and cite."""
    if type(move) is not str or not move or type(evidence) is not str or not evidence:
        return _binding_err("accepted_through", None)
    loaded = _read_binding(recovery_dir)
    if isinstance(loaded, Err):
        return loaded
    row = _workstream_row(loaded, workstream_id)
    if row is None:
        return _binding_err("workstream", _revision(loaded))
    authority = row.get("authority")
    if not isinstance(authority, dict):
        return _binding_err("schema", _revision(loaded))
    authority["accepted_through"] = move
    authority["evidence"] = evidence
    return _commit_binding(recovery_dir, loaded, closed_verbs, mapping)


def rebind_owner(recovery_dir, workstream_id, *, session, closed_verbs, mapping):
    """Replace ``owner.session`` with the supplied id and bump revision."""
    if type(session) is not str or not session:
        return _binding_err("owner", None)
    loaded = _read_binding(recovery_dir)
    if isinstance(loaded, Err):
        return loaded
    row = _workstream_row(loaded, workstream_id)
    if row is None:
        return _binding_err("workstream", _revision(loaded))
    owner = row.get("owner")
    if not isinstance(owner, dict):
        return _binding_err("schema", _revision(loaded))
    revision = loaded.get("revision")
    if type(revision) is not int:
        return _binding_err("schema", None)
    owner["session"] = session
    loaded["revision"] = revision + 1
    return _commit_binding(recovery_dir, loaded, closed_verbs, mapping)


def _commit_binding(recovery_dir, document, closed_verbs, mapping):
    validated = validate_binding(
        document,
        closed_verbs=closed_verbs,
        mapping=mapping,
        recovery_dir=recovery_dir,
    )
    if isinstance(validated, Err):
        return validated
    _atomic_write(Path(recovery_dir) / "binding.yaml", _yaml(document))
    return validated


def _read_binding(recovery_dir):
    path = Path(recovery_dir) / "binding.yaml"
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        return _binding_err("unreadable", None)
    try:
        data = safe_load(text)
    except Exception as exc:
        if _yaml_error(exc):
            return _binding_err("unparsable", None)
        raise
    if not isinstance(data, dict):
        return _binding_err("unparsable", None)
    return data


def _workstream_row(document, workstream_id):
    rows = document.get("workstreams")
    if not isinstance(rows, list):
        return None
    for row in rows:
        if isinstance(row, dict) and row.get("id") == workstream_id:
            return row
    return None


def _revision(document):
    revision = document.get("revision")
    if type(revision) is int:
        return revision
    return None


def _binding_err(reason: str, revision):
    return Err(Invalid("binding_invalid", reason, revision))


def _yaml_error(exc: BaseException) -> bool:
    return any(cls.__name__ == "YAMLError" for cls in type(exc).__mro__)


@dataclass(frozen=True)
class MintDecision:
    """Whether a mint for one subject and role is refused."""

    action: str
    reasons: tuple
    lost_worker: bool
    resume: tuple


@dataclass(frozen=True)
class ProgressFact:
    """A carried turn is not progress. A registry write is."""

    progressed: bool
    notice: str | None
    notice_owner: str | None


_LIVENESS = frozenset({"running", "absent", "unknown", "ended", "replaced"})
_BLOCKING = ("running", "absent", "unknown", "unconsumed")


def recheck_mint(subject, role, rows, *, digest=None, receipt=None, marker=None):
    """Refuse a second unit from handle facts. Digest text is not a command."""
    _observations_are_data(digest, receipt, marker)
    if not _ask_ok(subject, role):
        return MintDecision("refuse", ("unknown",), False, ())
    reasons = []
    lost = False
    resume = []
    for row in rows or ():
        reason, row_lost, handle = _matching_block(row, subject, role)
        if reason is not None:
            reasons.append(reason)
        if row_lost:
            lost = True
        if handle is not None:
            resume.append(handle)
    ordered = tuple(name for name in _BLOCKING if name in reasons)
    action = "refuse" if ordered else "clear"
    return MintDecision(action, ordered, lost, tuple(resume))


def progress_fact(*, carried, registry_write, marker=None, receipt=None):
    """Progress is a registry write. A marker or receipt is not that write."""
    _observations_are_data(marker, receipt)
    if registry_write is True:
        return ProgressFact(True, None, None)
    if carried is True:
        return ProgressFact(False, "no_progress", "scan")
    return ProgressFact(False, None, None)


def _observations_are_data(*items) -> None:
    """Caller observations are data. Their contents do not authorize a mint."""
    for item in items:
        if item is not None and not isinstance(item, (str, dict, list, int, bool)):
            return


def _ask_ok(subject, role) -> bool:
    if type(role) is not str or not role or not isinstance(subject, dict):
        return False
    kind = subject.get("kind")
    if kind == "member":
        return type(subject.get("id")) is str and bool(subject.get("id"))
    if kind == "stage":
        return type(subject.get("step")) is str and bool(subject.get("step"))
    return False


def _matching_block(row, subject, role):
    if not isinstance(row, dict):
        return "unknown", False, None
    if not _same_actor(row, subject, role):
        return None, False, None
    return _block(row)


def _same_actor(row, subject, role) -> bool:
    if row.get("role") != role:
        return False
    found = row.get("subject")
    if not isinstance(found, dict) or found.get("kind") != subject.get("kind"):
        return False
    if subject["kind"] == "member":
        return found.get("id") == subject.get("id")
    return found.get("step") == subject.get("step")


def _block(row):
    liveness = row.get("liveness")
    if liveness not in _LIVENESS:
        liveness = "unknown"
    consumed = isinstance(row.get("consumed"), dict) and bool(row.get("consumed"))
    if liveness in {"running", "absent", "unknown"}:
        return liveness, False, None
    if liveness in {"ended", "replaced"} and not consumed:
        return "unconsumed", True, _resume_id(row, liveness)
    return None, False, None


def _resume_id(row, liveness):
    handle_id = row.get("id")
    resumable = liveness == "ended" and row.get("resumable") is True
    if resumable and type(handle_id) is str:
        return handle_id
    return None
