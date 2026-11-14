import { useStore } from '@nanostores/react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  handleServerRequest,
  type ServerRequestContext
} from '@/app/session/hooks/use-message-stream/gateway-event/server-requests'
import { SecretCard } from '@/components/assistant-ui/clarify/secret-card'
import { I18nProvider } from '@/i18n'
import { createClientSessionState } from '@/lib/chat-runtime'
import { $gateway } from '@/store/gateway'
import { notify, notifyError } from '@/store/notifications'
import { sessionSecretRequest } from '@/store/prompts'
import { $secretRequest, $sudoRequest, clearAllPrompts, setSecretRequest, setSudoRequest } from '@/store/prompts'
import { hasOpenServerRequest, rememberServerRequest, resetServerRequestsForTests } from '@/store/server-requests'
import { $activeSessionId } from '@/store/session'

import { PromptOverlays } from './prompt-overlays'

vi.mock('@/lib/haptics', () => ({ triggerHaptic: vi.fn() }))
vi.mock('@/store/notifications', () => ({ notify: vi.fn(), notifyError: vi.fn() }))

function SecretHarness({ sessionId }: { sessionId: string | null }) {
  const request = useStore(sessionSecretRequest(sessionId))

  return request ? <SecretCard key={request.requestId} request={request} /> : null
}

function renderPrompts(sessionId: string | null = 's1') {
  render(
    <I18nProvider configClient={null}>
      <PromptOverlays sessionId={sessionId} />
      <SecretHarness sessionId={sessionId} />
    </I18nProvider>
  )
}

beforeEach(() => {
  resetServerRequestsForTests()
})

afterEach(() => {
  cleanup()
  clearAllPrompts()
  resetServerRequestsForTests()
  $activeSessionId.set(null)
  $gateway.set(null)
  vi.clearAllMocks()
})

describe('PromptOverlays', () => {
  it('shows the full command from the sudo request before accepting a password', () => {
    const command = `sudo install -m 755 '${'/tmp/path segment/'.repeat(24)}helper' /usr/local/bin/helper\n&& sudo /usr/local/bin/helper --version`
    const respond = vi.fn()

    const deps: ServerRequestContext['deps'] = {
      activeSessionIdRef: { current: 's1' },
      sessionInterrupted: () => false,
      sessionStateByRuntimeIdRef: { current: new Map() },
      updateSessionState: (_sid, update) => update(createClientSessionState('s1')),
      upsertToolCall: () => undefined
    }

    $activeSessionId.set('s1')
    $gateway.set({ request: vi.fn() } as never)
    handleServerRequest(
      {
        fail: vi.fn(),
        id: 'sudo-command',
        method: 'sudo',
        params: { command, session_id: 's1' },
        profile: 'default',
        respond
      },
      deps,
      's1'
    )
    renderPrompts()

    const preview = screen.getByRole('region', { name: 'Command' })
    const password = screen.getByPlaceholderText('sudo password')

    expect(preview.textContent).toBe(command)
    expect(preview.compareDocumentPosition(password) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(respond).not.toHaveBeenCalled()

    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' })
    expect(respond).toHaveBeenCalledExactlyOnceWith({ value: '' })
  })

  it('answers the live sudo request with an empty value on Cancel and clears the dialog', async () => {
    const respond = vi.fn()
    const request = vi.fn()

    $activeSessionId.set('s1')
    $gateway.set({ request } as never)
    rememberServerRequest({ fail: vi.fn(), id: 'sudo-1', method: 'sudo', params: {}, respond })
    setSudoRequest({ requestId: 'sudo-1', sessionId: 's1' })

    renderPrompts()

    expect(screen.getByText('Administrator password')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    await waitFor(() => expect($sudoRequest.get()).toBeNull())
    expect(respond).toHaveBeenCalledWith({ value: '' })
    expect(hasOpenServerRequest('sudo-1')).toBe(false)
    expect(request).not.toHaveBeenCalled()
    expect(notifyError).not.toHaveBeenCalled()
  })

  it('dismisses a stale sudo dialog when the gateway no longer has the request open', async () => {
    const request = vi.fn()

    $activeSessionId.set('s1')
    $gateway.set({ request } as never)
    // No server request registered under this id: it expired / was cancelled.
    setSudoRequest({ requestId: 'sudo-1', sessionId: 's1' })

    renderPrompts()

    expect(screen.getByText('Administrator password')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    await waitFor(() => expect($sudoRequest.get()).toBeNull())
    expect(request).not.toHaveBeenCalled()
    expect(notifyError).not.toHaveBeenCalled()
  })

  it('does not skip secret entry on Escape after a focus handoff', () => {
    const respond = vi.fn()
    $activeSessionId.set('s1')
    $gateway.set({ request: vi.fn() } as never)
    rememberServerRequest({ fail: vi.fn(), id: 'secret-handoff', method: 'secret', params: {}, respond })
    setSecretRequest({ envVar: 'TEST_SECRET', prompt: 'Paste a secret', requestId: 'secret-handoff', sessionId: 's1' })
    renderPrompts()

    const input = screen.getByPlaceholderText('TEST_SECRET')
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(input.closest('[data-slot="secret-inline"]')).toBeTruthy()
    expect(window.document.activeElement).not.toBe(input)
    fireEvent.change(input, { target: { value: 'dummy-value' } })
    fireEvent.blur(input)
    fireEvent.keyDown(input, { key: 'Escape' })

    expect(respond).not.toHaveBeenCalled()
    expect((input as HTMLInputElement).value).toBe('dummy-value')
    expect($secretRequest.get()?.requestId).toBe('secret-handoff')
  })

  it('answers the live secret request with an empty value on Cancel and clears the dialog', async () => {
    const respond = vi.fn()
    const request = vi.fn()

    $activeSessionId.set('s1')
    $gateway.set({ request } as never)
    rememberServerRequest({ fail: vi.fn(), id: 'secret-1', method: 'secret', params: {}, respond })
    setSecretRequest({ envVar: 'TEST_SECRET', prompt: 'Paste a secret', requestId: 'secret-1', sessionId: 's1' })

    renderPrompts()

    expect(screen.getByText('TEST_SECRET')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    await waitFor(() => expect($secretRequest.get()).toBeNull())
    expect(respond).toHaveBeenCalledWith({ value: '' })
    expect(hasOpenServerRequest('secret-1')).toBe(false)
    expect(request).not.toHaveBeenCalled()
    expect(notifyError).not.toHaveBeenCalled()
  })

  it('dismisses a stale secret card with neutral feedback when the request is no longer open', async () => {
    const request = vi.fn()

    $activeSessionId.set('s1')
    $gateway.set({ request } as never)
    setSecretRequest({ envVar: 'TEST_SECRET', prompt: 'Paste a secret', requestId: 'secret-1', sessionId: 's1' })

    renderPrompts()

    expect(screen.getByText('TEST_SECRET')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    await waitFor(() => expect($secretRequest.get()).toBeNull())
    expect(request).not.toHaveBeenCalled()
    expect(notifyError).not.toHaveBeenCalled()
    expect(notify).toHaveBeenCalledExactlyOnceWith({ kind: 'info', message: 'This request is no longer open.' })
  })
})
