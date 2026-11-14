import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { atom } from 'nanostores'
import { afterEach, expect, it, vi } from 'vitest'

import { ChatRuntimeBoundary } from '@/app/chat'
import { PRIMARY_SESSION_VIEW, SessionViewProvider } from '@/app/chat/session-view'
import { reconcileAuthoritativeMessages } from '@/app/session/hooks/use-session-actions/resume-reconcile'
import { stubThreadEnvironment, stubThreadViewportSize } from '@/components/assistant-ui/test-utils'
import { Thread } from '@/components/assistant-ui/thread'
import { I18nProvider } from '@/i18n'
import type { ChatMessage } from '@/lib/chat-messages'
import { $gateway } from '@/store/gateway'
import { $activeGatewayProfile } from '@/store/profile'
import { clearAllPrompts, clearSecretRequest, readSecretDraft, setSecretRequest } from '@/store/prompts'
import { rememberServerRequest, resetServerRequestsForTests } from '@/store/server-requests'
import { $activeSessionId, $connection } from '@/store/session'
import type { SessionMessage } from '@/types/hermes'

stubThreadEnvironment()
stubThreadViewportSize()
const respond = vi.fn()
const request = { sessionId: 's1', requestId: 'r1', envVar: 'TEST_KEY', prompt: 'Enter key', profile: 'default' }
const user = (id: string, text = 'Set up key'): ChatMessage => ({ id, role: 'user', timestamp: 1700000000.25, parts: [{ type: 'text', text }] })

const host = (id: string, toolName: string, args: Record<string, string | { name: string }>, toolCallId = 'current-call'): ChatMessage => ({
  id, role: 'assistant', pending: true,
  parts: [{ type: 'tool-call', toolCallId, toolName, args, argsText: JSON.stringify(args) }]
})

const anchor = (input: HTMLElement) => input.closest('[data-message-id]')?.getAttribute('data-message-id')

afterEach(() => {
  cleanup()
  clearAllPrompts()
  resetServerRequestsForTests()
  respond.mockClear()
  $gateway.set(null)
  $activeSessionId.set(null)
  $connection.set(null)
})

function mount(messages: ChatMessage[]) {
  $activeSessionId.set('s1')
  $activeGatewayProfile.set('default')
  setSecretRequest(request)
  $gateway.set({ request: vi.fn() } as never)
  rememberServerRequest({ id: request.requestId, method: 'secret', params: {}, respond, fail: vi.fn() })
  const $messages = atom(messages)
  const view = { ...PRIMARY_SESSION_VIEW, $messages, $runtimeId: atom<string | null>('s1'), $storedId: atom<string | null>(null) }
  render(<I18nProvider configClient={null}><SessionViewProvider value={view}>
    <ChatRuntimeBoundary busy onCancel={() => {}} onEdit={async () => {}} onReload={async () => {}} onThreadMessagesChange={() => {}} suppressMessages={false}>
      <Thread />
    </ChatRuntimeBoundary>
  </SessionViewProvider></I18nProvider>)

  return $messages
}

it.each([
  ['skill_view', { name: 'fixture' }],
  ['clarify', { secret_env: 'TEST_KEY' }],
  ['clarify', { secret_file: { name: 'TEST_KEY' } }]
] as const)('retains the %s card and draft when authoritative reconciliation replaces live IDs (%j)', async (toolName, args) => {
  const live = [user('user-submission'), host('live-tool:current', toolName, args)]
  const $messages = mount(live)
  const input = await screen.findByLabelText('TEST_KEY') as HTMLInputElement
  fireEvent.change(input, { target: { value: 'dummy-draft' } })
  input.focus()
  act(() => $messages.set([
    { ...live[0] },
    { ...live[1], parts: [...live[1].parts, { type: 'text', text: 'Still loading' }] },
    { id: 'parallel-row', role: 'assistant', pending: true, parts: [{ type: 'text', text: 'Parallel progress' }] },
    user('user-queued-next', 'Future submission')
  ]))
  await screen.findByText('Parallel progress')
  expect(screen.getByLabelText('TEST_KEY')).toBe(input)
  expect(window.document.activeElement).toBe(input)
  expect(anchor(input)).toBe('live-tool:current')

  const rows: SessionMessage[] = [
    { role: 'user', content: 'Set up key', timestamp: 1700000000 },
    { role: 'assistant', content: 'Still loading after reconnect', timestamp: 1700000001, tool_calls: [
      { id: 'current-call', type: 'function', function: { name: toolName, arguments: JSON.stringify(args) } }
    ] }
  ]

  const reconciled = reconcileAuthoritativeMessages(rows, $messages.get())
  expect(reconciled.some(message => message.id === 'live-tool:current')).toBe(false)
  act(() => $messages.set(reconciled))
  const expectedAnchor = reconciled.find(message => message.parts.some(part => part.type === 'tool-call' && part.toolCallId === 'current-call'))?.id
  await waitFor(() => expect(anchor(screen.getByLabelText('TEST_KEY'))).toBe(expectedAnchor))
  const restored = screen.getByLabelText('TEST_KEY') as HTMLInputElement
  expect(restored.value).toBe('dummy-draft')
  expect(readSecretDraft(request)).toBe('dummy-draft')
  act(() => setSecretRequest({ ...request }))
  expect(screen.getAllByLabelText('TEST_KEY')).toHaveLength(1)
  expect((screen.getByLabelText('TEST_KEY') as HTMLInputElement).value).toBe('dummy-draft')
})

