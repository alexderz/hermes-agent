import { atom } from 'nanostores'

import { triggerHaptic } from '@/lib/haptics'
import { $sessionSwitchHaptics } from '@/store/haptics'
import { $activeGatewayProfile } from '@/store/profile'
import {
  $connection,
  $gatewayState,
  $resumeFailedSessionId,
  $selectedStoredSessionId,
  knownSessionOwner,
  ownerLookupSessionRows
} from '@/store/session'
import { $focusedStoredSessionId, $focusedTreePaneId, TILE_PANE_PREFIX } from '@/store/session-focus'
import type { SessionProfileRoute } from '@/store/session-request-router'
import { $sessionTiles } from '@/store/session-states'

interface SessionSwitchIntent {
  previousIdentity: string | null
  paneId: string
  identity: string
  storedSessionId: string
  connectionId: string
}

// Window-local intent survives first mount of a tab; never persisted or armed
// by selection/list/lineage changes. Only explicit open and tab actions write it.
export const $sessionSwitchIntent = atom<SessionSwitchIntent | null>(null)

function connectionId(): string {
  const connection = $connection.get()

  return connection?.connectionId || (connection?.mode === 'local' ? 'local' : '')
}

export function sessionSwitchIdentity(storedSessionId: string, ownerRoute?: Partial<SessionProfileRoute>): string {
  const ambient = { connectionId: connectionId(), profile: $activeGatewayProfile.get() }

  const knownOwner =
    ownerRoute ??
    $sessionTiles.get().find(tile => tile.storedSessionId === storedSessionId)?.ownerRoute ??
    knownSessionOwner(ownerLookupSessionRows(), storedSessionId)

  const owner = typeof knownOwner === 'string' ? { profile: knownOwner } : knownOwner

  return JSON.stringify([
    owner?.connectionId || ambient.connectionId,
    owner?.targetProfile || owner?.profile || ambient.profile,
    storedSessionId
  ])
}

export function focusedSessionSwitchIdentity(): string | null {
  const stored = $focusedStoredSessionId.get()

  return stored ? sessionSwitchIdentity(stored) : null
}

export function beginSessionSwitch(
  storedSessionId: string,
  ownerRoute?: SessionProfileRoute,
  previous = focusedSessionSwitchIdentity(),
  paneId = 'workspace'
): void {
  const identity = sessionSwitchIdentity(storedSessionId, ownerRoute)
  $sessionSwitchIntent.set(
    identity === previous
      ? null
      : { previousIdentity: previous, paneId, identity, storedSessionId, connectionId: connectionId() }
  )
}

// focusOpenSession may front a tip-keyed tab for a root-id request. Record
// that actual destination during the explicit action, never on a list refresh.
export function resolveSessionSwitchDestination(
  storedSessionId = $focusedStoredSessionId.get(),
  paneId = $focusedTreePaneId.get() ?? 'workspace'
): void {
  const intent = $sessionSwitchIntent.get()

  if (!intent || !storedSessionId) {
    return
  }

  const identity = storedSessionId === intent.storedSessionId ? intent.identity : sessionSwitchIdentity(storedSessionId)
  $sessionSwitchIntent.set(
    identity === intent.previousIdentity ? null : { ...intent, storedSessionId, paneId, identity }
  )
}

// Keyboard commands resolve their target inside the layout action. Capture the
// source BEFORE it changes focus, then arm the same path as a clicked tab.
export function withSessionTabSwitch(activate: () => string | null): string | null {
  const previous = focusedSessionSwitchIdentity()
  const pane = activate()

  const stored =
    pane === 'workspace'
      ? $selectedStoredSessionId.get()
      : pane?.startsWith(TILE_PANE_PREFIX)
        ? pane.slice(TILE_PANE_PREFIX.length)
        : null

  if (stored && pane) {
    beginSessionSwitch(stored, undefined, previous, pane)
  } else {
    $sessionSwitchIntent.set(null)
  }

  return pane
}

export function cancelSessionSwitch(storedSessionId?: string): void {
  if (!storedSessionId || $sessionSwitchIntent.get()?.storedSessionId === storedSessionId) {
    $sessionSwitchIntent.set(null)
  }
}

export function confirmSessionSwitch(intent: SessionSwitchIntent, identity: string): void {
  if ($sessionSwitchIntent.get() !== intent || identity !== intent.identity || intent.connectionId !== connectionId()) {
    return
  }

  // Consume even when disabled/muted/unsupported: settings changes or reconnect
  // must never replay a confirmation the person already saw.
  $sessionSwitchIntent.set(null)

  if ($sessionSwitchHaptics.get()) {
    triggerHaptic('selection')
  }
}

$gatewayState.listen(state => {
  if (state !== 'open') {
    cancelSessionSwitch()
  }
})
$connection.listen(() => {
  if ($sessionSwitchIntent.get()?.connectionId !== connectionId()) {
    cancelSessionSwitch()
  }
})
$resumeFailedSessionId.listen(id => {
  if (id) {
    cancelSessionSwitch(id)
  }
})
$sessionTiles.listen(tiles => {
  const intent = $sessionSwitchIntent.get()

  if (intent && tiles.some(tile => tile.storedSessionId === intent.storedSessionId && tile.error)) {
    cancelSessionSwitch(intent.storedSessionId)
  }
})
