// @vitest-environment jsdom
import { AssistantRuntimeProvider, type ThreadMessageLike, useExternalStoreRuntime } from '@assistant-ui/react'
import { act, cleanup, createEvent, fireEvent, render } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

import { I18nProvider } from '@/i18n'
import { $touchPointer } from '@/lib/touch-interaction'

import { RICH_INPUT_SLOT } from './rich-editor'
import { placeCaretAtEnd } from './test-utils'
import type { ChatBarState } from './types'

import { ChatBar } from '.'

const state: ChatBarState = {
  model: { canSwitch: false, model: '', provider: '' },
  tools: { enabled: false, label: '' },
  voice: { enabled: false, active: false }
}

function Harness({ onSubmit, busy = false }: { onSubmit: (text: string) => Promise<boolean>; busy?: boolean }) {
  const runtime = useExternalStoreRuntime({
    convertMessage: (message: ThreadMessageLike) => message,
    isRunning: false,
    messages: [] as ThreadMessageLike[],
    onNew: async () => {}
  })

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <MemoryRouter>
        <I18nProvider configClient={null} initialLocale="en">
          <ChatBar busy={busy} disabled={false} gateway={null} onCancel={vi.fn()} onSubmit={onSubmit} state={state} />
        </I18nProvider>
      </MemoryRouter>
    </AssistantRuntimeProvider>
  )
}

// jsdom cannot execute native editing commands. Browser coverage verifies
// the resulting newline, caret, subsequent typing and explicit Send.
beforeEach(() => {
  window.document.execCommand = vi.fn(() => true)
})

afterEach(() => {
  cleanup()
  $touchPointer.set(false)
  Reflect.deleteProperty(window.document, 'execCommand')
})

async function draft(text: string, touch: boolean, busy = false) {
  $touchPointer.set(touch)
  const onSubmit = vi.fn(async (_text: string) => true)
  const view = render(<Harness busy={busy} onSubmit={onSubmit} />)
  const editor = view.container.querySelector<HTMLElement>(`[data-slot="${RICH_INPUT_SLOT}"]`)!
  editor.tabIndex = 0
  await act(async () => {
    editor.focus()
    editor.textContent = text
    placeCaretAtEnd(editor)
    fireEvent.input(editor)
  })

  return { ...view, editor, onSubmit }
}

it('keeps mobile Return as a newline while the session is busy', async () => {
  const { editor, onSubmit } = await draft('follow-up', true, true)
  const enter = createEvent.keyDown(editor, { key: 'Enter' })
  await act(async () => {
    fireEvent(editor, enter)
  })
  expect(editor.ownerDocument.execCommand).toHaveBeenCalledWith('insertLineBreak')
  expect(onSubmit).not.toHaveBeenCalled()
})

it('sends the complete multiline mobile draft only through the Send button', async () => {
  const { container, onSubmit } = await draft('first line\nsecond line', true)
  await act(async () => {
    fireEvent.click(container.querySelector('button[type="submit"]')!)
  })
  expect(onSubmit).toHaveBeenCalledTimes(1)
  expect(onSubmit.mock.calls[0][0]).toBe('first line\nsecond line')
})

it('preserves desktop Enter submission', async () => {
  const { editor, onSubmit } = await draft('desktop message', false)
  await act(async () => {
    fireEvent.keyDown(editor, { key: 'Enter' })
  })
  expect(onSubmit).toHaveBeenCalledTimes(1)
  expect(onSubmit.mock.calls[0][0]).toBe('desktop message')
})

it('preserves desktop Shift+Enter newline insertion', async () => {
  const { editor, onSubmit } = await draft('desktop draft', false)
  const enter = createEvent.keyDown(editor, { key: 'Enter', shiftKey: true })
  await act(async () => {
    fireEvent(editor, enter)
  })
  expect(enter.defaultPrevented).toBe(false)
  expect(onSubmit).not.toHaveBeenCalled()
})

it('does not send a mobile IME composition commit', async () => {
  const { editor, onSubmit } = await draft('composing', true)
  await act(async () => {
    fireEvent.keyDown(editor, { key: 'Enter', isComposing: true, keyCode: 229 })
  })
  expect(onSubmit).not.toHaveBeenCalled()
})

it('inserts a mobile newline without submitting', async () => {
  $touchPointer.set(true)
  const onSubmit = vi.fn(async (_text: string) => true)
  const { container } = render(<Harness onSubmit={onSubmit} />)
  const editor = container.querySelector<HTMLElement>(`[data-slot="${RICH_INPUT_SLOT}"]`)!
  editor.tabIndex = 0
  await act(async () => {
    editor.focus()
    editor.textContent = 'first line'
    placeCaretAtEnd(editor)
    fireEvent.input(editor)
  })
  const enter = createEvent.keyDown(editor, { key: 'Enter', code: 'Enter' })
  await act(async () => {
    fireEvent(editor, enter)
  })
  expect(onSubmit).not.toHaveBeenCalled()
  expect(editor.ownerDocument.execCommand).toHaveBeenCalledWith('insertLineBreak')
})
