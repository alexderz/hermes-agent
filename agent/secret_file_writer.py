"""Save a masked-card secret to a file (``clarify(secret_file=...)``), as the gateway's own user.

Two halves. ``plan_secret_file`` runs before the card is shown: it resolves the path and refuses,
with a reason naming this process's user and groups, any request the write could not fulfil, so the
user never types a value into a card that cannot be saved. ``write_secret_file`` runs in the surface's
secret callback with the typed value: it walks to the folder one component at a time without
following a symlink, creates an owner-only temp file there, sets its group and mode on the
descriptor, writes and syncs it, then hard-links it to the target name, which fails if anything
appeared there meanwhile (never an overwrite, even in a race). The value is then registered for
exact-value redaction and the caller drops it.

A surface's secret callback opts in by setting ``accepts_secret_file = True`` on itself and calling
``secret_file_answer`` when ``destination_of(metadata)`` is a file; the tool refuses before the card
on any other callback, so a value meant for a file never falls back to ``.env``.

Only two results exist: ``private`` = 0600 and ``standard`` = 0640. The owner is always this
process's user: no sudo, no ownership change.
"""
from __future__ import annotations

import os
import re
import secrets as _secrets
import stat

FILE_KIND = "file"
ACCESS_MODES = {"private": 0o600, "standard": 0o640}
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


class SecretFileError(Exception):
    """A secret file request that cannot be fulfilled; the message is safe to show the model."""


def _euid() -> int:
    return os.geteuid()  # windows-footgun: ok - POSIX-only writer; plan_secret_file refuses on Windows first


def _egid() -> int:
    return os.getegid()  # windows-footgun: ok - POSIX-only writer; plan_secret_file refuses on Windows first


def _user() -> str:
    import pwd
    try:
        return pwd.getpwuid(_euid()).pw_name
    except KeyError:
        return str(_euid())


def _group_name(gid: int) -> str:
    import grp
    try:
        return grp.getgrgid(gid).gr_name
    except KeyError:
        return str(gid)


def _my_groups() -> dict[str, int]:
    gids = [_egid(), *os.getgroups()]
    return {_group_name(gid): gid for gid in dict.fromkeys(gids)}


def _identity() -> str:
    return f"the gateway runs as user {_user()} (groups: {', '.join(_my_groups())})"


def destination_of(metadata) -> dict | None:
    """The file destination a secret request carries, or None for a ``.env`` request."""
    dest = (metadata or {}).get("destination") if isinstance(metadata, dict) else None
    return dest if isinstance(dest, dict) and dest.get("kind") == FILE_KIND else None


def _file_name(name: str) -> str:
    stem = _SAFE_NAME.sub("-", name.strip().lower()).strip(".-")
    if not stem:
        raise SecretFileError("secret_file.name must contain letters or digits to make a file name from.")
    return stem


def _check_components(path: str) -> None:
    """Refuse a symlink anywhere on *path* and an existing target; the folder must be usable."""
    parts = path.strip("/").split("/")
    current = "/"
    for i, part in enumerate(parts):
        current = os.path.join(current, part)
        try:
            st = os.lstat(current)
        except FileNotFoundError:
            if i < len(parts) - 1:
                raise SecretFileError(f"The folder {os.path.dirname(path)} does not exist ({current} is missing). "
                                      f"Create it first; the secret is never written to a missing folder.") from None
            return
        except OSError as exc:
            raise SecretFileError(f"Cannot inspect {current}: {exc.strerror}; {_identity()}.") from None
        if stat.S_ISLNK(st.st_mode):
            raise SecretFileError(
                f"{current} is a symbolic link (to {os.path.realpath(current)}); secrets are never written "
                f"through a link. Ask again with the real path.")
        if i < len(parts) - 1 and not stat.S_ISDIR(st.st_mode):
            raise SecretFileError(f"{current} is not a folder.")
        if i == len(parts) - 1:
            raise SecretFileError(
                f"{path} already exists and is never overwritten. If replacing it is right, delete it and ask "
                f"again, or ask for a new file (for example {os.path.basename(path)}.v2) and swap it in "
                f"with shell commands.")


