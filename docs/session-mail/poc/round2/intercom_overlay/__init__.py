"""DER-701 Trial round 2 (FROZEN RECORD, NEVER PRODUCT CODE): replaces intercom's register() in a
throwaway copy so the trial stand-ins in r2_trial.py drive intercom's unedited inbox module."""
from __future__ import annotations

from . import inbox
from . import r2_trial


def register(ctx) -> None:
    r2_trial.install(ctx, inbox)
