"""Handle documents and registration writes.

Registration checks lexical containment only. Output files may be absent.
The read-time regular-file check is authority classification, not this write.
A failing evidence path does not block a later consumption write.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from plugins.project_recovery.authority import lexical_escape, output_path_reason
from plugins.project_recovery.mapping import (
    PLAYBOOK_STEPS,
    Err,
    Invalid,
    Ok,
    matches_binding_id,
)

_HANDLE_KEYS = frozenset(
    {
        "schema",
        "handle",
        "workstream",
        "subject",
        "role",
        "attempt",
        "runtime",
        "outputs",
        "resume",
        "registered_at",
        "consumed",
    }
)
_OUTPUT_KEYS = frozenset({"summary", "report", "stage_result", "callback_receipt"})
_REF_KINDS = frozenset({"ask", "blocker", "operator"})


@dataclass(frozen=True)
class NextHandle:
    handle: str


@dataclass(frozen=True)
class NextWait:
    kind: str
    ref: str | None = None
    resume_after: str | None = None


@dataclass(frozen=True)
class NextDone:
    step: str


@dataclass(frozen=True)
class NextStopped:
    reason: str


@dataclass(frozen=True)
class SubjectMember:
    kind: str
    id: str


@dataclass(frozen=True)
class SubjectStage:
    kind: str
    step: str


@dataclass(frozen=True)
class Runtime:
    kind: str
    unit: str
    invocation_id: str | None


@dataclass(frozen=True)
class OutputPaths:
    summary: str
    report: str
    stage_result: str | None
    callback_receipt: str


@dataclass(frozen=True)
class Resume:
    kind: str
    ref: str


@dataclass(frozen=True)
class Consumed:
    at: str
    next: NextHandle | NextWait | NextDone | NextStopped


@dataclass(frozen=True)
class Handle:
    schema: str
    handle: str
    workstream: str
    subject: SubjectMember | SubjectStage
    role: str
    attempt: int
    runtime: Runtime
    outputs: OutputPaths
    resume: Resume
    registered_at: str
    consumed: Consumed | None

    def document(self) -> dict:
        return {
            "schema": self.schema,
            "handle": self.handle,
            "workstream": self.workstream,
            "subject": _subject_document(self.subject),
            "role": self.role,
            "attempt": self.attempt,
            "runtime": {
                "kind": self.runtime.kind,
                "unit": self.runtime.unit,
                "invocation_id": self.runtime.invocation_id,
            },
            "outputs": {
                "summary": self.outputs.summary,
                "report": self.outputs.report,
                "stage_result": self.outputs.stage_result,
                "callback_receipt": self.outputs.callback_receipt,
            },
            "resume": {"kind": self.resume.kind, "ref": self.resume.ref},
            "registered_at": self.registered_at,
            "consumed": _consumed_document(self.consumed),
        }


def _herr(reason: str) -> Err[Invalid]:
    return Err(Invalid("handle_invalid", reason, None))


def finishes_closing_step(nxt, closing_step: str) -> bool:
    return isinstance(nxt, NextDone) and nxt.step == closing_step


def validate_handle(document, *, outputs_root):
    if not isinstance(document, dict) or set(document) != _HANDLE_KEYS:
        return _herr("schema")
    if document.get("schema") != "project-recovery-handle/1":
        return _herr("schema")
    identity = _identity(document)
    if isinstance(identity, Err):
        return identity
    body = _body(document, outputs_root)
    if isinstance(body, Err):
        return body
    return Ok(_build_handle(identity.value, body.value))


def register_handle(recovery_dir, document, *, outputs_root):
    validated = validate_handle(document, outputs_root=outputs_root)
    if isinstance(validated, Err):
        return validated
    handle = validated.value
    destination = Path(recovery_dir) / "handles" / f"{handle.handle}.json"
    _atomic_write(destination, json.dumps(handle.document(), indent=2) + "\n")
    return Ok(handle)


def load_handle(path, *, outputs_root):
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        return _herr("unreadable")
    try:
        document = json.loads(text)
    except json.JSONDecodeError:
        return _herr("unparsable")
    return validate_handle(document, outputs_root=outputs_root)


def _identity(document):
    ident = document.get("handle")
    if not matches_binding_id(ident):
        return _herr("handle_id")
    workstream = document.get("workstream")
    role = document.get("role")
    attempt = document.get("attempt")
    if not matches_binding_id(workstream) or not matches_binding_id(role):
        return _herr("schema")
    if type(attempt) is not int or attempt < 1:
        return _herr("schema")
    subject = _subject(document.get("subject"))
    if isinstance(subject, Err):
        return subject
    registered = document.get("registered_at")
    if type(registered) is not str or not registered:
        return _herr("schema")
    return Ok((ident, workstream, subject.value, role, attempt, registered))


def _body(document, outputs_root):
    runtime = _runtime(document.get("runtime"))
    if isinstance(runtime, Err):
        return runtime
    outputs = _outputs(document.get("outputs"), outputs_root)
    if isinstance(outputs, Err):
        return outputs
    resume = _resume(document.get("resume"), outputs_root)
    if isinstance(resume, Err):
        return resume
    consumed = _consumed(document.get("consumed"))
    if isinstance(consumed, Err):
        return consumed
    return Ok((runtime.value, outputs.value, resume.value, consumed.value))


def _build_handle(identity, body) -> Handle:
    ident, workstream, subject, role, attempt, registered = identity
    runtime, outputs, resume, consumed = body
    return Handle(
        "project-recovery-handle/1",
        ident,
        workstream,
        subject,
        role,
        attempt,
        runtime,
        outputs,
        resume,
        registered,
        consumed,
    )


def _subject(raw):
    if not isinstance(raw, dict):
        return _herr("schema")
    kind = raw.get("kind")
    if kind == "member":
        return _subject_member(raw)
    if kind == "stage":
        return _subject_stage(raw)
    return _herr("schema")


def _subject_member(raw):
    if set(raw) != {"kind", "id"}:
        return _herr("schema")
    ident = raw["id"]
    if type(ident) is not str or not ident or "/" in ident or lexical_escape(ident):
        return _herr("schema")
    return Ok(SubjectMember("member", ident))


def _subject_stage(raw):
    if set(raw) != {"kind", "step"} or raw["step"] not in PLAYBOOK_STEPS:
        return _herr("schema")
    return Ok(SubjectStage("stage", raw["step"]))


def _runtime(raw):
    if not isinstance(raw, dict) or set(raw) != {"kind", "unit", "invocation_id"}:
        return _herr("schema")
    if raw["kind"] != "systemd-user-unit":
        return _herr("schema")
    unit = raw["unit"]
    if type(unit) is not str or not unit or "/" in unit or lexical_escape(unit):
        return _herr("schema")
    invocation = raw["invocation_id"]
    if invocation is not None and (type(invocation) is not str or not invocation):
        return _herr("schema")
    return Ok(Runtime("systemd-user-unit", unit, invocation))


def _outputs(raw, outputs_root):
    if not isinstance(raw, dict) or set(raw) != _OUTPUT_KEYS:
        return _herr("schema")
    stage = raw["stage_result"]
    if stage is not None and type(stage) is not str:
        return _herr("schema")
    names = (raw["summary"], raw["report"], raw["callback_receipt"])
    for path in names:
        reason = output_path_reason(path, outputs_root)
        if reason is not None:
            return _herr(reason)
    if stage is not None:
        reason = output_path_reason(stage, outputs_root)
        if reason is not None:
            return _herr(reason)
    return Ok(OutputPaths(raw["summary"], raw["report"], stage, raw["callback_receipt"]))


def _resume(raw, outputs_root):
    if not isinstance(raw, dict) or set(raw) != {"kind", "ref"}:
        return _herr("schema")
    if type(raw["kind"]) is not str or not raw["kind"]:
        return _herr("schema")
    reason = output_path_reason(raw["ref"], outputs_root)
    if reason is not None:
        return _herr(reason)
    return Ok(Resume(raw["kind"], raw["ref"]))


def _consumed(raw):
    if raw is None:
        return Ok(None)
    if not isinstance(raw, dict) or set(raw) != {"at", "next"}:
        return _herr("schema")
    if type(raw["at"]) is not str or not raw["at"]:
        return _herr("schema")
    nxt = _next(raw["next"])
    if isinstance(nxt, Err):
        return nxt
    return Ok(Consumed(raw["at"], nxt.value))


def _next(raw):
    if not isinstance(raw, dict) or len(raw) != 1:
        return _herr("handle_next")
    key, value = next(iter(raw.items()))
    parser = _NEXT.get(key)
    if parser is None:
        return _herr("handle_next")
    return parser(value)


def _next_handle(value):
    if not matches_binding_id(value):
        return _herr("handle_next")
    return Ok(NextHandle(value))


def _next_done(value):
    if value not in PLAYBOOK_STEPS:
        return _herr("handle_next")
    return Ok(NextDone(value))


def _next_stopped(value):
    if value != "operator":
        return _herr("handle_next")
    return Ok(NextStopped("operator"))


def _next_wait(value):
    if not isinstance(value, dict):
        return _herr("handle_next")
    kind = value.get("kind")
    if type(kind) is not str:
        return _herr("handle_next")
    if kind == "quota":
        return _quota_wait(value)
    if kind in _REF_KINDS:
        return _ref_wait(value, kind)
    return _herr("handle_next")


def _quota_wait(value):
    if set(value) != {"kind", "resume_after"}:
        return _herr("handle_next")
    when = value["resume_after"]
    if type(when) is not str or not when:
        return _herr("handle_next")
    return Ok(NextWait("quota", None, when))


def _ref_wait(value, kind):
    if set(value) != {"kind", "ref"}:
        return _herr("handle_next")
    ref = value["ref"]
    if type(ref) is not str or not ref:
        return _herr("handle_next")
    return Ok(NextWait(kind, ref, None))


def _subject_document(subject) -> dict:
    if isinstance(subject, SubjectMember):
        return {"kind": "member", "id": subject.id}
    return {"kind": "stage", "step": subject.step}


def _consumed_document(consumed) -> dict | None:
    if consumed is None:
        return None
    return {"at": consumed.at, "next": _next_document(consumed.next)}


def _next_document(nxt) -> dict:
    if isinstance(nxt, NextHandle):
        return {"handle": nxt.handle}
    if isinstance(nxt, NextDone):
        return {"done": nxt.step}
    if isinstance(nxt, NextStopped):
        return {"stopped": nxt.reason}
    return {"wait": _wait_document(nxt)}


def _wait_document(nxt: NextWait) -> dict:
    if nxt.kind == "quota":
        return {"kind": "quota", "resume_after": nxt.resume_after}
    return {"kind": nxt.kind, "ref": nxt.ref}


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


def _write_temp(descriptor: int, temporary: str, destination: Path, payload: str) -> None:
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


_NEXT = {
    "handle": _next_handle,
    "wait": _next_wait,
    "done": _next_done,
    "stopped": _next_stopped,
}
