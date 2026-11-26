"""Joined operational entry. Fixture I/O only; not a live certification.

These checks failed while ``plugins.project_recovery.operational`` was absent.
They call that entry, the accepted scan and delivery libraries, and fakes
for discovery, tracker reads, and intercom. They do not create a cron job.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

from plugins.intercom import client, profiles, record
from plugins.project_recovery import operational
from tests.plugins.project_recovery.support import workstream
from tests.plugins.project_recovery.test_scan import (
    _classes,
    _open,
    _prepare,
    _register,
    _snapshot,
)

_EPIC = {
    "kind": "epic",
    "id": "linear:epic-1",
    "key": "ABC-100",
    "workstream": "ws-alpha",
}
_ENDED = {
    "LoadState": "loaded",
    "ActiveState": "failed",
    "Result": "oom-kill",
    "InvocationID": "inv-1",
}
_UNIT = "example-architect-r1.service"
_GATE = '{"wakeAgent": false}'


@pytest.fixture(autouse=True)
def _board_scope(monkeypatch):
    """Every check in this file exercises the board-scope operational path."""
    monkeypatch.setenv("PROJECT_RECOVERY_SCOPE", "board")


_OWNER = "owner-session"
_TIP = "tip-9"
_PHYSICAL = "phys-4"
_STORED = "phys-stored"


def _refuse_mcp(*_args, **_kwargs):
    return "trust_refused"


def _raise_discover(_servers):
    raise RuntimeError("discovery refused")


def _board(calls):
    def mcp(server, verb, args):
        calls.append((server, verb, dict(args)))
        if verb == "get_user":
            return json.dumps({"id": "user-1"})
        if verb == "list_issues":
            return json.dumps({"issues": [], "hasNextPage": False})
        if verb == "get_issue":
            return json.dumps({"code": "not_found"})
        raise AssertionError(verb)

    return mcp


def _discover_ok(order=None):
    def discover(servers):
        if order is not None:
            order.append(("discover", list(servers)))
        return ["linear_list_issues"]

    return discover


@pytest.fixture(autouse=True)
def _fences(monkeypatch, tmp_path, _hermetic_environment):
    """Block discovery, tracker RPC, send, and job creation before the entry runs."""
    del _hermetic_environment
    from tools.mcp_readonly import call_mcp_tool_readonly

    runtime = tmp_path / "runtime"
    runtime.mkdir()
    monkeypatch.setenv("HERMES_RUNTIME_DIR", str(runtime))
    monkeypatch.delenv("PROJECT_RECOVERY_DELIVERY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("__HERMES_ACTIVATED", raising=False)
    _refuse_mcp.closed_verbs = call_mcp_tool_readonly.closed_verbs
    monkeypatch.setattr("tools.mcp_readonly.call_mcp_tool_readonly", _refuse_mcp)
    monkeypatch.setattr(
        "plugins.project_recovery.readers.call_mcp_tool_readonly", _refuse_mcp
    )
    monkeypatch.setattr(
        "tools.mcp_tool_discovery.discover_mcp_tools",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("live discovery")),
    )
    monkeypatch.setattr(
        "plugins.intercom.route.send",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("live send")),
    )
    monkeypatch.setattr(
        "plugins.project_recovery.deliver.keyed_intercom_send",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("keyed send")),
    )
    monkeypatch.setattr(
        "plugins.intercom.client.list_sessions",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("live list")),
    )
    monkeypatch.setattr(
        "plugins.intercom.client.receipt",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("live receipt")),
    )
    monkeypatch.setattr(
        "plugins.intercom.client.lookup_admission",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("live lookup")),
    )
    monkeypatch.setattr("plugins.intercom.record.get", lambda _message_id: None)
    monkeypatch.setattr(
        "plugins.intercom.address.resolve",
        lambda *_args, **_kwargs: {"ok": False, "error": "unknown", "candidates": []},
    )
    monkeypatch.setattr(
        "plugins.intercom.address.list_sessions",
        lambda *_args, **_kwargs: {"ok": False, "error": "list-failed"},
    )
    monkeypatch.setattr("plugins.project_recovery.scan.read_unit_show", lambda _unit: None)
    monkeypatch.setattr(
        "cron.jobs.create_job",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("create_job")),
    )
    monkeypatch.setattr(
        "plugins.project_recovery.reconcile.record_consumption",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("consume")),
    )
    monkeypatch.setattr(
        "plugins.project_recovery.launcher.register_before_start",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("register")),
    )
    monkeypatch.setattr("plugins.intercom.state.SessionReader", _SilentSessions)


def _quiet(tmp_path):
    return _prepare(tmp_path, roots=[dict(_EPIC)], stream=workstream(brief=""))


def _install_board(monkeypatch, calls):
    monkeypatch.setattr(
        "plugins.project_recovery.readers.call_mcp_tool_readonly", _board(calls)
    )


def _ended(tmp_path, monkeypatch):
    recovery, outputs = _quiet(tmp_path)
    document = _register(recovery, outputs)
    summary = Path(document["outputs"]["summary"])
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text("{}\n", encoding="utf-8")
    receipt = Path(document["outputs"]["callback_receipt"])
    receipt.write_text(json.dumps({"message_id": "msg-1"}), encoding="utf-8")
    monkeypatch.setattr(
        "plugins.project_recovery.scan.read_unit_show",
        lambda unit: dict(_ENDED) if unit == _UNIT else None,
    )
    return recovery


def _row_get(message_id):
    if message_id == "msg-1":
        return {
            "id": message_id,
            "admission_id": "adm-1",
            "target_session_id": _OWNER,
            "offered_turn": None,
        }
    return None


def _terminal_receipt(seen):
    def receipt(admission_id, *, session_id):
        seen.append((admission_id, session_id))
        return {"ok": True, "status": "terminal", "outcome": None}

    return receipt


class _SilentSessions:
    """No real session store. Revision stays absent."""

    def __init__(self):
        self.store = self
        self.lineage = self

    def close(self):
        return None

    def get_session(self, _session_id):
        return None

    def get_compression_tip(self, session_id):
        return session_id

    def current_segments(self, _ids):
        return {}


class _PhysicalSessions:
    """List rows have no revision. The physical receipt target does."""

    def __init__(self):
        self.store = self
        self.lineage = self
        self.revision = 4

    def close(self):
        return None

    def get_session(self, session_id):
        if session_id == _PHYSICAL:
            return {"id": session_id, "runtime_revision": self.revision}
        if session_id == _TIP:
            return {"id": session_id, "runtime_revision": 9}
        return None

    def get_compression_tip(self, _session_id):
        return _TIP

    def current_segments(self, ids):
        found = {}
        for ident in ids:
            if ident == _OWNER:
                found[ident] = _PHYSICAL
            elif ident == _TIP:
                found[ident] = _TIP
        return found


def _owner_view(monkeypatch, *, state, revision=None, listing_ok=True):
    monkeypatch.setattr(
        "plugins.intercom.address.resolve",
        lambda *_args, **_kwargs: {"ok": True, "session_id": _OWNER, "title": "Owner"},
    )

    def listing(*_args, **_kwargs):
        if not listing_ok:
            return {"ok": False, "error": "list-failed"}
        row = {"id": _OWNER, "state": state}
        if type(revision) is int:
            row["runtime_revision"] = revision
        return {"ok": True, "sessions": [row]}

    monkeypatch.setattr("plugins.intercom.address.list_sessions", listing)


def _wake_episode(recovery):
    rows = [row for row in _open(recovery) if row["class"] == "result_unprocessed"]
    assert len(rows) == 1
    return rows[0]


def test_discovery_runs_before_native_read(tmp_path, monkeypatch, capsys):
    recovery, _outputs = _quiet(tmp_path)
    order = []

    def mcp(server, verb, args):
        order.append(("read", verb))
        return _board([])(server, verb, args)

    monkeypatch.setattr("plugins.project_recovery.readers.call_mcp_tool_readonly", mcp)
    code = operational.run(recovery, discover=_discover_ok(order))
    assert code == 0
    assert order[0] == ("discover", ["linear"])
    assert any(kind == "read" for kind, _verb in order[1:])
    assert capsys.readouterr().out.strip() == _GATE
    assert _snapshot(recovery)["sources"]["tracker"]["complete"] is True


def test_selected_profile_is_the_process_home(tmp_path, monkeypatch):
    home = tmp_path / "selected-home"
    runtime = tmp_path / "selected-runtime"
    work = tmp_path / "recovery-cwd"
    home.mkdir()
    runtime.mkdir()
    work.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("HERMES_RUNTIME_DIR", str(runtime))
    monkeypatch.chdir(work)
    found = operational.selected_context()
    assert Path(found["home"]).resolve() == home.resolve()
    assert Path(found["runtime"]).resolve() == runtime.resolve()
    assert Path(found["recovery"]).resolve() == work.resolve()
    assert Path(found["interpreter"]) == Path(sys.executable)
    source = Path(operational.__file__).read_text(encoding="utf-8")
    for banned in (
        "operational-prep",
        "local-prep",
        "test-env",
        "runtime-wt",
        "/var/tmp",
    ):
        assert banned not in source
    assert not re.search(r"\b[A-Z]{2,5}-\d+\b", source)


def test_runtime_env_beats_resolver_and_resolver_fills_a_gap(tmp_path, monkeypatch):
    env_runtime = tmp_path / "env-runtime"
    env_runtime.mkdir()
    monkeypatch.setenv("HERMES_RUNTIME_DIR", str(env_runtime))

    def refused(_root):
        raise AssertionError("resolver")

    found = operational.selected_context(runtime_resolver=refused)
    assert Path(found["runtime"]).resolve() == env_runtime.resolve()
    monkeypatch.delenv("HERMES_RUNTIME_DIR", raising=False)
    store = tmp_path / "store"
    store.mkdir()
    python = tmp_path / "python"

    def runtime(_root):
        return store

    def interpreter(_root):
        return python

    chosen = operational.selected_context(
        runtime_resolver=runtime, interpreter_resolver=interpreter
    )
    assert Path(chosen["runtime"]).resolve() == store.resolve()
    assert Path(chosen["interpreter"]) == python


@pytest.mark.parametrize("discover", [None, _raise_discover, lambda _servers: [], lambda _servers: False])
def test_init_refusal_stays_incomplete(tmp_path, monkeypatch, capsys, discover):
    recovery, _outputs = _quiet(tmp_path)
    code = operational.run(recovery, discover=discover)
    assert code == 0
    snap = _snapshot(recovery)
    tracker = snap["sources"]["tracker"]
    assert tracker["complete"] is False
    assert tracker["error"] == "pagination"
    assert tracker.get("roots") == {"linear:epic-1": "incomplete"}
    assert snap["sources"]["handles"]["complete"] is True
    assert snap["sources"]["units"]["complete"] is True
    assert snap["members"] == {}
    text = capsys.readouterr().out
    assert "tracker_incomplete" in text
    assert "wakeAgent" not in text
    assert _classes(recovery) == ["tracker_incomplete"]
    again = operational.run(recovery, discover=discover)
    assert again == 0
    assert capsys.readouterr().out.strip() == _GATE
    assert _snapshot(recovery)["sources"]["tracker"]["complete"] is False


def test_invalid_mode_refuses_without_the_old_runtime_error(tmp_path, monkeypatch, capsys):
    recovery, _outputs = _quiet(tmp_path)
    monkeypatch.setenv("PROJECT_RECOVERY_DELIVERY", "submit")
    code = operational.run(recovery)
    assert code == 1
    assert capsys.readouterr().out.strip() == "delivery_mode"
    assert not (recovery / "state" / "snapshot.json").exists()


def test_notice_only_never_submits(tmp_path, monkeypatch, capsys):
    recovery = _ended(tmp_path, monkeypatch)
    calls = []
    _install_board(monkeypatch, calls)
    seen = []
    monkeypatch.setattr("plugins.intercom.record.get", _row_get)
    monkeypatch.setattr("plugins.intercom.client.receipt", _terminal_receipt(seen))
    keyed = []

    def send(*_args, **_kwargs):
        keyed.append("send")
        raise AssertionError("submit")

    monkeypatch.setattr("plugins.project_recovery.deliver.keyed_intercom_send", send)
    code = operational.run(recovery, discover=_discover_ok())
    assert code == 0
    assert keyed == []
    assert seen == [("adm-1", _OWNER)]
    episode = _wake_episode(recovery)
    assert episode["delivery"]["state"] == "undelivered"
    notice = f"recovery proj-example: {episode['id']} result_unprocessed h-0007"
    assert capsys.readouterr().out.strip() == notice
    assert not (recovery / "state" / "outbox").exists()
    again = operational.run(recovery, discover=_discover_ok())
    assert again == 0
    assert keyed == []
    assert capsys.readouterr().out.strip() == _GATE
    assert _wake_episode(recovery)["delivery"]["state"] == "undelivered"


def test_joined_handoff_submits_once_and_holds_on_the_next_scan(
    tmp_path, monkeypatch, capsys
):
    recovery = _ended(tmp_path, monkeypatch)
    _install_board(monkeypatch, [])
    seen = []
    monkeypatch.setattr("plugins.intercom.record.get", _row_get)
    monkeypatch.setattr("plugins.intercom.client.receipt", _terminal_receipt(seen))
    _owner_view(monkeypatch, state="idle")
    monkeypatch.setenv("PROJECT_RECOVERY_DELIVERY", "wake")
    sent = []

    def keyed(target, text, *, key, sender, ctx, lister=None):
        sent.append(
            {
                "target": target,
                "text": text,
                "key": key,
                "sender": sender,
                "ctx": ctx,
                "lister": lister,
            }
        )
        return {"ok": True, "message_id": "m-1001", "admission_id": "adm-9"}

    monkeypatch.setattr("plugins.project_recovery.deliver.keyed_intercom_send", keyed)
    first = operational.run(recovery, discover=_discover_ok())
    assert first == 0
    assert capsys.readouterr().out.strip() == _GATE
    assert len(sent) == 1
    assert sent[0]["target"] == _OWNER
    assert sent[0]["key"] == "recovery:proj-example:owner-session"
    assert sent[0]["sender"] == "recovery"
    assert isinstance(sent[0]["ctx"], profiles.Settings)
    assert sent[0]["lister"] is client.list_sessions
    assert "E-1-1" in sent[0]["text"]
    assert "result_unprocessed" in sent[0]["text"]
    assert "authorizes nothing" in sent[0]["text"]
    episode = _wake_episode(recovery)
    assert episode["delivery"]["state"] == "accepted"
    assert episode["delivery"]["admission"] == "adm-9"
    assert episode["delivery"]["message"] == "m-1001"
    stored = json.loads(
        (recovery / "state" / "outbox" / "recovery.proj-example.owner-session.json").read_text(
            encoding="utf-8"
        )
    )
    assert stored["receipt"] == "adm-9"
    assert stored["key"] == "recovery:proj-example:owner-session"
    owners = _snapshot(recovery)["sources"]["owners"]
    assert owners[_OWNER]["state"] == "idle"
    assert {session for _admission, session in seen} == {_OWNER}
    assert ("adm-1", _OWNER) in seen
    second = operational.run(recovery, discover=_discover_ok())
    assert second == 0
    assert len(sent) == 1
    assert _wake_episode(recovery)["delivery"]["state"] == "accepted"
    assert capsys.readouterr().out.strip() == _GATE


def test_running_owner_defers_through_existing_policy(tmp_path, monkeypatch, capsys):
    recovery = _ended(tmp_path, monkeypatch)
    _install_board(monkeypatch, [])
    monkeypatch.setattr("plugins.intercom.record.get", _row_get)
    monkeypatch.setattr("plugins.intercom.client.receipt", _terminal_receipt([]))
    _owner_view(monkeypatch, state="running")
    calls = []

    def keyed(*_args, **_kwargs):
        calls.append("keyed")
        raise AssertionError("submit")

    monkeypatch.setattr("plugins.project_recovery.deliver.keyed_intercom_send", keyed)
    code = operational.run(recovery, discover=_discover_ok(), mode="wake")
    assert code == 0
    assert calls == []
    assert _wake_episode(recovery)["delivery"]["state"] == "undelivered"
    assert _snapshot(recovery)["sources"]["owners"][_OWNER]["state"] == "running"
    assert not (recovery / "state" / "outbox").exists()
    assert capsys.readouterr().out.strip() == _GATE
    again = operational.run(recovery, discover=_discover_ok(), mode="wake")
    assert again == 0
    assert calls == []
    assert _snapshot(recovery)["sources"]["owners"][_OWNER]["state"] == "running"


def _tip_listing(monkeypatch, *, state):
    """Public session.list shape: no runtime_revision."""
    monkeypatch.setattr(
        "plugins.intercom.address.resolve",
        lambda *_args, **_kwargs: {"ok": True, "session_id": _TIP, "title": "Owner"},
    )

    def listing(*_args, **_kwargs):
        row = {"id": _TIP, "title": "Owner", "state": state}
        assert "runtime_revision" not in row
        return {"ok": True, "sessions": [row]}

    monkeypatch.setattr("plugins.intercom.address.list_sessions", listing)


def test_discovery_refusal_keeps_open_episode_and_unit_facts(
    tmp_path, monkeypatch, capsys
):
    recovery = _ended(tmp_path, monkeypatch)
    _install_board(monkeypatch, [])
    monkeypatch.setattr("plugins.intercom.record.get", _row_get)
    monkeypatch.setattr("plugins.intercom.client.receipt", _terminal_receipt([]))
    _owner_view(monkeypatch, state="idle")
    sent = []

    def keyed(*_args, **_kwargs):
        sent.append("keyed")
        return {"ok": True, "message_id": "m-1001", "admission_id": "adm-9"}

    monkeypatch.setattr("plugins.project_recovery.deliver.keyed_intercom_send", keyed)
    first = operational.run(recovery, discover=_discover_ok(), mode="wake")
    assert first == 0
    episode_id = _wake_episode(recovery)["id"]
    assert _wake_episode(recovery)["delivery"]["state"] == "accepted"
    snap = _snapshot(recovery)
    snap["units"]["h-0007"]["ever_running"] = True
    (recovery / "state" / "snapshot.json").write_text(
        json.dumps(snap), encoding="utf-8"
    )
    calls = []

    def refuse(_server, verb, _args):
        calls.append(verb)
        return "trust_refused"

    from tools.mcp_readonly import call_mcp_tool_readonly

    refuse.closed_verbs = call_mcp_tool_readonly.closed_verbs
    monkeypatch.setattr("tools.mcp_readonly.call_mcp_tool_readonly", refuse)
    monkeypatch.setattr("plugins.project_recovery.readers.call_mcp_tool_readonly", refuse)
    code = operational.run(recovery, discover=lambda _servers: [], mode="wake")
    assert code == 0
    assert calls
    open_ids = [
        row["id"]
        for row in _open(recovery)
        if row["class"] == "result_unprocessed"
    ]
    assert open_ids == [episode_id]
    assert _wake_episode(recovery)["delivery"]["state"] == "accepted"
    unit = _snapshot(recovery)["units"]["h-0007"]
    assert unit["invocation_id"] == "inv-1"
    assert unit["callback_message_id"] == "msg-1"
    assert unit["ever_running"] is True
    sources = _snapshot(recovery)["sources"]
    assert sources["tracker"]["complete"] is False
    assert sources["handles"]["complete"] is True
    assert sources["units"]["complete"] is True
    assert sent == ["keyed"]
    _install_board(monkeypatch, [])
    recovered = operational.run(recovery, discover=_discover_ok(), mode="wake")
    assert recovered == 0
    assert sent == ["keyed"]
    assert [row["id"] for row in _open(recovery) if row["class"] == "result_unprocessed"] == [
        episode_id
    ]
    assert _wake_episode(recovery)["delivery"]["state"] == "accepted"
    assert capsys.readouterr().out


def test_closed_owner_holds_across_the_next_scan(tmp_path, monkeypatch, capsys):
    recovery = _ended(tmp_path, monkeypatch)
    _install_board(monkeypatch, [])
    monkeypatch.setattr("plugins.intercom.record.get", _row_get)
    monkeypatch.setattr("plugins.intercom.client.receipt", _terminal_receipt([]))
    _tip_listing(monkeypatch, state="closed")
    sessions = _PhysicalSessions()

    class _Reader:
        def __init__(self):
            return None

        def close(self):
            return sessions.close()

        def get_session(self, session_id):
            return sessions.get_session(session_id)

        def get_compression_tip(self, session_id):
            return sessions.get_compression_tip(session_id)

        @property
        def store(self):
            return sessions

    monkeypatch.setattr("plugins.intercom.state.SessionReader", _Reader)
    calls = []

    def keyed(_target, _text, *, key, sender, ctx, lister=None):
        del key, sender, ctx, lister
        calls.append("keyed")
        return {
            "ok": False,
            "error": "closed-by-user",
            "data": {
                "detail": (
                    "logical_owner=owner-session physical=phys-4 "
                    "runtime_revision=4"
                )
            },
        }

    monkeypatch.setattr("plugins.project_recovery.deliver.keyed_intercom_send", keyed)
    code = operational.run(recovery, discover=_discover_ok(), mode="wake")
    assert code == 0
    assert calls == ["keyed"]
    assert "owner_closed" in capsys.readouterr().out
    assert _wake_episode(recovery)["delivery"]["state"] == "undelivered"
    holds = json.loads((recovery / "state" / "close-holds.json").read_text(encoding="utf-8"))
    assert holds["o3:proj-example:owner-session:4"] is True
    again = operational.run(recovery, discover=_discover_ok(), mode="wake")
    assert again == 0
    assert calls == ["keyed"]
    assert capsys.readouterr().out.strip() == _GATE
    sessions.revision = 5
    reopened = operational.run(recovery, discover=_discover_ok(), mode="wake")
    assert reopened == 0
    assert calls == ["keyed", "keyed"]


def test_receipt_uses_stored_target_across_statuses(tmp_path, monkeypatch, capsys):
    recovery = _ended(tmp_path, monkeypatch)
    _install_board(monkeypatch, [])
    rows = {
        "msg-1": {
            "id": "msg-1",
            "admission_id": "adm-1",
            "target_session_id": _OWNER,
            "offered_turn": None,
        }
    }

    def get(message_id):
        return rows.get(message_id)

    monkeypatch.setattr("plugins.intercom.record.get", get)
    seen = []
    status = {"value": "terminal"}

    def receipt(admission_id, *, session_id):
        seen.append((admission_id, session_id))
        if admission_id == "adm-1":
            if session_id != _OWNER:
                return {"ok": False, "error": "not_found"}
            return {"ok": True, "status": "terminal"}
        if admission_id != "adm-9" or session_id != _STORED:
            return {"ok": False, "error": "not_found"}
        return {"ok": True, "status": status["value"]}

    monkeypatch.setattr("plugins.intercom.client.receipt", receipt)
    _tip_listing(monkeypatch, state="idle")
    gate = {"conflict": False}
    original = record.lookup_message_admission

    def lookup(message_id):
        if message_id == "m-1001" and gate["conflict"]:
            return {"outcome": "conflict"}
        return original(message_id)

    monkeypatch.setattr("plugins.intercom.record.lookup_message_admission", lookup)

    def keyed(*_args, **_kwargs):
        return {"ok": True, "message_id": "m-1001", "admission_id": "adm-9"}

    monkeypatch.setattr("plugins.project_recovery.deliver.keyed_intercom_send", keyed)
    first = operational.run(recovery, discover=_discover_ok(), mode="wake")
    assert first == 0
    assert _wake_episode(recovery)["delivery"]["state"] == "accepted"
    rows["m-1001"] = {
        "id": "m-1001",
        "admission_id": "adm-9",
        "target_session_id": _STORED,
        "offered_turn": "turn-1",
    }
    gate["conflict"] = True
    seen.clear()
    blocked = operational.run(recovery, discover=_discover_ok(), mode="wake")
    assert blocked == 0
    assert all(admission != "adm-9" for admission, _session in seen)
    assert _wake_episode(recovery)["delivery"]["state"] != "settled"
    gate["conflict"] = False
    for name, count in (("queued", 1), ("started", 2)):
        status["value"] = name
        seen.clear()
        code = operational.run(recovery, discover=_discover_ok(), mode="wake")
        assert code == 0
        assert ("adm-9", _STORED) in seen
        assert ("adm-9", _OWNER) not in seen
        assert ("adm-9", _TIP) not in seen
        stalls = json.loads((recovery / "state" / "stalls.json").read_text(encoding="utf-8"))
        assert stalls["adm-9"] == count
        assert _wake_episode(recovery)["delivery"]["state"] == "carried"
    status["value"] = "terminal"
    seen.clear()
    settled = operational.run(recovery, discover=_discover_ok(), mode="wake")
    assert settled == 0
    assert ("adm-9", _STORED) in seen
    assert ("adm-9", _OWNER) not in seen
    assert ("adm-9", _TIP) not in seen
    assert _wake_episode(recovery)["delivery"]["state"] == "settled"
    assert capsys.readouterr().out


def test_unknown_owner_does_not_submit(tmp_path, monkeypatch, capsys):
    recovery = _ended(tmp_path, monkeypatch)
    _install_board(monkeypatch, [])
    monkeypatch.setattr("plugins.intercom.record.get", _row_get)
    monkeypatch.setattr("plugins.intercom.client.receipt", _terminal_receipt([]))
    _owner_view(monkeypatch, state="idle", listing_ok=False)
    calls = []

    def keyed(*_args, **_kwargs):
        calls.append("keyed")
        raise AssertionError("submit")

    monkeypatch.setattr("plugins.project_recovery.deliver.keyed_intercom_send", keyed)
    code = operational.run(recovery, discover=_discover_ok(), mode="wake")
    assert code == 0
    assert calls == []
    text = capsys.readouterr().out
    assert "owner_unreachable" in text
    assert _wake_episode(recovery)["delivery"]["state"] == "undelivered"
    assert _snapshot(recovery)["sources"]["owners"][_OWNER]["state"] == "unknown"
    again = operational.run(recovery, discover=_discover_ok(), mode="wake")
    assert again == 0
    assert calls == []
    assert capsys.readouterr().out.strip() == _GATE


def test_no_action_is_silent(tmp_path, monkeypatch, capsys):
    recovery, _outputs = _quiet(tmp_path)
    _install_board(monkeypatch, [])
    code = operational.run(recovery, discover=lambda _servers: True)
    assert code == 0
    assert capsys.readouterr().out.strip() == _GATE
    assert _open(recovery) == []


def test_job_specification_does_not_activate(tmp_path, monkeypatch, capsys):
    script = tmp_path / "scan.py"
    script.write_text("raise SystemExit(0)\n", encoding="utf-8")
    spec = operational.job_specification(
        script=str(script), workdir=str(tmp_path), interpreter=sys.executable
    )
    assert operational.specification_errors(spec) == []
    assert spec["name"] == "recovery-workshop"
    assert spec["schedule"] == "every 15m"
    assert spec["prompt"] == ""
    assert spec["deliver"] == "local"
    assert spec["no_agent"] is True
    assert "attach_to_session" not in spec
    assert "mirror_delivery" not in spec
    calls = []

    def create_job(**kwargs):
        calls.append(kwargs)
        return {"id": "fake"}

    monkeypatch.setattr("cron.jobs.create_job", create_job)
    recovery, _outputs = _quiet(tmp_path)
    _install_board(monkeypatch, [])
    code = operational.run(recovery, discover=_discover_ok())
    assert code == 0
    assert calls == []
    assert capsys.readouterr().out.strip() == _GATE
    create_job(**spec)
    assert calls == [spec]
    broken = dict(spec)
    broken["attach_to_session"] = True
    assert "attach_to_session" in operational.specification_errors(broken)


def test_default_scope_is_the_watchdog_and_reads_no_board(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("PROJECT_RECOVERY_SCOPE", raising=False)

    def refuse(*_args, **_kwargs):
        raise AssertionError("watchdog scope read the tracker")

    monkeypatch.setattr("plugins.project_recovery.scan.read_tracker", refuse)
    recovery, _outputs = _quiet(tmp_path)
    _install_board(monkeypatch, [])
    discovered = []

    def discover(servers):
        discovered.append(servers)
        return True

    code = operational.run(recovery, discover=discover)

    assert code == 0
    assert discovered == []
    assert capsys.readouterr().out.strip() == _GATE
    tracker = _snapshot(recovery)["sources"]["tracker"]
    assert tracker["scope"] == "watchdog"
    assert tracker["complete"] is None


def test_unknown_scope_is_refused_before_any_read(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PROJECT_RECOVERY_SCOPE", "everything")
    recovery, _outputs = _quiet(tmp_path)

    code = operational.run(recovery, discover=_discover_ok())

    assert code == 1
    assert capsys.readouterr().out.strip() == "scope_invalid"
