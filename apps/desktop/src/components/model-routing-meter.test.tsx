import { cleanup, render, within } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, expect, it, vi } from 'vitest'

// The plugin's public JS entry is intentionally untyped; exercise its registered UI.
// @ts-expect-error -- standalone plugin entry has no TypeScript declaration
import plugin from '../../../../plugins/model-routing/desktop/plugin.js'

const fixture = vi.hoisted(() => ({
  showPanel: false,
  data: {
    cards: [
      { id: 'claude', name: 'Claude', used_percent: 40 as number | null | undefined,
        short_used_percent: 15 as number | null | undefined, pace_used_percent: 9 as number | null | undefined,
        fresh: true, eligible: true, pace_delta: 2 },
      { id: 'codex', name: 'ChatGPT', used_percent: 70, fresh: true, eligible: true, pace_delta: 3 },
      { id: 'supergrok', name: 'SuperGrok', used_percent: 15, fresh: true, eligible: true, pace_delta: 4 }
    ],
    openrouter: { week: 12.34 as number | null | undefined, today: 1.23 as number | null | undefined },
    cheaperinference: {
      status: 'ok' as string,
      spend: { today: 0.42, week: 1.9, month: 4.47, balance: null } as Record<string, unknown> | null,
      active_model: 'model-b' as string | null,
      models: [
        { id: 'model-a', provider: 'DeepSeek', input: 0.5, output: 2, discount: 15 },
        { id: 'model-b', provider: 'DeepSeek', input: 0.075, output: 0.24, discount: 56 }
      ] as Array<Record<string, unknown>>
    }
  }
}))

vi.mock('@hermes/plugin-sdk', () => ({
  Button: ({ children, 'aria-label': label }: { children: ReactNode; 'aria-label': string }) => (
    <button aria-label={label}>{children}</button>
  ),
  Popover: ({ children }: { children: ReactNode }) => <>{children}</>,
  PopoverContent: ({ children }: { children: ReactNode }) => fixture.showPanel ? <div data-testid="usage-panel">{children}</div> : null,
  PopoverTrigger: ({ children }: { children: ReactNode }) => <>{children}</>,
  STATUSBAR_AREAS: { right: 'right' },
  StatusDot: ({ tone }: { tone: string }) => <span data-tone={tone} />,
  Tip: ({ children }: { children: ReactNode }) => <>{children}</>,
  queryClient: {},
  useQuery: () => ({ data: fixture.data })
}))

afterEach(() => {
  cleanup()
  fixture.showPanel = false
  Object.assign(fixture.data.cards[0], { used_percent: 40, short_used_percent: 15, pace_used_percent: 9, pace_delta: 2 })
  fixture.data.openrouter.week = 12.34
  fixture.data.openrouter.today = 1.23
})

function meter() {
  let draw: (() => ReactNode) | undefined
  plugin.register({ register: (item: { render: () => ReactNode }) => { draw = item.render } })
  expect(draw).toBeTypeOf('function')

  return draw!()
}

it('keeps weekly and daily OpenRouter totals with all quotas in both layouts without Left', () => {
  const { container } = render(meter())

  for (const selector of ['[data-usage-compact]', '[data-usage-full]']) {
    const row = container.querySelector(selector)!
    expect(row.textContent).toContain('OR W$12.34 D$1.23')
    expect(row.querySelector('[title^="OpenRouter"]')?.getAttribute('aria-label')).toContain('this week (UTC)')
    expect(row.querySelector('[title^="OpenRouter"]')?.getAttribute('aria-label')).toContain('today (UTC)')
    expect(row.textContent).toContain('Cl 60%')
    expect(row.textContent).toContain('GPT 30%')
    expect(row.textContent).toContain('Gr 85%')
    expect(row.textContent).not.toMatch(/\bleft\b/i)
    expect(row.querySelector('[aria-label^="Claude"]')?.getAttribute('aria-label')).toContain('remaining')
    expect(row.querySelectorAll('[data-tone="good"]')).toHaveLength(3)
  }
})

