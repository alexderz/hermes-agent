/** Registration/disposal contracts. The adjacent sidebar-workspace integration
 * test exercises real roster rendering, tile ownership and ordinary navigation. */
import type * as HermesSdk from '@hermes/plugin-sdk'
import type { PluginContext } from '@hermes/plugin-sdk'
import { atom } from 'nanostores'
import type { ReactNode } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// eslint-disable-next-line no-restricted-imports
import { I18nProvider } from '@/i18n'

const mocks = vi.hoisted(() => ({
  owns: vi.fn(() => false),
  unbindProfile: vi.fn(),
  paneVisibility: vi.fn(),
  setWorkspaceScope: vi.fn(),
  undismissPane: vi.fn()
}))

vi.mock('@hermes/plugin-sdk', async importOriginal => {
  const original = await importOriginal<typeof HermesSdk>()
  const { atom } = await import('nanostores')

  return {
    ...original,
    host: {
      ...original.host,
      onEvent: undefined,
      paneVisibility: mocks.paneVisibility,
      setWorkspaceScope: mocks.setWorkspaceScope,
      undismissPane: mocks.undismissPane,
      state: {
        ...original.host.state,
        focusedStoredSessionId: atom<null | string>(null),
        focusedPaneId: atom<null | string>(null),
        focusedSessionWorkspace: atom(null),
        workspaceMode: atom('sessions')
      }
    }
  }
})
vi.mock('./avatar', () => ({ startFaceClock: vi.fn(), stopFaceClock: vi.fn() }))
vi.mock('./relay', () => ({ startBotRelay: vi.fn(), stopBotRelay: vi.fn() }))
vi.mock('./screen-autoraise', () => ({ startScreenAutoRaise: () => () => {} }))
vi.mock('./session-sweep', () => ({ startHideSweepScheduler: vi.fn() }))
vi.mock('./canonical-chat', () => ({ openBotCanonicalChat: vi.fn() }))
vi.mock('./chat-empty', () => ({ BotChatEmpty: () => null }))
vi.mock('./cron', () => ({ bindProfileSync: () => mocks.unbindProfile, RoutinesPane: () => null }))
vi.mock('./roster-pane', async () => {
  const { useI18n } = await import('@hermes/plugin-sdk')

  return {
    botChatOwnsWorkspace: mocks.owns,
    BotsPane: ({ embedded }: { embedded: boolean }) => <span data-embedded={embedded}>{useI18n().t.common.bots}</span>,
    releaseStaleOpenBotChat: vi.fn(),
    selectedRosterBot: () => null
  }
})
vi.mock('./data', async importOriginal => ({
  ...(await importOriginal<object>()),
  migrateBotMeta: async () => undefined
}))

const { host, SIDEBAR_SECTIONS_AREA } = await import('@hermes/plugin-sdk')
const { $groupChatWorkspace } = await import('./group-chat')
const { recordGroupMainTab, dropGroupMainTab } = await import('./group-panes')
const { $openBotChat } = await import('./bot-state')
const plugin = (await import('./plugin')).default

interface Registration {
  area: string
  data?: Record<string, unknown>
  id: string
  render?: () => ReactNode
}
const harnesses: ReturnType<typeof recordingContext>[] = []

function recordingContext() {
  const disposers: (() => void)[] = []
  const registrations: Registration[] = []

  const ctx = {
    i18n: { register: () => () => {}, t: (key: string) => key },
    onDispose: (fn: () => void) => disposers.push(fn),
    register: (registration: Registration) => {
      registrations.push(registration)

      const dispose = () => {
        const at = registrations.indexOf(registration)

        if (at >= 0) {
          registrations.splice(at, 1)
        }
      }

      disposers.push(dispose)

      return dispose
    },
    storage: { get: async () => undefined, set: async () => {} }
  }

  return {
    ctx: ctx as unknown as PluginContext,
    dispose: () =>
      disposers
        .splice(0)
        .reverse()
        .forEach(fn => fn()),
    find: (id: string) => registrations.find(item => item.id === id)
  }
}

