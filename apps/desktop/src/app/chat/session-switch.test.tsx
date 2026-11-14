import { useStore } from '@nanostores/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { StrictMode } from 'react'
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
import { $activeGatewayProfile } from '@/store/profile'
import {
  $activeSessionId,
  $connection,
  $gatewayState,
  $resumeFailedSessionId,
  $selectedStoredSessionId,
  $sessionResumeRequest,
  $sessions,
  forgetSessionOwnerHintsForSession,
  getSessionOwnerHint,
  requestSessionResume,
  rotateFreshDraftKey,
  setSelectedStoredSessionId
} from '@/store/session'
import {
  $sessionStates,
  $sessionTiles,
  clearAllSessionStates,
  publishSessionState,
  recordSessionEventScope,
  runtimeSessionOwner,
  setSessionTileDelegate
} from '@/store/session-states'
import { setSessionSwitchVisual } from '@/store/session-switch-visual'
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

function mount(strict = false) {
  const app = (
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={['/A']}>
        <Harness />
      </MemoryRouter>
    </QueryClientProvider>
  )

  return render(strict ? <StrictMode>{app}</StrictMode> : app)
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
  $activeGatewayProfile.set('default')
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
  $sessionResumeRequest.set(null)
  $sessions.set([])
  $layoutTree.set(null)
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  Reflect.deleteProperty(Element.prototype, 'animate')
  setSessionSwitchVisual(false)
})

it('does not replay a pending primary switch after a fresh draft supersedes it', async () => {
  mount()
  act(() => {
    openSession('B', navigate)
    setSelectedStoredSessionId('B')
    $activeSessionId.set(null)
  })
  act(() => {
    navigate('/')
    setSelectedStoredSessionId(null)
    $activeSessionId.set(null)
  })
  await act(async () => {
    navigate('/B')
    bind('B')
  })
  expect(screen.getByTestId('transcript').textContent).toBe('Transcript B')
  expect(trigger).not.toHaveBeenCalled()
})

it('does not replay a pending switch after an unrelated same-connection profile change', async () => {
  mount()
  act(() => openSession('B', navigate))
  act(() => $activeGatewayProfile.set('other-profile'))
  await act(async () => bind('B'))
  act(() => $activeGatewayProfile.set('default'))
  expect(trigger).not.toHaveBeenCalled()
})

it('retires a pending switch when another fresh draft replaces an already blank source', async () => {
  setSelectedStoredSessionId(null)
  $activeSessionId.set(null)
  mount()
  act(() => openSession('B', navigate))
  act(() => {
    navigate('/')
    rotateFreshDraftKey()
  })
  await act(async () => {
    navigate('/B')
    bind('B')
  })
  expect(trigger).not.toHaveBeenCalled()
})

it.each(['tile', 'layout'] as const)('does not replay an ended %s destination after restoration', async lifetime => {
  $sessionTiles.set([{ storedSessionId: 'B', runtimeId: 'runtime-B', dir: 'center' }])
  $layoutTree.set(group(['workspace', 'session-tile:B'], { id: 'main', active: 'workspace' }))
  mount()
  act(() => openSession('B', navigate))
  const savedTiles = $sessionTiles.get()
  const savedTree = $layoutTree.get()
  act(() => {
    if (lifetime === 'tile') {
      $sessionTiles.set([])
    } else {
      $layoutTree.set(group(['workspace'], { id: 'main', active: 'workspace' }))
    }
  })
  act(() => {
    $sessionTiles.set(savedTiles)
    $layoutTree.set(savedTree)
  })
  await act(async () => {
    publishSessionState(
      'runtime-B',
      createClientSessionState('B', [
        { id: 'message-B', role: 'assistant', parts: [assistantTextPart('Transcript B')] }
      ])
    )
  })
  expect(screen.getAllByTestId('transcript').some(node => node.textContent === 'Transcript B')).toBe(true)
  expect(trigger).not.toHaveBeenCalled()
})

it('uses the bound runtime owner rather than the first duplicate list row for same-session silence', async () => {
  $sessions.set([
    { id: 'A', profile: 'default', connection_id: 'foreign', message_count: 1 },
    { id: 'A', profile: 'default', connection_id: 'local', message_count: 1 }
  ] as never)
  recordSessionEventScope({ session_id: 'runtime-A', connectionId: 'local', profile: 'default' })
  mount()
  act(() =>
    openSession('A', navigate, 'in-place', {
      workspaceMode: 'sessions',
      ownerRoute: { connectionId: 'local', profile: 'default' }
    })
  )
  expect(screen.getByTestId('transcript').textContent).toBe('Transcript A')
  expect(trigger).not.toHaveBeenCalled()
})

