import { cleanup, render } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, expect, it, vi } from 'vitest'

// The plugin's public JS entry is intentionally untyped; exercise its registered UI.
// @ts-expect-error -- standalone plugin entry has no TypeScript declaration
import plugin from '../../../../plugins/model-routing/desktop/plugin.js'

const fixture = vi.hoisted(() => ({
  data: {
    cards: [
      { id: 'claude', name: 'Claude', used_percent: 40, fresh: true, eligible: true, pace_delta: 2 },
      { id: 'codex', name: 'ChatGPT', used_percent: 70, fresh: true, eligible: true, pace_delta: 3 },
      { id: 'supergrok', name: 'SuperGrok', used_percent: 15, fresh: true, eligible: true, pace_delta: 4 }
    ],
    openrouter: { today: 1.23 as number | null | undefined }
  }
}))

vi.mock('@hermes/plugin-sdk', () => ({
  Button: ({ children, 'aria-label': label }: { children: ReactNode; 'aria-label': string }) => (
    <button aria-label={label}>{children}</button>
  ),
  Popover: ({ children }: { children: ReactNode }) => <>{children}</>,
  PopoverContent: () => null,
  PopoverTrigger: ({ children }: { children: ReactNode }) => <>{children}</>,
  STATUSBAR_AREAS: { right: 'right' },
  StatusDot: ({ tone }: { tone: string }) => <span data-tone={tone} />,
  Tip: ({ children }: { children: ReactNode }) => <>{children}</>,
  queryClient: {},
  useQuery: () => ({ data: fixture.data })
}))

afterEach(() => {
  cleanup()
  fixture.data.openrouter.today = 1.23
})

function meter() {
  let draw: (() => ReactNode) | undefined
  plugin.register({ register: (item: { render: () => ReactNode }) => { draw = item.render } })
  expect(draw).toBeTypeOf('function')

  return draw!()
}

it('keeps daily OpenRouter cost and all abbreviated quotas in both status-bar layouts without Left', () => {
  const { container } = render(meter())

  for (const selector of ['[data-usage-compact]', '[data-usage-full]']) {
    const row = container.querySelector(selector)!
    expect(row.textContent).toContain('OR $1.23')
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
    fixture.data.openrouter.today = value
    rerender(meter())

    for (const row of readouts()) {expect(row.textContent).toContain('OR –')}
  }

  fixture.data.openrouter.today = 0
  rerender(meter())

  for (const row of readouts()) {expect(row.textContent).toContain('OR $0.00')}
})
