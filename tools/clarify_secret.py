"""Masked secret questions for the clarify tool (``clarify(secret_env=NAME)`` / ``secret_file={...}``).

The user types the value into the surface's masked secret prompt (the same one skill setup uses:
CLI panel, TUI/Desktop ``secret`` overlay, a local viewer's gateway turn). The surface stores it in
this profile's ``.env``; this module only ever sees the callback's metadata, so the value never
reaches the tool result, the transcript or the model. On success the name joins the terminal /
execute_code passthrough allowlist, so commands use it as ``$NAME``.

``secret_file`` saves the value to a file instead (``agent/secret_file_writer.py``): the request is
checked before the card is shown, the card shows the path, mode and owner, and the result carries
only those facts and the byte count. The name never joins the passthrough list. Only a surface that
draws the destination itself, apart from the model's text (the Webapp and desktop app's secret
dialog), opts in; the CLI and TUI only show prompt text the model writes, so they refuse.
"""

import json
import re
import unicodedata

from hermes_constants import display_hermes_home
from tools.registry import tool_error
from tools.skills_tool_setup import _ENV_VAR_NAME_RE, resolve_secret_capture_callback


def _refusal(name: str) -> str:
    return tool_error(
        f"Masked secret entry is not available on this surface, so {name} cannot be collected here. "
        f"Tell the user to set it from a local Hermes CLI, TUI or Desktop session, or to add it to "
        f"{display_hermes_home()}/.env themselves. Never ask them to paste it into chat.")


def _one_question(questions) -> str | None:
    if not (isinstance(questions, list) and len(questions) == 1 and isinstance(questions[0], dict)):
        return None
    return str(questions[0].get("question") or "").strip()


def _question_error(question, field: str) -> str:
    if question is None:
        return tool_error(f"{field} takes exactly one question saying what the secret is for.")
    return tool_error("questions[0].question must say what the secret is for and where it is used.")


def _prompt_callback(interactive: bool):
    from gateway.session_context import session_is_messaging_surface
    # A chat channel never gets a prompt, even in a process that also serves a TUI/Desktop viewer.
    return resolve_secret_capture_callback() if interactive and not session_is_messaging_surface() else None


def _not_entered(question: str, label: str, reason: str, key: str) -> str:
    return json.dumps({"responses": [{"question": question, "status": "skipped", key: None}],
                       "outcome": "timed_out" if reason == "timeout" else "cancelled",
                       "notice": f"The user did not enter {label}. Do not ask for it in chat."})


def ask_secret(questions, name: str, interactive: bool) -> str:
    """Collect secret ``name`` through the masked prompt; the result names it, never carries it."""
    question = _one_question(questions)
    if not question:
        return _question_error(question, "secret_env")
    if not _ENV_VAR_NAME_RE.match(name):
        return tool_error(f"secret_env must be an environment variable name, got {name!r}.")
    callback = _prompt_callback(interactive)
    if callback is None:
        return _refusal(name)
    try:
        stored = callback(name, question, {"source": "agent"})
    except ValueError as exc:  # a locked/denylisted key: the save refused it before writing
        return tool_error(f"{name} was not stored: {exc}")
    if not (isinstance(stored, dict) and stored.get("success") and not stored.get("skipped")):
        reason = str((stored or {}).get("reason") or "cancelled") if isinstance(stored, dict) else "cancelled"
        return _not_entered(question, name, reason, "stored_as")
    from tools.env_passthrough import is_env_passthrough, register_env_passthrough
    register_env_passthrough([name])
    usable = is_env_passthrough(name)
    notice = (f"Stored in this profile's secrets as {name}; you never see the value. Use it only as "
              f"${name} inside terminal commands or os.environ[{name!r}] in execute_code, and never print "
              f"it. An execute_code kernel already running in this session keeps its old environment: "
              f"pass reset=true on the next execute_code call (this clears its Python state) to see it."
              if usable else
              f"Stored in this profile's secrets as {name}; you never see the value. It is a Hermes "
              f"provider credential, so Hermes uses it directly and it is not passed to commands.")
    return json.dumps({"responses": [{"question": question, "status": "answered", "stored_as": name}],
                       "outcome": "submitted", "notice": notice})