def plan_secret_file(spec, *, base_dir: str | None) -> dict:
    """Validate a ``secret_file`` request; the destination the card shows and the writer gets."""
    from hermes_platform.host import facts
    if facts.os_family() == "windows":
        raise SecretFileError("secret_file is not available on a Windows host.")
    if not isinstance(spec, dict):
        raise SecretFileError("secret_file must be an object with at least a name.")
    name = str(spec.get("name") or "").strip()
    if not name:
        raise SecretFileError("secret_file.name must say what the secret is (for example \"XYZ API key\").")
    access = str(spec.get("access") or "private").strip().lower()
    if access not in ACCESS_MODES:
        raise SecretFileError("secret_file.access must be \"private\" (0600) or \"standard\" (0640).")
    raw = os.path.expanduser(str(spec.get("path") or "").strip() or _file_name(name))
    if not os.path.isabs(raw):
        if not base_dir:
            raise SecretFileError(f"{raw} is relative and this session has no working directory on the "
                                  f"gateway host; give an absolute path.")
        raw = os.path.join(base_dir, raw)
    path = os.path.normpath(raw)
    if not os.path.isabs(path) or path == "/" or raw.endswith("/"):
        raise SecretFileError(f"{raw} is not an absolute file path.")
    groups = _my_groups()
    group = str(spec.get("group") or "").strip() or _group_name(_egid())
    if group not in groups:
        raise SecretFileError(f"{group} is not one of this user's groups; {_identity()}.")
    _check_components(path)
    parent = os.path.dirname(path)
    if not os.access(parent, os.W_OK | os.X_OK, effective_ids=os.access in os.supports_effective_ids):
        raise SecretFileError(f"The folder {parent} is not writable by this user; {_identity()}.")
    return {"kind": FILE_KIND, "path": path, "mode": f"{ACCESS_MODES[access]:04o}", "owner": _user(),
            "group": group, "name": name}


# getattr: these flags are POSIX-only, and plan_secret_file refuses on Windows after this import.
_DIR = getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
_O_PATH = getattr(os, "O_PATH", 0)  # Linux: search-only folders on the way; elsewhere O_RDONLY


def _open_parent(parent: str) -> tuple[int, bool]:
    """A descriptor for *parent*, reached from ``/`` one component at a time with no symlink followed.
    Returns ``(fd, syncable)``; a folder this user may search but not read is held by ``O_PATH`` and
    cannot be fsynced."""
    fd = os.open("/", os.O_DIRECTORY | os.O_RDONLY | os.O_CLOEXEC)
    parts = [p for p in parent.split("/") if p]
    syncable = True
    try:
        for i, part in enumerate(parts):
            if i < len(parts) - 1:
                nfd = os.open(part, _DIR | (_O_PATH or os.O_RDONLY), dir_fd=fd)
            else:
                try:
                    nfd = os.open(part, _DIR | os.O_RDONLY, dir_fd=fd)
                except PermissionError:
                    if not _O_PATH:
                        raise
                    nfd, syncable = os.open(part, _DIR | _O_PATH, dir_fd=fd), False
            os.close(fd)
            fd = nfd
        return fd, syncable
    except BaseException:
        os.close(fd)
        raise


def _fail(exc: OSError, what: str) -> SecretFileError:
    import errno
    if exc.errno in (errno.ELOOP, errno.ENOTDIR):
        return SecretFileError(f"A symbolic link or non-folder is on the path ({what}); nothing was written.")
    if exc.errno == errno.EEXIST:
        return SecretFileError("A file appeared at the path while the card was open; it was not overwritten "
                               "and the value was discarded.")
    return SecretFileError(f"Could not save the secret ({what}): {exc.strerror}; {_identity()}.")