it('uses the tile owner route when its runtime has no event-proven owner', async () => {
  const ownerRoute = { connectionId: 'foreign', profile: 'other-profile' }
  $sessionTiles.set([{ storedSessionId: 'B', runtimeId: 'runtime-B', dir: 'center', ownerRoute }])
  publishSessionState(
    'runtime-B',
    createClientSessionState('B', [{ id: 'message-B', role: 'assistant', parts: [assistantTextPart('Transcript B')] }])
  )
  $layoutTree.set(group(['workspace', 'session-tile:B'], { id: 'main', active: 'workspace' }))
  mount()
  act(() => openSession('B', navigate))
  await waitFor(() => expect(trigger).toHaveBeenCalledTimes(1))
})

it('distinguishes a real owner change even when the stored session id is unchanged', async () => {
  $sessions.set([{ id: 'A', profile: 'default', connection_id: 'local', message_count: 1 }] as never)
  recordSessionEventScope({ session_id: 'runtime-A', connectionId: 'foreign', profile: 'default' })
  mount()
  act(() =>
    openSession('A', navigate, 'in-place', {
      workspaceMode: 'sessions',
      ownerRoute: { connectionId: 'local', profile: 'default' }
    })
  )
  expect(trigger).not.toHaveBeenCalled()
  act(() => $activeSessionId.set(null))
  await act(async () => {
    recordSessionEventScope({ session_id: 'runtime-local-A', connectionId: 'local', profile: 'default' })
    publishSessionState(
      'runtime-local-A',
      createClientSessionState('A', [
        { id: 'local-A', role: 'assistant', parts: [assistantTextPart('Local transcript A')] }
      ])
    )
    $activeSessionId.set('runtime-local-A')
  })
  await waitFor(() => expect(trigger).toHaveBeenCalledTimes(1))
})

it.each(['picker', 'keyboard'] as const)(
  'uses a warm tile runtime owner over duplicate rows for %s switches',
  async action => {
    $sessions.set([
      { id: 'B', profile: 'default', connection_id: 'foreign', message_count: 1 },
      ...$sessions.get()
    ] as never)
    recordSessionEventScope({ session_id: 'runtime-B', connectionId: 'local', profile: 'default' })
    $sessionTiles.set([{ storedSessionId: 'B', runtimeId: 'runtime-B', dir: 'center' }])
    publishSessionState(
      'runtime-B',
      createClientSessionState('B', [
        { id: 'message-B', role: 'assistant', parts: [assistantTextPart('Transcript B')] }
      ])
    )
    $layoutTree.set(group(['workspace', 'session-tile:B'], { id: 'main', active: 'workspace' }))
    mount()
    act(() => {
      if (action === 'picker') {
        openSessionFromPicker('B', navigate)
      } else {
        fireEvent.keyDown(window, { key: '2', code: 'Digit2', ctrlKey: !isMacPlatform(), metaKey: isMacPlatform() })
      }
    })
    await waitFor(() => expect(trigger).toHaveBeenCalledTimes(1))
    clock += 100
    act(() =>
      openSession('B', navigate, 'in-place', {
        workspaceMode: 'sessions',
        ownerRoute: { connectionId: 'local', profile: 'default' }
      })
    )
    expect(trigger).toHaveBeenCalledTimes(1)
  }
)

it.each(['sidebar', 'picker', 'keyboard'] as const)(
  'confirms a foreground warm tile from %s without changing the workspace page',
  async action => {
    $sessionTiles.set([{ storedSessionId: 'B', runtimeId: 'runtime-B', dir: 'center' }])
    publishSessionState(
      'runtime-B',
      createClientSessionState('B', [
        { id: 'message-B', role: 'assistant', parts: [assistantTextPart('Transcript B')] }
      ])
    )
    $layoutTree.set(group(['workspace', 'session-tile:B'], { id: 'main', active: 'workspace' }))
    mount()
    act(() => navigate('/capabilities'))
    act(() => {
      if (action === 'sidebar') {
        openSession('B', navigate)
      } else if (action === 'picker') {
        openSessionFromPicker('B', navigate)
      } else {
        fireEvent.keyDown(window, { key: '2', code: 'Digit2', ctrlKey: !isMacPlatform(), metaKey: isMacPlatform() })
      }
    })
    expect(screen.getByTestId('path').textContent).toBe('/capabilities')
    await waitFor(() => expect(trigger).toHaveBeenCalledTimes(1))
  }
)

