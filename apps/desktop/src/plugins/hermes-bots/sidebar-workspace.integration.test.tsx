// @vitest-environment jsdom
import type * as HermesSdk from '@hermes/plugin-sdk'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

// Exercise the real plugin, roster, contribution slot, focus and workspace stores.
// Only external work (sockets, clocks, profile writes) is replaced.
const transport = vi.hoisted(() => ({ request: vi.fn(), agents: vi.fn(), requestProfile: vi.fn() }))
const canonical = vi.hoisted(() => ({ prepareBotSource: vi.fn(), openBotCanonicalChat: vi.fn() }))
vi.mock('./canonical-chat', async importOriginal => ({ ...(await importOriginal<object>()), ...canonical }))
vi.mock('@/store/gateway', async importOriginal => ({
  ...(await importOriginal<object>()),
  openGatewayForAgent: vi.fn(async () => {})
}))
vi.mock('@hermes/plugin-sdk', async importOriginal => {
  const sdk = await importOriginal<typeof HermesSdk>()

  return { ...sdk, host: { ...sdk.host, ...transport } }
})
vi.mock('./avatar', async importOriginal => ({
  ...(await importOriginal<object>()),
  startFaceClock: vi.fn(),
  stopFaceClock: vi.fn()
}))
vi.mock('./relay', () => ({ startBotRelay: vi.fn(), stopBotRelay: vi.fn() }))
vi.mock('./screen-autoraise', () => ({ startScreenAutoRaise: () => () => {} }))
vi.mock('./session-sweep', () => ({ startHideSweepScheduler: vi.fn() }))
vi.mock('./profile-ops', async importOriginal => ({
  ...(await importOriginal<object>()),
  mergeServerMeta: vi.fn(),
  pullServerAvatars: vi.fn()
}))

/* eslint-disable no-restricted-imports -- Integration harness drives host inputs;
   production plugin modules still use only the SDK. */
import { ChatSidebar } from '@/app/chat/sidebar'
import { openSession } from '@/app/open-session'
import { group, split } from '@/components/pane-shell/tree/model'
import { $layoutTree, noteActiveTreeGroup, setTreeSideCollapsed } from '@/components/pane-shell/tree/store'
import { $workspaceMode, $workspaceNewSessionTarget, setWorkspaceScope } from '@/components/pane-shell/workspace-scope'
import { SidebarProvider } from '@/components/ui/sidebar'
import { registry } from '@/contrib/registry'
import type { Contribution } from '@/contrib/types'
import { createPluginI18n } from '@/i18n'
import type { PluginContext } from '@/sdk'
import { $sidebarProjectFilter, $sidebarShowArchived, setSidebarAgentsGrouped } from '@/store/layout'
import { $projectScope, ALL_PROJECTS } from '@/store/project-scope'
import { $projectTree } from '@/store/projects'
import { $activeSessionId, $gatewayState, $selectedStoredSessionId, $sessions } from '@/store/session'
import { $botChatScopes, $sessionTiles } from '@/store/session-states'
import { makeSessionInfo } from '@/test/session-info'
/* eslint-enable no-restricted-imports */

import { $openBotChat, $rosterHydrated, $selectedRosterHydrated, $selectedRosterKey } from './bot-state'
import type * as CanonicalChat from './canonical-chat'
import { $lastRoster } from './data'
import { $groupChatWorkspace } from './group-chat'
import { openGroupChat } from './group-chat-view'
import { closeGroupChatMainTab, groupChatMainTabs } from './group-panes'
import plugin from './plugin'
import { openRosterBot } from './roster-actions'
import { $pendingBotOpen, bumpBotOpenGeneration } from './shared'

const bot = { name: 'bravo', connectionId: 'local', sourceScoped: true, canonical_session: { id: 'bot-chat' } }
const disposers: (() => void)[] = []

function registerPlugin() {
  const owned: (() => void)[] = []
  plugin.register({
    i18n: createPluginI18n('hermes-bots', fn => {
      owned.push(fn)

      return fn
    }),
    onDispose: (fn: () => void) => owned.push(fn),
    register: (item: Contribution) => {
      const dispose = registry.register({ ...item, id: `hermes-bots:${item.id}`, source: 'hermes-bots' })
      owned.push(dispose)

      return dispose
    },
    storage: { get: async (_key: string, fallback: unknown) => fallback, set: async () => {} }
  } as unknown as PluginContext)

  const dispose = () =>
    owned
      .splice(0)
      .reverse()
      .forEach(fn => fn())

  disposers.push(dispose)

  return dispose
}

