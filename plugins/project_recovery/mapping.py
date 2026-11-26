"""Tracker Mapping contract, display key pattern, and identity helpers.

Keys, titles, labels, and states are not membership identity. The key
pattern is a display check. Label identity is the label id.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Generic, TypeVar

T = TypeVar("T")
E = TypeVar("E")

CANONICAL_STATES = (
    "backlog",
    "ready",
    "in_progress",
    "in_review",
    "done",
    "canceled",
)
PLAYBOOK_STEPS = (
    "Entry",
    "Brief",
    "Repo",
    "Plan",
    "Trial",
    "Spec",
    "Groom",
    "Build",
    "Review",
    "Trunk",
    "Changelog",
    "Monthly",
)
DEFAULT_CLOSING_STEP = "Changelog"
PROJECT_STATUSES = frozenset({"open", "paused", "closed"})
WORKSTREAM_STATUSES = frozenset({"open", "paused", "closed", "done"})

_CONTRACT_LINE = re.compile(r"^Contract: tracker-sdlc v([0-9]+)$")
_INLINE_CODE = re.compile(r"`([^`]+)`")
_PREFIX = re.compile(r"^[a-z][a-z0-9]{0,5}$")
_LOCAL_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
_BINDING_ID = re.compile(r"^[A-Za-z0-9_-]+$")
_RULE = re.compile(r"^:?-{3,}:?$")


@dataclass(frozen=True)
class Ok(Generic[T]):
    value: T


@dataclass(frozen=True)
class Err(Generic[E]):
    error: E


@dataclass(frozen=True)
class Invalid:
    code: str
    reason: str
    revision: int | None = None


@dataclass(frozen=True)
class TrackerMapping:
    """Loaded Mapping.

    ``states`` maps each canonical state to its primary native write name.
    ``state_aliases`` maps that state to every decoded native read name, in
    order and without duplicates. A bare cell or one code span is a one-element
    tuple, and the primary is that first name. Callers read aliases from this
    field; they do not parse Mapping markdown again.
    """

    contract: str
    key_pattern: str
    states: dict[str, str]
    state_aliases: dict[str, tuple[str, ...]] = field(default_factory=dict)


def _invalid(reason: str, revision: int | None = None) -> Err[Invalid]:
    return Err(Invalid("binding_invalid", reason, revision))


def load_mapping(text: str) -> Ok[TrackerMapping] | Err[Invalid]:
    if type(text) is not str or not text.strip():
        return _invalid("mapping_unparsable")
    if _contract_version(text) != "2":
        return _invalid("mapping_contract")
    rows = _mapping_rows(text)
    if rows is None:
        return _invalid("mapping_unparsable")
    pattern_cell = rows.get("key pattern")
    if type(pattern_cell) is not str:
        return _invalid("mapping_key_pattern")
    pattern, _aliases = _decode_cell(pattern_cell)
    if not _compiles(pattern):
        return _invalid("mapping_key_pattern")
    decoded = _states(rows)
    if decoded is None:
        return _invalid("mapping_states")
    states, aliases = decoded
    return Ok(TrackerMapping("tracker-sdlc v2", pattern, states, aliases))


def _contract_version(text: str) -> str | None:
    for line in text.splitlines():
        match = _CONTRACT_LINE.fullmatch(line.strip())
        if match:
            return match.group(1)
    return None


def _mapping_rows(text: str) -> dict[str, str] | None:
    lines = text.splitlines()
    start = _mapping_start(lines)
    if start is None:
        return None
    rows: dict[str, str] = {}
    saw_table = False
    for line in lines[start:]:
        parsed = _consume_row(line.strip(), saw_table)
        if parsed is None:
            return None
        if parsed == "skip":
            continue
        if parsed == "stop":
            break
        saw_table = True
        if parsed != "header":
            name, value = parsed
            rows[name] = value
    if not saw_table:
        return None
    return rows


def _mapping_start(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        if line.strip() == "## Mapping":
            return index + 1
    return None


def _consume_row(stripped: str, saw_table: bool):
    if not stripped:
        return "stop" if saw_table else "skip"
    if stripped.startswith("#"):
        return "stop"
    cells = _table_cells(stripped)
    if cells is None:
        return None
    if _separator(cells) or cells[0].casefold() == "canonical":
        return "header"
    return cells[0], cells[1]


def _table_cells(line: str) -> list[str] | None:
    if not (line.startswith("|") and line.endswith("|")):
        return None
    cells = [cell.strip() for cell in line[1:-1].split("|")]
    if len(cells) < 2:
        return None
    return cells


def _separator(cells: list[str]) -> bool:
    return all(_RULE.fullmatch(cell) for cell in cells)


def _compiles(pattern: str) -> bool:
    try:
        re.compile(pattern)
    except re.error:
        return False
    return True


def _decode_cell(cell: str) -> tuple[str, tuple[str, ...]]:
    """Primary native name, then every inline-code body in order.

    A cell with no code span keeps its stripped text. The first span is the
    primary write name. Later spans are additional read aliases. Ticket ids
    are not passed through here.
    """
    aliases: list[str] = []
    seen: set[str] = set()
    for match in _INLINE_CODE.finditer(cell):
        body = match.group(1).strip()
        if not body or body in seen:
            continue
        seen.add(body)
        aliases.append(body)
    if aliases:
        return aliases[0], tuple(aliases)
    text = cell.strip()
    return text, (text,)


def _states(
    rows: dict[str, str],
) -> tuple[dict[str, str], dict[str, tuple[str, ...]]] | None:
    states: dict[str, str] = {}
    aliases: dict[str, tuple[str, ...]] = {}
    for name in CANONICAL_STATES:
        value = rows.get(name)
        if value is None:
            return None
        primary, names = _decode_cell(value)
        states[name] = primary
        aliases[name] = names
    return states, aliases


def member_identity(
    native_id: str,
    *,
    key: str | None = None,
    title: str | None = None,
    labels: tuple[str, ...] | None = None,
    state: str | None = None,
) -> str:
    del key, title, labels, state
    return native_id


def label_identity(label_id: str, *, name: str | None = None) -> str:
    del name
    return label_id


def key_matches(mapping: TrackerMapping, key: str) -> bool:
    if type(key) is not str:
        return False
    try:
        compiled = re.compile(mapping.key_pattern)
    except re.error:
        return False
    return compiled.fullmatch(key) is not None


def matches_binding_id(value: str) -> bool:
    return type(value) is str and _BINDING_ID.fullmatch(value) is not None


def matches_local_id(prefix: str, value: str) -> bool:
    if _PREFIX.fullmatch(prefix) is None or type(value) is not str:
        return False
    return re.fullmatch(re.escape(prefix) + r"-[a-z0-9]{4}", value) is not None


def matches_local_assignee(value: str) -> bool:
    return _LOCAL_NAME.fullmatch(value) is not None


def matches_local_label(value: str) -> bool:
    return _LOCAL_NAME.fullmatch(value) is not None


def is_canonical_state(value: str) -> bool:
    return value in CANONICAL_STATES
