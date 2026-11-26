"""Optional close-aware admit for ``prompt.submit``.

Absent, the stored target is the caller's session id. Present, a new admit stores
the platform canonical target and refuses when that owner is closed by the user.
Exact replay is decided in the admit write, before this gate.
"""

from __future__ import annotations

from gateway.session_persistence import authority_persistence
from persistence.authority.admissions import CloseAwareAdmit, GateRefusal
from persistence.core.errors import AuthorityRefusal


def close_flag(params) -> bool:
    """The wire flag. Absent is off. A non-bool is ``invalid_params``."""
    if 'unless_closed_by_user' not in params:
        return False
    flag = params['unless_closed_by_user']
    if type(flag) is not bool:
        raise AuthorityRefusal('invalid_params', field='unless_closed_by_user')
    return flag


def place_submission(connection, ref, *, close_aware: bool):
    """The ``SessionRef`` a submit stores. Unflagged callers keep *ref*.

    A flagged admit chooses the canonical target before the lineage check.
    The named id or that target must already be subscribed.
    """
    if not close_aware:
        if ref.session_id not in connection.subscriptions:
            raise AuthorityRefusal('permission_denied')
        return ref
    canonical = canonical_submit_ref(connection.authority, connection.actor, ref)
    chain = authority_persistence(connection.authority).lineage.lineage(canonical.session_id)
    if ref.session_id not in chain:
        raise AuthorityRefusal('owner_unreachable', field='session')
    subscribed = connection.subscriptions
    if ref.session_id not in subscribed and canonical.session_id not in subscribed:
        raise AuthorityRefusal('permission_denied')
    return canonical


def canonical_submit_ref(authority, actor, ref):
    """The platform target chosen before the identity lookup. Same rule as resume."""
    from gateway.config import Platform
    from gateway.session_local_migration import adopts_client_history, resolve_local_target
    from gateway.session_route_recovery import messaging_owner_ref
    from persistence.authority.vocabulary import LEGACY_LOCAL_SOURCES

    store = authority_persistence(authority)
    row = store.sessions.get(ref.session_id)
    if row is None:
        raise AuthorityRefusal('not_found')
    local = row.source in LEGACY_LOCAL_SOURCES | {Platform.LOCAL.value}
    if local or adopts_client_history(authority, actor, row):
        return resolve_local_target(authority, actor, store.lineage.tip(ref.session_id))
    return messaging_owner_ref(authority, ref)


def memory_close_refusal(authority, logical_owner: str):
    """Owner memory only. Does not read the session store.

    A pending orphan reap is not the user's close. Anything else still pending,
    and a dispatch the owner already refused, refuses the new admit.
    """
    from gateway.session_viewer_close import ORPHAN_REASONS
    from tools.async_delegation import refused_for_session

    pending = authority.pending_closes.get(logical_owner)
    refused = refused_for_session((authority.profile_id, logical_owner))
    pending_user = pending is not None and pending.reason not in ORPHAN_REASONS
    if not refused and not pending_user:
        return None
    return GateRefusal('closed-by-user', field='session', detail=f'logical_owner={logical_owner} memory=1')


def admission_gate(authority, logical_owner: str, *, queue_only: bool, close_aware: bool):
    """``(gate, close_aware)`` for one admit.

    Unflagged: the drain refusal decided before the SQL write, and no close check.
    Flagged: that same decision, then the memory refusal inside the write.
    """
    decided = authority.gate_refusal(queue_only=queue_only)
    if not close_aware:
        return decided, None

    def gate():
        if decided is not None:
            return decided
        return memory_close_refusal(authority, logical_owner)

    return gate, CloseAwareAdmit(logical_owner)


def lookup_target_ids(authority, session_id: str):
    """Targets for a read-only lookup, or None when the lineage cannot be listed.

    The named id must sit in the canonical target's compression lineage. This does not
    restore, adopt, or write. A session outside that lineage is ``owner_unreachable``.
    """
    from gateway.session_contract import SessionRef

    canonical = _readonly_canonical_id(authority, session_id)
    if canonical is None:
        return None
    try:
        chain = authority_persistence(authority).lineage.lineage(canonical)
    except (OSError, AuthorityRefusal):
        return None
    if not chain:
        return None
    if session_id not in chain:
        raise AuthorityRefusal('owner_unreachable', field='session')
    return tuple(dict.fromkeys((*chain, canonical)))


