import { useStore } from '@nanostores/react'
import { act, cleanup, fireEvent, render, renderHook, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useRuntimeMessageRepository } from '@/app/chat/runtime-repository'
import { I18nProvider } from '@/i18n'
import { type ChatMessage, restorePendingClarifyToolCall } from '@/lib/chat-messages'
import { $gateway } from '@/store/gateway'
import { $notifications, clearNotifications } from '@/store/notifications'
import { $activeGatewayProfile } from '@/store/profile'
import {
  $secretRequest,
  clearAllPrompts,
  clearSecretRequest,
  readSecretDraft,
  type SecretRequest,
  setSecretRequest
} from '@/store/prompts'
import { rememberServerRequest, resetServerRequestsForTests } from '@/store/server-requests'
import { $activeSessionId, $connection } from '@/store/session'

import { SecretCard } from './secret-card'

const request: SecretRequest = {
  connectionId: 'conn-a',
  profile: 'default',
  sessionId: 's1',
  requestId: 'r1',
  envVar: 'TEST_KEY',
  prompt: 'Enter key'
}

const tree = (r: SecretRequest) => (
  <I18nProvider configClient={null}>
    <SecretCard key={JSON.stringify(r)} request={r} />
  </I18nProvider>
)

function ActiveSecret() {
  const active = useStore($secretRequest)

  return active ? <SecretCard key={JSON.stringify([active.connectionId, active.profile, active.sessionId, active.requestId])} request={active} /> : null
}

afterEach(() => {
  cleanup()
  clearAllPrompts()
  clearNotifications()
  resetServerRequestsForTests()
  $gateway.set(null)
  $activeSessionId.set(null)
  $activeGatewayProfile.set('default')
  $connection.set(null)
})

