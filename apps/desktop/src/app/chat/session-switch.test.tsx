import { useStore } from '@nanostores/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, useLocation, useNavigate } from 'react-router'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

import { useKeybinds } from '@/app/hooks/use-keybinds'
import { openSession, openSessionFromPicker } from '@/app/open-session'
import { group } from '@/components/pane-shell/tree/model'
import { TreeGroup } from '@/components/pane-shell/tree/renderer/tree-group'
import { $layoutTree, activateTreePane, noteActiveTreeGroup } from '@/components/pane-shell/tree/store'
import { registry } from '@/contrib/registry'
import { assistantTextPart } from '@/lib/chat-messages'
import { createClientSessionState } from '@/lib/chat-runtime'
import { registerHapticTrigger } from '@/lib/haptics'
import { isMacPlatform } from '@/lib/platform'
import { setHapticsMuted, setSessionSwitchHaptics } from '@/store/haptics'
import {
  $activeSessionId,
  $connection,
  $gatewayState,
  $resumeFailedSessionId,
  $selectedStoredSessionId,
  $sessions,
  setSelectedStoredSessionId
} from '@/store/session'
import {
  $sessionStates,
  $sessionTiles,
  clearAllSessionStates,
  publishSessionState,
  recordSessionEventScope,
  setSessionTileDelegate
} from '@/store/session-states'
import { stubMenuDomApis, stubResizeObserver } from '@/test/jsdom'

vi.mock('@/themes/context', () => ({ useTheme: () => ({ resolvedMode: 'dark', setMode: () => undefined }) }))
vi.mock('@/components/assistant-ui/thread', async () => {
  const { useAuiState } = await import('@assistant-ui/react')

  return {
    Thread: () => {
      const messages = useAuiState(state => state.thread.messages)

      return (
        <div data-testid="transcript">
          {messages.map(m => m.content.map(p => (p.type === 'text' ? p.text : '')).join('')).join('\n')}
        </div>
      )
    }
  }
})
vi.mock('@/components/Backdrop', () => ({ Backdrop: () => null }))
vi.mock('@/components/prompt-overlays', () => ({ PromptOverlays: () => null }))
vi.mock('@/components/chat/vibe-hearts', () => ({ COMPOSER_HEART_CONFIG: {}, HeartField: () => null }))
vi.mock('@/lib/model-options', () => ({
  currentModelCapabilities: () => undefined,
  modelOptionsQueryKey: () => [],
  requestModelOptions: vi.fn(async () => ({ models: [] }))
}))
vi.mock('./chat-drop-overlay', () => ({ ChatDropOverlay: () => null }))
vi.mock('./chat-swap-overlay', () => ({ ChatSwapOverlay: () => null, ChatSyncBadge: () => null }))
vi.mock('./composer', () => ({ ChatBar: () => null, ChatBarFallback: () => null }))
vi.mock('./hooks/use-file-drop-zone', () => ({ useFileDropZone: () => ({ dragKind: null, dropHandlers: {} }) }))

const { ChatView } = await import('./index')
const { watchSessionTiles } = await import('./session-tile')
watchSessionTiles()
const noop = vi.fn()

const props = {
  gateway: null,
  onAddContextRef: noop,
  onAddUrl: noop,
  onAttachDroppedItems: noop,
  onAttachImageBlob: noop,
  onCancel: noop,
  onDeleteSelectedSession: noop,
  onEdit: noop,
  onPasteClipboardImage: noop,
  onPickFiles: noop,
  onPickFolders: noop,
  onPickImages: noop,
  onReload: noop,
  onRemoveAttachment: noop,
  onRetryResume: noop,
  onSteer: () => false,
  onSubmit: () => false,
  onThreadMessagesChange: noop,
  onToggleSelectedPin: noop
}

const trigger = vi.fn()
let navigate: ReturnType<typeof useNavigate>

function Harness() {
  navigate = useNavigate()
  useKeybinds({
    archiveSelectedSession: noop,
    openNewSessionTab: noop,
    requestGateway: async <T,>() => undefined as T,
    startFreshSession: noop,
    toggleCommandCenter: noop,
    toggleSelectedPin: noop
  })
  const tree = useStore($layoutTree)

  return (
    <>
      <output data-testid="path">{useLocation().pathname}</output>
      {tree?.type === 'group' && <TreeGroup node={tree} parentAxis="row" />}
    </>
  )
}

function mount() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={['/A']}>
        <Harness />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

function bind(id: string, text = `Transcript ${id}`) {
  const state = createClientSessionState()
  publishSessionState(`runtime-${id}`, {
    ...state,
    storedSessionId: id,
    messages: [{ id: `message-${id}`, role: 'assistant', parts: [assistantTextPart(text)] }]
  })
  $activeSessionId.set(`runtime-${id}`)
  setSelectedStoredSessionId(id)
}