it('shows unavailable cost as unknown while preserving a real zero', () => {
  fixture.data.openrouter.today = null
  const { container, rerender } = render(meter())
  const readouts = () => [...container.querySelectorAll('[data-usage-compact], [data-usage-full]')]

  for (const value of [null, undefined, Number.NaN, Number.POSITIVE_INFINITY]) {
    fixture.data.openrouter.week = value
    fixture.data.openrouter.today = 1.23
    rerender(meter())

    for (const row of readouts()) {expect(row.textContent).toContain('OR W– D$1.23')}

    fixture.data.openrouter.week = 12.34
    fixture.data.openrouter.today = value
    rerender(meter())

    for (const row of readouts()) {expect(row.textContent).toContain('OR W$12.34 D–')}
  }

  fixture.data.openrouter.today = 0
  rerender(meter())

  for (const row of readouts()) {expect(row.textContent).toContain('OR W$12.34 D$0')}
})

it('keeps the two totals very compact without rounding away cents', () => {
  const { container, rerender } = render(meter())
  for (const [value, label] of [[0, '$0'], [1, '$1'], [1.2, '$1.2'], [0.01, '$0.01'], [12.34, '$12.34']] as const) {
    fixture.data.openrouter.week = value
    fixture.data.openrouter.today = value
    rerender(meter())
    for (const row of container.querySelectorAll('[data-usage-compact], [data-usage-full]')) {
      expect(row.querySelector('[title^="OpenRouter"]')?.textContent).toBe(`OR W${label} D${label}`)
      expect(row.querySelector('[title^="OpenRouter"]')?.getAttribute('aria-label')).toContain(`today (UTC) $${value.toFixed(2)}`)
    }
  }
})

it('uses remaining quota consistently in the bar and popup with pace measured in points', () => {
  fixture.showPanel = true
  const card = fixture.data.cards[0]
  Object.assign(card, { used_percent: 21, short_used_percent: 15, pace_used_percent: 9, pace_delta: -12 })
  const { container, getByTestId } = render(meter())
  const panel = getByTestId('usage-panel')
  const row = within(panel).getByText('Claude').parentElement!

  expect(row.children[1].textContent).toBe('79%  P: -12pp')
  expect(row.children[2].textContent).toContain('5-hour 85%')
  expect(row.children[3].textContent).toBe('pace target 91%')
  expect(panel.textContent).toContain('Subscriptions')
  expect(panel.textContent).not.toContain('% used')
  expect(panel.textContent).toContain('percentage points')
  for (const bar of container.querySelectorAll('[data-usage-compact], [data-usage-full]')) {
    expect(bar.textContent).toContain('Cl 79%')
    expect(bar.textContent).not.toContain('P-12%')
  }
  expect(card.used_percent).toBe(21)
  expect(card.pace_delta).toBe(-12)
})

it('shows zero only for exhausted quota and keeps tiny or unknown amounts distinct', () => {
  fixture.showPanel = true
  const card = fixture.data.cards[0]
  const { container, getByTestId, rerender } = render(meter())

  for (const [used, label] of [[100, '0%'], [0, '100%'], [99.6, '<1%'], [null, '–'], [undefined, '–'], [Number.NaN, '–'], [Number.POSITIVE_INFINITY, '–']] as const) {
    Object.assign(card, { used_percent: used, short_used_percent: used, pace_used_percent: used })
    rerender(meter())
    const row = within(getByTestId('usage-panel')).getByText('Claude').parentElement!

    expect(row.children[1].textContent).toBe(`${label}  P: +2pp`)
    if (used != null) {
      expect(row.children[2].textContent).toContain(`5-hour ${label}`)
      expect(row.children[3].textContent).toBe(`pace target ${label}`)
    } else {
      expect(row.children[2].textContent).not.toContain('5-hour')
      expect(row.children[3].textContent).toBe('')
    }
    for (const bar of container.querySelectorAll('[data-usage-compact], [data-usage-full]')) {
      const chip = bar.querySelector('[aria-label^="Claude"]')
      if (label === '–') {
        expect(chip).toBeNull()
      } else {
        expect(chip?.getAttribute('aria-label')).toContain(`${label} remaining`)
      }
    }
  }
})