it.each(['primary', 'tile'] as const)('does not replay a %s completion covered by settings', async destination => {
  if (destination === 'tile') {
    $sessionTiles.set([{ storedSessionId: 'B', runtimeId: 'runtime-B', dir: 'center' }])
    $layoutTree.set(group(['workspace', 'session-tile:B'], { id: 'main', active: 'workspace' }))
  }

  mount()
  act(() => openSession('B', navigate))
  act(() => navigate('/settings'))
  await act(async () => bind('B'))
  expect(trigger).not.toHaveBeenCalled()
  act(() => navigate('/B'))
  expect(trigger).not.toHaveBeenCalled()
})

it('does not replay a first-mounted tile after actual profile-bucket removal and restoration', async () => {
  const completions: Array<(runtime: string) => void> = []
  setSessionTileDelegate({
    resumeTile: () =>
      new Promise<string>(resolve => {
        completions.push(resolve)
      })
  } as never)
  mount()
  act(() => openSession('B', navigate, 'tab'))
  expect(completions).toHaveLength(1)
  act(() => $activeGatewayProfile.set('other-profile'))
  expect($sessionTiles.get().some(tile => tile.storedSessionId === 'B')).toBe(false)
  act(() => {
    $activeGatewayProfile.set('default')
    $layoutTree.set(group(['workspace', 'session-tile:B'], { id: 'main', active: 'session-tile:B' }))
    noteActiveTreeGroup('main')
  })
  expect($sessionTiles.get().some(tile => tile.storedSessionId === 'B')).toBe(true)
  await act(async () => {
    publishSessionState(
      'runtime-B',
      createClientSessionState('B', [
        { id: 'message-B', role: 'assistant', parts: [assistantTextPart('Transcript B')] }
      ])
    )
    completions.at(-1)!('runtime-B')
  })
  expect(trigger).not.toHaveBeenCalled()
})

it('confirms the primary destination exactly once under StrictMode', async () => {
  mount(true)
  act(() => openSession('B', navigate))
  expect(trigger).not.toHaveBeenCalled()
  await act(async () => bind('B'))
  await waitFor(() => expect(trigger).toHaveBeenCalledTimes(1))
  act(() => openSession('B', navigate))
  expect(trigger).toHaveBeenCalledTimes(1)
})

it('preserves a first-mounted destination intent through StrictMode effect replay', async () => {
  let complete!: (runtime: string) => void
  setSessionTileDelegate({
    resumeTile: () =>
      new Promise<string>(resolve => {
        complete = resolve
      })
  } as never)
  mount(true)
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
})

it('keeps an untagged non-ambient primary same-session reselect silent', async () => {
  const owner = { connectionId: 'local', profile: 'other-profile' }
  $sessions.set($sessions.get().map(row => (row.id === 'A' ? { ...row, profile: 'other-profile' } : row)))
  requestSessionResume('A', owner)

  try {
    expect(getSessionOwnerHint('A')).toEqual(owner)
    expect(runtimeSessionOwner('runtime-A')).toBeUndefined()
    expect($activeGatewayProfile.get()).toBe('default')
    mount()
    act(() => openSession('A', navigate))
    expect(screen.getByTestId('transcript').textContent).toBe('Transcript A')
    expect($activeSessionId.get()).toBe('runtime-A')
    expect(trigger).not.toHaveBeenCalled()
  } finally {
    forgetSessionOwnerHintsForSession('A')
  }
})

