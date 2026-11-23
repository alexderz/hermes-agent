"""Await/notify rows on the classic CLI process dock.

The registry double below is an API double of ``process.list`` / ``process.get``.
It is not a live gateway and not proof of the joined service lifecycle.
"""


class _Proc:
    def __init__(self, **kwargs):
        self.id = kwargs["id"]
        self.command = kwargs.get("command", "job")
        self.exit_code = kwargs.get("exit_code")
        self.started_at = kwargs.get("started_at", 1_000.0)
        self.exited_at = kwargs.get("exited_at", 0.0)
        self.output_buffer = kwargs.get("output", "")
        self.completion_reason = kwargs.get("reason", "exited")


class _Registry:
    """API double of the gateway process registry the dock reads."""

    def __init__(self, entries, procs):
        self._entries = entries
        self._procs = procs

    def list_sessions(self, include_service_receipts=False):
        self.include_service_receipts = include_service_receipts
        return self._entries

    def get(self, process_id):
        return self._procs.get(process_id)


def _bind(monkeypatch, entries, procs):
    registry = _Registry(entries, procs)
    monkeypatch.setattr("hermes_cli.gateway_tools.process_registry", lambda: registry)
    return registry


def test_waiting_ready_lost_are_not_settled_success(monkeypatch):
    from hermes_cli import cli_process_dock as dock

    now = 10_000.0
    entries = [
        {
            "session_id": "wait",
            "command": "deploy-web",
            "status": "running",
            "exit_code": None,
            "attention": "waiting",
            "service_mode": "await",
            "completion_reason": None,
        },
        {
            "session_id": "ready",
            "command": "pack-image",
            "status": "exited",
            "exit_code": 0,
            "attention": "ready",
            "service_mode": "await",
            "completion_reason": "exited",
        },
        {
            "session_id": "lost",
            "command": "watcher",
            "status": "exited",
            "exit_code": 0,
            "completion_reason": "lost",
        },
        {
            "session_id": "killed",
            "command": "sleep 30",
            "status": "exited",
            "exit_code": 0,
            "completion_reason": "killed",
        },
        {
            "session_id": "odd",
            "command": "mystery",
            "status": "exited",
            "exit_code": 0,
            "attention": "mystery",
            "completion_reason": "exited",
        },
        {
            "session_id": "legacy",
            "command": "echo ok",
            "status": "exited",
            "exit_code": 0,
            "completion_reason": "exited",
        },
    ]
    procs = {
        "wait": _Proc(
            id="wait",
            command="deploy-web",
            started_at=now - 15,
            output="fetching\nstep 2/4\n",
        ),
        "ready": _Proc(
            id="ready",
            command="pack-image",
            exit_code=0,
            started_at=now - 400,
            exited_at=now - 120,
            output="published\n",
        ),
        "lost": _Proc(
            id="lost",
            command="watcher",
            exit_code=0,
            started_at=now - 20,
            exited_at=now - 3,
            reason="lost",
        ),
        "killed": _Proc(
            id="killed",
            command="sleep 30",
            exit_code=0,
            started_at=now - 9,
            exited_at=now - 2,
            reason="killed",
        ),
        "odd": _Proc(
            id="odd",
            command="mystery",
            exit_code=0,
            started_at=now - 12,
            exited_at=now - 1,
        ),
        "legacy": _Proc(
            id="legacy",
            command="echo ok",
            exit_code=0,
            started_at=now - 8,
            exited_at=now - 4,
            output="ok\n",
        ),
    }
    _bind(monkeypatch, entries, procs)

    rows = {row["id"]: row for row in dock.process_rows(now)}
    assert rows["wait"]["status"] == "waiting"
    assert rows["ready"]["status"] == "ready"
    assert rows["lost"]["status"] == "lost"
    assert rows["killed"]["status"] == "killed"
    assert rows["odd"]["status"] == "unknown"
    assert rows["legacy"]["status"] == "done"

    ready_line = dock.process_activity(rows["ready"])
    assert "result ready" in ready_line
    assert "continuation queued" not in ready_line.lower()
    assert dock.process_glyph(rows["wait"]) != "✔"
    assert dock.process_glyph(rows["ready"]) != "✔"
    assert dock.process_glyph(rows["lost"]) != "✔"
    assert dock.process_glyph(rows["killed"]) != "✔"
    assert "waiting" in dock.process_activity(rows["wait"])
    assert "step 2/4" in dock.process_activity(rows["wait"])


