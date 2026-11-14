import { act, cleanup, render } from '@testing-library/react'
import { useEffect, useRef } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { HermesConnection } from '@/global'
import { getLatestSessionMessages, type SessionInfo } from '@/hermes'
import { createClientSessionState } from '@/lib/chat-runtime'
import * as gateways from '@/store/gateway'
import { $activeGatewayProfile, $newChatRoute, $showAllProfiles } from '@/store/profile'
import {
  $sessionResumeRequest,
  _resetSessionOwnerHintsForTests,
  getSessionOwnerHint,
  requestSessionResume,
  setConnection,
  setSessions
} from '@/store/session'
import {
  $sessionStates,
  clearAllSessionStates,
  publishSessionState,
  requestForOwnedSession,
  runtimeSessionOwner
} from '@/store/session-states'

import type { ClientSessionState } from '../../../types'

import { useSessionActions } from './index'

vi.mock('@/app/contrib/hooks/use-background-sync', () => ({ resetLiveRuntimeTracking: vi.fn() }))
vi.mock('@/hermes', async importOriginal => ({
  ...(await importOriginal<Record<string, unknown>>()),
  getLatestSessionMessages: vi.fn(async () => ({ messages: [], session_id: 'stored' })),
  getProfiles: vi.fn(async () => ({ profiles: [{ name: 'default' }] })),
  HermesGateway: class {
    connectionState = 'closed'
    connect = async () => {
      this.connectionState = 'open'
    }
    close = () => {
      this.connectionState = 'closed'
    }
    onEvent = () => () => undefined
    onState = () => () => undefined
    request = vi.fn(async (method: string) => rpcResult(method))
  }
}))

function rpcResult(method: string) {
  if (method === 'session.create') {
    return { session_id: 'runtime-created', info: { stored_session_id: 'created' } }
  }

  return method === 'session.resume' ? { info: {}, messages: [], resumed: 'stored', session_id: 'runtime' } : {}
}

function descriptor(connectionId: string, registryScoped = true): HermesConnection {
  return {
    connectionId,
    profile: 'default',
    registryScoped,
    mode: connectionId === 'local' ? 'local' : 'remote',
    authMode: 'token',
    token: 'test',
    wsUrl: `ws://${connectionId}.invalid/ws`,
    baseUrl: `http://${connectionId}.invalid`
  } as HermesConnection
}

type Resume = ReturnType<typeof useSessionActions>['resumeSession']
const ambientRequest = vi.fn(async () => ({}) as never)

function Harness({
  onReady,
  onCreate
}: {
  onReady: (resume: Resume) => void
  onCreate?: (create: ReturnType<typeof useSessionActions>['createBackendSessionForSend']) => void
}) {
  const states = useRef(new Map<string, ClientSessionState>())
  const activeSessionIdRef = useRef<string | null>(null)
  const busyRef = useRef(false)
  const creatingSessionRef = useRef(false)
  const runtimeIdByStoredSessionIdRef = useRef(new Map<string, string>())
  const selectedStoredSessionIdRef = useRef<string | null>(null)

  const actions = useSessionActions({
    activeSessionId: null,
    activeSessionIdRef,
    busyRef,
    creatingSessionRef,
    ensureSessionState: () => createClientSessionState(null),
    getRouteToken: () => 'token',
    getRoutedStoredSessionId: () => null,
    navigate: vi.fn() as never,
    requestGateway: ambientRequest,
    resetViewSync: vi.fn(),
    routedSessionId: null,
    runtimeIdByStoredSessionIdRef,
    selectedStoredSessionId: null,
    selectedStoredSessionIdRef,
    sessionStateByRuntimeIdRef: states,
    syncSessionStateToView: vi.fn(),
    updateSessionState: (id, updater, storedId) => {
      const next = updater(states.current.get(id) ?? createClientSessionState(storedId ?? null))
      states.current.set(id, next)
      publishSessionState(id, next)

      return next
    }
  })

  useEffect(() => onReady(actions.resumeSession), [actions.resumeSession, onReady])
  useEffect(() => onCreate?.(actions.createBackendSessionForSend), [actions.createBackendSessionForSend, onCreate])

  return null
}

