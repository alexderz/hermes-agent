import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { atom } from 'nanostores'
import { afterEach, expect, it } from 'vitest'

import { ChatRuntimeBoundary } from '@/app/chat'
import { PRIMARY_SESSION_VIEW, SessionViewProvider } from '@/app/chat/session-view'
import { stubThreadEnvironment, stubThreadViewportSize } from '@/components/assistant-ui/test-utils'
import { Thread } from '@/components/assistant-ui/thread'
import { I18nProvider } from '@/i18n'
import type { ChatMessage } from '@/lib/chat-messages'
import { $activeGatewayProfile } from '@/store/profile'
import { clearAllPrompts, setSecretRequest } from '@/store/prompts'
import { $activeSessionId } from '@/store/session'

stubThreadEnvironment()
stubThreadViewportSize()
afterEach(() => { cleanup(); clearAllPrompts(); $activeSessionId.set(null) })

it('does not adopt the only unrelated clarify for a skill-origin secret', async () => {
  const messages: ChatMessage[] = [
    { id: 'old', role: 'assistant', pending: true, parts: [{ type: 'text', text: 'unrelated' }, { type: 'tool-call', toolCallId: 'old-call', toolName: 'clarify', args: { question: 'Choose colour' }, argsText: '{}' }] },
    { id: 'user-current', role: 'user', parts: [{ type: 'text', text: 'Run skill' }] },
    { id: 'skill', role: 'assistant', pending: true, parts: [{ type: 'text', text: 'skill-origin' }, { type: 'tool-call', toolCallId: 'skill-call', toolName: 'skill_view', args: {}, argsText: '{}' }] }
  ]

  const view = { ...PRIMARY_SESSION_VIEW, $messages: atom(messages), $runtimeId: atom<string | null>('s1'), $storedId: atom<string | null>(null) }
  $activeSessionId.set('s1')
  $activeGatewayProfile.set('default')
  setSecretRequest({ sessionId: 's1', requestId: 'r2', envVar: 'TEST_KEY', prompt: 'Enter key', profile: 'default' })
  render(<I18nProvider configClient={null}><SessionViewProvider value={view}><ChatRuntimeBoundary busy onCancel={() => {}} onEdit={async () => {}} onReload={async () => {}} onThreadMessagesChange={() => {}} suppressMessages={false}><Thread /></ChatRuntimeBoundary></SessionViewProvider></I18nProvider>)
  const input = await screen.findByLabelText('TEST_KEY')
  expect(input.closest('[data-message-id]')?.getAttribute('data-message-id')).toBe('skill')
})

it('anchors ahead of a prompt already queued for the next turn', async () => {
  const messages: ChatMessage[] = [
    { id: 'current-user', role: 'user', parts: [{ type: 'text', text: 'Run skill' }] },
    { id: 'current-skill', role: 'assistant', pending: true, parts: [{ type: 'text', text: 'current skill' }, { type: 'tool-call', toolCallId: 'skill-call', toolName: 'skill_view', args: {}, argsText: '{}' }] },
    { id: 'user-queued-next', role: 'user', parts: [{ type: 'text', text: 'queued next' }] }
  ]

  const view = { ...PRIMARY_SESSION_VIEW, $messages: atom(messages), $runtimeId: atom<string | null>('s1'), $storedId: atom<string | null>(null) }
  $activeSessionId.set('s1')
  $activeGatewayProfile.set('default')
  setSecretRequest({ sessionId: 's1', requestId: 'r3', envVar: 'TEST_KEY', prompt: 'Enter key', profile: 'default' })
  render(<I18nProvider configClient={null}><SessionViewProvider value={view}><ChatRuntimeBoundary busy onCancel={() => {}} onEdit={async () => {}} onReload={async () => {}} onThreadMessagesChange={() => {}} suppressMessages={false}><Thread /></ChatRuntimeBoundary></SessionViewProvider></I18nProvider>)
  const input = await screen.findByLabelText('TEST_KEY')
  expect(input.closest('[data-message-id]')?.getAttribute('data-message-id')).toBe('current-skill')
})

it('binds the secret clarify rather than an unrelated clarify arriving later', async () => {
  const first: ChatMessage = { id: 'secret-row', role: 'assistant', pending: true, parts: [{ type: 'text', text: 'secret-origin' }, { type: 'tool-call', toolName: 'clarify', toolCallId: 'secret-call', args: { secret_env: 'TEST_KEY' }, argsText: '{}' }] }
  const other: ChatMessage = { id: 'other-row', role: 'assistant', pending: true, parts: [{ type: 'text', text: 'other-origin' }, { type: 'tool-call', toolName: 'clarify', toolCallId: 'other-call', args: { question: 'Choose a colour' }, argsText: '{}' }] }
  const $messages = atom([first])
  const view = { ...PRIMARY_SESSION_VIEW, $messages, $runtimeId: atom<string | null>('s1'), $storedId: atom<string | null>(null) }
  $activeSessionId.set('s1')
  $activeGatewayProfile.set('default')
  setSecretRequest({ sessionId: 's1', requestId: 'r1', envVar: 'TEST_KEY', prompt: 'Enter key', profile: 'default' })
  render(<I18nProvider configClient={null}><SessionViewProvider value={view}><ChatRuntimeBoundary busy onCancel={() => {}} onEdit={async () => {}} onReload={async () => {}} onThreadMessagesChange={() => {}} suppressMessages={false}><Thread /></ChatRuntimeBoundary></SessionViewProvider></I18nProvider>)
  const input = await screen.findByLabelText('TEST_KEY')
  input.focus()
  fireEvent.change(input, { target: { value: 'dummy' } })
  act(() => $messages.set([first, other]))
  expect(screen.getByLabelText('TEST_KEY')).toBe(input)
  expect(input.closest('[data-message-id]')?.getAttribute('data-message-id')).toBe('secret-row')
  expect(window.document.activeElement).toBe(input)
})