const agyGroups = [
  {
    name: 'Gemini Models', tag: 'G',
    buckets: [
      { id: 'gemini-weekly', window: 'weekly', remaining_percent: 42, reset_label: 'Fri 12:00 PM' },
      { id: 'gemini-5h', window: '5h', remaining_percent: 90, reset_label: 'Sun 4:00 PM' }
    ]
  },
  {
    name: 'Claude and GPT models', tag: 'CG',
    buckets: [
      { id: '3p-weekly', window: 'weekly', remaining_percent: 15, reset_label: 'Thu 6:00 AM' },
      { id: '3p-5h', window: '5h', remaining_percent: 0, reset_label: 'Sun 2:00 PM' }
    ]
  },
  {
    name: 'Gemini 4 Argon', tag: 'Ar',
    buckets: [
      { id: 'gemini-argon-wtu-weekly', window: 'weekly', remaining_percent: 0.4, reset_label: 'Sat 6:00 PM' }
    ]
  }
]

function showAgy(card: Record<string, unknown>) {
  const cards = fixture.data.cards as Array<Record<string, unknown>>
  fixture.data.cards = [...cards.filter(item => item.id !== 'agy'), card] as typeof fixture.data.cards
}

function agyCard(overrides: Record<string, unknown> = {}) {
  return {
    id: 'agy', name: 'Antigravity', display_only: true, fresh: true, eligible: false,
    plan: null, used_percent: null, pace_delta: null, pace_used_percent: null,
    summary: { group_name: 'Gemini 4 Argon', tag: 'Ar', window: 'weekly', remaining_percent: 0.4 },
    groups: agyGroups,
    ...overrides
  }
}

afterEach(() => {
  fixture.data.cards = fixture.data.cards.filter(item => item.id !== 'agy')
})

it('identifies the lowest weekly Antigravity group in both bars without pace', () => {
  showAgy(agyCard())
  const { container } = render(meter())
  const compact = container.querySelector('[data-usage-compact]')!
  const full = container.querySelector('[data-usage-full]')!
  const compactChip = compact.querySelector('[data-agy-chip]')!
  const fullChip = full.querySelector('[data-agy-chip]')!

  expect(compact.querySelectorAll('[data-agy-chip]')).toHaveLength(1)
  expect(full.querySelectorAll('[data-agy-chip]')).toHaveLength(1)
  expect(compactChip.textContent).toBe('Ag Ar <1%')
  expect(fullChip.textContent).toBe('AGY Ar <1%')
  expect(compactChip.textContent).not.toMatch(/P/)
  expect(fullChip.textContent).not.toMatch(/P/)
  for (const chip of [compactChip, fullChip]) {
    const label = chip.getAttribute('aria-label') || ''
    expect(label).toContain('Gemini 4 Argon')
    expect(label).toContain('weekly')
    expect(label).toContain('<1% remaining')
    expect(label.toLowerCase()).toContain('other model groups are separate')
    expect(chip.getAttribute('title')).toBe(label)
  }
  expect(compact.textContent).toContain('Cl 60%')
  expect(compact.textContent).toContain('GPT 30%')
  expect(compact.textContent).toContain('Gr 85%')
  expect(compact.textContent).toContain('OR W$12.34 D$1.23')
  expect(full.textContent).toContain('P+2pp')
})

