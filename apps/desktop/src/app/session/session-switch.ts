import { atom } from 'nanostores'

import { findGroupOfPane } from '@/components/pane-shell/tree/model'
import { $layoutTree } from '@/components/pane-shell/tree/store'
import { triggerHaptic } from '@/lib/haptics'
import { $sessionSwitchHaptics } from '@/store/haptics'
import { $activeGatewayProfile, normalizeProfileKey } from '@/store/profile'
import {
  $activeSessionId,
  $connection,
  $freshDraftKey,
  $gatewayState,
  $resumeFailedSessionId,
  $selectedStoredSessionId,
  knownSessionOwner,
  ownerLookupSessionRows
} from '@/store/session'
import { $focusedStoredSessionId, $focusedTreePaneId, TILE_PANE_PREFIX } from '@/store/session-focus'
import type { SessionProfileRoute } from '@/store/session-request-router'
import { $sessionStates, $sessionTiles, runtimeSessionOwner } from '@/store/session-states'

interface SessionSwitchSource {
  identity: string | null
  runtimeId: string
  storedSessionId: string
}

interface SessionSwitchIntent {
  previous: SessionSwitchSource | null
  paneId: string
  identity: string
  storedSessionId: string
  connectionId: string
  ownerRoute: SessionProfileRoute
}

// Window-local intent survives first mount of a tab; never persisted or armed
// by selection/list/lineage changes. Only explicit open and tab actions write it.
export const $sessionSwitchIntent = atom<SessionSwitchIntent | null>(null)

function connectionId(): string {
  const connection = $connection.get()

  return connection?.connectionId || (connection?.mode === 'local' ? 'local' : '')
}

function sessionSwitchOwner(storedSessionId: string, ownerRoute?: Partial<SessionProfileRoute>): SessionProfileRoute {
  const ambient = { connectionId: connectionId(), profile: $activeGatewayProfile.get() }
  const tile = $sessionTiles.get().find(candidate => candidate.storedSessionId === storedSessionId)
  const states = $sessionStates.get()
  const activeRuntime = $activeSessionId.get()

  const primaryRuntime =
    activeRuntime && states[activeRuntime]?.storedSessionId === storedSessionId ? activeRuntime : null

  const tileRuntime =
    tile?.runtimeId && states[tile.runtimeId]?.storedSessionId === storedSessionId ? tile.runtimeId : null

  const knownOwner =
    ownerRoute ??
    boundRuntimeOwner(tileRuntime, tile?.ownerRoute) ??
    boundRuntimeOwner(primaryRuntime) ??
    knownSessionOwner(ownerLookupSessionRows(), storedSessionId)

  const owner = typeof knownOwner === 'string' ? { profile: knownOwner } : knownOwner

  return {
    ...owner,
    connectionId: owner?.connectionId || ambient.connectionId,
    profile: owner?.profile || ambient.profile
  }
}

function boundRuntimeOwner(runtimeId?: null | string, fallback?: SessionProfileRoute): SessionProfileRoute | undefined {
  const owner = runtimeSessionOwner(runtimeId) ?? (runtimeId ? $sessionStates.get()[runtimeId]?.boundOwner : undefined)

  return typeof owner === 'string'
    ? { connectionId: fallback?.connectionId || connectionId(), profile: owner }
    : (owner ?? fallback)
}

export function sessionSwitchIdentity(storedSessionId: string, ownerRoute?: Partial<SessionProfileRoute>): string {
  const owner = sessionSwitchOwner(storedSessionId, ownerRoute)

  return JSON.stringify([owner.connectionId, owner.targetProfile || owner.profile, storedSessionId])
}

function focusedSessionSwitchSource(): SessionSwitchSource | null {
  const tree = $layoutTree.get()
  const pane = $focusedTreePaneId.get() ?? (tree ? findGroupOfPane(tree, 'workspace')?.active : undefined)

  const tile = pane?.startsWith(TILE_PANE_PREFIX)
    ? $sessionTiles.get().find(candidate => `${TILE_PANE_PREFIX}${candidate.storedSessionId}` === pane)
    : undefined

  const runtimeId = pane === 'workspace' ? $activeSessionId.get() : tile?.runtimeId
  const stored = runtimeId ? $sessionStates.get()[runtimeId]?.storedSessionId : null

  // The selected id may already name an incoming transcript. The source is
  // the bound runtime, never a same-id row from another unified-list owner.
  if (!stored || !runtimeId) {
    return null
  }

  const owner = boundRuntimeOwner(runtimeId, tile?.ownerRoute)

  return { runtimeId, storedSessionId: stored, identity: owner ? sessionSwitchIdentity(stored, owner) : null }
}

export function beginSessionSwitch(
  storedSessionId: string,
  ownerRoute?: SessionProfileRoute,
  previous = focusedSessionSwitchSource(),
  paneId = 'workspace'
): void {
  const owner = sessionSwitchOwner(storedSessionId, ownerRoute)
  const identity = sessionSwitchIdentity(storedSessionId, owner)
  $sessionSwitchIntent.set(
    identity === previous?.identity
      ? null
      : {
          previous,
          paneId,
          identity,
          storedSessionId,
          connectionId: connectionId(),
          ownerRoute: owner
        }
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

  const ownerRoute =
    storedSessionId === intent.storedSessionId ? intent.ownerRoute : sessionSwitchOwner(storedSessionId)

  const identity = sessionSwitchIdentity(storedSessionId, ownerRoute)
  $sessionSwitchIntent.set(
    identity === intent.previous?.identity ? null : { ...intent, storedSessionId, paneId, identity, ownerRoute }
  )
}

// Keyboard commands resolve their target inside the layout action. Capture the
// source BEFORE it changes focus, then arm the same path as a clicked tab.
export function withSessionTabSwitch(activate: () => string | null): string | null {
  const previous = focusedSessionSwitchSource()
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
$freshDraftKey.listen(() => cancelSessionSwitch())
$selectedStoredSessionId.listen(id => {
  if (!id) {
    cancelSessionSwitch()
  }
})
$activeGatewayProfile.listen(profile => {
  const intent = $sessionSwitchIntent.get()

  if (
    intent &&
    ![intent.ownerRoute.profile, intent.ownerRoute.targetProfile].some(
      ownerProfile => ownerProfile !== undefined && normalizeProfileKey(ownerProfile) === normalizeProfileKey(profile)
    )
  ) {
    cancelSessionSwitch()
  }
})
$layoutTree.listen((tree, previous) => {
  const intent = $sessionSwitchIntent.get()

  // Layout/store lifetime, not React cleanup: StrictMode may replay effects
  // and a first-mounted target may not have a transcript component yet.
  if (
    intent &&
    previous &&
    findGroupOfPane(previous, intent.paneId) &&
    (!tree || !findGroupOfPane(tree, intent.paneId))
  ) {
    cancelSessionSwitch()
  }
})
$sessionTiles.listen((tiles, previous) => {
  const intent = $sessionSwitchIntent.get()

  if (!intent) {
    return
  }

  const target = tiles.find(tile => `${TILE_PANE_PREFIX}${tile.storedSessionId}` === intent.paneId)
  const removed = previous?.some(tile => `${TILE_PANE_PREFIX}${tile.storedSessionId}` === intent.paneId) && !target

  if (removed || tiles.some(tile => tile.storedSessionId === intent.storedSessionId && tile.error)) {
    cancelSessionSwitch(intent.storedSessionId)
  }
})
