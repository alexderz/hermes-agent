import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

import { TitlebarControls } from '@/app/shell/titlebar-controls'
import { PANE_TOGGLE_REVEAL_EVENT } from '@/components/pane-shell'
import { $narrowOverlayPaneIds } from '@/components/pane-shell/narrow-overlay-state'
import { registry } from '@/contrib/registry'
import { I18nProvider } from '@/i18n'
import { LAYOUT_KEYS } from '@/lib/layout-persistence'
import { $paneStates, setPaneWidthOverride } from '@/store/panes'
import { $connection } from '@/store/session'
import { stubResizeObserver } from '@/test/jsdom'

import { group, removePane, split } from '../model'
import {
  $activePresetId,
  $collapsedTreeSides,
  $hiddenTreePanes,
  $layoutTree,
  $narrowViewport,
  declareDefaultTree,
  persistTree
} from '../store'

import { NarrowOverlays, narrowOverlayWidth } from './narrow-overlays'

// Ground truth for "the Bots tab is still visible when the sessions sidebar
// collapses on a narrow window". A collapsible pane DOCKED into the sessions
// zone (SESSIONS | BOTS) must leave the grid with the zone, and the narrow
// edge overlay must mirror the zone's tab strip so the docked pane stays
// reachable — not just the zone's first pane.

beforeAll(() => {
  stubResizeObserver()
})

const disposers: (() => void)[] = []

const registerPane = (id: string, title: string, data: Record<string, unknown>, body: string) => {
  disposers.push(
    registry.register({
      area: 'panes',
      data,
      id,
      render: () => <div data-testid={`${id}-body`}>{body}</div>,
      title
    })
  )
}

beforeEach(() => {
  window.localStorage.clear()
  $hiddenTreePanes.set(new Set())

  registerPane(
    'sessions',
    'sessions',
    { collapsible: true, placement: 'left', width: '237px', revealAliases: ['chat-sidebar'] },
    'session rows'
  )
  registerPane('bots', 'Bots', { collapsible: true, placement: 'left', width: '260px' }, 'bot roster')
  registerPane('workspace', 'workspace', { placement: 'main', uncloseable: true }, 'chat')

  declareDefaultTree(split('row', [group(['sessions', 'bots']), group(['workspace'])]))
  $narrowViewport.set(true)
})

afterEach(() => {
  cleanup()
  $narrowViewport.set(false)
  $layoutTree.set(null)
  $connection.set(null)
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  delete window.document.documentElement.dataset.hermesDesktopHost
  delete (window as unknown as { hermesDesktop?: unknown }).hermesDesktop
  disposers.splice(0).forEach(dispose => dispose())
})

const revealPane = (id: string) => {
  act(() => {
    window.dispatchEvent(new CustomEvent(PANE_TOGGLE_REVEAL_EVENT, { detail: { id, mode: 'open' } }))
  })
}

const overlayTab = (paneId: string) =>
  globalThis.document.querySelector<HTMLElement>(`[data-narrow-overlay-tab="${paneId}"]`)

// The page the browser-hosted Desktop serves (its bridge writes this marker).
const asBrowserHost = () => {
  window.document.documentElement.dataset.hermesDesktopHost = 'browser'
}

// Native Desktop: the Electron preload's bridge exists and no browser marker is set.
const asNativeDesktop = () => {
  ;(window as unknown as { hermesDesktop?: unknown }).hermesDesktop = {}
}

describe('narrow overlay in native Desktop', () => {
  // A narrow native window keeps main's overlay: no full-window backdrop, so a
  // click outside a pinned overlay reaches the app under it and the overlay
  // stays open until Escape, the toggle or the edge hover closes it.
  it('puts no outside-click backdrop over the app and keeps a pinned overlay open', () => {
    asNativeDesktop()
    render(<NarrowOverlays />)
    revealPane('sessions')

    expect(globalThis.document.querySelector('[data-narrow-overlay-backdrop]')).toBeNull()
    expect(globalThis.document.querySelector('[data-narrow-overlay="sessions"]')).not.toBeNull()
  })

  // Closing the sessions sidebar (⌘B's setter in a narrow window) closes the
  // overlay only when it shows that pane, as on main; a zone mate it shows
  // instead (Bots) stays open.
  it('closes only the named pane, not the zone mate the overlay shows', () => {
    asNativeDesktop()
    const { queryByTestId } = render(<NarrowOverlays />)
    revealPane('bots')
    act(() =>
      window.dispatchEvent(new CustomEvent(PANE_TOGGLE_REVEAL_EVENT, { detail: { id: 'chat-sidebar', mode: 'close' } }))
    )
    expect(queryByTestId('bots-body')).toBeTruthy()

    act(() =>
      window.dispatchEvent(new CustomEvent(PANE_TOGGLE_REVEAL_EVENT, { detail: { id: 'bots', mode: 'close' } }))
    )
    expect(queryByTestId('bots-body')).toBeNull()
  })
})