describe('inline secret entry', () => {
  it('keeps an in-memory draft across blur, visibility, scroll and session remount; isolates it by scope', () => {
    setSecretRequest(request)
    const respond = vi.fn()
    rememberServerRequest({ id: 'r1', method: 'secret', params: {}, respond, fail: vi.fn() })
    $gateway.set({ request: vi.fn() } as never)
    const view = render(tree(request))
    const input = screen.getByLabelText('TEST_KEY') as HTMLInputElement
    fireEvent.change(input, { target: { value: 'dummy-value' } })
    act(() => setSecretRequest({ ...request })) // open_requests replay of the same request
    expect(readSecretDraft(request)).toBe('dummy-value')
    fireEvent.blur(input)
    fireEvent(window.document, new Event('visibilitychange'))
    fireEvent.scroll(window)
    fireEvent.keyDown(input, { key: 'Escape' })
    fireEvent.pointerDown(window.document.body)
    expect(respond).not.toHaveBeenCalled()
    expect(input.value).toBe('dummy-value')
    const other = { ...request, sessionId: 's2', requestId: 'r2', profile: 'other' }
    expect(readSecretDraft({ ...request, profile: 'other' })).toBe('')
    expect(readSecretDraft({ ...request, connectionId: 'conn-b' })).toBe('')
    expect(readSecretDraft({ ...request, sessionId: 's2' })).toBe('')
    expect(readSecretDraft({ ...request, requestId: 'r2' })).toBe('')
    view.rerender(tree(other))
    expect((screen.getByLabelText('TEST_KEY') as HTMLInputElement).value).toBe('')
    view.rerender(tree(request))
    expect((screen.getByLabelText('TEST_KEY') as HTMLInputElement).value).toBe('dummy-value')
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(respond).toHaveBeenCalledExactlyOnceWith({ value: 'dummy-value' })
    expect(readSecretDraft(request)).toBe('')
  })

  it('keeps each session draft when the active session changes away and back', () => {
    const other = { ...request, sessionId: 's2', requestId: 'r2', profile: 'other' }
    $activeSessionId.set('s1')
    $connection.set({ connectionId: 'conn-a', mode: 'ssh' } as never)
    setSecretRequest(request)
    setSecretRequest(other)
    render(<I18nProvider configClient={null}><ActiveSecret /></I18nProvider>)
    fireEvent.change(screen.getByLabelText('TEST_KEY'), { target: { value: 'dummy-a' } })
    act(() => { $activeSessionId.set('s2'); $activeGatewayProfile.set('other') })
    expect((screen.getByLabelText('TEST_KEY') as HTMLInputElement).value).toBe('')
    fireEvent.change(screen.getByLabelText('TEST_KEY'), { target: { value: 'dummy-b' } })
    act(() => { $activeSessionId.set('s1'); $activeGatewayProfile.set('default') })
    expect((screen.getByLabelText('TEST_KEY') as HTMLInputElement).value).toBe('dummy-a')
    act(() => { $activeSessionId.set('s2'); $activeGatewayProfile.set('other') })
    expect((screen.getByLabelText('TEST_KEY') as HTMLInputElement).value).toBe('dummy-b')
  })

  it('wipes drafts on cancellation, including backend withdrawal', () => {
    setSecretRequest(request)
    const respond = vi.fn()
    rememberServerRequest({ id: 'r1', method: 'secret', params: {}, respond, fail: vi.fn() })
    $gateway.set({ request: vi.fn() } as never)
    const view = render(tree(request))
    fireEvent.change(screen.getByLabelText('TEST_KEY'), { target: { value: 'dummy-value' } })
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(respond).toHaveBeenCalledExactlyOnceWith({ value: '' })
    expect(readSecretDraft(request)).toBe('')
    view.unmount()
    setSecretRequest(request)
    render(tree(request))
    fireEvent.change(screen.getByLabelText('TEST_KEY'), { target: { value: 'other-dummy' } })
    act(() => clearSecretRequest('s1', 'r1', request))
    expect(readSecretDraft(request)).toBe('')
  })

  it('keeps an open draft across a stale running=false prompt cleanup', () => {
    setSecretRequest(request)
    rememberServerRequest({ id: 'r1', method: 'secret', params: {}, respond: vi.fn(), fail: vi.fn() })
    const view = render(tree(request))
    fireEvent.change(screen.getByLabelText('TEST_KEY'), { target: { value: 'dummy-value' } })
    clearAllPrompts('s1', true, request)
    expect(readSecretDraft(request)).toBe('dummy-value')
    view.unmount()
  })

  it.each(['Save', 'Cancel'])('wipes a stale draft and gives neutral feedback when %s finds no open server request', action => {
    setSecretRequest(request)
    $gateway.set({ request: vi.fn() } as never)
    render(tree(request))
    const input = screen.getByLabelText('TEST_KEY') as HTMLInputElement
    fireEvent.change(input, { target: { value: 'dummy-stale' } })
    fireEvent.click(screen.getByRole('button', { name: action }))
    expect(input.value).toBe('')
    expect(readSecretDraft(request)).toBe('')
    expect($notifications.get()).toMatchObject([{ kind: 'info', message: 'This request is no longer open.' }])
    expect(JSON.stringify($notifications.get())).not.toContain('dummy-stale')
    fireEvent.click(screen.getByRole('button', { name: action }))
    expect($notifications.get()).toHaveLength(1)
  })

  it('projects one request-bound clarify row and retains its binding through runtime normalization', () => {
    const base: ChatMessage[] = [
      {
        id: 'm1',
        role: 'assistant',
        pending: true,
        parts: [
          {
            type: 'tool-call',
            toolName: 'clarify',
            toolCallId: 'call1',
            args: { secret_env: 'TEST_KEY' },
            argsText: '{}'
          }
        ]
      }
    ]

    const first = restorePendingClarifyToolCall(base, { tool_id: 'r1', args: {} }).messages
    const replay = restorePendingClarifyToolCall(first, { tool_id: 'r1', args: {} }).messages
    const parts = replay.flatMap(message => message.parts.filter(part => part.type === 'tool-call'))
    expect(parts).toHaveLength(1)
    expect(parts[0]).toMatchObject({ clarifyRequestId: 'r1' })
    const { result } = renderHook(() => useRuntimeMessageRepository(replay))
    expect(result.current.messages[0].message.content[0]).toMatchObject({ clarifyRequestId: 'r1' })
  })
})
