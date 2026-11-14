import { AssistantRuntimeProvider, type ThreadMessage, useExternalStoreRuntime } from '@assistant-ui/react'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'

import { stubThreadEnvironment, stubThreadViewportSize } from '@/components/assistant-ui/test-utils'
import { Thread } from '@/components/assistant-ui/thread'
import { I18nProvider } from '@/i18n'
import { type ChatMessage, restorePendingClarifyToolCall } from '@/lib/chat-messages'
import { toRuntimeMessage } from '@/lib/chat-runtime'
import { clearAllPrompts, setSecretRequest } from '@/store/prompts'
import { $activeSessionId } from '@/store/session'

stubThreadEnvironment()
stubThreadViewportSize()

afterEach(() => {
  cleanup()
  clearAllPrompts()
  $activeSessionId.set(null)
})

function Harness({ messages }: { messages: ThreadMessage[] }) {
  const runtime = useExternalStoreRuntime({ messages, isRunning: true, onNew: async () => {} })

  return (
    <I18nProvider configClient={null}>
      <AssistantRuntimeProvider runtime={runtime}>
        <Thread />
      </AssistantRuntimeProvider>
    </I18nProvider>
  )
}

it('renders the secret in the bound tool row of the actual transcript', async () => {
  $activeSessionId.set('s1')
  setSecretRequest({ envVar: 'TEST_KEY', prompt: 'Enter key', requestId: 'r1', sessionId: 's1' })

  const messages: ChatMessage[] = [
    {
      id: 'm1',
      role: 'assistant',
      pending: true,
      parts: [
        {
          type: 'tool-call',
          toolCallId: 'call1',
          toolName: 'clarify',
          args: { secret_env: 'TEST_KEY' },
          argsText: '{}'
        }
      ]
    }
  ]

  const projected = restorePendingClarifyToolCall(messages, { tool_id: 'r1', args: {} }).messages.map(toRuntimeMessage)
  const { container } = render(<Harness messages={projected} />)
  expect(await screen.findByLabelText('TEST_KEY')).toBeTruthy()
  expect(container.querySelector('[data-slot="secret-inline"]')).toBeTruthy()
  expect(screen.queryByRole('dialog')).toBeNull()
})