it('re-resolves an empty-assistant anchor after the user ID changes on hydration', async () => {
  const live = [user('user-submission')]
  const $messages = mount(live)
  fireEvent.change(await screen.findByLabelText('TEST_KEY'), { target: { value: 'dummy-empty' } })
  const reconciled = reconcileAuthoritativeMessages([{ role: 'user', content: 'Set up key', timestamp: 1700000000 }], live)
  expect(reconciled[0].id).not.toBe(live[0].id)
  act(() => $messages.set(reconciled))
  await waitFor(() => expect(window.document.querySelector(`[data-message-id="${reconciled[0].id}"]`)).toBeTruthy())
  expect((screen.getByLabelText('TEST_KEY') as HTMLInputElement).value).toBe('dummy-empty')
  const order = Array.from(window.document.querySelectorAll('[data-message-id]'), element => element.getAttribute('data-message-id'))
  expect(order.indexOf('secret-message:r1')).toBeGreaterThan(order.indexOf(reconciled[0].id))
})

it('places replay-before-history in the current started turn, not above old history or under a queued turn', async () => {
  const $messages = mount([])
  fireEvent.change(await screen.findByLabelText('TEST_KEY'), { target: { value: 'dummy-early' } })

  const history = reconcileAuthoritativeMessages([
    { role: 'user', content: 'Old request', timestamp: 1 },
    { role: 'assistant', content: 'Old reply', timestamp: 2 },
    { role: 'user', content: 'Set up key', timestamp: 3 },
    { role: 'assistant', content: 'Loading skill', timestamp: 4, tool_calls: [
      { id: 'current-call', type: 'function', function: { name: 'skill_view', arguments: '{}' } }
    ] }
  ], [])

  act(() => $messages.set([...history, user('user-queued-next', 'Future submission')]))
  await screen.findByText('Old reply')
  const input = screen.getByLabelText('TEST_KEY') as HTMLInputElement
  // Settled history alone is provisional until the in-flight snapshot arrives.
  expect(anchor(input)).toBe(`secret-message:${request.requestId}`)
  const ids = Array.from(window.document.querySelectorAll('[data-message-id]'), row => row.getAttribute('data-message-id'))
  expect(ids.indexOf(anchor(input) ?? '')).toBeGreaterThan(ids.indexOf(history.at(-1)?.id ?? ''))
  expect(ids.indexOf(anchor(input) ?? '')).toBeLessThan(ids.indexOf('user-queued-next'))
  expect(input.value).toBe('dummy-early')
})

it.each(['secret_env', 'secret_file'])('Stop then retry does not adopt the previous interrupted %s clarify', async kind => {
  const args: Parameters<typeof host>[2] = kind === 'secret_env' ? { secret_env: 'TEST_KEY' } : { secret_file: { name: 'TEST_KEY' } }
  const previous = host('old-clarify', 'clarify', args)
  previous.parts = previous.parts.map(part => part.type === 'tool-call' ? { ...part, toolCallId: 'old-call' } : part)
  const $messages = mount([user('old-user', 'Old request'), previous])
  await screen.findByLabelText('TEST_KEY')
  act(() => clearSecretRequest('s1', request.requestId, request))
  expect(screen.queryByLabelText('TEST_KEY')).toBeNull()
  act(() => {
    $messages.set([user('old-user', 'Old request'), { ...previous, pending: false, interrupted: true }, user('retry-user'), host('current-skill', 'skill_view', {}), user('user-queued-next', 'Future submission')])
    setSecretRequest({ ...request, requestId: 'retry' })
  })
  expect(anchor(await screen.findByLabelText('TEST_KEY'))).toBe('current-skill')
})

it('does not transfer a card to a conflicting durable turn with identical prompt text and timestamp', async () => {
  const $messages = mount([{ ...user('original-user'), rowId: 11 }, host('original-skill', 'skill_view', {})])
  fireEvent.change(await screen.findByLabelText('TEST_KEY'), { target: { value: 'dummy-original' } })

  const otherTurn = reconcileAuthoritativeMessages([
    { role: 'user', id: 22, content: 'Set up key', timestamp: 1700000000.25 },
    { role: 'assistant', content: 'A different turn', timestamp: 1700000001, tool_calls: [
      { id: 'different-call', type: 'function', function: { name: 'skill_view', arguments: '{}' } }
    ] }
  ], [])

  act(() => $messages.set(otherTurn))
  await screen.findByText('A different turn')
  const input = screen.getByLabelText('TEST_KEY') as HTMLInputElement
  expect(anchor(input)).toBe(`secret-message:${request.requestId}`)
  expect(input.value).toBe('dummy-original')
  expect(readSecretDraft(request)).toBe('dummy-original')
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(respond).toHaveBeenCalledExactlyOnceWith({ value: 'dummy-original' })
  expect(readSecretDraft(request)).toBe('')
})

it('does not rebind an existing request to a different started turn after its origin disappears', async () => {
  const $messages = mount([user('original-user'), host('original-skill', 'skill_view', {})])
  fireEvent.change(await screen.findByLabelText('TEST_KEY'), { target: { value: 'dummy-original' } })
  act(() => $messages.set([user('different-user', 'Unrelated new turn'), host('different-skill', 'skill_view', {}, 'different-call')]))
  await screen.findByText('Unrelated new turn')
  const input = screen.getByLabelText('TEST_KEY') as HTMLInputElement
  expect(anchor(input)).toBe(`secret-message:${request.requestId}`)
  expect(input.value).toBe('dummy-original')
  expect(readSecretDraft(request)).toBe('dummy-original')
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(respond).toHaveBeenCalledExactlyOnceWith({ value: 'dummy-original' })
  expect(readSecretDraft(request)).toBe('')
})
