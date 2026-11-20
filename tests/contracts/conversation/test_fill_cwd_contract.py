"""The resumed-CLI cwd stamp is an atomic fill, not a workspace move."""
from persistence import SessionId
from persistence.conversation.sessions import NewSession


def test_fill_cwd_preserves_git_identity_and_only_the_first_fill_wins(backend, scope_a):
    store = backend.open(scope_a)
    sid = SessionId("cli-cwd-fill")
    store.sessions.create(NewSession(session_id=sid, source="cli", git_repo_root="/repo"))
    before = store.sessions.get(sid)
    assert store.sessions.fill_cwd_if_missing(sid, "/first") is True
    first = store.sessions.get(sid)
    assert (first.cwd, first.git_repo_root, first.git_branch) == ("/first", "/repo", before.git_branch)
    assert first.git_metadata_generation == before.git_metadata_generation + 1
    assert store.sessions.fill_cwd_if_missing(sid, "/second") is False
    assert store.sessions.get(sid) == first
    assert store.sessions.publish_git_metadata(
        sid, "/first", before.git_metadata_generation, git_branch="stale") is False


def test_fill_cwd_does_not_create_a_row_or_accept_an_empty_value(backend, scope_a):
    store = backend.open(scope_a)
    missing = SessionId("missing-cwd-fill")
    assert store.sessions.fill_cwd_if_missing(missing, "/work") is False
    assert store.sessions.get(missing) is None
    sid = SessionId("empty-cwd-fill")
    store.sessions.create(NewSession(session_id=sid, source="cli", cwd=""))
    assert store.sessions.fill_cwd_if_missing(sid, "") is False
    assert store.sessions.fill_cwd_if_missing(SessionId(""), "/work") is False
    assert store.sessions.fill_cwd_if_missing(sid, "/work") is True