it('keeps RPC-bound source ownership when a same-id destination hint changes before its runtime arrives', async () => {
  const previousOwner = { connectionId: 'local', profile: 'other-profile' }
  const nextOwner = { connectionId: 'local', profile: 'default' }
  publishSessionState('runtime-A', { ...$sessionStates.get()['runtime-A']!, boundOwner: previousOwner })
  mount()
  act(() => {
    requestSessionResume('A', nextOwner)
    openSession('A', navigate, 'in-place', { workspaceMode: 'sessions', ownerRoute: nextOwner })
  })
  expect(trigger).not.toHaveBeenCalled()
  act(() => $activeSessionId.set(null))
  await act(async () => {
    publishSessionState('runtime-next-A', {
      ...createClientSessionState('A', [
        { id: 'next-A', role: 'assistant', parts: [assistantTextPart('Next owner A')] }
      ]),
      boundOwner: nextOwner
    })
    $activeSessionId.set('runtime-next-A')
  })

  try {
    await waitFor(() => expect(screen.getByTestId('transcript').textContent).toBe('Next owner A'))
    expect(trigger).toHaveBeenCalledTimes(1)
  } finally {
    forgetSessionOwnerHintsForSession('A')
  }
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

it.each([
  [false, false, false, false],
  [false, true, false, false],
  [true, false, false, false],
  [true, true, false, false],
  [true, false, true, false],
  [true, true, true, false],
  [true, true, false, true]
])('confirms independently: visual=%s haptic=%s mute=%s reduced=%s', async (visual, haptic, mute, reduced) => {
  const animate = vi.fn()
  vi.stubGlobal('matchMedia', () => ({ matches: reduced, addEventListener: vi.fn(), removeEventListener: vi.fn() }))
  Object.defineProperty(Element.prototype, 'animate', { configurable: true, value: animate })
  setSessionSwitchVisual(visual)
  setSessionSwitchHaptics(haptic)
  setHapticsMuted(mute)
  mount()
  act(() => openSession('B', navigate))
  expect(animate).not.toHaveBeenCalled()
  await act(async () => bind('B'))
  await waitFor(() => expect(screen.getByTestId('transcript').textContent).toBe('Transcript B'))
  expect(animate).toHaveBeenCalledTimes(visual && !reduced ? 1 : 0)
  expect(trigger).toHaveBeenCalledTimes(haptic && !mute ? 1 : 0)
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
  const animated: Element[] = []
  vi.stubGlobal('matchMedia', () => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }))
  Object.defineProperty(Element.prototype, 'animate', {
    configurable: true,
    value: function (this: Element) {
      animated.push(this)
    }
  })
  setSessionSwitchVisual(true)
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
  expect(animated).toHaveLength(3)
  expect(animated[0]).toBe(transcript.closest('[data-chat-surface]'))
  expect(animated[2]).toBe(transcript.closest('[data-chat-surface]'))
})

it('only confirms C after rapid A to B to C, ignoring a stale B completion and later metadata', async () => {
  const animate = vi.fn()
  vi.stubGlobal('matchMedia', () => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }))
  Object.defineProperty(Element.prototype, 'animate', { configurable: true, value: animate })
  setSessionSwitchVisual(true)
  mount()
  expect(animate).not.toHaveBeenCalled()
  act(() => openSession('B', navigate))
  act(() => openSession('C', navigate))
  await act(async () => bind('B'))
  expect(trigger).not.toHaveBeenCalled()
  expect(animate).not.toHaveBeenCalled()
  await act(async () => bind('C'))
  await waitFor(() => expect(trigger).toHaveBeenCalledTimes(1))
  expect(animate).toHaveBeenCalledTimes(1)
  clock += 100
  act(() =>
    $sessions.set($sessions.get().map(row => ({ ...row, _lineage_root_id: `root-${row.id}`, title: 'Updated title' })))
  )
  await act(async () => bind('C', 'Updated transcript'))
  expect(trigger).toHaveBeenCalledTimes(1)
  expect(animate).toHaveBeenCalledTimes(1)
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

it('preserves pending confirmation during legitimate owner-profile activation', async () => {
  $sessions.set(
    $sessions.get().map(row => (row.id === 'B' ? { ...row, connection_id: 'local', profile: 'other-profile' } : row))
  )
  mount()
  act(() => openSession('B', navigate))
  act(() => $activeGatewayProfile.set('other-profile'))
  recordSessionEventScope({ session_id: 'runtime-B', connectionId: 'local', profile: 'other-profile' })
  await act(async () => bind('B'))
  expect(trigger).toHaveBeenCalledTimes(1)
})

it('keeps the most recent explicit reselect while the target is still loading', async () => {
  recordSessionEventScope({ session_id: 'runtime-A', connectionId: 'local', profile: 'default' })
  $sessions.set(
    $sessions.get().map(row => (row.id === 'B' ? { ...row, connection_id: 'local', profile: 'other-profile' } : row))
  )
  mount()
  act(() => {
    openSession('B', navigate)
    $activeSessionId.set(null)
    setSelectedStoredSessionId('B')
  })
  act(() => openSessionFromPicker('B', navigate))
  recordSessionEventScope({ session_id: 'runtime-B', connectionId: 'local', profile: 'other-profile' })
  await act(async () => bind('B'))
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