it('treats 0% as that named weekly group being exhausted and keeps the others', () => {
  fixture.showPanel = true
  const groups = structuredClone(agyGroups)
  groups[0].buckets[0].remaining_percent = 0
  groups[2].buckets[0].remaining_percent = 50
  showAgy(agyCard({
    summary: { group_name: 'Gemini Models', tag: 'G', window: 'weekly', remaining_percent: 0 },
    groups
  }))
  const { container, getByTestId } = render(meter())
  const panel = getByTestId('usage-panel')
  const details = panel.querySelector('[data-agy-details]')!

  for (const row of container.querySelectorAll('[data-usage-compact], [data-usage-full]')) {
    const chip = row.querySelector('[data-agy-chip]')!
    const label = chip.getAttribute('aria-label') || ''
    expect(chip.textContent).toMatch(/Ag|AGY/)
    expect(chip.textContent).toContain('G 0%')
    expect(label).toContain('Gemini Models')
    expect(label).toContain('weekly')
    expect(label).toContain('exhausted')
    expect(label).toContain('0% remaining')
    expect(label.toLowerCase()).toContain('other model groups are separate')
    expect(label.toLowerCase()).not.toMatch(/all (agy|models|antigravity)/)
  }
  expect(details.textContent).toContain('Claude and GPT models')
  expect(details.textContent).toContain('15%')
  expect(details.textContent).toContain('Gemini 4 Argon')
  expect(details.textContent).toContain('50%')
  expect(panel.querySelector('[data-agy-group="Gemini 4 Argon"]')?.textContent).not.toContain('5-hour')
})

it('shows every Antigravity group and bucket with its own reset and no pace', () => {
  fixture.showPanel = true
  showAgy(agyCard())
  const { getByTestId } = render(meter())
  const panel = getByTestId('usage-panel')
  const details = panel.querySelector('[data-agy-details]')!
  const claude = within(panel).getByText('Claude').parentElement!

  expect(panel.textContent).toContain('Subscriptions')
  expect(panel.textContent).toContain('percentage points')
  expect(panel.textContent?.toLowerCase()).toContain('not paced')
  expect(claude.children[1].textContent).toBe('60%  P: +2pp')
  expect(details.textContent).toContain('Antigravity')
  expect(details.textContent).not.toMatch(/Max|Pro Lite|Heavy|plan/i)
  expect(details.textContent?.toLowerCase()).not.toContain('pace')
  expect(details.textContent).not.toContain('P:')
  expect(details.querySelector('[data-agy-summary]')?.textContent).toBe('<1%')
  for (const group of agyGroups) {
    const block = details.querySelector(`[data-agy-group="${group.name}"]`)
    expect(block).not.toBeNull()
    const weekly = group.buckets.find(bucket => bucket.window === 'weekly') || group.buckets[0]
    const metric = block.querySelector('[data-agy-metric]')
    expect(metric?.textContent).toBe(weekly.remaining_percent > 0 && weekly.remaining_percent < 1 ? '<1%' : `${Math.round(weekly.remaining_percent)}%`)
    for (const bucket of group.buckets) {
      expect(block!.textContent).toContain(bucket.window === '5h' ? '5-hour' : 'weekly')
      expect(block!.textContent).toContain('resets ' + bucket.reset_label)
    }
  }
  const argon = details.querySelector('[data-agy-group="Gemini 4 Argon"]')
  expect(argon?.textContent).toContain('<1%')
  expect(argon?.textContent).not.toContain('5-hour')
  expect(argon?.textContent).not.toContain('5h')
  expect(details.textContent).toContain('resets Sun 4:00 PM')
  expect(details.textContent).toContain('resets Sun 2:00 PM')
  expect(details.textContent).toContain('0%')
})

