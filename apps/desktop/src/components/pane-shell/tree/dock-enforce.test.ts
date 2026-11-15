import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

// Enforced dock invariants: a plugin pane whose dock hint carries `enforce: true`
// re-homes onto its center anchor at EVERY boot's
// first adoption pass — persisted layouts otherwise pin the stale stacked
// arrangement forever, because adoption only ever places panes MISSING from
// the tree. Unlike the retired one-time heal, nothing exempts the pane: not
// a previously burned heal token, not $userPlacedPanes. The invariant is
// boot-scoped, so an intra-session drag sticks until the next launch.

const TREE_KEY = 'hermes.desktop.layoutTree.v2'
const USER_PLACED_KEY = 'hermes.desktop.userPlacedPanes.v1'
const LEGACY_HEAL_KEY = 'hermes.desktop.paneDockHeals.v1'

// The shipped regression shape: sessions and bots as SIBLING groups in a
// column (the old `pos: 'bottom'` split), workspace beside them.
const stackedTree = {
  type: 'split',
  id: 'root',
  orientation: 'row',
  weights: [1, 3],
  children: [
    {
      type: 'split',
      id: 'left-col',
      orientation: 'column',
      weights: [1, 1],
      children: [
        { type: 'group', id: 'g-sessions', panes: ['sessions'], active: 'sessions' },
        { type: 'group', id: 'g-bots', panes: ['sample:pane'], active: 'sample:pane' }
      ]
    },
    { type: 'group', id: 'g-main', panes: ['workspace'], active: 'workspace' }
  ]
}