function focus(pane: string) {
  act(() => {
    $layoutTree.set(
      split('row', [
        group(['sessions'], { id: 'side', active: 'sessions' }),
        group(
          [
            'workspace',
            ...$sessionTiles.get().map(tile => `session-tile:${tile.storedSessionId}`),
            'hermes-bots:routines',
            ...[...groupChatMainTabs.keys()].map(name => `plugin-workspace:hermes-bots:group:${name}`)
          ],
          { id: 'main', active: pane }
        )
      ])
    )
    noteActiveTreeGroup(pane === 'sessions' ? 'side' : 'main')
  })
}

const routines = () => registry.getArea('panes').find(item => item.id === 'hermes-bots:routines')

const settle = () =>
  act(async () => {
    await new Promise(resolve => setTimeout(resolve, 10))
  })

async function canonicalPrimaryLanding(profile: string, storedId: string, hydrate = true) {
  const actual = await vi.importActual<typeof CanonicalChat>('./canonical-chat')
  canonical.openBotCanonicalChat.mockImplementationOnce(actual.openBotCanonicalChat)
  transport.requestProfile.mockImplementation(async (_route: unknown, method: string, params: unknown) => {
    expect(method).toBe('session.list')
    expect(params).toMatchObject({ profile, title: 'Bot Chat', include_hidden: true })

    return { sessions: [{ id: storedId, title: 'Bot Chat', message_count: 0 }] }
  })
  const routes = [{ connectionId: 'local', profile, targetProfile: profile, mode: 'local' as const }]
  const previousDesktop = window.hermesDesktop
  window.hermesDesktop = { ...previousDesktop, getProfileRoutes: async () => routes } as typeof window.hermesDesktop
  disposers.push(() => {
    window.hermesDesktop = previousDesktop
  })
  // Only the async route-resume publication is driven here. Canonical lookup,
  // SDK/core navigation, scope metadata and hydration/current-intent are real.
  const landed = Promise.withResolvers<void>()

  const onRoute = () => {
    if (window.location.hash.endsWith(`/${storedId}`)) {
      $selectedStoredSessionId.set(storedId)

      if (hydrate) {
        $activeSessionId.set(`${profile}-runtime`)
      }

      landed.resolve()
    }
  }

  window.addEventListener('hashchange', onRoute)
  disposers.push(() => window.removeEventListener('hashchange', onRoute))

  return { landed: landed.promise }
}

beforeEach(() => {
  vi.clearAllMocks()
  $botChatScopes.set({})
  $activeSessionId.set(null)
  $gatewayState.set('closed')
  transport.agents.mockResolvedValue({ profiles: [bot], sources: [], fetchedAt: 1 })
  transport.request.mockImplementation(async (method: string) =>
    method === 'profiles.list' ? { profiles: [bot] } : {}
  )
  transport.requestProfile.mockResolvedValue({ rooms: [], next_offset: null })
  $sessions.set([makeSessionInfo({ id: 'ordinary', title: 'Ordinary conversation', profile: 'default' })])
  $selectedStoredSessionId.set('ordinary')
  $sessionTiles.set([
    {
      storedSessionId: 'bot-chat',
      workspaceMode: 'bots',
      workspaceOwnerKey: 'bot:local::bravo',
      workspaceTabTitle: 'Bot Chat',
      ownerRoute: { connectionId: 'local', profile: 'bravo', mode: 'local' }
    },
    { storedSessionId: 'ordinary', workspaceMode: 'sessions' }
  ])
  $lastRoster.set([bot])
  $rosterHydrated.set(true)
  $selectedRosterHydrated.set(true)
  $selectedRosterKey.set('local::bravo')
  $openBotChat.set(null)
  $groupChatWorkspace.set(null)
  $sidebarProjectFilter.set([])
  $sidebarShowArchived.set(false)
  setWorkspaceScope('sessions')
  focus('workspace')
})
afterEach(() => {
  cleanup()

  for (const name of groupChatMainTabs.keys()) {
    closeGroupChatMainTab(name)
  }

  disposers
    .splice(0)
    .reverse()
    .forEach(fn => fn())
  $sessionTiles.set([])
  $sessions.set([])
  $openBotChat.set(null)
  $groupChatWorkspace.set(null)
  bumpBotOpenGeneration()
  $sidebarProjectFilter.set([])
  $sidebarShowArchived.set(false)
  $projectScope.set(ALL_PROJECTS)
  $projectTree.set([])
  setSidebarAgentsGrouped(false)
})

