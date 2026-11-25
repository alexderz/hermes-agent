"""``hermes chat`` session-argument steps split out of ``hermes_cli.main``: ``--in DIR``, session
resolution (last / by title / by id), ``--resume @claude/@codex`` imports, and recreating a removed
``--tui -w`` worktree a resumed session needs (N8)."""

import contextlib
import logging
import os
import subprocess
import sys

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def _session_db():
    """Yield the CLI's read-only session reads over a storage interface reader on the current profile's
    store, or None when it cannot open (lazy imports, so test patches on ``persistence_assembly``
    intercept). Every caller is a lookup (last session, title → id, recorded cwd), so it never opens a
    writer beside the one the CLI opens a moment later. Open failures yield None and any error raised by
    the ``with`` body is swallowed: callers fall through to their ``return None``."""
    reader, handles = None, contextlib.ExitStack()
    try:
        from persistence_assembly import open_persistence_reader
        from hermes_cli.config import get_hermes_home

        store = handles.enter_context(open_persistence_reader(get_hermes_home()))
        store.ready()
        # Gateway rows the CLI/TUI created are labelled ``local``; source-scoped lookups read main's labels.
        from hermes_cli.gateway_session_store import SurfaceLabelReader
        reader = SurfaceLabelReader(store)
    except Exception:
        pass
    try:
        yield reader  # body errors (incl. AttributeError on a None reader) are swallowed
    except Exception:
        pass
    finally:
        handles.close()


def _resolve_workspace_key() -> str | None:
    """The current workspace identity for cwd-scoped resume.

    Git repo root when CWD is inside a repo (so all sessions across its
    subdirs/worktrees group together), else the CWD itself. Returns None when
    neither can be determined — callers fall back to the global MRU then.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return os.path.abspath(result.stdout.strip())
    except Exception:
        pass
    try:
        return os.getcwd()
    except Exception:
        return None


def _resolve_last_session(source: str = "cli") -> str | None:
    """Look up the most recently-used session ID for a source.

    Scoped to the current workspace first (git repo root, else cwd) so
    ``hermes -c`` from repo A continues repo A's last session rather than the
    global MRU. Falls back to the unscoped MRU when no session matches the
    current workspace, preserving the old behaviour for fresh directories.
    """
    # A finite `hermes -z`/`chat -q` run is CLI history too: `hermes -z … --resume latest` chains on it.
    if source == "cli":
        from agent.session_source import CLI_FAMILY_SOURCES
        source = sorted(CLI_FAMILY_SOURCES)
    with _session_db() as db:
        ws_key = _resolve_workspace_key()
        if ws_key:
            sessions = db.search_sessions(source=source, limit=1, workspace_key=ws_key, skip_launch_stubs=True)
            if sessions:
                return sessions[0]["id"]
        # Fallback: global MRU for this source.
        sessions = db.search_sessions(source=source, limit=1, skip_launch_stubs=True)
        return sessions[0]["id"] if sessions else None
    return None


def _cli_launch_cwd() -> str | None:
    """cwd to stamp on a CLI-created session row: the process cwd (``--in DIR`` already chdir'd there),
    or None on non-local terminal backends. Mirrors ``run_agent._launch_cwd_for_session`` for the CLI
    family without importing the agent module on the startup path."""
    if (os.environ.get("TERMINAL_ENV") or "local").strip().lower() not in ("", "local"):
        return None
    try:
        return os.getcwd()
    except OSError:  # cwd was unlinked out from under us
        return None


def _stamp_resumed_session_cwd(session_id: str) -> None:
    """``--in DIR`` pins a resumed session there: record DIR when the row has no cwd yet.

    A resumed session never runs the agent's lazy row create (which stamps cwd), so a row minted without
    one (older ``--create-if-missing``, imports, scripts) stayed cwd-less forever and never grouped under
    its project. Only fills an empty cwd, only for CLI-family rows (the same set the agent's lazy create
    stamps); an existing cwd and any git fields are left alone."""
    cwd = _cli_launch_cwd()
    if not (session_id and cwd):
        return
    from agent.session_source import CLI_FAMILY_SOURCES

    # Read-only first: most resumes already have a cwd, so no writer is opened for them. A failed read
    # (no store yet, unreadable row) stamps nothing rather than guessing.
    needs_fill = False
    with _session_db() as ro:
        session = ro.get_session(session_id) or {}
        needs_fill = bool(session) and not session.get("cwd") and session.get("source") in CLI_FAMILY_SOURCES
    if not needs_fill:
        return
    try:
        from persistence_assembly import open_persistence, profile_scope

        with open_persistence(profile_scope(), eager=True) as store:
            store.sessions.fill_cwd_if_missing(session_id, cwd)
    except Exception:
        logger.debug("Could not stamp cwd on resumed session %s", session_id, exc_info=True)


def apply_in_dir(args) -> None:
    """--in DIR: chdir first so workspace-scoped lookups key off DIR; pins the session there."""
    in_dir = getattr(args, "in_dir", None)
    if not in_dir:
        return
    # Git Bash / MSYS hands us POSIX-style paths (`--in ~` → `/c/Users/x`);
    # translate drive-root spellings to native Windows form. No-op elsewhere.
    from tools.environments.local import _msys_to_windows_path

    _target_dir = os.path.abspath(os.path.expanduser(_msys_to_windows_path(in_dir)))
    if not os.path.isdir(_target_dir):
        print(f"Error: --in directory not found: {in_dir}")
        sys.exit(1)
    try:
        os.chdir(_target_dir)
    except OSError as e:
        print(f"Error: cannot enter --in directory {in_dir}: {e}")
        sys.exit(1)
    # Every cwd consumer (resolve_agent_cwd -> Codex app-server thread cwd, the
    # terminal tool, context-file discovery) prefers TERMINAL_CWD over the process
    # cwd, so a value inherited from a parent surface, the shell or .env outlives
    # this chdir and re-homes the session in the old directory (#106220). Refresh
    # it. An unset variable stays unset: the backends then derive from the new
    # process cwd (local exports it at cli import, docker mounts it, ssh and
    # container backends keep their own remote/sandbox default).
    if os.environ.get("TERMINAL_CWD", "").strip():
        os.environ["TERMINAL_CWD"] = _target_dir
    args.no_restore_cwd = True


def import_foreign_resume(args) -> None:
    """--resume @claude / @codex: import a foreign session and resume it."""
    _resume_foreign = getattr(args, "resume", None)
    if not (isinstance(_resume_foreign, str) and _resume_foreign.strip().lower() in ("@claude", "@codex")):
        return
    from hermes_cli.foreign_sessions import import_foreign_session, pick_foreign_session

    _picked = pick_foreign_session(_resume_foreign.strip().lower().lstrip("@"))
    if _picked is None:
        sys.exit(1)
    try:
        _imported_id = import_foreign_session(_picked.source, _picked.path)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    print(f"✓ Imported as {_imported_id} — resuming it now.")
    print(f"  (later: hermes --resume {_imported_id})")
    args.resume = _imported_id


def recreate_resumed_tui_worktree(args) -> None:
    """A resumed session whose frozen cwd is a ``-w`` / ``--tui -w`` tree that quit removed gets that
    tree back before attaching, or the owner refuses every turn ``workspace_unavailable`` (N8)."""
    if not getattr(args, "resume", None) or getattr(args, "worktree", False):
        return
    from hermes_cli.session_worktree import restore
    tree = restore(args.resume)
    if tree:
        print(f"↪ recreated the session's worktree: {tree}")
