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
import { projectSecret } from '@/lib/secret-projection'
import { $gateway } from '@/store/gateway'
import { $activeGatewayProfile } from '@/store/profile'
import { clearAllPrompts, readSecretDraft, setSecretRequest } from '@/store/prompts'
import { rememberServerRequest, resetServerRequestsForTests } from '@/store/server-requests'
import { $activeSessionId, $connection } from '@/store/session'
import type { SessionMessage } from '@/types/hermes'

stubThreadEnvironment()
stubThreadViewportSize()
const request = { sessionId: 's1', requestId: 'no-host', envVar: 'TEST_KEY', prompt: 'Enter key', profile: 'default' }
const anchorOf = (input: HTMLElement) => input.closest('[data-message-id]')?.getAttribute('data-message-id')

const earlierRows = (text: string): SessionMessage[] => [
  { id: 1, role: 'user', content: text, timestamp: 100 },
  { id: 2, role: 'assistant', content: 'Earlier reply', timestamp: 101 }
]

afterEach(() => {
  cleanup()
  clearAllPrompts()
  resetServerRequestsForTests()
  $gateway.set(null)
  $activeSessionId.set(null)
  $connection.set(null)
})

function mount(messages: ChatMessage[]) {
  const respond = vi.fn()
  $activeSessionId.set('s1')
  $activeGatewayProfile.set('default')
  $gateway.set({ request: vi.fn() } as never)
  setSecretRequest(request)
  rememberServerRequest({ id: request.requestId, method: 'secret', params: {}, respond, fail: vi.fn() })
  const $messages = atom(messages)
  const view = { ...PRIMARY_SESSION_VIEW, $messages, $runtimeId: atom<string | null>('s1'), $storedId: atom<string | null>(null) }
  render(<I18nProvider configClient={null}><SessionViewProvider value={view}>
    <ChatRuntimeBoundary busy onCancel={() => {}} onEdit={async () => {}} onReload={async () => {}} onThreadMessagesChange={() => {}} suppressMessages={false}>
      <Thread />
    </ChatRuntimeBoundary>
  </SessionViewProvider></I18nProvider>)

  return { $messages, respond }
}

const repeatedPrompts = ['yes', 'continue', 'Set up the key'].flatMap(text =>
  ['empty', 'text-only'].flatMap(host => [true, false].map(timestamp => ({ text, host, timestamp }))))

it.each(repeatedPrompts)('recovers repeated "$text" with $host host and client timestamp=$timestamp without borrowing an earlier or queued turn', async ({ text, host, timestamp }) => {
  const older = reconcileAuthoritativeMessages(earlierRows(text), [])
  const user: ChatMessage = { id: 'user-submission', role: 'user', ...(timestamp ? { timestamp: 200.123 } : {}), parts: [{ type: 'text', text }] }
  const assistant: ChatMessage = { id: 'assistant-live', role: 'assistant', pending: true, parts: [{ type: 'text', text: 'Preparing request' }] }
  const live = [...older, user, ...(host === 'text-only' ? [assistant] : [])]
  const { $messages, respond } = mount(live)
  const input = await screen.findByLabelText('TEST_KEY') as HTMLInputElement
  fireEvent.change(input, { target: { value: 'dummy-repeated' } })
  input.focus()
  const originalAnchor = anchorOf(input)
  const queued: ChatMessage = { id: 'user-queued-future', role: 'user', parts: [{ type: 'text', text }] }
  act(() => $messages.set([...live.map<ChatMessage>(row => row.id === assistant.id ? { ...row, parts: [{ type: 'text', text: 'Preparing request, still working' }] } : row), queued]))
  await waitFor(() => expect(window.document.querySelector('[data-message-id="user-queued-future"]')).toBeTruthy())
  expect(screen.getByLabelText('TEST_KEY')).toBe(input)
  expect(window.document.activeElement).toBe(input)
  expect(anchorOf(input)).toBe(originalAnchor)

  const rows: SessionMessage[] = [...earlierRows(text),
    { id: 3, role: 'user', content: text, timestamp: 200.456 },
    ...(host === 'text-only' ? [{ id: 4, role: 'assistant' as const, content: 'Preparing request, still working after reconnect', timestamp: 201 }] : [])
  ]

  const reconciled = reconcileAuthoritativeMessages(rows, $messages.get(), { session_id: 's1', inflight: null, queued: { user: text } })
  expect(reconciled.find(row => row.rowId === 3)?.id).not.toBe(user.id)
  expect(reconciled.find(row => row.rowId === 3)?.timestamp).not.toBe(user.timestamp)
  act(() => $messages.set(reconciled))
  await waitFor(() => expect(window.document.querySelector('[data-message-id="200.456-2-user"]')).toBeTruthy())
  const restored = screen.getByLabelText('TEST_KEY') as HTMLInputElement
  expect(restored.value).toBe('dummy-repeated')
  const order = Array.from(window.document.querySelectorAll('[data-message-id]'), element => element.getAttribute('data-message-id'))
  expect(order.indexOf(anchorOf(restored) ?? '')).toBeGreaterThan(order.indexOf('200.456-2-user'))
  expect(order.indexOf(anchorOf(restored) ?? '')).toBeLessThan(order.indexOf('user-queued-s1'))
  expect(anchorOf(restored)).not.toBe(older[1].id)
  expect(JSON.stringify(projectSecret(reconciled, request))).not.toContain('dummy-repeated')
  act(() => setSecretRequest({ ...request }))
  expect(screen.getAllByLabelText('TEST_KEY')).toHaveLength(1)
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(respond).toHaveBeenCalledExactlyOnceWith({ value: 'dummy-repeated' })
  expect(readSecretDraft(request)).toBe('')
})

