"""Intercom's read-only session view over the public storage interface.

Keep the plugin's row-shaped addressing/folding code independent of storage records; the
handle is explicitly owned by this reader and never opens a writer or migrates a store.
"""
from __future__ import annotations

from contextlib import ExitStack

from hermes_constants import get_hermes_home
from persistence.conversation.sessions import CANONICAL_BOT_CHAT_TITLE, SessionOrder, SessionQuery, SessionWindow
from persistence_assembly import open_persistence_reader


class SessionReader:
    CANONICAL_BOT_CHAT_TITLE = CANONICAL_BOT_CHAT_TITLE

    def __init__(self):
        self._handles = ExitStack()
        try:
            self.store = self._handles.enter_context(open_persistence_reader(get_hermes_home()))
            self.store.ready()
        except BaseException:
            self._handles.close()
            raise

    def close(self):
        self._handles.close()

    def get_session(self, session_id):
        row = self.store.sessions.get(session_id)
        return row.as_session_row() if row is not None else None

    def get_session_by_title(self, title):
        row = self.store.sessions.get_by_title(title)
        return row.as_session_row() if row is not None else None

    def get_session_title(self, session_id):
        return self.store.sessions.get_title(session_id)

    def resolve_session_id(self, session_id):
        return self.store.sessions.resolve_id(session_id)

    def get_compression_tip(self, session_id):
        return self.store.lineage.tip(session_id)

    def get_compression_lineage(self, session_id):
        return self.store.lineage.lineage(session_id)

    def list_sessions_rich(self, *, limit=20, offset=0, compact_rows=False,
                           order_by_last_active=False, **filters):
        query = SessionQuery(
            order=SessionOrder.LAST_ACTIVE if order_by_last_active else SessionOrder.STARTED_AT,
            **filters)
        return [row.as_list_row() for row in self.store.sessions.list_sessions(
            query, SessionWindow(limit=limit, offset=offset), compact_rows=compact_rows)]
