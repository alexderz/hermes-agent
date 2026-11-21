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
    openrouter: { week: 12.34 as number | null | undefined, today: 1.23 as number | null | undefined }
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
  expect(panel.textContent).toContain('Weekly quota remaining')
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
      expect(bar.querySelector('[aria-label^="Claude"]')?.getAttribute('aria-label')).toContain(`${label} remaining`)
    }
  }
})