it.each(['durable', 'optimistic receipt'])('keeps partial completed %s history provisional until the actual in-flight turn arrives', async kind => {
  const oldRows: SessionMessage[] = [
    { id: 1, role: 'user', content: 'Earlier request', timestamp: 100 },
    { id: 2, role: 'assistant', content: '', timestamp: 101, tool_calls: [{ id: 'old-call', type: 'function', function: { name: 'terminal', arguments: '{}' } }] },
    { role: 'tool', content: 'ok', tool_call_id: 'old-call', name: 'terminal', timestamp: 102 }
  ]

  const older = reconcileAuthoritativeMessages(oldRows, []).map(row => kind === 'optimistic receipt' && row.role === 'user'
    ? { ...row, id: 'user-old-submission' } : row)

  const { $messages } = mount(older)
  const input = await screen.findByLabelText('TEST_KEY') as HTMLInputElement
  expect(anchorOf(input)).toBe(`secret-message:${request.requestId}`)
  fireEvent.change(input, { target: { value: 'dummy-partial' } })
  input.focus()
  act(() => setSecretRequest({ ...request }))
  expect(screen.getByLabelText('TEST_KEY')).toBe(input)
  expect(window.document.activeElement).toBe(input)

  const full = reconcileAuthoritativeMessages(oldRows, older, {
    session_id: 's1', inflight: { user: 'Set up the key', assistant: 'Actual in-flight reply', streaming: true }
  })

  act(() => $messages.set(full))
  await screen.findByText('Actual in-flight reply')
  expect(anchorOf(screen.getByLabelText('TEST_KEY'))).toBe(full.findLast(row => row.role === 'assistant')?.id)
  expect((screen.getByLabelText('TEST_KEY') as HTMLInputElement).value).toBe('dummy-partial')
})

it('keeps an established skill-origin card and focus after the skill result settles', async () => {
  const user: ChatMessage = { id: 'user-current', role: 'user', parts: [{ type: 'text', text: 'Set up the key' }] }
  const skill: ChatMessage = { id: 'skill-live', role: 'assistant', pending: true, parts: [{ type: 'tool-call', toolCallId: 'skill-call', toolName: 'skill_view', args: {}, argsText: '{}' }] }
  const { $messages, respond } = mount([user, skill])
  const input = await screen.findByLabelText('TEST_KEY') as HTMLInputElement
  fireEvent.change(input, { target: { value: 'dummy-result' } })
  input.focus()
  act(() => $messages.set([user, { ...skill, pending: false, parts: skill.parts.map(part => part.type === 'tool-call' ? { ...part, result: 'Loaded skill' } : part) }]))
  await waitFor(() => expect($messages.get()[1].pending).toBe(false))
  expect(screen.getByLabelText('TEST_KEY')).toBe(input)
  expect(window.document.activeElement).toBe(input)
  expect(anchorOf(input)).toBe(skill.id)
  expect(input.value).toBe('dummy-result')
  expect(respond).not.toHaveBeenCalled()
})

