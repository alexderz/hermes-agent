import { act, cleanup, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

import { MAIN_COMPOSER_SCOPE } from '@/app/chat/composer/scope'
import { useSessionTileActions } from '@/app/chat/session-tile-actions'
import { actRender, Harness, type HarnessHandle, RUNTIME_SESSION_ID } from '@/app/session/hooks/use-prompt-actions/index-test-utils'
import { useSessionActions } from '@/app/session/hooks/use-session-actions'
import type { ClientSessionState } from '@/app/types'
import { createClientSessionState } from '@/lib/chat-runtime'
import { $gateway, configureGatewayRegistry, setPrimaryGateway } from '@/store/gateway'
import { $activeGatewayProfile } from '@/store/profile'
import { clearAllPrompts, readSecretDraft, sessionSecretRequest, setSecretRequest, writeSecretDraft } from '@/store/prompts'
import { $activeSessionId, $connection, _resetSessionOwnerHintsForTests, setSessionOwnerHint, setSessions } from '@/store/session'
import { $sessionTiles, clearAllSessionStates } from '@/store/session-states'
import type { SessionInfo } from '@/types/hermes'

vi.mock('@/hermes', async importOriginal => ({
  ...(await importOriginal<Record<string, unknown>>()),
  deleteSession: vi.fn(async () => ({ ok: true })),
  getLatestSessionMessages: vi.fn(async () => ({ messages: [], session_id: 'stored' }))
}))
vi.mock('@/store/gateway', async importOriginal => ({
  ...(await importOriginal<Record<string, unknown>>()),
  requestGatewayForAgent: vi.fn(async () => ({}))
}))

const ownerA = { connectionId: 'conn-a', profile: 'desktop-a', targetProfile: 'backend-a' }
const ownerB = { connectionId: 'conn-b', profile: 'backend-b' }
const a = { ...ownerA, profile: ownerA.targetProfile, sessionId: RUNTIME_SESSION_ID, requestId: 'request-a', envVar: 'TEST_KEY', prompt: 'Dummy' }
const b = { ...ownerB, sessionId: RUNTIME_SESSION_ID, requestId: 'request-b', envVar: 'TEST_KEY', prompt: 'Dummy' }
const ref = <T,>(current: T) => ({ current })

beforeEach(() => {
  clearAllPrompts()
  clearAllSessionStates()
  _resetSessionOwnerHintsForTests({ storage: true })
  setSessions([])
  $sessionTiles.set([])
  $activeGatewayProfile.set(ownerA.targetProfile)
  $connection.set({ connectionId: ownerA.connectionId, mode: 'ssh' } as never)
  configureGatewayRegistry({ activeConnectionId: () => ownerA.connectionId, onEvent: vi.fn() })
  const gateway = { connectionState: 'open', request: vi.fn(async () => ({})) }
  setPrimaryGateway(gateway as never, ownerA.targetProfile)
  $gateway.set(gateway as never)
  setSessionOwnerHint('stored', ownerA)
  setSessionOwnerHint(RUNTIME_SESSION_ID, ownerA)
})
afterEach(() => {
  cleanup()
  clearAllPrompts()
  clearAllSessionStates()
  setSessions([])
  $sessionTiles.set([])
  $activeSessionId.set(null)
  $connection.set(null)
  $gateway.set(null)
  _resetSessionOwnerHintsForTests({ storage: true })
})

async function action(kind: string) {
  const requestGateway = vi.fn(async () => ({} as never))

  if (kind === 'Stop') {
    let handle: HarnessHandle | undefined
    await actRender(<Harness onReady={value => { handle = value }} refreshSessions={async () => {}} requestGateway={requestGateway} storedSessionId="stored" />)
    await handle!.cancelRun()

    return
  }

  if (kind === 'tile Stop') {
    $sessionTiles.set([{ ownerRoute: ownerA, runtimeId: RUNTIME_SESSION_ID, storedSessionId: 'stored' }])
    const { result } = renderHook(() => useSessionTileActions({ requestGateway, runtimeId: RUNTIME_SESSION_ID, storedSessionId: 'stored', scope: MAIN_COMPOSER_SCOPE }))
    await act(() => result.current.cancelRun())

    return
  }

  const row: SessionInfo = {
    id: 'stored', connection_id: ownerA.connectionId, profile: ownerA.profile, title: 'Fixture', is_active: true,
    ended_at: null, input_tokens: 0, output_tokens: 0, last_active: 1, message_count: 1, model: null,
    preview: null, source: 'desktop', started_at: 1, tool_call_count: 0
  }

  setSessions([row])
  const state = { ...createClientSessionState(), storedSessionId: 'stored' }

  const { result } = renderHook(() => useSessionActions({
    activeSessionId: null, activeSessionIdRef: ref<string | null>(null), busyRef: ref(false), creatingSessionRef: ref(false),
    ensureSessionState: () => state, getRouteToken: () => 'fixture', getRoutedStoredSessionId: () => null,
    navigate: vi.fn(), requestGateway, resetViewSync: vi.fn(), routedSessionId: null,
    runtimeIdByStoredSessionIdRef: ref(new Map([['stored', RUNTIME_SESSION_ID]])),
    selectedStoredSessionId: null, selectedStoredSessionIdRef: ref<string | null>(null),
    sessionStateByRuntimeIdRef: ref(new Map([[RUNTIME_SESSION_ID, state]])),
    syncSessionStateToView: vi.fn(), updateSessionState: (_id: string, update: (value: ClientSessionState) => ClientSessionState) => update(state)
  }))

  await act(() => result.current.removeSession('stored'))
}

it.each(['Stop', 'tile Stop', 'close'])('%s leaves the OTHER owner’s only same-ID request and draft untouched', async kind => {
  setSecretRequest(b)
  writeSecretDraft(b, 'dummy-b')
  await action(kind)
  expect(sessionSecretRequest(RUNTIME_SESSION_ID, b).get()?.requestId).toBe(b.requestId)
  expect(readSecretDraft(b)).toBe('dummy-b')
})

it.each(['Stop', 'tile Stop', 'close'])('%s clears its own request with both owners present, preserving the other draft', async kind => {
  setSecretRequest(a)
  setSecretRequest(b)
  writeSecretDraft(a, 'dummy-a')
  writeSecretDraft(b, 'dummy-b')
  await action(kind)
  expect(sessionSecretRequest(RUNTIME_SESSION_ID, a).get()).toBeNull()
  expect(readSecretDraft(a)).toBe('')
  expect(sessionSecretRequest(RUNTIME_SESSION_ID, b).get()?.requestId).toBe(b.requestId)
  expect(readSecretDraft(b)).toBe('dummy-b')
})

it('unscoped session cleanup clears only genuinely unscoped entries; a global reset still clears all', () => {
  const unscoped = { sessionId: RUNTIME_SESSION_ID, requestId: 'legacy', envVar: 'TEST_KEY', prompt: 'Dummy' }
  setSecretRequest(unscoped)
  setSecretRequest(b)
  writeSecretDraft(b, 'dummy-b')
  clearAllPrompts(RUNTIME_SESSION_ID)
  expect(sessionSecretRequest(RUNTIME_SESSION_ID, b).get()?.requestId).toBe(b.requestId)
  expect(readSecretDraft(b)).toBe('dummy-b')
  clearAllPrompts()
  expect(sessionSecretRequest(RUNTIME_SESSION_ID, b).get()).toBeNull()
  expect(readSecretDraft(b)).toBe('')
})
