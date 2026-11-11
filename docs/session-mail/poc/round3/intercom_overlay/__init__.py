"""DER-701 Trial round 3 (FROZEN RECORD, NEVER PRODUCT CODE): replaces intercom's register() in a
throwaway copy so r3_trial.py drives intercom's unedited inbox module inside each Hermes process."""
from __future__ import annotations

from . import inbox
from . import r3_trial


def register(ctx) -> None:
    r3_trial.install(ctx, inbox)