it('learns an authoritative user_row_id receipt arriving after the request was bound', async () => {
  const older = reconcileAuthoritativeMessages(earlierRows('continue'), [])
  const user: ChatMessage = { id: 'user-submission', role: 'user', parts: [{ type: 'text', text: 'continue' }] }
  const { $messages } = mount([...older, user])
  fireEvent.change(await screen.findByLabelText('TEST_KEY'), { target: { value: 'dummy-receipt' } })
  act(() => $messages.set([...older, { ...user, rowId: 3 }]))
  await waitFor(() => expect($messages.get().at(-1)?.rowId).toBe(3))
  const reconciled = reconcileAuthoritativeMessages([...earlierRows('continue'), { id: 3, role: 'user', content: 'continue', timestamp: 200 }], $messages.get())
  act(() => $messages.set(reconciled))
  await waitFor(() => expect(window.document.querySelector('[data-message-id="200-2-user"]')).toBeTruthy())
  expect((screen.getByLabelText('TEST_KEY') as HTMLInputElement).value).toBe('dummy-receipt')
})

it('keeps an ambiguous no-host request answerable without choosing the latest matching prompt', async () => {
  const older = reconcileAuthoritativeMessages(earlierRows('continue'), [])
  const { $messages, respond } = mount([...older, { id: 'user-submission', role: 'user', parts: [{ type: 'text', text: 'continue' }] }])
  fireEvent.change(await screen.findByLabelText('TEST_KEY'), { target: { value: 'dummy-ambiguous' } })

  const uncertain = reconcileAuthoritativeMessages([...earlierRows('continue'),
    { id: 3, role: 'user', content: 'continue', timestamp: 200 },
    { id: 4, role: 'user', content: 'continue', timestamp: 300 }
  ], $messages.get())

  act(() => $messages.set(uncertain))
  await waitFor(() => expect(window.document.querySelector('[data-message-id="300-3-user"]')).toBeTruthy())
  const input = screen.getByLabelText('TEST_KEY') as HTMLInputElement
  expect(anchorOf(input)).toBe(`secret-message:${request.requestId}`)
  expect(input.value).toBe('dummy-ambiguous')
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(respond).toHaveBeenCalledExactlyOnceWith({ value: 'dummy-ambiguous' })
  expect(readSecretDraft(request)).toBe('')
})

it('does not mistake newly backfilled older history for the missing live turn', async () => {
  const known: SessionMessage[] = [
    { id: 10, role: 'user', content: 'Other previous prompt', timestamp: 100 },
    { id: 11, role: 'assistant', content: 'Known previous reply', timestamp: 101 }
  ]

  const live: ChatMessage[] = [...reconcileAuthoritativeMessages(known, []), { id: 'user-current', role: 'user', parts: [{ type: 'text', text: 'continue' }] }]
  const { $messages } = mount(live)
  fireEvent.change(await screen.findByLabelText('TEST_KEY'), { target: { value: 'dummy-backfill' } })

  const backfilled: SessionMessage[] = [
    { id: 1, role: 'user', content: 'continue', timestamp: 1 },
    { id: 2, role: 'assistant', content: 'Newly loaded older reply', timestamp: 2 },
    ...known
  ]

  act(() => $messages.set(reconcileAuthoritativeMessages(backfilled, [])))
  await screen.findByText('Newly loaded older reply')
  expect(anchorOf(screen.getByLabelText('TEST_KEY'))).toBe(`secret-message:${request.requestId}`)
  act(() => $messages.set(reconcileAuthoritativeMessages([...backfilled,
    { id: 12, role: 'user', content: 'continue', timestamp: 200 },
    { id: 13, role: 'assistant', content: 'Current reply finally arrived', timestamp: 201 }
  ], [])))
  await screen.findByText('Current reply finally arrived')
  expect(anchorOf(screen.getByLabelText('TEST_KEY'))).toBe('201-5-assistant')
  expect((screen.getByLabelText('TEST_KEY') as HTMLInputElement).value).toBe('dummy-backfill')
})

