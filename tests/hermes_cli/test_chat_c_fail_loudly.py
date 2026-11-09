"""Tests for `chat -c <title>` failing loudly (stderr) and `--create-if-missing`.

Regression for #86794: a background/quiet `hermes chat -c "<title>" -q "..."`
against a not-yet-existing titled session silently no-oped — the error message
was written to stdout (which quiet/programmatic callers treat as the "final
response" channel) instead of stderr, and there was no way to create the
titled session from the same invocation.

Two behaviors are fixed here:

1. **fail loudly on stderr** — when no session matches `-c <title>`, the error
   goes to stderr (exit 1), so programmatic callers always see it.
2. **--create-if-missing** — same invocation with the flag creates a fresh
   session carrying the title and proceeds, giving plugins/scripts a
   deterministic "send to this named thread, making it if needed" primitive.
"""

import pytest


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """Point HERMES_HOME at a temp dir so session creation stays isolated."""
    home = tmp_path / "hermes_home"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    return home


def _create_titled_session(title):
    from hermes_cli.main import _create_titled_session as fn

    return fn(title)


class TestCreateIfMissingFlagParsing:
    def test_flag_parses_on_chat_subparser(self):
        """--create-if-missing is accepted by the real chat parser."""
        from hermes_cli._parser import build_top_level_parser

        parser, _subparsers, _chat_parser = build_top_level_parser()
        args = parser.parse_args(
            ["chat", "-c", "Bot Chat", "--create-if-missing", "-q", "hi"]
        )
        assert args.continue_last == "Bot Chat"
        assert getattr(args, "create_if_missing", False) is True

    def test_flag_absent_means_false(self):
        """Without the flag, create_if_missing stays unset (SUPPRESS default)."""
        from hermes_cli._parser import build_top_level_parser

        parser, _subparsers, _chat_parser = build_top_level_parser()
        args = parser.parse_args(["chat", "-c", "Bot Chat", "-q", "hi"])
        # SUPPRESS default: attribute absent, and cmd_chat's getattr(..., False)
        # must treat it as False.
        assert getattr(args, "create_if_missing", False) is False


class TestCreateTitledSession:
    def test_creates_session_with_title(self, isolated_home):
        sid = _create_titled_session("Bot Chat")
        assert sid, "should return a session id"

        from hermes_state import SessionDB

        db = SessionDB()
        try:
            session = db.get_session(sid)
            assert session is not None
            assert db.get_session_title(sid) == "Bot Chat"
        finally:
            db.close()

    def test_created_session_resolvable_by_title(self, isolated_home):
        """After creation, resolve_session_by_title finds it (idempotent sends)."""
        sid = _create_titled_session("Bot Chat")
        assert sid

        from hermes_state import SessionDB

        db = SessionDB()
        try:
            resolved = db.resolve_session_by_title("Bot Chat")
            assert resolved == sid
        finally:
            db.close()