def _fill_temp(dfd: int, tmp: str, data: bytes, gid: int, mode: int) -> os.stat_result:
    """Create the temp file *tmp* holding *data*, group and mode set on the descriptor before any byte;
    on any failure after creating it, remove it."""
    fd = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=dfd)
    try:
        os.fchown(fd, -1, gid)  # also for private: in a setgid folder the card's group stays the file's group
        os.fchmod(fd, mode)
        _drop_access_acl(fd)
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
        return os.fstat(fd)
    except BaseException:
        _remove_quietly(tmp, dfd)
        raise
    finally:
        os.close(fd)


def _drop_access_acl(fd: int) -> None:
    """Remove the access ACL a folder's default ACL gave the new file: its named entries could let other
    users read past the mode the card shows. Without it the mode bits are the whole story."""
    import errno
    removexattr = getattr(os, "removexattr", None)  # Linux; elsewhere no POSIX access ACL xattr
    if removexattr is None:
        return
    try:
        removexattr(fd, "system.posix_acl_access")
    except OSError as exc:
        if exc.errno not in (errno.ENODATA, errno.ENOTSUP, errno.EOPNOTSUPP):
            raise


def _remove_quietly(name: str, dfd: int) -> None:
    try:
        os.unlink(name, dir_fd=dfd)
    except FileNotFoundError:
        pass


def write_secret_file(destination: dict, value: str) -> dict:
    """Create ``destination['path']`` holding *value* (trailing CR/LF stripped). Never overwrites, never
    follows a symlink. Returns the stored facts (no value); raises ``SecretFileError``."""
    path = os.path.normpath(str(destination.get("path") or "/"))
    mode = {f"{m:04o}": m for m in ACCESS_MODES.values()}.get(str(destination.get("mode")))
    gid = _my_groups().get(str(destination.get("group") or ""))
    if not os.path.isabs(path) or path == "/" or mode is None or gid is None:
        raise SecretFileError("The secret file request is malformed; nothing was written.")
    data = value.rstrip("\r\n").encode("utf-8")
    parent, leaf = os.path.split(path)
    tmp = f".{leaf}.{_secrets.token_hex(6)}.tmp"
    try:
        dfd, syncable = _open_parent(parent)
    except OSError as exc:
        raise _fail(exc, f"opening the folder {parent}") from None
    try:
        try:
            st = _fill_temp(dfd, tmp, data, gid, mode)
        except OSError as exc:
            raise _fail(exc, f"writing a temporary file in {parent}") from None
        try:
            os.link(tmp, leaf, src_dir_fd=dfd, dst_dir_fd=dfd, follow_symlinks=False)  # EEXIST: never replaces
        except OSError as exc:
            raise _fail(exc, f"naming the file {path}") from None
        finally:
            _remove_quietly(tmp, dfd)
        if syncable:
            os.fsync(dfd)
    finally:
        os.close(dfd)
    from agent.redact import register_vault_redaction_value
    register_vault_redaction_value(data.decode("utf-8"))
    return {"status": "saved", "path": path, "mode": f"{stat.S_IMODE(st.st_mode):04o}", "owner": _user(),
            "group": _group_name(st.st_gid), "bytes": len(data)}


def secret_file_answer(destination: dict, value: str) -> dict:
    """A surface secret callback's result for a file destination: saved, skipped (empty) or failed."""
    if not value.rstrip("\r\n"):
        return {"success": True, "skipped": True, "reason": "cancelled", "message": "Secret entry was skipped."}
    try:
        saved = write_secret_file(destination, value)
    except SecretFileError as exc:
        return {"success": False, "skipped": False, "reason": "write_failed", "error": str(exc)}
    return {"success": True, "skipped": False, "secret_file": saved,
            "message": f"Secret saved to {saved['path']}. The value was not exposed to the model."}