it('keeps Antigravity unknown, full, tiny and zero distinct', () => {
  fixture.showPanel = true
  const { container, getByTestId, rerender } = render(meter())

  showAgy(agyCard({ fresh: false, reason: 'no reading', summary: null, groups: [] }))
  rerender(meter())
  for (const row of container.querySelectorAll('[data-usage-compact], [data-usage-full]')) {
    expect(row.querySelector('[data-agy-chip]')).toBeNull()
  }
  expect(getByTestId('usage-panel').querySelector('[data-agy-details]')?.textContent).toContain('no reading')
  expect(getByTestId('usage-panel').textContent).not.toContain('Gemini 4 Argon')

  showAgy(agyCard({
    summary: { group_name: 'Gemini Models', tag: 'G', window: 'weekly', remaining_percent: 100 },
    groups: [{ name: 'Gemini Models', tag: 'G', buckets: [
      { id: 'gemini-weekly', window: 'weekly', remaining_percent: 100, reset_label: 'Fri 12:00 PM' }
    ] }]
  }))
  rerender(meter())
  expect(container.querySelector('[data-usage-compact] [data-agy-chip]')?.textContent).toBe('Ag G 100%')
  expect(getByTestId('usage-panel').textContent).toContain('100%')

  showAgy(agyCard())
  rerender(meter())
  expect(container.querySelector('[data-usage-full] [data-agy-chip]')?.textContent).toBe('AGY Ar <1%')

  showAgy(agyCard({
    summary: { group_name: 'Gemini Models', tag: 'G', window: 'weekly', remaining_percent: 0 },
    groups: [{ name: 'Gemini Models', tag: 'G', buckets: [
      { id: 'gemini-weekly', window: 'weekly', remaining_percent: 0, reset_label: 'Fri 12:00 PM' }
    ] }]
  }))
  rerender(meter())
  expect(container.querySelector('[data-usage-compact] [data-agy-chip]')?.textContent).toBe('Ag G 0%')
  expect(getByTestId('usage-panel').querySelector('[data-agy-group="Gemini Models"]')?.textContent).toContain('0%')
})

it('hides a blank reading from the status bar but keeps it named in the popup', () => {
  fixture.showPanel = true
  fixture.data.cards[0].used_percent = null
  const { container, getByTestId } = render(meter())

  for (const row of container.querySelectorAll('[data-usage-compact], [data-usage-full]')) {
    expect(row.querySelector('[aria-label^="Claude"]')).toBeNull()
    expect(row.textContent).not.toContain('Cl ')
    expect(row.textContent).toContain('Gr 85%')
  }
  expect(getByTestId('usage-panel').textContent).toContain('No reading: Claude')
})

it('shows Cheaper Inference rates in a pay-per-use grid and a status chip', () => {
  fixture.showPanel = true
  const { container, getByTestId } = render(meter())
  const panel = getByTestId('usage-panel')
  const ci = panel.querySelector('[data-payg-cheaperinference]')!
  const rates = panel.querySelector('[data-ci-rates]')!

  expect(panel.textContent).toContain('Subscriptions')
  expect(panel.textContent).toContain('Pay per use')
  expect(ci.textContent).toContain('Cheaper Inference')
  const active = rates.querySelector('[data-ci-model="model-b"]')!
  expect(active.textContent).toContain('model-b')
  expect(active.textContent).toContain('0.075')
  expect(active.textContent).toContain('0.24')
  expect(active.textContent).toContain('-56%')
  expect(rates.textContent).toContain('Current model: model-b')

  expect(ci.textContent).toContain('W $1.90  D $0.42')
  expect(ci.textContent).toContain('M $4.47')
  for (const row of container.querySelectorAll('[data-usage-compact], [data-usage-full]')) {
    const chip = row.querySelector('[data-ci-chip]')
    expect(chip?.textContent).toContain('CI W$1.9 D$0.42')
    expect(chip?.getAttribute('aria-label')).toContain('this week (UTC)')
  }
})

it('colours the Antigravity chip by remaining Neon quota', () => {
  const cases: Array<[number, string]> = [[100, 'good'], [35, 'good'], [20, 'warn'], [9, 'bad'], [0, 'bad']]
  for (const [left, tone] of cases) {
    showAgy(agyCard({ summary: { group_name: 'Gemini Models', tag: 'G', window: 'weekly', remaining_percent: left } }))
    const { container, unmount } = render(meter())
    expect(container.querySelector('[data-usage-compact] [data-agy-chip] [data-tone]')?.getAttribute('data-tone')).toBe(tone)
    unmount()
  }
})
