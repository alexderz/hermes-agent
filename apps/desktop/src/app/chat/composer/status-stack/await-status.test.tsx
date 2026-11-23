import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { openAgentTerminal } from '@/app/right-sidebar/terminal/terminals'
import { formatElapsed } from '@/components/chat/activity-timer'
import type { ComposerStatusItem } from '@/store/composer-status'
import { $backgroundStatusBySession } from '@/store/composer-status'
import { $gateway } from '@/store/gateway'
import { $interfaceMode } from '@/store/interface-mode'
import { $previewStatusBySession } from '@/store/preview-status'
import { $subagentsBySession, upsertSubagent } from '@/store/subagents'

import { StatusItemRow } from './status-row'

import { ComposerStatusStack } from './index'

vi.mock('@/app/right-sidebar/terminal/terminals', () => ({ openAgentTerminal: vi.fn() }))

const SID = 'owner'

function backgroundItem(overrides: Record<string, unknown>): ComposerStatusItem {
  return {
    id: 'job-1',
    output: 'fetching layers\nstep 2/4\n',
    startedEpochMs: Date.now() - 10_400,
    state: 'waiting',
    title: 'deploy-web',
    type: 'background',
    uptimeSeconds: 999,
    ...overrides
  } as unknown as ComposerStatusItem
}

function renderRow(
  item: ComposerStatusItem,
  handlers?: { onDismiss?: (id: string) => void; onStop?: (id: string) => void }
) {
  return render(
    <div style={{ height: 480, width: 390 }}>
      <StatusItemRow item={item} onDismiss={handlers?.onDismiss ?? vi.fn()} onStop={handlers?.onStop ?? vi.fn()} />
    </div>
  )
}

function renderStack() {
  return render(
    <MemoryRouter>
      <div style={{ height: 480, width: 390 }}>
        <ComposerStatusStack queue={null} sessionId={SID} />
      </div>
    </MemoryRouter>
  )
}

afterEach(() => {
  cleanup()
  $backgroundStatusBySession.set({})
  $previewStatusBySession.set({})
  $subagentsBySession.set({})
  $gateway.set(null as never)
  $interfaceMode.set('advanced')
  vi.clearAllTimers()
  vi.useRealTimers()
  vi.clearAllMocks()
})