describe('untagged resume ambient owner', () => {
  beforeEach(() => {
    clearAllSessionStates()
    _resetSessionOwnerHintsForTests()
    $showAllProfiles.set(false)
    $newChatRoute.set(null)
    $activeGatewayProfile.set('default')
    vi.clearAllMocks()
    Object.defineProperty(window, 'hermesDesktop', {
      configurable: true,
      value: {
        getConnectionFor: vi.fn(async ({ connectionId }: { connectionId: string }) => descriptor(connectionId)),
        getGatewayWsUrlFor: vi.fn(async ({ connectionId }: { connectionId: string }) => ({
          ok: true,
          wsUrl: `ws://${connectionId}.invalid/ws`
        }))
      }
    })
    gateways.configureGatewayRegistry({ onEvent: vi.fn(), onActiveRouteChanged: p => $activeGatewayProfile.set(p) })
  })

  afterEach(() => {
    cleanup()
    gateways.closeSecondaryGateways()
    gateways.setPrimaryGateway(null)
    setConnection(null)
    setSessions([])
    clearAllSessionStates()
    _resetSessionOwnerHintsForTests()
    $newChatRoute.set(null)
    $sessionResumeRequest.set(null)
    vi.restoreAllMocks()
  })

  it.each(['local', 'remote-secondary'])(
    'keeps resume, transcript and subsequent prompt on registry secondary %s',
    async connectionId => {
      const primary = { connectionState: 'open', request: vi.fn(async (method: string) => rpcResult(method)) }
      gateways.setPrimaryGateway(primary as never, 'default')
      gateways.setPrimaryGatewayConnection(descriptor('home'))
      setConnection(descriptor('home'))
      await gateways.ensureGatewayForAgent(connectionId, 'default')
      const secondary = gateways.activeGateway()!
      expect(gateways.isActivePrimary()).toBe(false)
      expect(gateways.activeGatewayConnectionId()).toBe(connectionId)
      // Deliberately no row tag or remembered owner: this is the ambient fallback.
      setSessions([{ id: 'stored', profile: 'default', message_count: 0 } as SessionInfo])
      expect(getSessionOwnerHint('stored')).toBeUndefined()
      let resume!: Resume
      render(
        <Harness
          onReady={ready => {
            resume = ready
          }}
        />
      )
      await act(() => resume('stored', true))

      expect(secondary.request).toHaveBeenCalledWith(
        'session.resume',
        expect.objectContaining({ session_id: 'stored' })
      )
      expect(getLatestSessionMessages).toHaveBeenCalledWith('stored', { connectionId, profile: 'default' })
      expect(runtimeSessionOwner('runtime')).toBeUndefined()
      expect($sessionStates.get().runtime?.boundOwner).toEqual({ connectionId, profile: 'default' })
      await gateways.ensureGatewayForAgent('home', 'default')
      await requestForOwnedSession('runtime', ambientRequest, 'prompt.submit', {
        session_id: 'runtime',
        text: 'continue'
      })
      expect(secondary.request).toHaveBeenCalledWith('prompt.submit', { session_id: 'runtime', text: 'continue' })
      expect(primary.request).not.toHaveBeenCalled()
      expect(ambientRequest).not.toHaveBeenCalled()
    }
  )

  it('binds the captured create owner before any scoped runtime event', async () => {
    const owner = { connectionId: 'local', profile: 'other-profile' }
    const primary = { connectionState: 'open', request: vi.fn(async (method: string) => rpcResult(method)) }
    gateways.setPrimaryGateway(primary as never, 'default')
    gateways.setPrimaryGatewayConnection(descriptor('local'))
    setConnection(descriptor('local'))
    $newChatRoute.set(owner)
    let create!: ReturnType<typeof useSessionActions>['createBackendSessionForSend']
    render(
      <Harness
        onCreate={ready => {
          create = ready
        }}
        onReady={() => undefined}
      />
    )
    await act(() => create())
    expect(runtimeSessionOwner('runtime-created')).toBeUndefined()
    expect($sessionStates.get()['runtime-created']?.boundOwner).toEqual(owner)
  })

  it('keeps a quiet all-profiles primary binding separate from a later destination hint', async () => {
    const owner = { connectionId: 'local', profile: 'other-profile' }
    const primary = { connectionState: 'open', request: vi.fn(async (method: string) => rpcResult(method)) }
    gateways.setPrimaryGateway(primary as never, 'default')
    gateways.setPrimaryGatewayConnection(descriptor('local'))
    setConnection(descriptor('local'))
    $showAllProfiles.set(true)
    setSessions([{ id: 'stored', connection_id: 'local', profile: 'other-profile', message_count: 0 } as SessionInfo])
    let resume!: Resume
    render(
      <Harness
        onReady={ready => {
          resume = ready
        }}
      />
    )
    await act(() => resume('stored', true, owner))
    expect(runtimeSessionOwner('runtime')).toBeUndefined()
    expect($activeGatewayProfile.get()).toBe('default')
    expect($sessionStates.get().runtime?.boundOwner).toEqual(owner)
    requestSessionResume('stored', { connectionId: 'local', profile: 'default' })
    expect(getSessionOwnerHint('stored', { connectionId: 'local', profile: 'default' })?.profile).toBe('default')
    expect($sessionStates.get().runtime?.boundOwner).toEqual(owner)
  })

  it('does not remember the foreground source for a session it could not resolve', async () => {
    const primary = { connectionState: 'open', request: vi.fn(async (method: string) => rpcResult(method)) }
    gateways.setPrimaryGateway(primary as never, 'default')
    gateways.setPrimaryGatewayConnection(descriptor('home'))
    setConnection(descriptor('home'))
    await gateways.ensureGatewayForAgent('local', 'default')
    expect(gateways.isActivePrimary()).toBe(false)
    // No listed row and no reachable detail endpoint: the owner is unknown.
    setSessions([])
    let resume!: Resume
    render(
      <Harness
        onReady={ready => {
          resume = ready
        }}
      />
    )
    await act(() => resume('stored', true))

    expect(getSessionOwnerHint('stored')).toBeUndefined()
  })

  it.each([false, true])(
    'preserves the profile-only door on a local primary (registryScoped=%s)',
    async registryScoped => {
      const primary = { connectionState: 'open', request: vi.fn(async (method: string) => rpcResult(method)) }
      gateways.setPrimaryGateway(primary as never, 'default')
      gateways.setPrimaryGatewayConnection(descriptor('local', registryScoped))
      setConnection(descriptor('local', registryScoped))
      const profileRequest = vi.spyOn(gateways, 'requestGatewayForProfile')
      const agentRequest = vi.spyOn(gateways, 'requestGatewayForAgent')
      setSessions([{ id: 'stored', profile: 'default', message_count: 0 } as SessionInfo])
      let resume!: Resume
      render(
        <Harness
          onReady={ready => {
            resume = ready
          }}
        />
      )
      await act(() => resume('stored', true))

      expect(profileRequest).toHaveBeenCalledWith(
        'default',
        'session.resume',
        expect.objectContaining({ session_id: 'stored' }),
        undefined,
        undefined
      )
      expect(agentRequest).not.toHaveBeenCalled()
      expect(getLatestSessionMessages).toHaveBeenCalledWith('stored', 'default')
      expect(primary.request).toHaveBeenCalledWith('session.resume', expect.objectContaining({ session_id: 'stored' }))
    }
  )
})
