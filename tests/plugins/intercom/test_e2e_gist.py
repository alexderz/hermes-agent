"""Owner end-to-end of message gists (DER-701, G18c).

One temporary home and two owner-attached sessions (``_owner_world``). A send with a gist, a send
without one, a CLI script send whose body is ``**``-wrapped Markdown, a reply whose block starts
with ``Gist:``, and a block that is only that line. The record and the delivered notice lines are
checked here. The same frames, with session and message ids made stable, are the fixture
``agent-gist.test.ts`` parses, so a frame-format change between the plugin and the Webapp fails
one of the two.

Run (the explicit ``--`` lets the conftest option through). The file completed in about 22s;
``--file-timeout 120``::

    HERMES_HOME="$(mktemp -d)" scripts/run_tests.sh --fail-on-skip --file-retries 0 --file-timeout 120 \
        tests/plugins/intercom/test_e2e_gist.py -- --intercom-src=<intercom checkout>

A stale check writes ``gist-frames.actual.json`` under the test home; review it and copy it over the checked-in fixture.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

import pytest

from tests.e2e.core.chaos._helpers import kill_tagged, new_tag

from ._owner_world import TURN_S, USER_NAME, Request, World

pytestmark = [pytest.mark.platforms("linux"), pytest.mark.spawns_gateway_lookalike]

FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "apps"
    / "desktop"
    / "src"
    / "components"
    / "assistant-ui"
    / "thread"
    / "gist-frames.json"
)
LQ, RQ = "\u201c", "\u201d"
MARK = "\U0001f4e1"

# Stable ids stay 8 hex characters so the Webapp parser accepts the fixture.
WITH_GIST, FALLBACK, MARKDOWN = "1111aaaa", "2222bbbb", "3333cccc"
REPLY_TO, REPLY, SILENT = "4444dddd", "5555eeee", "6666ffff"
EXPLICIT = "Third review round passed."
FALLBACK_GIST = "The harness is ready to merge."
MARKDOWN_SENTENCE = "Thinking on fixed the labyrinth test and the suite is green"
MARKDOWN_GIST = f"{MARKDOWN_SENTENCE}."
REPLY_GIST = "The third review passed."
SILENT_GIST = "Nothing new to report."

_SESSION_RE = re.compile(rf"hermes@(\S+) says \(session ([^ {chr(0xB7)}\n)]+)")


def _notice(sender: str, gist: str, *, script: bool = False) -> str:
    handle = "" if script else " (@default)"
    return f"Message from {MARK} {sender}{handle}: {LQ}{gist}{RQ}"


def _message_ids(world: World) -> set[str]:
    path = world.hermes_home / "plugin-data" / "intercom" / "record.db"
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30)
    try:
        return {row[0] for row in conn.execute("SELECT id FROM messages")}
    finally:
        conn.close()


def _extract_frame(text: str, message_id: str) -> str | None:
    end = f"{MARK} End of message {message_id}"
    header = f"message {message_id})"
    start_at = 0
    while True:
        start = text.find(f"Message from {MARK} ", start_at)
        if start < 0:
            return None
        stop = text.find(end, start)
        if stop < 0:
            return None
        frame = text[start : stop + len(end)]
        if any(
            line.startswith(f"{MARK} Not ") and header in line
            for line in frame.splitlines()[:3]
        ):
            return frame
        start_at = start + 1


def _find_frame(world: World, message_id: str) -> str | None:
    for req in world.model.find(lambda _r: True):
        for text in (*req.rows, *req.steers):
            found = _extract_frame(text, message_id)
            if found:
                return found
    return None


def _frame(world: World, message_id: str) -> str:
    return world.poll(
        lambda: _find_frame(world, message_id), TURN_S, f"the frame of {message_id}"
    )


def _replace(text: str, ids: dict[str, str]) -> str:
    for real, stable in sorted(
        ids.items(), key=lambda item: len(item[0]), reverse=True
    ):
        if real:
            text = text.replace(real, stable)
    return text


def _note_sessions(frame: str, ids: dict[str, str]) -> None:
    for name, session in _SESSION_RE.findall(frame):
        ids.setdefault(session, f"{name}-session")


def _canonical(payload: dict) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def _model_text(world: World, request: Request) -> str:
    """The text ``Model`` returned for this request, once that reply is stored on it."""
    return world.poll(
        lambda: request.answer or None, TURN_S, f"the model text for {request.tag}"
    )


@pytest.fixture(scope="module")
def world(tmp_path_factory: pytest.TempPathFactory, intercom_src: Path):
    tag = new_tag()
    home = World(tmp_path_factory.mktemp("gist-e2e"), intercom_src, tag)
    mp = pytest.MonkeyPatch()
    mp.setenv("HERMES_HOME", str(home.hermes_home))
    try:
        home.start_owner()
        home.sender = home.attached_session("TAG=seedA STEPS=0", title="planner")
        home.builder = home.attached_session("TAG=seedB STEPS=0", title="builder")
        home.answered("seedA")
        home.answered("seedB")
        home.quiet()
        yield home
    finally:
        try:
            home.close()
        finally:
            kill_tagged(tag)
            mp.undo()


@pytest.fixture(autouse=True)
def _world_home(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test's own isolated home is replaced by the world's: the owner client reads it."""
    monkeypatch.setenv("HERMES_HOME", str(world.hermes_home))