describe('narrow overlay of a stacked zone', () => {
  it('DER-794 explicitly shows toggle-hidden Files without changing desktop state or revealing unavailable neighbors', () => {
    asBrowserHost()
    registerPane(
      'files',
      'Files',
      {
        collapsible: true,
        placement: 'right',
        width: '237px',
        revealAliases: ['file-browser'],
        narrowRevealWhenHidden: true
      },
      'file tree'
    )
    registerPane('review', 'Review', { collapsible: true, placement: 'right' }, 'unavailable review')
    disposers.push(
      registry.register({
        id: 'disabled:pane',
        area: 'panes',
        source: 'plugin:disabled',
        enabled: false,
        data: { collapsible: true, placement: 'right', narrowRevealWhenHidden: true },
        render: () => <div>Disabled plugin</div>
      })
    )
    $layoutTree.set(
      split(
        'row',
        [
          group(['sessions', 'bots'], { id: 'nav' }),
          group(['workspace'], { id: 'main' }),
          group(['files', 'review', 'disabled:pane'], { id: 'tools', active: 'review', minimized: true }),
          group(['jobs'], { id: 'jobs' })
        ],
        [1, 5, 2, 1]
      )
    )
    $hiddenTreePanes.set(new Set(['files', 'review']))
    $collapsedTreeSides.set(new Set(['right']))
    $activePresetId.set('focus')
    setPaneWidthOverride('files', 321)
    persistTree()

    const snapshot = () => ({
      tree: $layoutTree.get(),
      hidden: $hiddenTreePanes.get(),
      sides: $collapsedTreeSides.get(),
      panes: $paneStates.get(),
      preset: $activePresetId.get(),
      raw: window.localStorage.getItem(LAYOUT_KEYS.tree)
    })

    const desktop = structuredClone(snapshot())

    const view = render(
      <MemoryRouter>
        <I18nProvider configClient={null} initialLocale="en">
          <TitlebarControls onOpenSettings={() => {}} />
          <NarrowOverlays />
        </I18nProvider>
      </MemoryRouter>
    )

    const overlay = () => globalThis.document.querySelector('[data-narrow-overlay]')

    const hoverEdges = () =>
      [...view.container.querySelectorAll('div')]
        .filter(element => element.classList.contains('w-1.5'))
        .forEach(element => fireEvent.mouseEnter(element))

    expect(overlay()).toBeNull()
    hoverEdges()
    expect(screen.queryByText('file tree')).toBeNull()
    fireEvent.keyDown(window, { key: 'Escape' })

    fireEvent.click(screen.getByRole('button', { name: 'Show right sidebar' }))
    expect(screen.getByText('file tree')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Hide right sidebar' }).getAttribute('aria-expanded')).toBe('true')
    expect(screen.queryByText('unavailable review')).toBeNull()
    expect(overlayTab('review')).toBeNull()
    expect(snapshot()).toEqual(desktop)
    const files = registry.getArea('panes').find(pane => pane.id === 'files')!
    expect(
      narrowOverlayWidth(
        {
          paneFor: id => registry.getArea('panes').find(pane => pane.id === id),
          paneGone: () => false,
          overrides: $paneStates.get()
        },
        $layoutTree.get(),
        files
      )
    ).toBe('321px')
    fireEvent.click(screen.getByRole('button', { name: 'Hide right sidebar' }))
    expect(overlay()).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Show right sidebar' }))
    expect(screen.getByText('file tree')).toBeTruthy()
    fireEvent.keyDown(window, { key: 'Escape' })
    revealPane('review')
    expect(overlay()).toBeNull()
    revealPane('disabled:pane')
    expect(overlay()).toBeNull()

    act(() => registerPane('jobs', 'Jobs', { placement: 'main', collapsible: true }, 'scheduled jobs'))
    fireEvent.click(screen.getByRole('button', { name: 'Show right sidebar' }))
    expect(screen.getByText('scheduled jobs')).toBeTruthy()
    revealPane('file-browser')
    expect(screen.getByText('file tree')).toBeTruthy()
    expect(screen.queryByText('scheduled jobs')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Hide right sidebar' }))
    expect(overlay()).toBeNull()
    expect(snapshot()).toEqual(desktop)

    act(() => {
      $narrowViewport.set(false)
    })
    act(() => {
      $narrowViewport.set(true)
    })
    act(() =>
      registerPane(
        'files',
        'Files',
        { collapsible: true, placement: 'right', narrowRevealWhenHidden: true, revealAliases: ['file-browser'] },
        'file tree'
      )
    )
    expect(overlay()).toBeNull()
    hoverEdges()
    expect(screen.queryByText('file tree')).toBeNull()
    expect(screen.queryByText('unavailable review')).toBeNull()
    expect(snapshot()).toEqual(desktop)
    fireEvent.keyDown(window, { key: 'Escape' })
    // A dismissed Files slot is not an excuse to rewrite the desktop tree.
    act(() => $layoutTree.set(removePane($layoutTree.get()!, 'files')))
    persistTree()
    const withoutSlot = structuredClone(snapshot())
    revealPane('file-browser')
    expect(screen.getByText('file tree')).toBeTruthy()
    expect(snapshot()).toEqual(withoutSlot)
    fireEvent.click(screen.getByRole('button', { name: 'Hide right sidebar' }))
    expect(overlay()).toBeNull()
  })

  it('dismisses an outside tap while preserving inside controls and cancelled gestures', () => {
    asBrowserHost()
    render(<NarrowOverlays />)
    revealPane('sessions')
    fireEvent.pointerDown(overlayTab('bots')!, { button: 0 })
    expect(overlayTab('bots')?.getAttribute('aria-selected')).toBe('true')

    const backdrop = globalThis.document.querySelector<HTMLElement>('[data-narrow-overlay-backdrop]')!
    expect(backdrop).not.toBeNull()
    fireEvent.pointerDown(backdrop, { pointerId: 1, button: 0, clientX: 300, clientY: 200 })
    fireEvent.pointerCancel(backdrop, { pointerId: 1 })
    fireEvent.pointerUp(backdrop, { pointerId: 1, button: 0, clientX: 300, clientY: 200 })
    expect(overlayTab('bots')).not.toBeNull()

    fireEvent.pointerDown(backdrop, { pointerId: 2, button: 0, clientX: 300, clientY: 200 })
    fireEvent.pointerUp(backdrop, { pointerId: 2, button: 0, clientX: 300, clientY: 200 })
    expect(globalThis.document.querySelector('[data-narrow-overlay]')).toBeNull()
    expect($narrowOverlayPaneIds.get().size).toBe(0)
  })

  it('closes the visible zone mate through the sessions sidebar alias', () => {
    asBrowserHost()
    const { queryByTestId } = render(<NarrowOverlays />)
    revealPane('bots')
    expect(queryByTestId('bots-body')).toBeTruthy()
    act(() =>
      window.dispatchEvent(new CustomEvent(PANE_TOGGLE_REVEAL_EVENT, { detail: { id: 'chat-sidebar', mode: 'close' } }))
    )
    expect(queryByTestId('bots-body')).toBeNull()
    expect($narrowOverlayPaneIds.get().size).toBe(0)
  })
  it('publishes visible zone mates and clears them when Escape closes the overlay', () => {
    const view = render(<NarrowOverlays />)
    expect($narrowOverlayPaneIds.get().size).toBe(0)
    revealPane('sessions')
    expect([...$narrowOverlayPaneIds.get()]).toEqual(expect.arrayContaining(['sessions', 'bots', 'chat-sidebar']))
    fireEvent.keyDown(window, { key: 'Escape' })
    expect($narrowOverlayPaneIds.get().size).toBe(0)
    revealPane('bots')
    view.unmount()
    expect($narrowOverlayPaneIds.get().size).toBe(0)
  })

  it('reserves the browser touch titlebar above overlay tabs', () => {
    window.document.documentElement.dataset.hermesDesktopHost = 'browser'

    const overlayInset = (touch: boolean) => {
      vi.stubGlobal(
        'matchMedia',
        vi.fn().mockReturnValue({ matches: touch, addEventListener: vi.fn(), removeEventListener: vi.fn() })
      )
      const { container, unmount } = render(<NarrowOverlays />)
      revealPane('sessions')
      const inset = parseFloat(container.querySelector<HTMLElement>('[data-narrow-overlay]')!.style.paddingTop)
      unmount()

      return inset
    }

    // The touch titlebar is taller than the pointer one; the tabs clear it.
    expect(overlayInset(true)).toBeGreaterThan(overlayInset(false))
  })
  it('mirrors the zone tab strip so every stacked collapsible stays reachable', () => {
    const { getByTestId, queryByTestId } = render(<NarrowOverlays />)

    revealPane('sessions')

    // Both zone-mates surface as tabs; the revealed pane's body is on screen.
    expect(overlayTab('sessions')).toBeTruthy()
    expect(overlayTab('bots')).toBeTruthy()
    expect(getByTestId('sessions-body')).toBeTruthy()
    expect(queryByTestId('bots-body')).toBeNull()

    // Clicking the BOTS tab swaps the overlay to the docked pane.
    fireEvent.pointerDown(overlayTab('bots')!, { button: 0 })
    expect(getByTestId('bots-body')).toBeTruthy()
    expect(queryByTestId('sessions-body')).toBeNull()
  })

  it('focuses zone tabs without switching until keyboard activation and retains tab focus', () => {
    const { getByTestId, queryByTestId } = render(<NarrowOverlays />)
    revealPane('sessions')
    const sessions = overlayTab('sessions')!
    const bots = overlayTab('bots')!
    act(() => sessions.focus())

    expect(sessions.tabIndex).toBe(0)
    expect(bots.tabIndex).toBe(-1)
    fireEvent.keyDown(sessions, { key: 'ArrowRight' })
    expect(globalThis.document.activeElement).toBe(bots)
    expect(getByTestId('sessions-body')).toBeTruthy()
    expect(queryByTestId('bots-body')).toBeNull()
    fireEvent.keyDown(bots, { key: 'Enter' })
    expect(getByTestId('bots-body')).toBeTruthy()
    expect(queryByTestId('sessions-body')).toBeNull()
    expect(globalThis.document.activeElement).toBe(overlayTab('bots'))
  })

  it('keeps the stripless form for a zone with a single collapsible', () => {
    // Direct set: declareDefaultTree only ADOPTS into an existing tree — it
    // would keep the beforeEach zone (with bots) instead of replacing it.
    $layoutTree.set(split('row', [group(['sessions']), group(['workspace'])]))

    const { getByTestId } = render(<NarrowOverlays />)

    revealPane('sessions')

    expect(getByTestId('sessions-body')).toBeTruthy()
    expect(overlayTab('sessions')).toBeNull()
  })

  it('pads the overlay below the native window controls on macOS', () => {
    // Ground truth for "the SESSIONS tab strip slides under the traffic
    // lights on a narrow window" (#110033). The overlay starts at the
    // viewport's top edge, so without a reservation its tab strip sits under
    // the native controls.
    Object.defineProperty(window, 'hermesDesktop', { configurable: true, value: {} })
    $connection.set({ windowButtonPosition: { x: 24, y: 0 } } as never)
    // jsdom has no layout: the overlay fills the viewport's top-left corner.
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({
      bottom: 800,
      height: 800,
      left: 0,
      right: 237,
      toJSON: () => ({}),
      top: 0,
      width: 237,
      x: 0,
      y: 0
    } as DOMRect)

    render(<NarrowOverlays />)
    revealPane('sessions')

    // Controls rect = { x: 0, y: 0, width: 24 + 58, height: 34 }; the
    // reservation is the overlap's bottom edge, so the strip starts below it.
    const overlay = globalThis.document.querySelector<HTMLElement>('[data-narrow-overlay="sessions"]')
    expect(overlay?.style.paddingTop).toBe('34px')
    // The reserved band stays a window-drag target, as in a docked TreeGroup.
    const dragSpacer = overlay?.querySelector<HTMLElement>('[aria-hidden="true"]')
    expect(dragSpacer).not.toBeNull()
    expect(dragSpacer?.style.height).toBe('34px')
  })

  it('honors the user drag width, not the declared width, when the zone collapsed', () => {
    // The sash writes a widthOverride per shown pane of the zone; the overlay
    // must size from the same resolution the docked zone uses (fixedTrackSize
    // = declared max() refined by overrides), not from data.width alone.
    // jsdom's CSSOM drops the min() wrapper from style.width, so the rendered
    // width is unobservable here — assert the overlay's own resolution
    // (narrowOverlayWidth, the pure helper the component styles from) against
    // the live tree + store the mounted overlay saw.
    setPaneWidthOverride('sessions', 170)
    setPaneWidthOverride('bots', 170)

    const { container } = render(<NarrowOverlays />)

    revealPane('bots')

    const overlay = container.querySelector<HTMLElement>('[data-narrow-overlay]')
    expect(overlay).toBeTruthy()

    const tree = $layoutTree.get()!
    const bots = registry.getArea('panes').find(p => p.id === 'bots')!

    const width = narrowOverlayWidth(
      {
        paneFor: id => registry.getArea('panes').find(p => p.id === id),
        paneGone: () => false,
        overrides: $paneStates.get()
      },
      tree,
      bots
    )

    // The user dragged the zone to 170px; the declared 260px must lose.
    expect(width).toBe('170px')
    expect(width).not.toBe('260px')

    // And the seamless fallback: without a tree the declared width still
    // sizes the overlay.
    expect(narrowOverlayWidth({ paneFor: () => undefined, paneGone: () => false, overrides: {} }, null, bots)).toBe(
      '260px'
    )
  })
})
