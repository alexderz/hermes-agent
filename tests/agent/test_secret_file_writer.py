"""The secret file writer: checked before the card, create-only, never through a symlink, 0600 or 0640.

``plan_secret_file`` refuses what cannot be saved before the user types anything; ``write_secret_file``
writes as this process's user and never overwrites, even when something appears at the path or a
link is swapped in while the card is open.
"""
from __future__ import annotations

import grp
import os
import pwd
import stat

import pytest

from agent.redact import redact_sensitive_text
from agent.secret_file_writer import SecretFileError, plan_secret_file, secret_file_answer, write_secret_file

pytestmark = pytest.mark.platforms("posix")

DUMMY = "dummy-" + "file-secret-3b9d0c41"  # built by concatenation: a fake value
ME = pwd.getpwuid(os.geteuid()).pw_name
PRIMARY = grp.getgrgid(os.getegid()).gr_name


@pytest.fixture
def folder(tmp_path):
    """An empty folder of its own (the test home lives beside it in ``tmp_path``)."""
    path = tmp_path / "secrets"
    path.mkdir()
    return path


def _leftovers(folder):
    return sorted(n for n in os.listdir(folder) if n.endswith(".tmp"))


def test_private_file_is_owner_only_and_holds_the_value_without_the_pasted_newline(folder):
    dest = plan_secret_file({"name": "XYZ API key", "path": str(folder / "xyz-key")}, base_dir=None)
    assert dest == {"kind": "file", "path": str(folder / "xyz-key"), "mode": "0600", "owner": ME,
                    "group": PRIMARY, "name": "XYZ API key"}

    saved = write_secret_file(dest, DUMMY + "\r\n")

    target = folder / "xyz-key"
    assert target.read_bytes() == DUMMY.encode()
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert saved == {"status": "saved", "path": str(target), "mode": "0600", "owner": ME, "group": PRIMARY,
                     "bytes": len(DUMMY.encode())}
    assert _leftovers(folder) == []
    assert DUMMY not in redact_sensitive_text(f"cat said {DUMMY}")  # registered for exact-value redaction


def test_standard_access_is_group_readable_never_world_readable(folder):
    dest = plan_secret_file({"name": "token", "path": str(folder / "t"), "access": "standard"}, base_dir=None)
    saved = write_secret_file(dest, "ünïcode-" + DUMMY)
    assert stat.S_IMODE((folder / "t").stat().st_mode) == 0o640
    assert (saved["mode"], saved["bytes"]) == ("0640", len(("ünïcode-" + DUMMY).encode("utf-8")))


def test_a_relative_or_missing_path_resolves_in_the_session_folder(folder):
    assert plan_secret_file({"name": "XYZ API key!"}, base_dir=str(folder))["path"] == str(folder / "xyz-api-key")
    (folder / "sub").mkdir()
    assert plan_secret_file({"name": "k", "path": "sub/../sub/key"}, base_dir=str(folder))["path"] == \
        str(folder / "sub" / "key")
    with pytest.raises(SecretFileError, match="give an absolute path"):
        plan_secret_file({"name": "k", "path": "key"}, base_dir=None)


@pytest.mark.parametrize("make, expected", [
    (lambda d: (d / "key").write_text("old", encoding="utf-8"), "already exists and is never overwritten"),
    (lambda d: (d / "key").symlink_to(d / "elsewhere"), "is a symbolic link"),
    (lambda d: None, "does not exist"),
])
def test_refused_before_the_card(folder, make, expected):
    make(folder)
    path = folder / ("missing/key" if expected == "does not exist" else "key")
    with pytest.raises(SecretFileError, match=expected):
        plan_secret_file({"name": "k", "path": str(path)}, base_dir=None)


def test_a_symlinked_folder_on_the_path_is_refused_and_named(folder):
    (folder / "real").mkdir()
    (folder / "link").symlink_to(folder / "real")
    with pytest.raises(SecretFileError, match=r"link is a symbolic link .*real"):
        plan_secret_file({"name": "k", "path": str(folder / "link" / "key")}, base_dir=None)