class TestTitledSessionRecordsCwd:
    """A titled session made by ``--create-if-missing`` (or resumed with ``--in``) records its cwd, so it
    groups under the project whose folder contains it."""

    def test_created_session_records_launch_cwd(self, isolated_home, tmp_path, monkeypatch):
        work = tmp_path / "project"
        work.mkdir()
        monkeypatch.chdir(work)
        monkeypatch.delenv("TERMINAL_ENV", raising=False)
        sid = _create_titled_session("Project — Orchestrator")
        from hermes_state import SessionDB

        db = SessionDB()
        try:
            assert db.get_session(sid)["cwd"] == str(work)
        finally:
            db.close()

    def test_remote_backend_records_no_cwd(self, isolated_home, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("TERMINAL_ENV", "ssh")
        sid = _create_titled_session("Remote")
        from hermes_state import SessionDB

        db = SessionDB()
        try:
            assert not db.get_session(sid).get("cwd")
        finally:
            db.close()

    def test_fill_keeps_git_fields_and_skips_non_cli(self, isolated_home, tmp_path, monkeypatch):
        from hermes_cli.main import _stamp_resumed_session_cwd
        from hermes_state import SessionDB

        db = SessionDB()
        try:
            db.create_session("s_git", source="cli", git_repo_root="/repo")
            db.create_session("s_tg", source="telegram")
        finally:
            db.close()
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("TERMINAL_ENV", raising=False)
        _stamp_resumed_session_cwd("s_git")
        _stamp_resumed_session_cwd("s_tg")
        db = SessionDB()
        try:
            row = db.get_session("s_git")
            assert row["cwd"] == str(tmp_path) and row["git_repo_root"] == "/repo"
            assert not db.get_session("s_tg").get("cwd")
        finally:
            db.close()

    def test_remote_backend_does_not_stamp_resume(self, isolated_home, tmp_path, monkeypatch):
        from hermes_cli.main import _stamp_resumed_session_cwd
        from hermes_state import SessionDB

        db = SessionDB()
        try:
            db.create_session("s_r", source="cli")
        finally:
            db.close()
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("TERMINAL_ENV", "docker")
        _stamp_resumed_session_cwd("s_r")
        db = SessionDB()
        try:
            assert not db.get_session("s_r").get("cwd")
        finally:
            db.close()

    def test_resolve_args_stamps_only_with_in(self, isolated_home, tmp_path, monkeypatch):
        import argparse

        from hermes_cli import main as hm
        from hermes_state import SessionDB

        db = SessionDB()
        try:
            db.create_session("s_a", source="cli")
            db.create_session("s_b", source="cli")
        finally:
            db.close()
        work = tmp_path / "w"
        work.mkdir()
        monkeypatch.delenv("TERMINAL_ENV", raising=False)
        monkeypatch.delenv("TERMINAL_CWD", raising=False)
        monkeypatch.chdir(tmp_path)
        hm._resolve_chat_session_args(argparse.Namespace(in_dir=str(work), resume="s_a", continue_last=None), False)
        hm._resolve_chat_session_args(argparse.Namespace(in_dir=None, resume="s_b", continue_last=None), False)
        db = SessionDB()
        try:
            assert db.get_session("s_a")["cwd"] == str(work)
            assert not db.get_session("s_b").get("cwd")
        finally:
            db.close()

    def test_resume_with_in_fills_missing_cwd_only(self, isolated_home, tmp_path, monkeypatch):
        from hermes_cli.main import _stamp_resumed_session_cwd
        from hermes_state import SessionDB

        db = SessionDB()
        try:
            db.create_session("s_null", source="cli")
            db.create_session("s_set", source="cli", cwd="/elsewhere")
        finally:
            db.close()
        work = tmp_path / "proj"
        work.mkdir()
        monkeypatch.chdir(work)
        monkeypatch.delenv("TERMINAL_ENV", raising=False)
        _stamp_resumed_session_cwd("s_null")
        _stamp_resumed_session_cwd("s_set")
        db = SessionDB()
        try:
            assert db.get_session("s_null")["cwd"] == str(work)
            assert db.get_session("s_set")["cwd"] == "/elsewhere"
        finally:
            db.close()


class TestChatCFailLoudlyOnStderr:
    """Behavior-level: run the real cmd_chat path and inspect channels."""

    def test_missing_session_fails_on_stderr(self, isolated_home, monkeypatch):
        """-c <missing title> → exit 1, message on stderr, stdout untouched."""
        import sys

        import hermes_cli.main as main_mod

        stderr_lines = []

        class _Exit(Exception):
            pass

        def _fake_exit(code):
            raise _Exit(code)

        class _Stderr:
            def write(self, text):
                stderr_lines.append(text)
                return len(text)

        class _Stdout:
            def write(self, text):
                return len(text)

        monkeypatch.setattr(sys, "exit", _fake_exit)
        monkeypatch.setattr(sys, "stderr", _Stderr())
        monkeypatch.setattr(sys, "stdout", _Stdout())

        args = type(
            "Args",
            (),
            {
                "continue_last": "Bot Chat",
                "resume": None,
                "create_if_missing": False,
            },
        )()

        with pytest.raises(_Exit) as ei:
            main_mod._resolve_continue_arg(args, use_tui=False)

        assert ei.value.args[0] == 1
        assert any("No session found matching 'Bot Chat'" in l for l in stderr_lines)
        assert not stderr_lines[0].startswith("Use 'hermes sessions list'")

    def test_create_if_missing_sets_resume(self, isolated_home, monkeypatch):
        """--create-if-missing resolves to a new session id on args.resume."""
        import hermes_cli.main as main_mod

        args = type(
            "Args",
            (),
            {
                "continue_last": "Bot Chat",
                "resume": None,
                "create_if_missing": True,
            },
        )()

        main_mod._resolve_continue_arg(args, use_tui=False)

        assert args.resume, "resume should be set to the new session id"
        from hermes_state import SessionDB

        db = SessionDB()
        try:
            assert db.get_session_title(args.resume) == "Bot Chat"
        finally:
            db.close()