def test_legacy_running_and_failed_rows_stay_unchanged(monkeypatch):
    from hermes_cli import cli_process_dock as dock

    now = 5_000.0
    entries = [
        {
            "session_id": "run",
            "command": "sleep 30",
            "status": "running",
            "exit_code": None,
            "completion_reason": None,
        },
        {
            "session_id": "bad",
            "command": "echo bad",
            "status": "exited",
            "exit_code": 3,
            "completion_reason": "exited",
        },
    ]
    procs = {
        "run": _Proc(id="run", command="sleep 30", started_at=now - 5),
        "bad": _Proc(
            id="bad",
            command="echo bad",
            exit_code=3,
            started_at=now - 6,
            exited_at=now - 1,
        ),
    }
    _bind(monkeypatch, entries, procs)
    rows = dock.process_rows(now)
    assert [(row["id"], row["status"]) for row in rows] == [
        ("run", "running"),
        ("bad", "failed"),
    ]
    assert dock.process_glyph(rows[0]) == "⚙"
    assert dock.process_glyph(rows[1]) == "✘"


def test_process_status_ignores_direct_blocking_exit_zero():
    from hermes_cli.cli_process_dock import process_status

    settled = {
        "status": "exited",
        "exit_code": 0,
        "completion_reason": "exited",
        "service_mode": "await",
    }
    assert process_status(settled) == "done"
    assert process_status({"status": "running", "service_mode": "await"}) == "waiting"
    assert process_status({"status": "running"}) == "running"


def test_missing_proc_paints_a_live_receipt_and_killed_beats_stale_attention(monkeypatch):
    """A pending receipt has no in-memory proc. Killed still beats stale attention."""
    from hermes_cli import cli_process_dock as dock

    now = 8_000.0
    entries = [
        {
            "session_id": "receipt",
            "command": "pack image",
            "status": "exited",
            "exit_code": 0,
            "attention": "ready",
            "service_mode": "await",
            "completion_reason": "exited",
            "uptime_seconds": 40,
            "output_preview": "published\n",
        },
        {
            "session_id": "stopped",
            "command": "sleep 30",
            "status": "exited",
            "exit_code": 0,
            "attention": "ready",
            "service_mode": "await",
            "completion_reason": "killed",
            "uptime_seconds": 9,
        },
        {
            "session_id": "settled",
            "command": "echo ok",
            "status": "exited",
            "exit_code": 0,
            "completion_reason": "exited",
            "uptime_seconds": 3,
        },
    ]
    procs = {
        "stopped": _Proc(
            id="stopped",
            command="sleep 30",
            exit_code=0,
            started_at=now - 9,
            exited_at=now - 2,
            reason="killed",
            output="stopped\n",
        ),
    }
    registry = _bind(monkeypatch, entries, procs)
    rows = {row["id"]: row for row in dock.process_rows(now)}
    assert registry.include_service_receipts is True
    assert set(rows) == {"receipt", "stopped"}
    assert rows["receipt"]["status"] == "ready"
    assert rows["receipt"]["detail"] == "published"
    assert rows["receipt"]["elapsed"] == 40
    assert rows["receipt"]["since_exit"] == 0
    assert dock.process_activity(rows["receipt"]) == "result ready"
    assert "published" not in dock.process_activity(rows["receipt"])
    assert rows["stopped"]["status"] == "killed"
    assert "settled" not in rows