def test_a_group_this_user_is_not_in_is_refused_with_the_users_groups(folder):
    mine = {grp.getgrgid(g).gr_name for g in {os.getegid(), *os.getgroups()}}
    other = next((g.gr_name for g in grp.getgrall() if g.gr_name not in mine), None)
    if other is None:
        pytest.skip("this user is in every group on the host")
    with pytest.raises(SecretFileError) as err:
        plan_secret_file({"name": "k", "path": str(folder / "k"), "group": other}, base_dir=None)
    assert f"user {ME}" in str(err.value) and PRIMARY in str(err.value)


@pytest.mark.skipif(os.geteuid() == 0, reason="root writes anywhere")
def test_an_unwritable_folder_is_refused_with_the_users_identity(folder):
    locked = folder / "locked"
    locked.mkdir(mode=0o500)
    try:
        with pytest.raises(SecretFileError, match=f"not writable .*user {ME}"):
            plan_secret_file({"name": "k", "path": str(locked / "k")}, base_dir=None)
    finally:
        locked.chmod(0o700)


def test_a_file_that_appears_while_the_card_is_open_is_not_overwritten(folder):
    dest = plan_secret_file({"name": "k", "path": str(folder / "key")}, base_dir=None)
    (folder / "key").write_text("theirs", encoding="utf-8")

    answer = secret_file_answer(dest, DUMMY)

    assert answer["success"] is False and "not overwritten" in answer["error"]
    assert (folder / "key").read_text(encoding="utf-8") == "theirs"
    assert _leftovers(folder) == []


def test_a_symlink_swapped_in_while_the_card_is_open_is_not_followed(folder):
    (folder / "dir").mkdir()
    (folder / "attacker").mkdir()
    dest = plan_secret_file({"name": "k", "path": str(folder / "dir" / "key")}, base_dir=None)
    (folder / "dir").rename(folder / "moved")
    (folder / "dir").symlink_to(folder / "attacker")

    with pytest.raises(SecretFileError, match="symbolic link"):
        write_secret_file(dest, DUMMY)
    assert os.listdir(folder / "attacker") == []


def test_a_failed_write_leaves_no_temp_file(folder, monkeypatch):
    dest = plan_secret_file({"name": "k", "path": str(folder / "key")}, base_dir=None)

    def full_disk(fd, data):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(os, "write", full_disk)

    with pytest.raises(SecretFileError, match="No space left"):
        write_secret_file(dest, DUMMY)
    assert os.listdir(folder) == []


def test_an_empty_answer_is_a_skip_and_writes_nothing(folder):
    dest = plan_secret_file({"name": "k", "path": str(folder / "key")}, base_dir=None)
    assert secret_file_answer(dest, "\r\n")["skipped"] is True
    assert os.listdir(folder) == []


@pytest.mark.parametrize("access, mode", [("private", 0o600), ("standard", 0o640)])
def test_a_folders_default_acl_never_widens_the_file_past_its_mode(folder, access, mode):
    import subprocess
    try:
        set_default = subprocess.run(["setfacl", "-d", "-m", "u:nobody:rw", str(folder)],
                                     capture_output=True, check=False)
    except FileNotFoundError:
        pytest.skip("setfacl is not installed")
    if set_default.returncode != 0:
        pytest.skip(f"this filesystem has no POSIX ACLs: {set_default.stderr.decode(errors='replace')}")
    assert "system.posix_acl_default" in os.listxattr(folder)

    dest = plan_secret_file({"name": "k", "path": str(folder / "key"), "access": access}, base_dir=None)
    write_secret_file(dest, DUMMY)

    assert "system.posix_acl_access" not in os.listxattr(folder / "key")  # no named user or group entries
    assert stat.S_IMODE((folder / "key").stat().st_mode) == mode
