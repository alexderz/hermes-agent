import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  handleServerRequest,
  type ServerRequestContext
} from '@/app/session/hooks/use-message-stream/gateway-event/server-requests'
import { I18nProvider } from '@/i18n'
import { createClientSessionState } from '@/lib/chat-runtime'
import { $gateway } from '@/store/gateway'
import { clearAllPrompts } from '@/store/prompts'
import { resetServerRequestsForTests } from '@/store/server-requests'
import { $activeSessionId } from '@/store/session'

import { PromptOverlays } from './prompt-overlays'

vi.mock('@/lib/haptics', () => ({ triggerHaptic: vi.fn() }))
vi.mock('@/store/notifications', () => ({ notifyError: vi.fn() }))

const deps: ServerRequestContext['deps'] = {
  activeSessionIdRef: { current: 's1' },
  sessionInterrupted: () => false,
  sessionStateByRuntimeIdRef: { current: new Map() },
  updateSessionState: (_sid, update) => update(createClientSessionState('s1')),
  upsertToolCall: () => undefined
}

function openSecretCard(params: Record<string, unknown>, respond = vi.fn()) {
  $activeSessionId.set('s1')
  $gateway.set({ request: vi.fn() } as never)
  handleServerRequest(
    {
      fail: vi.fn(),
      id: 'secret-file',
      method: 'secret',
      params: { session_id: 's1', ...params },
      profile: 'default',
      respond
    },
    deps,
    's1'
  )
  render(
    <I18nProvider configClient={null}>
      <PromptOverlays sessionId="s1" />
    </I18nProvider>
  )

  return respond
}

afterEach(() => {
  cleanup()
  clearAllPrompts()
  resetServerRequestsForTests()
  $activeSessionId.set(null)
  $gateway.set(null)
  vi.clearAllMocks()
})

describe('SecretDialog file destination', () => {
  it('shows where the secret will be saved, with mode and owner, before the masked input', () => {
    const path = '/srv/workspaces/example-project/config/secrets/xyz/api-key'

    const respond = openSecretCard({
      env_var: 'XYZ API key',
      metadata: {
        destination: { group: 'devs', kind: 'file', mode: '0640', owner: 'hermes', path },
        source: 'agent'
      },
      prompt: 'XYZ API key, used by the sync timer'
    })

    const block = screen.getByRole('region', { name: 'Will be saved to' })
    const input = screen.getByPlaceholderText('XYZ API key')

    expect(block.querySelector('code')?.textContent).toBe(path)
    expect(block.textContent).toContain('Mode 0640, owner hermes:devs')
    expect(block.compareDocumentPosition(input) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(input.getAttribute('type')).toBe('password')

    fireEvent.change(input, { target: { value: 'dummy-value' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))
    expect(respond).toHaveBeenCalledExactlyOnceWith({ value: 'dummy-value' })
  })

  it('shows no destination block for a .env secret', () => {
    openSecretCard({ env_var: 'WEATHER_API_KEY', metadata: { source: 'agent' }, prompt: 'Weather key' })

    expect(screen.getByText('WEATHER_API_KEY')).toBeTruthy()
    expect(screen.queryByRole('region', { name: 'Will be saved to' })).toBeNull()
  })
})