let disposeWorkspace: () => void
let clock = 10000
beforeEach(() => {
  stubResizeObserver()
  stubMenuDomApis()
  vi.stubGlobal('CSS', { ...globalThis.CSS, escape: (value: string) => value })
  disposeWorkspace = registry.register({
    id: 'workspace',
    area: 'panes',
    title: 'Workspace',
    data: { placement: 'main', uncloseable: true },
    render: () => <ChatView {...props} />
  })
  clock += 2000
  vi.spyOn(performance, 'now').mockImplementation(() => clock)
  setHapticsMuted(false)
  setSessionSwitchHaptics(true)
  $connection.set({ mode: 'local', connectionId: 'local' } as never)
  $gatewayState.set('open')
  $sessionTiles.set([])
  $layoutTree.set(group(['workspace'], { id: 'main', active: 'workspace' }))
  noteActiveTreeGroup(null)
  $sessions.set(['A', 'B', 'C'].map(id => ({ id, profile: 'default', message_count: 1, title: id })) as never)
  bind('A')
  registerHapticTrigger(trigger)
  trigger.mockClear()
})
afterEach(() => {
  cleanup()
  disposeWorkspace()
  registerHapticTrigger(null)
  $gatewayState.set('closed')
  $sessionTiles.set([])
  clearAllSessionStates()
  $activeSessionId.set(null)
  $selectedStoredSessionId.set(null)
  $sessions.set([])
  $layoutTree.set(null)
  vi.restoreAllMocks()
})

it('waits for the new normalized message objects even when profiles reuse message ids', async () => {
  publishSessionState(
    'runtime-A',
    createClientSessionState('A', [{ id: 'shared-id', role: 'assistant', parts: [assistantTextPart('Transcript A')] }])
  )
  mount()
  const observed: string[] = []
  trigger.mockImplementationOnce(() => {
    observed.push(screen.getByTestId('transcript').textContent ?? '')
  })
  await act(async () => {
    openSession('B', navigate)
    $activeSessionId.set('runtime-B')
    publishSessionState(
      'runtime-B',
      createClientSessionState('B', [
        { id: 'shared-id', role: 'assistant', parts: [assistantTextPart('Transcript B')] }
      ])
    )
    setSelectedStoredSessionId('B')
  })
  await waitFor(() => expect(trigger).toHaveBeenCalledTimes(1))
  expect(observed).toEqual(['Transcript B'])
})

it('confirms the active normalized branch rather than waiting for off-branch rows to render', async () => {
  mount()
  act(() => openSession('B', navigate))
  await act(async () => {
    $activeSessionId.set('runtime-B')
    publishSessionState(
      'runtime-B',
      createClientSessionState('B', [
        { id: 'prompt-B', role: 'user', parts: [{ type: 'text', text: 'Synthetic prompt' }] },
        { id: 'branch-one', role: 'assistant', branchGroupId: 'branches', parts: [assistantTextPart('Older branch')] },
        {
          id: 'branch-two',
          role: 'assistant',
          branchGroupId: 'branches',
          parts: [assistantTextPart('Selected branch')]
        }
      ])
    )
    setSelectedStoredSessionId('B')
  })
  await waitFor(() => expect(screen.getByTestId('transcript').textContent).toContain('Selected branch'))
  expect(trigger).toHaveBeenCalledTimes(1)
})

it('waits for an empty destination to replace the old runtime transcript before confirming', async () => {
  mount()
  act(() => $sessions.set($sessions.get().map(row => (row.id === 'B' ? { ...row, message_count: 0 } : row))))
  const observed: string[] = []
  trigger.mockImplementationOnce(() => {
    observed.push(screen.getByTestId('transcript').textContent ?? '')
  })
  await act(async () => {
    openSession('B', navigate)
    $activeSessionId.set('runtime-B')
    publishSessionState('runtime-B', createClientSessionState('B'))
    setSelectedStoredSessionId('B')
  })
  await waitFor(() => expect(trigger).toHaveBeenCalledTimes(1))
  expect(observed).toEqual([''])
})