function register() {
  const harness = recordingContext()
  harnesses.push(harness)
  plugin.register(harness.ctx)

  return harness
}

const settle = () => new Promise(resolve => setTimeout(resolve, 10))

function focus(id: string | null) {
  // The production SDK is readonly; these stand-ins are test inputs.
  ;(host.state.focusedStoredSessionId as ReturnType<typeof atom<null | string>>).set(id)
}

function pane(id: string | null) {
  ;(host.state.focusedPaneId as ReturnType<typeof atom<null | string>>).set(id)
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.owns.mockReturnValue(false)
  mocks.paneVisibility.mockImplementation(() => atom(false))
  focus(null)
  pane(null)
  $groupChatWorkspace.set(null)
  $openBotChat.set(null)
})
afterEach(() => {
  harnesses.splice(0).forEach(harness => harness.dispose())
  dropGroupMainTab('crew')
})

describe('the embedded roster contribution', () => {
  it('uses the shared section area, not a pane, and localizes its label live', () => {
    const harness = register()
    expect(harness.find('pane')).toBeUndefined()
    expect(harness.find('roster')?.area).toBe(SIDEBAR_SECTIONS_AREA)
    const render = harness.find('roster')!.render!

    const localized = (locale: string) =>
      renderToStaticMarkup(
        <I18nProvider configClient={null} initialLocale={locale}>
          {render()}
        </I18nProvider>
      )

    expect(localized('en')).toContain('data-embedded="true"')
    expect(localized('ru')).not.toBe(localized('en'))
  })
})
describe('Routines registration', () => {
  it('arrives collapsed on the enforced workspace-right dock only after bot ownership', async () => {
    const harness = register()
    await settle()
    expect(harness.find('routines')).toBeUndefined()
    mocks.owns.mockReturnValue(true)
    focus('bot')
    await settle()
    expect(harness.find('routines')?.data).toMatchObject({
      defaultCollapsed: true,
      dock: { pane: 'workspace', pos: 'right', enforce: true }
    })
  })
  it('honors Close through a group detour, then restores it on real ordinary-to-bot entry', async () => {
    mocks.owns.mockReturnValue(true)
    const harness = register()
    await settle()
    expect(mocks.undismissPane).toHaveBeenCalledTimes(1)
    recordGroupMainTab('crew', () => {})
    mocks.owns.mockReturnValue(false)
    pane('plugin-workspace:hermes-bots:group:crew')
    await settle()
    expect(harness.find('routines')).toBeUndefined()
    mocks.owns.mockReturnValue(true)
    pane('session-tile:bot')
    await settle()
    expect(harness.find('routines')).toBeTruthy()
    expect(mocks.undismissPane).toHaveBeenCalledTimes(1)
    mocks.owns.mockReturnValue(false)
    focus('ordinary')
    await settle()
    mocks.owns.mockReturnValue(true)
    focus('bot')
    await settle()
    expect(mocks.undismissPane).toHaveBeenCalledTimes(2)
    expect(mocks.undismissPane).toHaveBeenLastCalledWith('hermes-bots:routines')
  })
  it('tears down pending reconciliation and every listener on disable/re-enable', async () => {
    const harness = register()
    harness.dispose()
    mocks.owns.mockReturnValue(true)
    focus('bot')
    $openBotChat.set({ key: 'local::bravo', openedRegistryId: 'bot' })
    await settle()
    expect(harness.find('routines')).toBeUndefined()
    expect(mocks.unbindProfile).toHaveBeenCalledTimes(1)
    const next = register()
    await settle()
    expect(next.find('routines')).toBeTruthy()
    expect(mocks.undismissPane).toHaveBeenCalledTimes(1)
  })
  it('keeps the established always-registered fallback when paneVisibility is absent', () => {
    const restore = host.paneVisibility
    // @ts-expect-error modelling an older SDK
    host.paneVisibility = undefined

    try {
      expect(register().find('routines')).toBeTruthy()
    } finally {
      host.paneVisibility = restore
    }
  })
})
