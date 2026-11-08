"""model-routing: limit-aware routing across Alex's subscriptions (step 1: usage readers and status).

Registers ``/routing`` (in-session status) and ``hermes model-routing collect|status`` (the collector
run by a systemd user timer every 15 minutes). Advisory only in this version: nothing changes which
model a session uses.
"""
from __future__ import annotations

import json


def _status_command(raw_args: str = "") -> str:
    from . import core
    return core.render_text(core.load_state())


def _setup_cli(parser) -> None:
    sub = parser.add_subparsers(dest="routing_cmd")
    sub.add_parser("collect", help="Read every subscription's usage once and update the routing state")
    st = sub.add_parser("status", help="Show the current usage cards and would-be pick")
    st.add_argument("--json", action="store_true", help="Print the raw state document")


def _run_cli(args) -> int:
    from . import core
    cmd = getattr(args, "routing_cmd", None) or "status"
    if cmd == "collect":
        state = core.collect()
        print(core.render_text(state))
        return 0
    state = core.load_state()
    print(json.dumps(state, indent=1) if getattr(args, "json", False) else core.render_text(state))
    return 0


def register(ctx) -> None:
    ctx.register_command("routing", _status_command,
                         description="Subscription usage, pace and the routing pick")
    ctx.register_cli_command("model-routing", "Limit-aware model routing: usage collector and status",
                             _setup_cli, _run_cli)