def test_gist_records_notices_and_captured_frames(world: World) -> None:
    """The five sends, then the checked-in frames the Webapp parser reads."""
    builder = world.builder
    ids: dict[str, str] = {}
    frames: list[dict] = []

    receipt = world.tool_send(
        builder,
        "steer",
        "none",
        "The third review passed its checks. TAG=g1 STEPS=0",
        gist=EXPLICIT,
    )
    assert receipt.get("ok") is True and receipt.get("applied") == "start", receipt
    mid = receipt["message_id"]
    world.answered("g1")
    row = world.record(mid)
    frame = _frame(world, mid)
    assert row["gist"] == EXPLICIT and row["result"] == "delivered", row
    assert frame.splitlines()[0] == _notice("planner", EXPLICIT), frame.splitlines()[0]
    assert frame.splitlines()[1].startswith(
        f"{MARK} Not {USER_NAME} · no reply needed · hermes@planner says "
    )
    ids[mid] = WITH_GIST
    _note_sessions(frame, ids)
    frames.append(
        {
            "name": "with-gist",
            "gist": EXPLICIT,
            "id": WITH_GIST,
            "showsReplyGist": False,
            "text": frame,
        }
    )
    world.quiet()

    receipt = world.tool_send(
        builder,
        "steer",
        "none",
        f"{FALLBACK_GIST} The rest is detail for the transcript. TAG=g2 STEPS=0",
    )
    assert receipt.get("ok") is True and receipt.get("applied") == "start", receipt
    mid = receipt["message_id"]
    world.answered("g2")
    row = world.record(mid)
    frame = _frame(world, mid)
    assert row["gist"] is None and row["result"] == "delivered", row
    assert frame.splitlines()[0] == _notice("planner", FALLBACK_GIST), (
        frame.splitlines()[0]
    )
    ids[mid] = FALLBACK
    _note_sessions(frame, ids)
    frames.append(
        {
            "name": "fallback",
            "gist": FALLBACK_GIST,
            "id": FALLBACK,
            "showsReplyGist": False,
            "text": frame,
        }
    )
    world.quiet()

    code, receipt = world.intercom(
        "send",
        "--to",
        builder,
        "--from",
        "nightly",
        "--reply",
        "none",
        "--message",
        f"**{MARKDOWN_SENTENCE}.** More follows.\nTAG=md1 STEPS=0",
    )
    assert code == 0 and receipt.get("ok") is True, (code, receipt)
    mid = receipt["message_id"]
    world.answered("md1")
    row = world.record(mid)
    frame = _frame(world, mid)
    notice = frame.splitlines()[0]
    assert row["gist"] is None and row["result"] == "delivered", row
    assert notice == _notice("nightly", MARKDOWN_GIST, script=True), notice
    assert "**" not in notice and f"**{MARKDOWN_SENTENCE}.**" in frame
    assert frame.splitlines()[1].startswith(
        f"{MARK} Not {USER_NAME} · no reply needed · hermes@script nightly says "
    )
    ids[mid] = MARKDOWN
    frames.append(
        {
            "name": "markdown",
            "gist": MARKDOWN_GIST,
            "id": MARKDOWN,
            "showsReplyGist": False,
            "text": frame,
        }
    )
    world.quiet()

    receipt = world.tool_send(
        builder,
        "steer",
        "requested",
        f'Please confirm the review. TAG=rep1 STEPS=0 BLOCKGIST="{REPLY_GIST}"',
    )
    assert receipt.get("ok") is True and receipt.get("applied") == "start", receipt
    inbound = receipt["message_id"]
    request = world.answered("rep1")
    reply_answer = _model_text(world, request)
    inbound_frame = _frame(world, inbound)
    assert "· reply requested ·" in inbound_frame.splitlines()[1], (
        inbound_frame.splitlines()[1]
    )
    origin = world.poll(
        lambda: (
            (found := world.record(inbound)) and found.get("reply_message_id") and found
        ),
        TURN_S,
        "the reply to be delivered",
    )
    assert origin["reply_state"] == "sent" and origin["reply"] == "answer from rep1", (
        origin
    )
    assert "Gist:" not in origin["reply"]
    reply_id = origin["reply_message_id"]
    reply_row = world.record(reply_id)
    frame = _frame(world, reply_id)
    assert reply_row["gist"] == REPLY_GIST and reply_row["result"] == "delivered", (
        reply_row
    )
    assert reply_row["body"] == "answer from rep1", reply_row
    assert frame.splitlines()[0] == _notice("builder", REPLY_GIST), frame.splitlines()[
        0
    ]
    assert "reply to your message" in frame.splitlines()[1]
    assert "· reply optional ·" in frame.splitlines()[1]
    ids[inbound] = REPLY_TO
    ids[reply_id] = REPLY
    _note_sessions(frame, ids)
    _note_sessions(inbound_frame, ids)
    frames.append(
        {
            "name": "reply",
            "gist": REPLY_GIST,
            "id": REPLY,
            "showsReplyGist": True,
            "text": frame,
        }
    )
    world.quiet()

    before = _message_ids(world)
    receipt = world.tool_send(
        builder,
        "steer",
        "requested",
        f'Please leave this one. TAG=sil1 STEPS=0 BLOCKONLY="{SILENT_GIST}"',
    )
    assert receipt.get("ok") is True and receipt.get("applied") == "start", receipt
    silent_id = receipt["message_id"]
    silent_request = world.answered("sil1")
    silent_answer = _model_text(world, silent_request)
    silent_frame = _frame(world, silent_id)
    assert "· reply requested ·" in silent_frame.splitlines()[1], (
        silent_frame.splitlines()[1]
    )
    silent_row = world.poll(
        lambda: (
            (found := world.record(silent_id)) and found.get("reply_state") and found
        ),
        TURN_S,
        "the gist-only block to be recorded",
    )
    world.quiet()
    assert silent_row["reply_state"] == "silent", silent_row
    assert silent_row.get("reply") in (None, "") and not silent_row.get(
        "reply_message_id"
    ), silent_row
    assert _message_ids(world) == before | {silent_id}
    _note_sessions(silent_frame, ids)
    assert not any(
        f"reply to your message {silent_id}" in text
        for req in world.model.find(lambda _r: True)
        for text in (*req.rows, *req.steers)
    )
    ids[silent_id] = SILENT

    payload = {
        "frames": [
            {
                "name": item["name"],
                "gist": item["gist"],
                "id": item["id"],
                "showsReplyGist": item["showsReplyGist"],
                "text": _replace(item["text"], ids),
            }
            for item in frames
        ],
        "replies": [
            {
                "name": "gist-block",
                "id": REPLY_TO,
                "gist": REPLY_GIST,
                "request": _replace(inbound_frame, ids),
                "text": _replace(reply_answer, ids),
            },
            {
                "name": "gist-only",
                "id": SILENT,
                "gist": "No reply",
                "request": _replace(silent_frame, ids),
                "text": _replace(silent_answer, ids),
            },
        ],
    }
    rendered = _canonical(payload)
    actual = world.root / "gist-frames.actual.json"
    actual.write_text(rendered, encoding="utf-8")
    assert FIXTURE.is_file(), "the captured frame fixture is not checked in"
    assert json.loads(FIXTURE.read_text(encoding="utf-8")) == payload, (
        f"fixture is stale; review and copy {actual} to {FIXTURE}"
    )
