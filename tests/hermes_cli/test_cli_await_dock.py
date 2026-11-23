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


def test_disk_only_pending_failed_and_lost_outlive_the_retain_window(monkeypatch):
    """A disk receipt with no proc stays up past 60s only while admission is pending.

    Settled failures still leave. Killed is not held by a stale attention or the flag.
    """
    from hermes_cli import cli_process_dock as dock

    now = 20_000.0
    old = now - (dock.RETAIN_SECONDS + 30)
    entries = [
        {
            "session_id": "fail-disk",
            "command": "fail-cold",
            "status": "exited",
            "exit_code": 1,
            "attention": "failed",
            "service_mode": "notify",
            "completion_reason": "exited",
            "admission_pending": True,
            "uptime_seconds": 90,
            "exited_at": old,
            "output_preview": "boom\n",
        },
        {
            "session_id": "lost-disk",
            "command": "lost-cold",
            "status": "exited",
            "exit_code": 0,
            "attention": "lost",
            "service_mode": "await",
            "completion_reason": "lost",
            "admission_pending": True,
            "uptime_seconds": 12,
            "exited_at": old,
            "output_preview": "gone\n",
        },
        {
            "session_id": "fail-mem",
            "command": "fail-live",
            "status": "exited",
            "exit_code": 7,
            "attention": "failed",
            "service_mode": "notify",
            "completion_reason": "exited",
            "admission_pending": True,
        },
        {
            "session_id": "fail-fresh",
            "command": "echo fresh",
            "status": "exited",
            "exit_code": 4,
            "completion_reason": "exited",
        },
        {
            "session_id": "fail-old",
            "command": "echo settled",
            "status": "exited",
            "exit_code": 2,
            "completion_reason": "exited",
        },
        {
            "session_id": "stopped-old",
            "command": "sleep 30",
            "status": "exited",
            "exit_code": 0,
            "attention": "ready",
            "service_mode": "await",
            "completion_reason": "killed",
            "admission_pending": True,
        },
        {
            "session_id": "fail-orphan",
            "command": "echo orphan",
            "status": "exited",
            "exit_code": 1,
            "attention": "failed",
            "completion_reason": "exited",
            "exited_at": old,
        },
    ]
    procs = {
        "fail-mem": _Proc(
            id="fail-mem",
            command="fail-live",
            exit_code=7,
            started_at=old - 10,
            exited_at=old,
            output="boom-live\n",
        ),
        "fail-fresh": _Proc(
            id="fail-fresh",
            command="echo fresh",
            exit_code=4,
            started_at=now - 8,
            exited_at=now - 5,
        ),
        "fail-old": _Proc(
            id="fail-old",
            command="echo settled",
            exit_code=2,
            started_at=old - 8,
            exited_at=old,
        ),
        "stopped-old": _Proc(
            id="stopped-old",
            command="sleep 30",
            exit_code=0,
            started_at=old - 9,
            exited_at=old,
            reason="killed",
        ),
    }
    registry = _bind(monkeypatch, entries, procs)
    rows = {row["id"]: row for row in dock.process_rows(now)}
    assert registry.include_service_receipts is True
    assert set(rows) == {"fail-disk", "lost-disk", "fail-mem", "fail-fresh"}
    assert rows["fail-disk"]["status"] == "failed"
    assert rows["fail-disk"]["exit_code"] == 1
    assert rows["fail-disk"]["detail"] == "boom"
    assert rows["fail-disk"]["since_exit"] == 0
    assert rows["lost-disk"]["status"] == "lost"
    assert rows["lost-disk"]["exit_code"] == 0
    assert rows["fail-mem"]["status"] == "failed"
    assert rows["fail-mem"]["since_exit"] > dock.RETAIN_SECONDS
    assert rows["fail-fresh"]["status"] == "failed"
    assert dock.process_is_open("failed") is False
    assert dock.process_is_open("lost") is False
    assert dock.process_glyph(rows["fail-disk"]) == "✘"
    assert dock.process_glyph(rows["lost-disk"]) == "?"
    assert dock.process_glyph(rows["fail-disk"]) != "⚙"
    assert dock.process_glyph(rows["lost-disk"]) != "◆"
    assert dock.process_activity(rows["fail-disk"]) != "result ready"
    assert dock.process_activity(rows["lost-disk"]) != "result ready"
    assert dock.process_status(entries[5]) == "killed"