it('prefers conflicting durable row ids over a coincidentally identical rendered message id', async () => {
  const original = reconcileAuthoritativeMessages([
    { id: 11, role: 'user', content: 'continue', timestamp: 100 },
    { id: 12, role: 'assistant', content: 'Original live reply', timestamp: 101 }
  ], []).map(row => row.role === 'assistant' ? { ...row, pending: true } : row)

  const { $messages, respond } = mount(original)
  fireEvent.change(await screen.findByLabelText('TEST_KEY'), { target: { value: 'dummy-conflict' } })

  const conflict = reconcileAuthoritativeMessages([
    { id: 22, role: 'user', content: 'continue', timestamp: 100 },
    { id: 23, role: 'assistant', content: 'Conflicting durable turn', timestamp: 101 }
  ], [])

  expect(conflict.map(row => row.id)).toEqual(original.map(row => row.id))
  act(() => $messages.set(conflict))
  await screen.findByText('Conflicting durable turn')
  const input = screen.getByLabelText('TEST_KEY') as HTMLInputElement
  expect(anchorOf(input)).toBe(`secret-message:${request.requestId}`)
  expect(input.value).toBe('dummy-conflict')
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(respond).toHaveBeenCalledExactlyOnceWith({ value: 'dummy-conflict' })
  expect(readSecretDraft(request)).toBe('')
})

it('keeps a first-turn no-host request local when only an older completed same-prose turn is resumed', async () => {
  const { $messages, respond } = mount([{ id: 'user-first', role: 'user', parts: [{ type: 'text', text: 'go' }] }])
  fireEvent.change(await screen.findByLabelText('TEST_KEY'), { target: { value: 'dummy-first' } })

  const older = reconcileAuthoritativeMessages([
    { id: 5, role: 'user', content: 'go', timestamp: 50 },
    { id: 6, role: 'assistant', content: 'Older completed reply', timestamp: 51 }
  ], [])

  act(() => $messages.set(older))
  await screen.findByText('Older completed reply')
  const input = screen.getByLabelText('TEST_KEY') as HTMLInputElement
  expect(anchorOf(input)).toBe(`secret-message:${request.requestId}`)
  expect(input.value).toBe('dummy-first')
  expect(respond).not.toHaveBeenCalled()
})

it('recovers a first-turn no-host request when the actual pending turn returns after partial older history', async () => {
  const { $messages, respond } = mount([{ id: 'user-first', role: 'user', parts: [{ type: 'text', text: 'go' }] }])
  fireEvent.change(await screen.findByLabelText('TEST_KEY'), { target: { value: 'dummy-return' } })

  const olderRows: SessionMessage[] = [
    { id: 5, role: 'user', content: 'go', timestamp: 50 },
    { id: 6, role: 'assistant', content: 'Older completed reply', timestamp: 51 }
  ]

  act(() => $messages.set(reconcileAuthoritativeMessages(olderRows, [])))
  await screen.findByText('Older completed reply')

  const active = reconcileAuthoritativeMessages(olderRows, [], {
    session_id: 's1', inflight: { user: 'go', assistant: 'Actual pending reply returns', streaming: true }, queued: null
  })

  act(() => $messages.set(active))
  await screen.findByText('Actual pending reply returns')
  const input = screen.getByLabelText('TEST_KEY') as HTMLInputElement
  expect(anchorOf(input)).toBe(active.findLast(row => row.role === 'assistant')?.id)
  expect(input.value).toBe('dummy-return')
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(respond).toHaveBeenCalledExactlyOnceWith({ value: 'dummy-return' })
})