it('registers the real roster in Sessions, including empty, search, archive and project modes, and removes it on disable', async () => {
  const disable = registerPlugin()
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <SidebarProvider>
          <ChatSidebar
            currentView="chat"
            onArchiveSession={() => {}}
            onBranchSession={() => {}}
            onDeleteSession={() => {}}
            onLoadMoreSessions={() => {}}
            onManageCronJob={() => {}}
            onNavigate={() => {}}
            onNewSessionInWorkspace={() => {}}
            onNewSessionSplit={() => {}}
            onResumeSession={() => {}}
            onRetrySessions={async () => {}}
            onTriggerCronJob={async () => {}}
          />
        </SidebarProvider>
      </MemoryRouter>
    </QueryClientProvider>
  )
  expect(await screen.findByText('Bravo')).toBeTruthy()
  expect(screen.getByText('Ordinary conversation')).toBeTruthy()
  const heading = screen.getByRole('button', { name: 'Bots', expanded: true })
  expect(heading).toBeTruthy()
  expect(registry.getArea('panes').some(item => item.id === 'hermes-bots:pane')).toBe(false)
  const roster = screen.getByText('Bravo').closest('[data-slot="bots-roster"]')
  expect(roster?.className).not.toContain('flex-1')
  expect(roster?.className).toContain('overscroll-y-auto')
  fireEvent.change(screen.getByPlaceholderText(/search sessions/i), { target: { value: 'no match' } })
  expect(screen.getByText('Bravo')).toBeTruthy()
  act(() => $sidebarShowArchived.set(true))
  expect(screen.getByText('Bravo')).toBeTruthy()
  act(() => {
    $sidebarProjectFilter.set(['project-does-not-match'])
    $sessions.set([])
  })
  expect(screen.getByText('Bravo')).toBeTruthy()
  fireEvent.change(screen.getByPlaceholderText(/search sessions/i), { target: { value: '' } })
  act(() => {
    $sidebarShowArchived.set(false)
    $sidebarProjectFilter.set([])
    setSidebarAgentsGrouped(true)
    $projectTree.set([{ id: '/repos/demo', label: 'Demo project', path: '/repos/demo', repos: [], sessionCount: 0 }])
    $projectScope.set('/repos/demo')
  })
  expect(screen.getByText('Bravo')).toBeTruthy()
  expect(globalThis.document.querySelector('[data-sessions-project="/repos/demo"]')).toBeTruthy()
  // A real query refresh and selection reconciliation cannot reclaim the
  // ordinary workspace just because the shared roster is mounted.
  focus('session-tile:bot-chat')
  await settle()
  focus('session-tile:ordinary')
  await settle()
  transport.request.mockImplementation(async (method: string) =>
    method === 'profiles.list' ? { profiles: [{ ...bot, description: 'fresh roster snapshot' }] } : {}
  )
  await act(async () => {
    await client.invalidateQueries()
  })
  expect($workspaceMode.get()).toBe('sessions')
  act(disable)
  expect(screen.queryByText('Bravo')).toBeNull()
  act(() => {
    registerPlugin()
  })
  expect(await screen.findByText('Bravo')).toBeTruthy()
})