describe('enforced dock (stacked Bots pane → sessions-zone tab, every boot)', () => {
  beforeAll(async () => {
    // Transform the store graph outside the first test's deadline. Each boot
    // still loads a fresh instance after beforeEach resets the module cache.
    await import('@/components/pane-shell/tree/store')
    vi.resetModules()
  })

  beforeEach(() => {
    window.localStorage.clear()
    vi.resetModules()
  })

  afterEach(() => {
    vi.resetModules()
  })

  async function setupTree(initialTree: object, options: { routines?: boolean } = {}) {
    window.localStorage.setItem(TREE_KEY, JSON.stringify(initialTree))

    const tree = await import('@/components/pane-shell/tree/store')
    const model = await import('@/components/pane-shell/tree/model')
    const { registry } = await import('@/contrib/registry')

    registry.register({
      id: 'workspace',
      area: 'panes',
      title: 'chat',
      data: { placement: 'main' },
      render: () => null
    })
    registry.register({
      id: 'sessions',
      area: 'panes',
      title: 'sessions',
      data: { placement: 'left' },
      render: () => null
    })
    registry.register({
      id: 'sample:pane',
      area: 'panes',
      title: 'Bots',
      data: {
        placement: 'left',
        dock: { pane: 'sessions', pos: 'center', enforce: true }
      },
      render: () => null
    })

    if (options.routines) {
      registry.register({
        id: 'hermes-bots:routines',
        area: 'panes',
        title: 'Cronjobs',
        data: { placement: 'main', dock: { pane: 'workspace', pos: 'right', enforce: true } },
        render: () => null
      })
    }

    return { model, registry, tree }
  }

  async function setup() {
    return setupTree(stackedTree)
  }

  it('retires only the old Bots tab on restore, selecting its neighbor', async () => {
    window.localStorage.setItem(
      TREE_KEY,
      JSON.stringify({
        type: 'split',
        id: 'root',
        orientation: 'row',
        weights: [1, 3],
        children: [
          {
            type: 'group',
            id: 'side',
            panes: ['sessions', 'hermes-bots:pane', 'other:tile'],
            active: 'hermes-bots:pane'
          },
          { type: 'group', id: 'main', panes: ['workspace'], active: 'workspace' }
        ]
      })
    )
    const tree = await import('@/components/pane-shell/tree/store')
    const model = await import('@/components/pane-shell/tree/model')
    const restored = tree.$layoutTree.get()!
    expect(model.findGroupOfPane(restored, 'hermes-bots:pane')).toBeNull()
    expect(model.findGroupOfPane(restored, 'sessions')).toMatchObject({
      panes: ['sessions', 'other:tile'],
      active: 'other:tile'
    })
    expect(restored).toMatchObject({ weights: [1, 3] })
  })

  it('cleans a retired split in each mode without pruning disabled plugins or changing unrelated preferences', async () => {
    const saved = {
      type: 'split',
      id: 'root',
      orientation: 'row',
      weights: [2, 7, 3],
      children: [
        {
          type: 'split',
          id: 'sidebar',
          orientation: 'column',
          weights: [4, 1],
          children: [
            { type: 'group', id: 'sessions-zone', panes: ['sessions'], active: 'sessions', tabStrip: 'never' },
            { type: 'group', id: 'retired-zone', panes: ['hermes-bots:pane'], active: 'hermes-bots:pane' }
          ]
        },
        {
          type: 'group',
          id: 'content',
          panes: ['workspace', 'session-tile:kept'],
          active: 'session-tile:kept',
          tabStrip: 'always'
        },
        { type: 'group', id: 'disabled-plugin', panes: ['disabled:tile'], active: 'disabled:tile' }
      ]
    }

    window.localStorage.setItem(TREE_KEY, JSON.stringify(saved))
    window.localStorage.setItem(`${TREE_KEY}.simple`, JSON.stringify(saved))
    const tree = await import('@/components/pane-shell/tree/store')
    const { setInterfaceMode } = await import('@/store/interface-mode')
    const { allPaneIds } = await import('./model')
    const expected = { ...saved, children: [saved.children[0].children![0], ...saved.children.slice(1)] }
    expect(tree.$layoutTree.get()).toEqual(expected)
    setInterfaceMode('simple')
    expect(tree.$layoutTree.get()).toEqual(expected)
    expect(allPaneIds(tree.$layoutTree.get()!)).toEqual(['sessions', 'workspace', 'session-tile:kept', 'disabled:tile'])
    tree.persistTree()
    setInterfaceMode('advanced')
    expect(tree.$layoutTree.get()).toEqual(expected)
    tree.persistTree()
    expect(JSON.parse(window.localStorage.getItem(TREE_KEY)!)).toEqual(expected)
    expect(JSON.parse(window.localStorage.getItem(`${TREE_KEY}.simple`)!)).toEqual(expected)
  })

  it('leaves layouts without the retired pane structurally unchanged', async () => {
    const saved = {
      type: 'split',
      id: 'kept',
      orientation: 'row',
      weights: [2, 9],
      children: [
        { type: 'group', id: 'left', panes: ['sessions', 'disabled:tile'], active: 'disabled:tile', tabStrip: 'never' },
        { type: 'group', id: 'main', panes: ['workspace'], active: 'workspace' }
      ]
    }

    window.localStorage.setItem(TREE_KEY, JSON.stringify(saved))
    const tree = await import('@/components/pane-shell/tree/store')
    expect(tree.$layoutTree.get()).toEqual(saved)
  })

  it('re-homes a stacked bots pane into the sessions tab strip, keeping sessions active', async () => {
    const { model, tree } = await setup()

    tree.watchContributedPanes()

    const group = model.findGroupOfPane(tree.$layoutTree.get()!, 'sample:pane')!

    expect(group.panes).toEqual(['sessions', 'sample:pane'])
    // Silent like adoption — the enforce must not steal the sessions tab.
    expect(group.active).toBe('sessions')
    // The persisted tree carries the tabbed shape (survives the next boot).
    const persisted = JSON.parse(window.localStorage.getItem(TREE_KEY)!) as { children?: unknown[] }

    expect(JSON.stringify(persisted)).toContain('"panes":["sessions","sample:pane"]')
  })

  it('re-homes even a USER-PLACED pane — the owner invariant beats the drag record', async () => {
    window.localStorage.setItem(USER_PLACED_KEY, JSON.stringify(['sample:pane']))

    const { model, tree } = await setup()

    tree.watchContributedPanes()

    const group = model.findGroupOfPane(tree.$layoutTree.get()!, 'sample:pane')!

    expect(group.panes).toEqual(['sessions', 'sample:pane'])
  })

  it('re-homes even when the retired heal token was already burned, and clears the stale ledger', async () => {
    window.localStorage.setItem(LEGACY_HEAL_KEY, JSON.stringify(['sample:pane:sessions-tab-v1']))

    const { model, tree } = await setup()

    tree.watchContributedPanes()

    const group = model.findGroupOfPane(tree.$layoutTree.get()!, 'sample:pane')!

    expect(group.panes).toEqual(['sessions', 'sample:pane'])
    // The one-time-heal ledger is dead state now — importing the store drops it.
    expect(window.localStorage.getItem(LEGACY_HEAL_KEY)).toBeNull()
  })

  it('is idempotent within a boot and does not fight an intra-session drag', async () => {
    const { model, tree, registry } = await setup()

    tree.watchContributedPanes()

    // Sanity: enforced into the strip.
    expect(model.findGroupOfPane(tree.$layoutTree.get()!, 'sample:pane')!.panes).toContain('sessions')

    // The user drags the pane back out into its own zone below sessions.
    tree.$layoutTree.set(JSON.parse(JSON.stringify(stackedTree)))

    // A later registry mutation re-runs the adoption pass (the enforce's
    // caller) — same boot, so the drag sticks until the next launch.
    registry.register({
      id: 'other',
      area: 'panes',
      title: 'other',
      data: { placement: 'right' },
      render: () => null
    })

    const group = model.findGroupOfPane(tree.$layoutTree.get()!, 'sample:pane')!

    expect(group.panes).toEqual(['sample:pane'])
  })

  it('re-homes again on the NEXT boot after a drag persisted the stacked shape', async () => {
    const first = await setup()

    first.tree.watchContributedPanes()
    first.tree.$layoutTree.set(JSON.parse(JSON.stringify(stackedTree)))
    first.tree.persistTree()

    // Simulate the next launch: fresh module graph, persisted stacked tree.
    vi.resetModules()

    const second = await setup()

    second.tree.watchContributedPanes()

    const group = second.model.findGroupOfPane(second.tree.$layoutTree.get()!, 'sample:pane')!

    expect(group.panes).toEqual(['sessions', 'sample:pane'])
  })

  it('shows the tab strip when already co-located but hidden with bots active (community "only Bots shows" regression)', async () => {
    // The Aug 2026 field reports: sessions+bots already share one group, the
    // legacy strip flag is set, and bots holds the active tab — the sessions
    // pane exists but is unreachable. The re-home path never runs (nothing to
    // move), so reachability has to come from somewhere else: the migration
    // drops the legacy flag, and a two-pane zone on auto shows its strip.
    const hiddenStackedTree = {
      type: 'split',
      id: 'root',
      orientation: 'row',
      weights: [1, 3],
      children: [
        {
          type: 'group',
          id: 'g-left',
          panes: ['sessions', 'sample:pane'],
          active: 'sample:pane',
          headerHidden: true
        },
        { type: 'group', id: 'g-main', panes: ['workspace'], active: 'workspace' }
      ]
    }

    const { model, tree } = await setupTree(hiddenStackedTree)

    tree.watchContributedPanes()

    const group = model.findGroupOfPane(tree.$layoutTree.get()!, 'sample:pane')!

    // Both panes stay put — but the strip is visible so SESSIONS is reachable
    // again. The active tab is NOT stolen mid-boot.
    expect(group.panes).toEqual(['sessions', 'sample:pane'])
    expect(tree.tabStripVisibleForGroup(group)).toBe(true)
  })

  it('re-homes an edge-enforced pane stranded in the sessions tab strip', async () => {
    const staleRoutinesTree = {
      type: 'split',
      id: 'root',
      orientation: 'row',
      weights: [1, 3],
      children: [
        {
          type: 'group',
          id: 'g-sessions',
          panes: ['sessions', 'sample:pane', 'hermes-bots:routines'],
          active: 'sample:pane'
        },
        { type: 'group', id: 'g-main', panes: ['workspace'], active: 'workspace' }
      ]
    }

    const { model, tree } = await setupTree(staleRoutinesTree, { routines: true })

    tree.watchContributedPanes()

    const botsGroup = model.findGroupOfPane(tree.$layoutTree.get()!, 'sample:pane')!
    const routinesGroup = model.findGroupOfPane(tree.$layoutTree.get()!, 'hermes-bots:routines')!

    expect(botsGroup.panes).toEqual(['sessions', 'sample:pane'])
    expect(botsGroup.active).toBe('sample:pane')
    expect(routinesGroup.panes).toEqual(['hermes-bots:routines'])
    expect(routinesGroup.id).not.toBe(botsGroup.id)
  })

  it('leaves an edge-enforced pane alone when it already occupies the declared split', async () => {
    const dockedRoutinesTree = {
      type: 'split',
      id: 'root',
      orientation: 'row',
      weights: [1, 3, 1],
      children: [
        {
          type: 'group',
          id: 'g-sessions',
          panes: ['sessions', 'sample:pane'],
          active: 'sample:pane'
        },
        { type: 'group', id: 'g-main', panes: ['workspace'], active: 'workspace' },
        {
          type: 'group',
          id: 'g-routines',
          panes: ['hermes-bots:routines'],
          active: 'hermes-bots:routines'
        }
      ]
    }

    const { tree } = await setupTree(dockedRoutinesTree, { routines: true })

    tree.watchContributedPanes()

    expect(tree.$layoutTree.get()).toEqual(dockedRoutinesTree)
  })
})