describe('StatusItemRow required-result paint', () => {
  it('shows Waiting for the job name, elapsed, output, and Stop', () => {
    const onStop = vi.fn()
    const view = renderRow(backgroundItem({}), { onStop })

    expect(screen.getByText('deploy-web')).toBeTruthy()
    expect(screen.getByText('Waiting for deploy-web')).toBeTruthy()
    expect(screen.getByText(formatElapsed(10))).toBeTruthy()
    expect(screen.queryByText('999')).toBeNull()
    expect(screen.getByText('step 2/4')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Stop' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Dismiss' })).toBeNull()
    expect(screen.queryByText(/continuation queued/i)).toBeNull()

    const dot = view.container.querySelector('[data-state="waiting"]')
    expect(dot?.className).toContain('border-(--ui-text-tertiary)')
    expect(dot?.className).not.toContain('bg-emerald')

    fireEvent.click(screen.getByRole('button', { name: 'Stop' }))
    expect(onStop).toHaveBeenCalledWith('job-1')
    expect(openAgentTerminal).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: /Waiting for deploy-web/ }))
    expect(openAgentTerminal).toHaveBeenCalledWith('job-1', 'deploy-web')
  })

  it('paints ready, failed, lost, and unknown as labels with truthful controls', () => {
    const cases = [
      { state: 'ready', label: 'Result ready', stop: false, dot: 'ready', fail: false },
      { state: 'failed', label: 'Failed', stop: false, dot: 'failed', fail: true, exitCode: 3 },
      { state: 'lost', label: 'Lost', stop: false, dot: 'lost', fail: true },
      { state: 'unknown', label: 'Unknown', stop: false, dot: 'unknown', fail: true },
      { state: 'running', label: 'Running', stop: true, dot: null, fail: false }
    ] as const

    for (const entry of cases) {
      cleanup()

      const view = renderRow(
        backgroundItem({
          exitCode: 'exitCode' in entry ? entry.exitCode : 0,
          id: entry.state,
          startedEpochMs: undefined,
          state: entry.state,
          uptimeSeconds: 40
        })
      )

      expect(screen.getByText(entry.label)).toBeTruthy()
      expect(screen.getByText('deploy-web')).toBeTruthy()
      expect(screen.queryByText(/continuation queued/i)).toBeNull()
      expect(screen.queryByText(/goal complete/i)).toBeNull()
      expect(Boolean(screen.queryByRole('button', { name: 'Stop' }))).toBe(entry.stop)
      expect(Boolean(screen.queryByRole('button', { name: 'Dismiss' }))).toBe(!entry.stop)

      if (entry.dot) {
        const dot = view.container.querySelector(`[data-state="${entry.dot}"]`)
        expect(dot).toBeTruthy()
        expect(dot?.className.includes('bg-emerald')).toBe(false)

        if (entry.fail) {
          expect(dot?.className).toContain('bg-destructive/80')
        }
      }

      if (entry.state === 'failed') {
        expect(screen.getByText('exit 3')).toBeTruthy()
      }

      if (entry.state === 'ready' || entry.state === 'failed' || entry.state === 'lost' || entry.state === 'unknown') {
        expect(screen.getByText(formatElapsed(40))).toBeTruthy()
      }
    }
  })

  it('preserves a legacy done row as settled success', () => {
    const view = renderRow(
      backgroundItem({ output: undefined, startedEpochMs: undefined, state: 'done', uptimeSeconds: undefined })
    )

    expect(screen.getByText('deploy-web')).toBeTruthy()
    expect(screen.queryByText('Result ready')).toBeNull()
    expect(screen.queryByText(/Waiting for/)).toBeNull()
    expect(screen.queryByRole('button', { name: 'Stop' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Dismiss' })).toBeTruthy()
    expect(view.container.querySelector('[data-state="done"]')?.className ?? '').toContain('bg-emerald-500/70')
  })

  it('wraps a long job name and output inside a phone-width, keyboard-height frame', () => {
    const title = 'deploy-web-service-with-a-very-long-command-name-that-must-stay-intact'
    const output = `published ${'x'.repeat(240)}`
    const view = renderRow(backgroundItem({ output, title }))
    const frame = view.container.firstElementChild as HTMLElement

    expect(frame.style.width).toBe('390px')
    expect(frame.style.height).toBe('480px')
    expect(screen.getByText(title).className).toContain('break-words')
    expect(screen.getByText(title).className).not.toContain('truncate')
    const outputNode = screen.getByText(output)
    expect(outputNode.className).toContain('break-words')
    expect(outputNode.className).toContain('line-clamp-2')
    expect(screen.getByText(`Waiting for ${title}`).className).toContain('break-words')
  })
})

describe('ComposerStatusStack simple mode', () => {
  beforeEach(() => {
    $gateway.set(null as never)
  })

  it('shows the background row in Simple mode and keeps subagents advanced-only', () => {
    $interfaceMode.set('simple')
    $backgroundStatusBySession.set({
      [SID]: [
        backgroundItem({
          output: 'still fetching',
          startedEpochMs: undefined,
          uptimeSeconds: 15
        })
      ]
    })
    upsertSubagent(SID, { goal: 'Worker task', subagent_id: 'worker' })

    renderStack()

    expect(screen.getByRole('button', { name: /deploy-web/ })).toBeTruthy()
    expect(screen.getByText('Waiting for deploy-web')).toBeTruthy()
    expect(screen.getByText('still fetching')).toBeTruthy()
    expect(screen.getByText(formatElapsed(15))).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Stop' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: /Subagent/ })).toBeNull()
    expect(screen.queryByText('Worker task')).toBeNull()
    expect(screen.queryByText(/continuation queued/i)).toBeNull()

    const header = screen.getByRole('button', { name: /deploy-web/ })
    const labelAt = header.textContent?.indexOf('deploy-web') ?? -1
    const countAt = header.textContent?.indexOf('Background') ?? -1
    expect(labelAt).toBeGreaterThanOrEqual(0)
    expect(countAt === -1 || labelAt < countAt).toBe(true)
  })

  it('shows subagents again in advanced mode', () => {
    $interfaceMode.set('advanced')
    $backgroundStatusBySession.set({ [SID]: [backgroundItem({})] })
    upsertSubagent(SID, { goal: 'Worker task', subagent_id: 'worker' })

    renderStack()

    expect(screen.getByRole('button', { name: /Subagent/ })).toBeTruthy()
    expect(screen.getByRole('button', { name: /deploy-web/ })).toBeTruthy()
  })

  it('keeps a localhost preview only while a command is actually running', () => {
    $previewStatusBySession.set({
      [SID]: [{ cwd: '/work', id: 'url', label: 'Live preview', target: 'http://localhost:5174' }]
    })
    $backgroundStatusBySession.set({ [SID]: [backgroundItem({ state: 'waiting' })] })
    const view = renderStack()
    expect(screen.queryByText('Live preview')).toBeNull()

    act(() => {
      $backgroundStatusBySession.set({ [SID]: [backgroundItem({ state: 'running', title: 'vite' })] })
    })
    view.rerender(
      <MemoryRouter>
        <ComposerStatusStack queue={null} sessionId={SID} />
      </MemoryRouter>
    )
    expect(screen.getByText('Live preview')).toBeTruthy()
  })
})

describe('background poll while ready', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  it('keeps polling a ready receipt and does not success-dismiss it', async () => {
    const request = vi.fn(async (method: string) => {
      if (method === 'process.list') {
        return {
          processes: [
            {
              attention: 'ready',
              command: 'deploy-web',
              exit_code: 0,
              output_tail: 'published',
              service_mode: 'await',
              session_id: 'job-1',
              status: 'exited',
              uptime_seconds: 40
            }
          ]
        }
      }

      return {}
    })

    $gateway.set({ request } as never)
    renderStack()

    await act(async () => {
      await Promise.resolve()
      await Promise.resolve()
      await Promise.resolve()
    })

    expect($backgroundStatusBySession.get()[SID]?.[0]?.state).toBe('ready')
    expect(screen.getByText('Result ready')).toBeTruthy()
    const first = request.mock.calls.filter(([method]) => method === 'process.list').length
    expect(first).toBeGreaterThan(0)

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000)
    })

    expect($backgroundStatusBySession.get()[SID]?.map(item => item.state)).toEqual(['ready'])
    const later = request.mock.calls.filter(([method]) => method === 'process.list').length
    expect(later).toBeGreaterThan(first)
    expect(screen.queryByText(/continuation queued/i)).toBeNull()
  })
})