it('keeps the same conflict-fallback input and focus across appended rows, then releases its placement on Save and Cancel', async () => {
  const original = reconcileAuthoritativeMessages([
    { id: 11, role: 'user', content: 'go', timestamp: 100 },
    { id: 12, role: 'assistant', content: 'Original pending reply', timestamp: 101 }
  ], []).map(row => row.role === 'assistant' ? { ...row, pending: true } : row)

  const { $messages, respond } = mount(original)
  fireEvent.change(await screen.findByLabelText('TEST_KEY'), { target: { value: 'dummy-focus' } })

  const conflict = reconcileAuthoritativeMessages([
    { id: 22, role: 'user', content: 'go', timestamp: 100 },
    { id: 23, role: 'assistant', content: 'Conflicting durable reply', timestamp: 101 }
  ], [])

  act(() => $messages.set(conflict))
  await screen.findByText('Conflicting durable reply')
  const input = screen.getByLabelText('TEST_KEY') as HTMLInputElement
  input.focus()
  expect(anchorOf(input)).toBe(`secret-message:${request.requestId}`)

  const appended: ChatMessage[] = [
    { id: 'parallel-text', role: 'assistant', pending: true, parts: [{ type: 'text', text: 'Parallel progress' }] },
    { id: 'parallel-tool', role: 'assistant', pending: true, parts: [{ type: 'tool-call', toolCallId: 'parallel-call', toolName: 'skill_view', args: {}, argsText: '{}', result: 'Fixture loaded' }] }
  ]

  for (const row of appended) {
    act(() => $messages.set([...$messages.get(), row]))
    await waitFor(() => expect(window.document.querySelector(`[data-message-id="${row.id}"]`)).toBeTruthy())
    expect(screen.getByLabelText('TEST_KEY')).toBe(input)
    expect(window.document.activeElement).toBe(input)
    expect(input.value).toBe('dummy-focus')
  }

  act(() => $messages.set([...$messages.get(), { id: 'user-queued-next', role: 'user', parts: [{ type: 'text', text: 'Queued future request' }] }]))
  await screen.findByText('Queued future request')
  act(() => setSecretRequest({ ...request }))
  expect(screen.getByLabelText('TEST_KEY')).toBe(input)
  expect(window.document.activeElement).toBe(input)
  const ids = Array.from(window.document.querySelectorAll('[data-message-id]'), row => row.getAttribute('data-message-id'))
  expect(ids.indexOf(anchorOf(input) ?? '')).toBeLessThan(ids.indexOf('parallel-text'))
  expect(ids.indexOf(anchorOf(input) ?? '')).toBeLessThan(ids.indexOf('user-queued-next'))
  expect(JSON.stringify(projectSecret($messages.get(), request))).not.toContain('dummy-focus')
  expect(respond).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  expect(respond).toHaveBeenCalledExactlyOnceWith({ value: 'dummy-focus' })
  expect(readSecretDraft(request)).toBe('')

  act(() => {
    $messages.set([...conflict, { id: 'later-settled', role: 'assistant', parts: [{ type: 'text', text: 'Later settled reply' }] }])
    rememberServerRequest({ id: request.requestId, method: 'secret', params: {}, respond, fail: vi.fn() })
    setSecretRequest(request)
  })
  await waitFor(() => {
    const current = screen.getByLabelText('TEST_KEY')
    const currentIds = Array.from(window.document.querySelectorAll('[data-message-id]'), row => row.getAttribute('data-message-id'))
    expect(currentIds.indexOf(anchorOf(current) ?? '')).toBeGreaterThan(currentIds.indexOf('later-settled'))
  })
  const nextInput = await screen.findByLabelText('TEST_KEY') as HTMLInputElement
  const nextIds = Array.from(window.document.querySelectorAll('[data-message-id]'), row => row.getAttribute('data-message-id'))
  expect(nextIds.indexOf(anchorOf(nextInput) ?? '')).toBeGreaterThan(nextIds.indexOf('later-settled'))
  expect(nextInput.value).toBe('')
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  expect(respond).toHaveBeenCalledTimes(2)
  expect(respond).toHaveBeenLastCalledWith({ value: '' })
  expect(readSecretDraft(request)).toBe('')
})
