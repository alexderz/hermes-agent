"""Mapping load, key pattern, and identity. The skill text is a fixture."""

from __future__ import annotations

from plugins.project_recovery import (
    Err,
    Ok,
    TrackerMapping,
    is_canonical_state,
    key_matches,
    label_identity,
    load_mapping,
    matches_local_assignee,
    matches_local_id,
    matches_local_label,
    member_identity,
)
from tests.plugins.project_recovery.support import MAPPING


def test_v2_mapping_loads_key_pattern_and_state_names():
    result = load_mapping(MAPPING)

    assert isinstance(result, Ok)
    mapping = result.value
    assert mapping.contract == "tracker-sdlc v2"
    assert mapping.key_pattern == "ABC-[0-9]+"
    assert mapping.states["backlog"] == "Backlog"
    assert mapping.states["ready"] == "Ready"
    assert mapping.states["in_progress"] == "In Progress"
    assert mapping.states["in_review"] == "In Review"
    assert mapping.states["done"] == "Done"
    assert mapping.states["canceled"] == "Canceled"


def test_contract_other_than_v2_is_not_an_empty_mapping():
    text = MAPPING.replace("Contract: tracker-sdlc v2", "Contract: tracker-sdlc v1")
    result = load_mapping(text)

    assert isinstance(result, Err)
    assert result.error.code == "binding_invalid"
    assert result.error.reason == "mapping_contract"


def test_missing_contract_line_is_not_an_empty_mapping():
    result = load_mapping(MAPPING.replace("Contract: tracker-sdlc v2\n", ""))

    assert isinstance(result, Err)
    assert result.error.code == "binding_invalid"
    assert result.error.reason == "mapping_contract"


def test_unparsable_mapping_is_not_an_empty_success():
    text = "Contract: tracker-sdlc v2\n\n## Mapping\nnot a table\n"
    result = load_mapping(text)

    assert isinstance(result, Err)
    assert result.error.code == "binding_invalid"
    assert result.error.reason == "mapping_unparsable"


def test_missing_key_pattern_is_invalid():
    text = MAPPING.replace("| key pattern | ABC-[0-9]+ |\n", "")
    result = load_mapping(text)

    assert isinstance(result, Err)
    assert result.error.reason == "mapping_key_pattern"


def test_key_pattern_that_does_not_compile_is_invalid():
    text = MAPPING.replace("ABC-[0-9]+", "[")
    result = load_mapping(text)

    assert isinstance(result, Err)
    assert result.error.reason == "mapping_key_pattern"


def test_missing_canonical_state_is_invalid():
    text = MAPPING.replace("| ready | Ready |\n", "")
    result = load_mapping(text)

    assert isinstance(result, Err)
    assert result.error.reason == "mapping_states"


def test_blank_mapping_text_is_not_empty_success():
    result = load_mapping("   \n")

    assert isinstance(result, Err)
    assert result.error.code == "binding_invalid"
    assert result.error.reason == "mapping_unparsable"


def test_identity_ignores_key_title_labels_and_state():
    first = member_identity(
        "native-1",
        key="ABC-100",
        title="One",
        labels=("recovery-x",),
        state="ready",
    )
    renamed = member_identity(
        "native-1",
        key="nope",
        title="Other",
        labels=(),
        state="done",
    )
    other = member_identity("native-2", key="ABC-100", title="One", state="ready")

    assert first == "native-1"
    assert renamed == "native-1"
    assert other == "native-2"
    assert first != other


def test_label_identity_is_the_label_id():
    assert label_identity("linear-label:7c1d", name="old") == "linear-label:7c1d"
    assert label_identity("linear-label:7c1d", name="old") == label_identity(
        "linear-label:7c1d", name="renamed"
    )
    assert label_identity("linear-label:7c1d", name="same") != label_identity(
        "linear-label:91aa", name="same"
    )


def test_key_pattern_is_a_display_check():
    mapping = TrackerMapping(
        contract="tracker-sdlc v2",
        key_pattern="ABC-[0-9]+",
        states={},
    )

    assert key_matches(mapping, "ABC-100")
    assert key_matches(mapping, "ABC-131")
    assert not key_matches(mapping, "nope")
    assert not key_matches(mapping, "abc-100")


def test_local_adapter_patterns_are_not_membership_ids():
    assert matches_local_id("abc", "abc-a1b2")
    assert not matches_local_id("abc", "ABC-100")
    assert not matches_local_id("ab", "abc-a1b2")
    assert not matches_local_id("ABC", "abc-a1b2")
    assert matches_local_assignee("ws-alpha-mgr")
    assert not matches_local_assignee("Bad_Label")
    assert matches_local_label("recovery-x")
    assert not matches_local_label("Recovery")
    assert is_canonical_state("in_progress")
    assert is_canonical_state("canceled")
    assert not is_canonical_state("open")
    assert not is_canonical_state("paused")


def test_bare_cells_keep_singleton_read_aliases():
    result = load_mapping(MAPPING)

    assert isinstance(result, Ok)
    aliases = result.value.state_aliases
    assert aliases["backlog"] == ("Backlog",)
    assert aliases["in_progress"] == ("In Progress",)
    assert aliases["canceled"] == ("Canceled",)
    assert result.value.states["canceled"] == aliases["canceled"][0]


_SPANNED = """\
Contract: tracker-sdlc v2

## Mapping

| Canonical | Native |
| --- | --- |
| backlog | `Backlog` |
| ready | `Ready` |
| in_progress | `In Progress` |
| in_review | `In Review` |
| done | `Done` |
| canceled | `Canceled`; `Duplicate` also maps to canceled |
| key pattern | `ABC-[0-9]+` |
"""


def test_inline_code_spans_decode_primary_names_and_read_aliases():
    result = load_mapping(_SPANNED)

    assert isinstance(result, Ok)
    mapping = result.value
    assert mapping.key_pattern == "ABC-[0-9]+"
    assert mapping.states["backlog"] == "Backlog"
    assert mapping.states["in_progress"] == "In Progress"
    assert mapping.states["canceled"] == "Canceled"
    assert mapping.state_aliases["backlog"] == ("Backlog",)
    assert mapping.state_aliases["ready"] == ("Ready",)
    assert mapping.state_aliases["canceled"] == ("Canceled", "Duplicate")
    assert key_matches(mapping, "ABC-100")
    assert not key_matches(mapping, "`ABC-100`")

    repeated = _SPANNED.replace(
        "`Canceled`; `Duplicate` also maps to canceled",
        "`Canceled`; `Duplicate`; `Canceled` also maps to canceled",
    )
    again = load_mapping(repeated)

    assert isinstance(again, Ok)
    assert again.value.states["canceled"] == "Canceled"
    assert again.value.state_aliases["canceled"] == ("Canceled", "Duplicate")
