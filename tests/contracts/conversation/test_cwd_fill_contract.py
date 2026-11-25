"""Contract cases for ``SessionRepository.fill_cwd_if_missing`` (the ``persistence/conversation/sessions.py``
docstring).

Every case runs both registered backends, seeds through public protocol operations only and observes
through ``sessions.get``.
"""

from __future__ import annotations

from persistence import SessionId
from persistence.conversation.sessions import NewSession


def _seed(backend, scope, sid: str, *, cwd=None, git_repo_root=None) -> None:
    store = backend.open(scope)
    store.sessions.create(NewSession(session_id=SessionId(sid), source="cli", cwd=cwd,
                                     git_repo_root=git_repo_root))


def _row(backend, scope, sid: str):
    return backend.open(scope).sessions.get(SessionId(sid))


def test_fill_records_a_cwd_only_where_the_row_has_none(backend, scope_a):
    store = backend.open(scope_a)
    _seed(backend, scope_a, "missing", cwd=None)
    _seed(backend, scope_a, "blank", cwd="")
    _seed(backend, scope_a, "set", cwd="/own")

    assert store.sessions.fill_cwd_if_missing(SessionId("missing"), "/work") is True
    assert store.sessions.fill_cwd_if_missing(SessionId("blank"), "/work") is True
    assert store.sessions.fill_cwd_if_missing(SessionId("set"), "/work") is False
    assert (_row(backend, scope_a, "missing").cwd, _row(backend, scope_a, "blank").cwd,
            _row(backend, scope_a, "set").cwd) == ("/work", "/work", "/own")
    # Idempotent: a recorded cwd is never rewritten.
    assert store.sessions.fill_cwd_if_missing(SessionId("missing"), "/elsewhere") is False
    assert _row(backend, scope_a, "missing").cwd == "/work"


def test_fill_leaves_git_fields_to_their_probe_but_claims_a_generation(backend, scope_a):
    store = backend.open(scope_a)
    _seed(backend, scope_a, "repo", cwd="", git_repo_root="/repo")

    assert store.sessions.fill_cwd_if_missing(SessionId("repo"), "/work") is True

    row = _row(backend, scope_a, "repo")
    assert row.cwd == "/work" and row.git_repo_root == "/repo"
    assert row.git_metadata_generation >= 1


def test_fill_answers_false_for_a_missing_row_or_empty_input(backend, scope_a):
    store = backend.open(scope_a)
    _seed(backend, scope_a, "row")

    assert store.sessions.fill_cwd_if_missing(SessionId("absent"), "/work") is False
    assert store.sessions.fill_cwd_if_missing(SessionId("row"), "") is False
    assert store.sessions.fill_cwd_if_missing(SessionId(""), "/work") is False
    assert _row(backend, scope_a, "row").cwd in (None, "")


def test_fill_is_scope_isolated(backend, scope_a, scope_b):
    store_a, store_b = backend.open(scope_a), backend.open(scope_b)
    _seed(backend, scope_a, "iso")
    _seed(backend, scope_b, "iso")

    assert store_a.sessions.fill_cwd_if_missing(SessionId("iso"), "/work/a") is True

    assert _row(backend, scope_a, "iso").cwd == "/work/a"
    assert _row(backend, scope_b, "iso").cwd in (None, "")
    assert store_b.sessions.fill_cwd_if_missing(SessionId("iso"), "/work/b") is True
    assert _row(backend, scope_b, "iso").cwd == "/work/b"
