"""Flagged keyed recovery pins the canonical owner, not the compression tip.

Address resolution returns the open tip. A flagged send learns the platform
canonical id, admits under that id, and can die before the plugin stores
``admission_id``. The next send of the same key must find that admission and
``prompt.receipt`` of the stored target must read it. An unflagged send of the
tip still stores the tip.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from plugins.intercom import address, record, route


class _Ctx:
    def __init__(self):
        self.settings = {"user_name": "Sam"}

    def get_config(self, key, default=None):
        return self.settings.get(key, default)


class CanonicalPinTests(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="intercom-canonical-pin-"))
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        self._old_home = os.environ.get("HERMES_HOME")
        os.environ["HERMES_HOME"] = str(self.home)
        self.addCleanup(self._restore_home)
        (self.home / "config.yaml").write_text(
            "plugins:\n  enabled: [intercom]\n  entries:\n    intercom:\n"
            "      allow_gateway_injection: true\n      settings: {}\n",
            encoding="utf-8",
        )
        self.return_admission = False
        self.submits = []
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, name="canonical-pin", daemon=True)
        self.thread.start()
        self.connection = None
        self.addCleanup(self._stop_loop)
        self.connection = self._run(self._open())
        self.ctx = _Ctx()
        self._patch_owner()

    def _restore_home(self):
        if self._old_home is None:
            os.environ.pop("HERMES_HOME", None)
        else:
            os.environ["HERMES_HOME"] = self._old_home

    def _stop_loop(self):
        connection = getattr(self, "connection", None)
        if connection is not None:
            try:
                self._run(connection.close())
            except Exception:
                pass
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(10)

    def _run(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(60)

    async def _open(self):
        from types import SimpleNamespace

        from gateway.config import GatewayConfig
        from gateway.session import SessionStore
        from gateway.session_authority import initialize_session_authority
        from gateway.session_controls import AuthorityConnection
        from tests.fixtures.storage_seed import seed_session

        store = SessionStore(self.home / "sessions", GatewayConfig())

        async def _answer(_event):
            return "ok"

        runner = SimpleNamespace(
            _session_db=store.persistence, session_store=store, _draining=False,
            _handle_message=_answer, _adapter_for_source=lambda source: None)
        authority = await initialize_session_authority(runner, profile_id="p", instance_id="owner")

        def _hold(ref):
            authority.sessions[ref.session_id].rescan = True

        authority._schedule = _hold
        connection = AuthorityConnection(authority, object(), {"user_id": "owner"})
        subject = connection.actor.subject
        self._seed(seed_session, authority, "local-owner", subject, end_reason="compression")
        self._seed(seed_session, authority, "tip-1", subject, parent="local-owner")
        self._mount(authority, "local-owner", subject)
        self._mount(authority, "tip-1", subject)
        connection.subscriptions["local-owner"] = "sub-owner"
        connection.subscriptions["tip-1"] = "sub-tip"
        self.authority = authority
        return connection

    @staticmethod
    def _seed(seed_session, authority, session_id, subject, *, parent=None, end_reason=None):
        fields = {"chat_id": "local-owner", "user_id": subject}
        if parent is not None:
            fields["parent_session_id"] = parent
        seed_session(authority.persistence, session_id, "local", end_reason=end_reason, **fields)

    @staticmethod
    def _mount(authority, session_id, subject):
        from gateway.config import Platform
        from gateway.session import SessionSource
        from gateway.session_authority import LiveSession

        authority.sessions[session_id] = LiveSession(
            SessionSource(platform=Platform.LOCAL, chat_id=session_id, user_id=subject), session_id)

    def _patch_owner(self):
        async def _lookup(session_id, params):
            from gateway.session_close_aware import answer_lookup

            return answer_lookup(self.connection, session_id, params)

        def lookup(session_id, request_id, payload_digest=None):
            params = {"request_id": request_id}
            if isinstance(payload_digest, str):
                params["payload_digest"] = payload_digest
            try:
                body = self._run(_lookup(session_id, params))
            except Exception:
                return {"outcome": "unavailable"}
            if not isinstance(body, dict):
                return {"outcome": "unavailable"}
            projected = {"outcome": body.get("outcome")}
            for key in ("admission_id", "target_session_id", "payload_digest", "canonical_session_id"):
                value = body.get(key)
                if value is not None:
                    projected[key] = value
            return projected

        def deliver(target, text, delivery, submission_id, unless_closed_by_user=False):
            outcome = self._run(self._submit(target, text, submission_id, bool(unless_closed_by_user)))
            self.submits.append({"target": target, "flag": bool(unless_closed_by_user), "outcome": outcome})
            error = outcome.get("error") if isinstance(outcome, dict) else None
            if isinstance(error, dict):
                return {
                    "ok": False, "error": error.get("message"), "code": error.get("message"),
                    "exit": 4, "message": "refused",
                }
            admission = (outcome.get("result") or {}).get("admission_id") if isinstance(outcome, dict) else None
            if unless_closed_by_user and not self.return_admission:
                return {"ok": False, "error": "delivery-unknown", "code": None, "exit": 5, "message": "lost"}
            return {
                "ok": True, "applied": "queue", "applied_detail": None,
                "admission_id": admission, "instance_id": "inst-1",
            }

        for name, value in (
            ("lookup_admission", lookup),
            ("deliver_sync", deliver),
            ("owner_instance", lambda: "inst-1"),
        ):
            patch = mock.patch.object(route.client, name, value)
            patch.start()
            self.addCleanup(patch.stop)

    async def _submit(self, target, text, submission_id, flag):
        params = {
            "session_id": target, "text": text, "submission_id": submission_id, "queued": True,
        }
        if flag:
            params["unless_closed_by_user"] = True
        return await self.connection.dispatch({"id": 1, "method": "prompt.submit", "params": params})

    async def _receipt(self, admission_id, session_id):
        return await self.connection.dispatch({
            "id": 3, "method": "prompt.receipt",
            "params": {"session_id": session_id, "admission_id": admission_id},
        })

    def _rows(self, session_id):
        return list(self.authority.persistence.admissions.list(session_id=session_id, pending_only=False))

    def _send(self, to, message, *, key, flag=False):
        kwargs = {}
        if flag:
            kwargs["unless_closed_by_user"] = True
        return route.send(
            "status-script", to, message, ctx=self.ctx,
            lister=lambda *_args, **_kwargs: {"ok": True, "sessions": [{"id": "tip-1"}]},
            script=True, delivery="queue", reply_mode="none", key=key, **kwargs,
        )

    def test_root_tip_crash_recovers_the_canonical_admission(self):
        resolved = address.resolve("local-owner")
        self.assertEqual(resolved.get("session_id"), "tip-1", resolved)
        first = self._send("local-owner", "wake the owner", key="recovery-pin", flag=True)
        self.assertTrue(first.get("ok"), first)
        row = record.get(first["message_id"])
        self.assertIsNone(row["admission_id"])
        self.assertTrue(row["framed_text"])
        owned = self._rows("local-owner")
        self.assertEqual(len(owned), 1, self.submits)
        self.assertEqual(owned[0].target_session_id, "local-owner")
        self.assertEqual(self._rows("tip-1"), [])
        self.assertEqual(row["target_session_id"], "local-owner", row["target_session_id"])
        second = self._send("local-owner", "a different picture", key="recovery-pin", flag=True)
        self.assertEqual(second.get("admission_id"), owned[0].admission_id, second)
        self.assertEqual(second.get("stored_target"), "local-owner", second)
        self.assertEqual(len(self._rows("local-owner")), 1)
        self.assertEqual(len(self.submits), 1, self.submits)
        receipt = self._run(self._receipt(second["admission_id"], second["stored_target"]))
        self.assertEqual(receipt["result"]["admission_id"], owned[0].admission_id, receipt)
        self.assertEqual(receipt["result"]["ref"]["session_id"], "local-owner", receipt)
        self.assertEqual(record.get(first["message_id"])["admission_id"], owned[0].admission_id)

    def test_unflagged_tip_stays_the_caller_target(self):
        self.return_admission = True
        receipt = self._send("tip-1", "plain wake", key="plain-pin")
        self.assertTrue(receipt.get("ok"), receipt)
        row = record.get(receipt["message_id"])
        self.assertEqual(row["target_session_id"], "tip-1")
        stored = self._rows("tip-1")
        self.assertEqual(len(stored), 1, self.submits)
        self.assertEqual(stored[0].target_session_id, "tip-1")
        self.assertEqual(self._rows("local-owner"), [])
        self.assertFalse(self.submits[0]["flag"])
        self.assertEqual(self.submits[0]["target"], "tip-1")
