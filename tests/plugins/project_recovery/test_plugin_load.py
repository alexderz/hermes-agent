"""Plugin discovery entry registers nothing and import does no package I/O."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from hermes_yaml import safe_load

_REPO = Path(__file__).resolve().parents[3]

_PROBE = r"""
import json
import os
import sys
import threading
import traceback

hits = {"env": [], "open": [], "threads": 0}

def _direct_package_caller(stack):
    for frame in reversed(stack):
        name = frame.filename.replace("\\", "/")
        if name == "<string>" or name.endswith("/traceback.py"):
            continue
        return "plugins/project_recovery" in name
    return False

real_get = os.environ.get

def env_get(key, default=None):
    stack = traceback.extract_stack()
    if _direct_package_caller(stack):
        hits["env"].append(str(key))
    return real_get(key, default)

os.environ.get = env_get
real_getenv = os.getenv

def getenv(key, default=None):
    stack = traceback.extract_stack()
    if _direct_package_caller(stack):
        hits["env"].append(str(key))
    return real_getenv(key, default)

os.getenv = getenv

def audit(event, args):
    if event != "open":
        return
    path = str(args[0]) if args else ""
    if path.endswith((".py", ".pyc", ".so")) or "__pycache__" in path:
        return
    stack = traceback.extract_stack()
    if any("plugins/project_recovery" in frame.filename.replace("\\", "/") for frame in stack):
        hits["open"].append(path)

sys.addaudithook(audit)
before = threading.active_count()
import plugins.project_recovery
hits["threads"] = threading.active_count() - before
print(json.dumps(hits))
"""


def test_register_adds_no_hook_or_tool():
    from plugins.project_recovery import register

    calls = []

    class Ctx:
        def register_tool(self, *args, **kwargs):
            calls.append(("tool", args, kwargs))

        def register_hook(self, *args, **kwargs):
            calls.append(("hook", args, kwargs))

        def register_cli_command(self, *args, **kwargs):
            calls.append(("cli", args, kwargs))

    register(Ctx())
    assert calls == []


def test_import_does_no_package_io_thread_or_env_read():
    env = {
        "PATH": os_path(),
        "HOME": str(Path.home()),
        "LANG": "C.UTF-8",
        "PYTHONPATH": str(_REPO),
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    completed = subprocess.run(
        [sys.executable, "-c", _PROBE],
        cwd=_REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    hits = json.loads(completed.stdout.strip().splitlines()[-1])
    assert hits["env"] == []
    assert hits["open"] == []
    assert hits["threads"] == 0


def os_path() -> str:
    import os

    return os.environ.get("PATH", "")


def test_manifest_declares_no_tools_or_hooks():
    manifest = safe_load(
        (_REPO / "plugins" / "project_recovery" / "plugin.yaml").read_text(encoding="utf-8")
    )

    assert manifest["name"] == "project_recovery"
    assert not manifest.get("provides_tools")
    assert not manifest.get("provides_hooks")


def test_facade_exports_only_the_membership_api():
    import plugins.project_recovery as recovery

    assert set(recovery.__all__) == {
        "AuthorityClass",
        "Err",
        "Invalid",
        "LivenessObservation",
        "NextDone",
        "NextHandle",
        "NextStopped",
        "NextWait",
        "Ok",
        "TrackerMapping",
        "classify_authority_path",
        "classify_evidence_paths",
        "classify_liveness",
        "finishes_closing_step",
        "is_canonical_state",
        "key_matches",
        "label_identity",
        "load_binding",
        "load_handle",
        "load_mapping",
        "matches_local_assignee",
        "matches_local_id",
        "matches_local_label",
        "member_identity",
        "observe_invocation",
        "observe_liveness",
        "register",
        "register_before_start",
        "register_handle",
        "unit_directives",
        "validate_binding",
        "validate_handle",
    }