it('does not replay a hidden tab’s late completion on a later automatic reveal', async () => {
  let complete!: (id: string) => void
  setSessionTileDelegate({
    resumeTile: () =>
      new Promise<string>(resolve => {
        complete = resolve
      })
  } as never)
  mount()
  act(() => openSession('B', navigate, 'tab'))
  act(() => activateTreePane('main', 'workspace'))
  await act(async () => {
    publishSessionState(
      'runtime-B',
      createClientSessionState('B', [
        { id: 'message-B', role: 'assistant', parts: [assistantTextPart('Transcript B')] }
      ])
    )
    complete('runtime-B')
  })
  expect(trigger).not.toHaveBeenCalled()
  act(() => activateTreePane('main', 'session-tile:B'))
  await waitFor(() =>
    expect(screen.getAllByTestId('transcript').some(node => node.textContent === 'Transcript B')).toBe(true)
  )
  expect(trigger).not.toHaveBeenCalled()
})

it('confirms one explicit in-place switch only after its real transcript binds and commits', async () => {
  mount()
  expect(screen.getByTestId('transcript').textContent).toBe('Transcript A')
  expect(trigger).not.toHaveBeenCalled()
  act(() => openSession('B', navigate))
  expect(trigger).not.toHaveBeenCalled()
  await act(async () => bind('B'))
  expect($sessionStates.get()['runtime-B']?.messages.length).toBe(1)
  expect($selectedStoredSessionId.get()).toBe('B')
  expect($activeSessionId.get()).toBe('runtime-B')
  expect(screen.getByTestId('path').textContent).toBe('/B')
  await waitFor(() => expect(screen.getByTestId('transcript').textContent).toBe('Transcript B'))
  expect(trigger).toHaveBeenCalledTimes(1)
  act(() => openSessionFromPicker('B', navigate))
  expect(trigger).toHaveBeenCalledTimes(1)
})

it('confirms a first-mounted tab after resume and a warm picker focus without remounting its transcript', async () => {
  let complete!: (runtime: string) => void
  setSessionTileDelegate({
    resumeTile: () =>
      new Promise<string>(resolve => {
        complete = resolve
      })
  } as never)
  mount()
  act(() => openSession('B', navigate, 'tab'))
  expect(trigger).not.toHaveBeenCalled()
  await act(async () => {
    publishSessionState(
      'runtime-B',
      createClientSessionState('B', [
        { id: 'message-B', role: 'assistant', parts: [assistantTextPart('Transcript B')] }
      ])
    )
    complete('runtime-B')
  })
  await waitFor(() => expect(trigger).toHaveBeenCalledTimes(1))
  const transcript = screen.getAllByTestId('transcript').find(node => node.textContent === 'Transcript B')!
  expect(transcript).toBeTruthy()
  clock += 100
  act(() => openSession('A', navigate))
  await waitFor(() => expect(trigger).toHaveBeenCalledTimes(2))
  clock += 100
  act(() => openSessionFromPicker('B', navigate))
  await waitFor(() => expect(trigger).toHaveBeenCalledTimes(3))
  expect(screen.getAllByTestId('transcript')).toContain(transcript)
})

it('only confirms C after rapid A to B to C, ignoring a stale B completion and later metadata', async () => {
  mount()
  act(() => openSession('B', navigate))
  act(() => openSession('C', navigate))
  await act(async () => bind('B'))
  expect(trigger).not.toHaveBeenCalled()
  await act(async () => bind('C'))
  await waitFor(() => expect(trigger).toHaveBeenCalledTimes(1))
  clock += 100
  act(() =>
    $sessions.set($sessions.get().map(row => ({ ...row, _lineage_root_id: `root-${row.id}`, title: 'Updated title' })))
  )
  await act(async () => bind('C', 'Updated transcript'))
  expect(trigger).toHaveBeenCalledTimes(1)
})

it('confirms direct tab activation but not restored tabs or same-tab activation', async () => {
  $sessionTiles.set([{ storedSessionId: 'B', runtimeId: 'runtime-B', dir: 'center' }])
  publishSessionState(
    'runtime-B',
    createClientSessionState('B', [{ id: 'message-B', role: 'assistant', parts: [assistantTextPart('Transcript B')] }])
  )
  $layoutTree.set(group(['workspace', 'session-tile:B'], { id: 'main', active: 'workspace' }))
  const { container } = mount()
  expect(trigger).not.toHaveBeenCalled()
  const tab = container.querySelector<HTMLElement>('[data-tree-tab="session-tile:B"]')!
  fireEvent.keyDown(tab, { key: 'Enter' })
  await waitFor(() =>
    expect(screen.getAllByTestId('transcript').some(node => node.textContent === 'Transcript B')).toBe(true)
  )
  expect(trigger).toHaveBeenCalledTimes(1)
  clock += 100
  fireEvent.keyDown(tab, { key: 'Enter' })
  expect(trigger).toHaveBeenCalledTimes(1)
})