def answer_lookup(connection, session_id, params) -> dict:
    """The ``prompt.lookup_admission`` result. Read-only."""
    _authorize_lookup(connection, session_id)
    request_id = params.get('request_id')
    if not isinstance(request_id, str) or not request_id:
        raise AuthorityRefusal('invalid_params', field='request_id')
    digest = params.get('payload_digest')
    if 'payload_digest' in params and digest is not None and not isinstance(digest, str):
        raise AuthorityRefusal('invalid_params', field='payload_digest')
    canonical = _readonly_canonical_id(connection.authority, session_id)
    targets = lookup_target_ids(connection.authority, session_id)
    if targets is None:
        return _lookup_body('unavailable')
    looked = authority_persistence(connection.authority).admissions.lookup_admission_by_request(
        principal_id=connection.actor.subject, request_id=request_id, target_ids=targets,
        payload_digest=digest)
    return _lookup_body(looked.outcome, looked.admission_id, looked.target_session_id,
                        looked.payload_digest, canonical_session_id=canonical)


def _lookup_body(outcome, admission_id=None, target_session_id=None, payload_digest=None,
                 canonical_session_id=None) -> dict:
    body = {'outcome': outcome, 'admission_id': admission_id, 'target_session_id': target_session_id,
            'payload_digest': payload_digest}
    if isinstance(canonical_session_id, str) and canonical_session_id:
        body['canonical_session_id'] = canonical_session_id
    return body


def _authorize_lookup(connection, session_id: str) -> None:
    """``session:submit`` without mounting or restoring the session."""
    from gateway.config import Platform
    from gateway.owner_identity import same_owner
    from gateway.session_authorities import require_serving
    from persistence.authority.vocabulary import LEGACY_LOCAL_SOURCES

    authority, actor = connection.authority, connection.actor
    require_serving(authority)
    if actor.profile_id != authority.profile_id:
        raise AuthorityRefusal('profile_mismatch')
    if 'session:submit' not in actor.capabilities:
        raise AuthorityRefusal('permission_denied')
    live = authority.sessions.get(session_id)
    if live is not None:
        from gateway.session_history_mount import is_history_mount, require_history_access
        if is_history_mount(live):
            require_history_access(authority, actor, session_id, 'session:submit')
        source = live.source
        if (source is not None and source.platform == Platform.LOCAL
                and not same_owner(source.user_id, actor.subject)
                and 'session:operator' not in actor.capabilities):
            raise AuthorityRefusal('permission_denied')
        return
    row = authority_persistence(authority).sessions.get(session_id)
    if row is None:
        return
    local = row.source in LEGACY_LOCAL_SOURCES | {Platform.LOCAL.value}
    if (local and not same_owner(row.user_id, actor.subject)
            and 'session:operator' not in actor.capabilities):
        raise AuthorityRefusal('permission_denied')


def _readonly_canonical_id(authority, session_id: str) -> str | None:
    """The E2 canonical id, read from the row. None when that id cannot be named."""
    from gateway.config import Platform
    from gateway.session_contract import SessionRef
    from gateway.session_route_recovery import messaging_owner_ref
    from persistence.authority.vocabulary import LEGACY_LOCAL_SOURCES

    store = authority_persistence(authority)
    try:
        row = store.sessions.get(session_id)
    except (OSError, AuthorityRefusal):
        return None
    if row is None:
        return None
    if row.source in LEGACY_LOCAL_SOURCES | {Platform.LOCAL.value}:
        return _local_canonical_id(store, row, session_id)
    try:
        return messaging_owner_ref(authority, SessionRef(authority.profile_id, session_id)).session_id
    except (OSError, AuthorityRefusal):
        return None


def _local_canonical_id(store, row, session_id: str) -> str | None:
    chat = row.chat_id if isinstance(row.chat_id, str) else ''
    if chat.startswith('local-'):
        return chat
    try:
        marks = store.bindings.binding_marks(chat or session_id, lineage_of=session_id if chat else None)
    except (OSError, AuthorityRefusal, TypeError, ValueError):
        return None
    if not (marks.policy or marks.legacy):
        return session_id
    if chat and marks.lineage_owner != chat:
        return None
    return chat or session_id


def stamp_operator(authority, actor, request, payload, *, close_aware: bool) -> None:
    """Unflagged operator provenance. A flagged admit stays the pinned text frame."""
    if close_aware:
        return
    source = authority.sessions[request.ref.session_id].source
    from gateway.owner_identity import same_owner
    if source is None or same_owner(source.user_id, actor.subject):
        return
    payload['local_operator_v1'] = {
        'profile_id': authority.profile_id,
        'session_id': request.ref.session_id,
        'principal_id': actor.subject,
    }