# CSI / OSC / other ESC sequences; C1 controls are category Cc and go with the rest below.
_ANSI_ESCAPE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\)|[@-_])")


def _plain(text: str) -> str:
    """*text* without terminal escapes, control or format characters (bidi overrides, zero-width; newlines
    kept): what the model writes must not hide, reorder or restyle the destination the card shows."""
    text = _ANSI_ESCAPE.sub("", text)
    return "".join(ch for ch in text if ch == "\n" or unicodedata.category(ch) not in ("Cc", "Cf"))


def _session_base_dir(task_id) -> str | None:
    """The session's working directory on this host, in the terminal tool's order
    (``tools/terminal_tool.py`` ``_get_or_create_env``: a registered cwd override, then the session's
    recorded cwd, then the configured ``TERMINAL_CWD``), or None, so a relative path is refused. Never
    this process's own cwd: one gateway serves many sessions and profiles, so its launch folder is
    nobody's workspace. A sandboxed or remote terminal's cwd is not a host folder, so only absolute
    paths work there."""
    from tools.file_tools_paths import _configured_terminal_cwd, _sentinel_free_abs_cwd, _terminal_env_type_for_task
    from tools.terminal_tool import get_session_cwd, resolve_task_overrides
    key = task_id or "default"
    if _terminal_env_type_for_task(key) != "local":
        return None
    session_cwd = resolve_task_overrides(key).get("cwd") or get_session_cwd(key)
    return _sentinel_free_abs_cwd(session_cwd) if session_cwd else _configured_terminal_cwd()


def ask_secret_file(questions, spec, interactive: bool, task_id=None) -> str:
    """Collect a secret through the masked prompt and save it to a file; the result names the file."""
    from agent.secret_file_writer import SecretFileError, plan_secret_file

    question = _one_question(questions)
    if not question:
        return _question_error(question, "secret_file")
    if isinstance(spec, str):  # some models send an object argument as its JSON text
        try:
            spec = json.loads(spec)
        except ValueError:
            return tool_error("secret_file must be an object: {name, path?, access?, group?}.")
    callback = _prompt_callback(interactive)
    label = str(spec.get("name") or "the secret") if isinstance(spec, dict) else "the secret"
    # Only a callback whose card draws the destination itself may prompt; any other would show only the
    # model's text (or save the value to .env).
    if not getattr(callback, "accepts_secret_file", False):
        return tool_error(
            f"Saving a secret to a file needs the Hermes Webapp or desktop app, which show where the file goes "
            f"before the user types, so {label} cannot be saved from this session. Ask the user to continue "
            f"there. Never ask them to paste it into chat.")
    try:
        dest = plan_secret_file(spec, base_dir=_session_base_dir(task_id))
    except SecretFileError as exc:
        return tool_error(f"{label} cannot be saved: {exc}")
    facts = f"{dest['path']} ({dest['mode']}, {dest['owner']}:{dest['group']})"
    destination = {k: dest[k] for k in ("kind", "path", "mode", "owner", "group")}
    # The facts first, so a client that ignores metadata never shows the model's text ahead of them.
    stored = callback(_plain(dest["name"]), f"Will be saved to {facts}\n\n{_plain(question)}",
                      {"source": "agent", "destination": destination})
    stored = stored if isinstance(stored, dict) else {}
    if stored.get("error"):
        return tool_error(f"{label} was not saved: {stored['error']}")
    saved = stored.get("secret_file")
    if not (stored.get("success") and not stored.get("skipped") and isinstance(saved, dict)):
        return _not_entered(question, label, str(stored.get("reason") or "cancelled"), "saved_to")
    return json.dumps({
        "responses": [{"question": question, "status": "answered", "saved_to": saved["path"]}],
        "outcome": "submitted", "secret_file": saved,
        "notice": f"Saved to {saved['path']}; you never see the value. Refer to it by this path in commands "
                  f"and config; never print, cat or echo it."})