it('focuses and confirms an already-open lineage alias under its actual tab identity', async () => {
  $sessions.set([
    ...$sessions.get(),
    { id: 'B-tip', _lineage_root_id: 'B', profile: 'default', title: 'B', message_count: 1 } as never
  ])
  $sessionTiles.set([{ storedSessionId: 'B-tip', runtimeId: 'runtime-tip', dir: 'center' }])
  publishSessionState(
    'runtime-tip',
    createClientSessionState('B-tip', [
      { id: 'message-tip', role: 'assistant', parts: [assistantTextPart('Transcript tip')] }
    ])
  )
  $layoutTree.set(group(['workspace', 'session-tile:B-tip'], { id: 'main', active: 'workspace' }))
  mount()
  act(() => openSession('B', navigate))
  await waitFor(() =>
    expect(screen.getAllByTestId('transcript').some(node => node.textContent === 'Transcript tip')).toBe(true)
  )
  expect(trigger).toHaveBeenCalledTimes(1)
  clock += 100
  act(() => openSession('B-tip', navigate))
  expect(trigger).toHaveBeenCalledTimes(1)
})

it.each(['slot', 'cycle'] as const)('confirms the real keyboard %s tab action', async action => {
  $sessionTiles.set([{ storedSessionId: 'B', runtimeId: 'runtime-B', dir: 'center' }])
  publishSessionState(
    'runtime-B',
    createClientSessionState('B', [{ id: 'message-B', role: 'assistant', parts: [assistantTextPart('Transcript B')] }])
  )
  $layoutTree.set(group(['workspace', 'session-tile:B'], { id: 'main', active: 'workspace' }))
  mount()
  fireEvent.keyDown(
    window,
    action === 'slot'
      ? { key: '2', code: 'Digit2', ctrlKey: !isMacPlatform(), metaKey: isMacPlatform() }
      : { key: 'Tab', code: 'Tab', ctrlKey: true }
  )
  await waitFor(() =>
    expect(screen.getAllByTestId('transcript').some(node => node.textContent === 'Transcript B')).toBe(true)
  )
  expect(trigger).toHaveBeenCalledTimes(1)
})

it.each(['failed', 'reconnect', 'settings', 'connection'] as const)(
  'does not confirm a pending switch after %s',
  async reason => {
    mount()
    act(() => openSession('B', navigate))
    act(() => {
      if (reason === 'failed') {
        $resumeFailedSessionId.set('B')
      }

      if (reason === 'reconnect') {
        $gatewayState.set('closed')
        $gatewayState.set('open')
      }

      if (reason === 'settings') {
        navigate('/settings')
      }

      if (reason === 'connection') {
        $connection.set({ mode: 'remote', connectionId: 'other' } as never)
      }
    })
    await act(async () => bind('B'))
    expect(trigger).not.toHaveBeenCalled()
    clock += 100
    act(() => {
      $resumeFailedSessionId.set(null)
      navigate('/B')
    })
    await act(async () => bind('B', 'Background refresh'))
    expect(trigger).not.toHaveBeenCalled()
  }
)

it('confirms a selected session on its owning profile rather than the ambient profile', async () => {
  $sessions.set(
    $sessions.get().map(row => (row.id === 'B' ? { ...row, connection_id: 'local', profile: 'other-profile' } : row))
  )
  mount()
  act(() => openSession('B', navigate))
  recordSessionEventScope({ session_id: 'runtime-B', connectionId: 'local', profile: 'other-profile' })
  await act(async () => bind('B'))
  await waitFor(() => expect(screen.getByTestId('transcript').textContent).toBe('Transcript B'))
  expect(trigger).toHaveBeenCalledTimes(1)
})

it('rejects a runtime with the same durable id from another connection or profile', async () => {
  mount()
  act(() => openSession('B', navigate))
  recordSessionEventScope({ session_id: 'runtime-B', connectionId: 'other', profile: 'default' })
  await act(async () => bind('B'))
  await waitFor(() => expect(screen.getByTestId('transcript').textContent).toBe('Transcript B'))
  expect(trigger).not.toHaveBeenCalled()
})

it.each(['mute', 'preference'] as const)(
  'consumes a disabled confirmation without replay when %s is reenabled',
  async kind => {
    mount()
    act(() => {
      if (kind === 'mute') {
        setHapticsMuted(true)
      } else {
        setSessionSwitchHaptics(false)
      }

      openSession('B', navigate)
    })
    await act(async () => bind('B'))
    await waitFor(() => expect(screen.getByTestId('transcript').textContent).toBe('Transcript B'))
    expect(trigger).not.toHaveBeenCalled()
    act(() => {
      setHapticsMuted(false)
      setSessionSwitchHaptics(true)
    })
    await act(async () => bind('B', 'Updated transcript'))
    expect(trigger).not.toHaveBeenCalled()
  }
)
