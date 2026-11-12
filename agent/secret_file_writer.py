"""Save a masked-card secret to a file (``clarify(secret_file=...)``), as the gateway's own user.

Two halves. ``plan_secret_file`` runs before the card is shown: it resolves the path and refuses,
with a reason naming this process's user and groups, any request the write could not fulfil, so the
user never types a value into a card that cannot be saved. ``write_secret_file`` runs in the surface's
secret callback with the typed value: it walks to the folder one component at a time without
following a symlink, creates an owner-only anonymous file there (``O_TMPFILE``; a named temp file
where the filesystem has none), sets its group and mode and drops any inherited access ACL on the
descriptor, writes and syncs it, then hard-links it to the target name, which fails if anything
appeared there meanwhile (never an overwrite, even in a race), and checks the name is that very
file. The value is then registered for exact-value redaction and the caller drops it.

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


_HIDDEN_CATEGORIES = frozenset({"Cc", "Cf", "Zl", "Zp"})  # controls (NUL too), bidi/zero-width, line breaks


def _refuse_hidden_characters(spec: dict) -> None:
    """A path, name or group the card would draw differently from what is written: refused."""
    import unicodedata
    for field in ("path", "name", "group"):
        text = str(spec.get(field) or "")
        hidden = next((ch for ch in text if unicodedata.category(ch) in _HIDDEN_CATEGORIES), None)
        if hidden is not None:
            raise SecretFileError(f"secret_file.{field} contains a control or invisible character "
                                  f"(U+{ord(hidden):04X}); use plain visible text.")


def plan_secret_file(spec, *, base_dir: str | None) -> dict:
    """Validate a ``secret_file`` request; the destination the card shows and the writer gets."""
    from hermes_platform.host import facts
    if facts.os_family() == "windows":
        raise SecretFileError("secret_file is not available on a Windows host.")
    if not isinstance(spec, dict):
        raise SecretFileError("secret_file must be an object with at least a name.")
    _refuse_hidden_characters(spec)
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


def _create(dfd: int, leaf: str) -> tuple[int, str | None]:
    """A new owner-only file in the folder: ``(fd, None)`` for an anonymous ``O_TMPFILE`` (Linux; nothing
    in the folder carries the value until it is linked to its name), else ``(fd, temp name)``."""
    import errno
    tmpfile = getattr(os, "O_TMPFILE", 0)
    if tmpfile:
        try:
            return os.open(".", tmpfile | os.O_WRONLY | os.O_CLOEXEC, 0o600, dir_fd=dfd), None
        except OSError as exc:
            if exc.errno not in (errno.EOPNOTSUPP, errno.EISDIR, errno.EINVAL):  # no O_TMPFILE here
                raise
    tmp = f".{leaf}.{_secrets.token_hex(6)}.tmp"
    return os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600,
                   dir_fd=dfd), tmp


def _fill(fd: int, data: bytes, gid: int, mode: int) -> os.stat_result:
    """Group, mode and ACL set on the descriptor before any byte, then *data*, synced."""
    os.fchown(fd, -1, gid)  # also for private: in a setgid folder the card's group stays the file's group
    os.fchmod(fd, mode)
    _drop_access_acl(fd)
    view = memoryview(data)
    while view:
        view = view[os.write(fd, view):]
    os.fsync(fd)
    return os.fstat(fd)


def _link(fd: int, tmp: str | None, leaf: str, dfd: int) -> None:
    """Give the written file its name; ``EEXIST`` if anything is there (never replaces)."""
    if tmp is None:
        os.link(f"/proc/self/fd/{fd}", leaf, dst_dir_fd=dfd, follow_symlinks=True)
    else:
        os.link(tmp, leaf, src_dir_fd=dfd, dst_dir_fd=dfd, follow_symlinks=False)


def _check_linked(dfd: int, leaf: str, written: os.stat_result, path: str) -> None:
    """The name must now be the file this call wrote: in a folder others can write, a temp name could be
    swapped for their file before the link, or the name replaced right after it."""
    try:
        st = os.stat(leaf, dir_fd=dfd, follow_symlinks=False)
    except OSError:
        st = None
    if st is None or (st.st_dev, st.st_ino) != (written.st_dev, written.st_ino):
        raise SecretFileError(f"The file now at {path} is not the one Hermes wrote: something in that folder "
                              f"replaced it while saving. Do not use it; check the folder, delete it and ask "
                              f"again.")


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
    try:
        data = value.rstrip("\r\n").encode("utf-8")
    except UnicodeEncodeError:  # a lone surrogate a JSON frame can carry; the error object holds the value
        data = None
    if data is None:  # raised outside the handler: no exception context keeps the value alive
        raise SecretFileError("The value is not valid text (it contains an unpaired surrogate); nothing was "
                              "written. Ask the user to paste it again.")
    parent, leaf = os.path.split(path)
    try:
        dfd, syncable = _open_parent(parent)
    except OSError as exc:
        raise _fail(exc, f"opening the folder {parent}") from None
    try:
        try:
            fd, tmp = _create(dfd, leaf)
        except OSError as exc:
            raise _fail(exc, f"creating a file in {parent}") from None
        try:
            try:
                st = _fill(fd, data, gid, mode)
            except OSError as exc:
                raise _fail(exc, f"writing a file in {parent}") from None
            try:
                _link(fd, tmp, leaf, dfd)
            except OSError as exc:
                raise _fail(exc, f"naming the file {path}") from None
            _check_linked(dfd, leaf, st, path)
        finally:
            os.close(fd)
            if tmp is not None:
                _remove_quietly(tmp, dfd)
        warning = _sync_folder(dfd) if syncable else None
    finally:
        os.close(dfd)
    from agent.redact import register_vault_redaction_value
    register_vault_redaction_value(data.decode("utf-8"))
    saved = {"status": "saved", "path": path, "mode": f"{stat.S_IMODE(st.st_mode):04o}", "owner": _user(),
             "group": _group_name(st.st_gid), "bytes": len(data)}
    return {**saved, "warning": warning} if warning else saved


def _sync_folder(dfd: int) -> str | None:
    """fsync the folder so the new name survives a power loss; the file is already saved either way, so a
    failure is a warning, never an error (a retry would only hit "already exists")."""
    try:
        os.fsync(dfd)
    except OSError as exc:
        return f"The file is saved, but syncing its folder failed ({exc.strerror}); it may not survive a power loss."
    return None


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
