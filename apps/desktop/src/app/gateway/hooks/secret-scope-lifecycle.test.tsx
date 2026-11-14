import type { GatewayEvent } from '@hermes/shared'
import { useStore } from '@nanostores/react'
import { QueryClient } from '@tanstack/react-query'
import { act, cleanup, render } from '@testing-library/react'
import { useRef } from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

import { useGatewayBoot } from '@/app/gateway/hooks/use-gateway-boot'
import { useMessageStream } from '@/app/session/hooks/use-message-stream'
import type { ClientSessionState } from '@/app/types'
import { createClientSessionState } from '@/lib/chat-runtime'
import { closeSecondaryGateways, ensureGatewayForAgent, type ScopedServerRequest } from '@/store/gateway'
import { $primaryGatewayRoute } from '@/store/gateway-primary-route'
import { clearNotifications } from '@/store/notifications'
import { $activeGatewayProfile, $profiles } from '@/store/profile'
import { clearAllPrompts, readSecretDraft, sessionSecretRequest, setSecretRequest, writeSecretDraft } from '@/store/prompts'
import { resetServerRequestsForTests } from '@/store/server-requests'
import { $activeSessionId, $connection } from '@/store/session'
import { clearAllSessionStates } from '@/store/session-states'
import { FakeWebSocket } from '@/test/fake-gateway-socket'

import { takeGatewaySurvivor } from './gateway-hmr-survivor'

class FixtureSocket extends FakeWebSocket {
  private receivers = new Set<(event: unknown) => void>()
  override addEventListener(type: string, handler: (event: unknown) => void) {
    super.addEventListener(type, handler)

    if (type === 'message') { this.receivers.add(handler) }
  }
  override removeEventListener(type: string, handler: (event: unknown) => void) {
    super.removeEventListener(type, handler)
    this.receivers.delete(handler)
  }
  receive(frame: object) {
    for (const handler of this.receivers) { handler({ data: JSON.stringify(frame) }) }
  }
}

const originalWebSocket = globalThis.WebSocket
const events: GatewayEvent[] = []
const requests: ScopedServerRequest[] = []
const descriptor = (connectionId: string, profile: string) => ({ connectionId, profile, mode: 'remote' as const, authMode: 'token' as const, baseUrl: `https://${connectionId}.invalid`, wsUrl: `wss://${connectionId}.invalid/api/ws`, token: 'dummy-fixture-token' })
const primary = descriptor('fixture-primary', 'default')

function Harness() {
  const states = useRef(new Map<string, ClientSessionState>())
  const active = useRef<string | null>('s1')
  active.current = useStore($activeSessionId)
  const queryClient = useRef(new QueryClient())

  const stream = useMessageStream({
    activeSessionIdRef: active, sessionStateByRuntimeIdRef: states, queryClient: queryClient.current,
    updateSessionState: (id, update) => {
      const next = update(states.current.get(id) ?? createClientSessionState())
      states.current.set(id, next)

      return next
    },
    hydrateFromStoredSession: async () => {}, refreshHermesConfig: async () => {}, refreshSessions: async () => {}
  })

  useGatewayBoot({
    beforeConnectionSwitch: () => {},
    handleGatewayEvent: event => { events.push(event); stream.handleGatewayEvent(event) },
    handleServerRequest: request => { requests.push(request);

 return stream.handleServerRequest(request) },
    onConnectionReady: () => {}, onGatewayReady: () => {}, refreshHermesConfig: async () => {}, refreshSessions: async () => {}
  })

  return null
}