it('keeps group workspaces out of Routines, including sidebar focus, and ordinary focus releases group routing', async () => {
  registerPlugin()
  focus('session-tile:bot-chat')
  await settle()
  expect(routines()).toBeTruthy()
  act(() => openGroupChat('crew', 'name'))
  expect(registry.getArea('panes').some(item => item.id === 'plugin-workspace:hermes-bots:group:crew')).toBe(true)
  focus('plugin-workspace:hermes-bots:group:crew')
  await settle()
  expect(routines()).toBeUndefined()
  focus('sessions')
  await settle()
  expect(routines()).toBeUndefined()
  focus('session-tile:ordinary')
  await settle()
  expect($workspaceMode.get()).toBe('sessions')
  expect($groupChatWorkspace.get()).toBeNull()
  // The room remains open; focusing its tab is a real group entry again.
  focus('plugin-workspace:hermes-bots:group:crew')
  await settle()
  expect($workspaceMode.get()).toBe('bots')
  expect(routines()).toBeUndefined()
})

it('seats Routines only for focused bot tiles, retains it through self-focus, and yields to ordinary focus', async () => {
  registerPlugin()
  await settle()
  expect(routines()).toBeUndefined()
  focus('session-tile:bot-chat')
  await settle()
  expect(routines()?.data).toMatchObject({
    defaultCollapsed: true,
    dock: { pane: 'workspace', pos: 'right', enforce: true }
  })
  expect($workspaceNewSessionTarget.get()).toMatchObject({ kind: 'route', route: { profile: 'bravo' } })
  focus('hermes-bots:routines')
  await settle()
  expect(routines()).toBeTruthy()
  focus('session-tile:ordinary')
  await settle()
  expect(routines()).toBeUndefined()
  expect($workspaceMode.get()).toBe('sessions')
})

it('keeps a new bot tap current while the previous bot owns focus; only an ordinary selection supersedes the awaited open', async () => {
  registerPlugin()
  focus('session-tile:bot-chat')
  await settle()
  const pending = Promise.withResolvers<void>()
  canonical.prepareBotSource.mockReturnValueOnce(pending.promise)
  canonical.openBotCanonicalChat.mockResolvedValue({ registryId: 'next-chat', openedId: 'next-chat' })
  const opening = openRosterBot({ ...bot, name: 'next', canonical_session: { id: 'next-chat' } })
  // Opening navigation does not change the working conversation.
  focus('sessions')
  await settle()
  expect($workspaceNewSessionTarget.get()).toMatchObject({ kind: 'route', route: { profile: 'next' } })
  act(() => setTreeSideCollapsed('left', true))
  expect($pendingBotOpen.get()?.key).toBe('local::next')
  openSession('not-yet-resumed', () => {})
  expect($pendingBotOpen.get()).toBeNull()
  pending.resolve()
  await expect(opening).resolves.toBe(false)
  expect(canonical.openBotCanonicalChat).not.toHaveBeenCalled()
  await settle()
  expect($workspaceMode.get()).toBe('sessions')
  expect(routines()).toBeUndefined()
})

it('ordinary tile focus supersedes a pending open before its next async continuation', async () => {
  registerPlugin()
  focus('session-tile:bot-chat')
  await settle()
  const pending = Promise.withResolvers<void>()
  canonical.prepareBotSource.mockReturnValueOnce(pending.promise)
  const opening = openRosterBot({ ...bot, name: 'next', canonical_session: { id: 'next-chat' } })
  focus('session-tile:ordinary')
  expect($pendingBotOpen.get()).toBeNull()
  pending.resolve()
  await expect(opening).resolves.toBe(false)
})

it('a failed source wake releases routing even without a new focus or open claim', async () => {
  registerPlugin()
  focus('session-tile:ordinary')
  await settle()
  // A failed source wake is also a terminal transition, even if no claim or
  // focus change was ever published. It cannot leave '+' on the absent bot.
  canonical.prepareBotSource.mockRejectedValueOnce(new Error('source unavailable'))
  await expect(openRosterBot({ ...bot, name: 'offline', canonical_session: { id: 'offline-chat' } })).resolves.toBe(
    false
  )
  await settle()
  expect($workspaceMode.get()).toBe('sessions')
})