beforeEach(() => {
  closeSecondaryGateways()
  clearAllSessionStates()
  clearAllPrompts()
  resetServerRequestsForTests()
  events.length = 0
  requests.length = 0
  $profiles.set([])
  $activeGatewayProfile.set('default')
  $activeSessionId.set('s1')
  $connection.set(null)
  FakeWebSocket.instances = []
  FakeWebSocket.mode = 'open'
  globalThis.WebSocket = FixtureSocket as never
  window.hermesDesktop = {
    getConnection: vi.fn(async () => primary),
    getConnectionFor: vi.fn(async ({ connectionId, profile }: { connectionId: string; profile: string }) => descriptor(connectionId, profile)),
    getGatewayWsUrl: vi.fn(async (connection: { wsUrl: string }) => connection.wsUrl),
    getGatewayWsUrlFor: vi.fn(async (connection: { wsUrl: string }) => connection.wsUrl),
    getBootProgress: vi.fn(async () => ({ running: true, phase: 'init', progress: 0, timestamp: 0, message: '', fakeMode: false, retryable: false, error: null })),
    onBootProgress: vi.fn(() => () => {}), onWindowStateChanged: vi.fn(() => () => {}),
    onConnectionApplied: vi.fn(() => () => {}), onBackendExit: vi.fn(() => () => {}), onPowerResume: vi.fn(() => () => {}),
    profile: { get: vi.fn(async () => ({ profile: 'default' })) }
  } as never
  vi.useFakeTimers()
})
afterEach(() => {
  cleanup()
  takeGatewaySurvivor()?.gateway.close()
  closeSecondaryGateways()
  clearAllPrompts()
  clearAllSessionStates()
  resetServerRequestsForTests()
  clearNotifications()
  $activeSessionId.set(null)
  $connection.set(null)
  globalThis.WebSocket = originalWebSocket
  delete (window as { hermesDesktop?: unknown }).hermesDesktop
  vi.useRealTimers()
})

const receiveRequest = (socket: FixtureSocket, id: string) => socket.receive({ jsonrpc: '2.0', id, method: 'secret', params: { session_id: 's1', env_var: 'TEST_KEY', prompt: 'Dummy' } })
const receiveEvent = (socket: FixtureSocket, type: string, payload: object) => socket.receive({ jsonrpc: '2.0', method: 'event', params: { session_id: 's1', type, payload } })

it.each(['primary', 'owner-routed'] as const)('%s socket produces matching request and event scope, withdrawing only its own draft', async kind => {
  render(<Harness />)
  await act(() => vi.advanceTimersByTimeAsync(100))
  let socket = FakeWebSocket.instances[0] as FixtureSocket
  expect(socket.readyState).toBe(FakeWebSocket.OPEN)

  if (kind === 'owner-routed') {
    let opening: Promise<unknown>
    act(() => { opening = ensureGatewayForAgent('fixture-secondary', 'worker') })
    await act(() => vi.advanceTimersByTimeAsync(100))
    await opening!
    socket = FakeWebSocket.instances.at(-1) as FixtureSocket
    expect(socket).not.toBe(FakeWebSocket.instances[0])
  } else {
    // The published route, not a temporarily replaced descriptor, owns this socket.
    expect($primaryGatewayRoute.get().connectionId).toBe('fixture-primary')
    $connection.set({ ...primary, connectionId: 'stale-descriptor' } as never)
  }

  act(() => receiveRequest(socket, 'owned-request'))
  const scoped = requests.at(-1)!
  expect(scoped).toBeDefined()
  const request = sessionSecretRequest('s1', scoped).get()!
  expect(request?.requestId).toBe('owned-request')
  const other = { ...request, connectionId: 'other-source', requestId: 'other-request' }
  setSecretRequest(other)
  writeSecretDraft(other, 'dummy-other')
  writeSecretDraft(request, 'dummy-owned')
  act(() => receiveEvent(socket, 'request.cancel', { id: 'owned-request', method: 'secret', reason: 'resolved' }))
  const event = events.at(-1)!
  expect({ connectionId: scoped.connectionId, profile: scoped.profile }).toEqual({ connectionId: event.connectionId, profile: event.profile })
  expect(sessionSecretRequest('s1', scoped).get()).toBeNull()
  expect(readSecretDraft(request)).toBe('')
  expect(readSecretDraft(other)).toBe('dummy-other')
})

it.each(['active', 'background'])('same-owner %s completion clears the request without touching a colliding owner', async focus => {
  render(<Harness />)
  await act(() => vi.advanceTimersByTimeAsync(100))
  const socket = FakeWebSocket.instances[0] as FixtureSocket
  act(() => receiveRequest(socket, 'owned-request'))
  const scoped = requests.at(-1)!
  const request = sessionSecretRequest('s1', scoped).get()!
  const other = { ...request, connectionId: 'other-source', requestId: 'other-request' }
  setSecretRequest(other)
  writeSecretDraft(request, 'dummy-owned')
  writeSecretDraft(other, 'dummy-other')

  if (focus === 'background') { act(() => $activeSessionId.set('s2')) }
  act(() => receiveEvent(socket, 'message.complete', { text: 'Finished' }))
  expect(sessionSecretRequest('s1', scoped).get()).toBeNull()
  expect(readSecretDraft(request)).toBe('')
  expect(readSecretDraft(other)).toBe('dummy-other')
})