it('lands a default canonical open in primary after mobile sidebar dismissal, then yields to ordinary selection', async () => {
  $sessionTiles.set([])
  registerPlugin()
  focus('workspace')
  await settle()
  expect(routines()).toBeUndefined()
  const { landed } = await canonicalPrimaryLanding('next', 'next-chat')
  const pending = Promise.withResolvers<void>()
  canonical.prepareBotSource.mockReturnValueOnce(pending.promise)
  const opening = openRosterBot({ ...bot, name: 'next', canonical_session: { id: 'next-chat' } })
  act(() => setTreeSideCollapsed('left', true))
  await settle()
  expect($pendingBotOpen.get()?.key).toBe('local::next')
  pending.resolve()
  await landed
  await expect(opening).resolves.toBe(true)
  await settle()
  expect($sessionTiles.get()).toEqual([])
  expect($selectedStoredSessionId.get()).toBe('next-chat')
  expect($openBotChat.get()?.openedRegistryId).toBe('next-chat')
  expect($workspaceNewSessionTarget.get()).toMatchObject({ kind: 'route', route: { profile: 'next' } })
  expect(routines()).toBeTruthy()
  const { host } = await import('@hermes/plugin-sdk')
  expect(host.state.focusedSessionOwner.get()).toMatchObject({ profile: 'next', connectionId: 'local' })
  // Ownership survives the transient claim and does not follow roster selection.
  act(() => {
    $openBotChat.set(null)
    $selectedRosterKey.set('local::bravo')
  })
  focus('hermes-bots:routines')
  await settle()
  expect(routines()).toBeTruthy()
  expect($workspaceNewSessionTarget.get()).toMatchObject({ kind: 'route', route: { profile: 'next' } })
  openSession('ordinary', () => {
    $selectedStoredSessionId.set('ordinary')
  })
  await settle()
  expect($workspaceMode.get()).toBe('sessions')
  expect(routines()).toBeUndefined()
  // A second, pending open is superseded even by selecting an ordinary chat
  // already on screen. The sidebar-close gesture above was not such intent.
  const successor = Promise.withResolvers<void>()
  canonical.prepareBotSource.mockReturnValueOnce(successor.promise)
  const successorOpening = openRosterBot(bot)
  openSession('ordinary', () => {})
  expect($pendingBotOpen.get()).toBeNull()
  expect($workspaceMode.get()).toBe('sessions')
  successor.resolve()
  await expect(successorOpening).resolves.toBe(false)
})

it('ordinary selection during primary hydration supersedes the canonical landing and its stale completion', async () => {
  $sessionTiles.set([])
  registerPlugin()
  focus('workspace')
  await settle()
  const { landed } = await canonicalPrimaryLanding('slow', 'slow-chat', false)
  const opening = openRosterBot({ ...bot, name: 'slow', canonical_session: { id: 'slow-chat' } })
  await landed
  expect($pendingBotOpen.get()?.key).toBe('local::slow')
  expect($selectedStoredSessionId.get()).toBe('slow-chat')
  openSession('ordinary', () => {
    $selectedStoredSessionId.set('ordinary')
  })
  expect($pendingBotOpen.get()).toBeNull()
  $activeSessionId.set('late-slow-runtime')
  await expect(opening).resolves.toBe(false)
  await settle()
  expect($selectedStoredSessionId.get()).toBe('ordinary')
  expect($openBotChat.get()).toBeNull()
  expect($workspaceMode.get()).toBe('sessions')
  expect($workspaceNewSessionTarget.get()).toBeNull()
  expect(routines()).toBeUndefined()
  expect($sessionTiles.get()).toEqual([])
})

it('listens to a late open claim and releases it on ordinary selection without roster refresh reclaiming routing', async () => {
  registerPlugin()
  await settle()
  // Focus can precede the canonical resolver publishing its claim.
  act(() => $openBotChat.set({ key: 'local::bravo', openedRegistryId: 'ordinary', openedSessionId: 'ordinary' }))
  await settle()
  expect(routines()).toBeTruthy()
  focus('session-tile:bot-chat')
  await settle()
  act(() => $openBotChat.set({ key: 'local::bravo', openedRegistryId: 'bot-registry', openedSessionId: 'bot-chat' }))
  expect($openBotChat.get()).not.toBeNull()
  focus('session-tile:ordinary')
  await settle()
  expect($openBotChat.get()).toBeNull()
  expect(routines()).toBeUndefined()
  act(() => $lastRoster.set([{ ...bot, title: 'refreshed' }]))
  expect($workspaceMode.get()).toBe('sessions')
})
