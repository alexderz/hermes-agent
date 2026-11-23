import { PassThrough } from 'node:stream'

import { renderSync } from '@hermes/ink'
import React from 'react'
import stripAnsi from 'strip-ansi'
import { expect, it } from 'vitest'

import { buildProcessRows, PROCESS_RETAIN_SECONDS, type ProcessEntry } from '../app/processRoster.js'
import { AgentsPanelView, buildProcessBlock, processSummary, splitDockBudget } from '../components/agentsPanel.js'
import { buildAgentRows, dockRowLimit } from '../lib/agentRows.js'
import { DEFAULT_THEME } from '../theme.js'
import type { SubagentProgress } from '../types.js'

const NOW = 1_000_000_000

const agent = (id: string): SubagentProgress => ({
  id,
  goal: 'Investigate authentication handshake',
  depth: 0,
  index: 0,
  parentId: null,
  notes: [],
  tools: ['read_file auth.ts'],
  thinking: [],
  toolCount: 1,
  taskCount: 1,
  startedAt: NOW * 1000 - 5000,
  status: 'running'
})

const running: ProcessEntry = {
  session_id: 'proc_run',
  command: 'npm run build\n',
  status: 'running',
  uptime_seconds: 42,
  output_preview: 'compiling…\nbundled 300 modules\n\n'
}

const exited = (id: string, exitedAgoSeconds: number, exitCode = 0): ProcessEntry => ({
  session_id: id,
  command: 'pytest tests/',
  status: 'exited',
  uptime_seconds: 12 + exitedAgoSeconds,
  exit_code: exitCode,
  exited_at: NOW - exitedAgoSeconds,
  completion_reason: 'exited'
})

const paint = (element: React.ReactElement, rows = 30): string => {
  const stdout = Object.assign(new PassThrough(), { columns: 80, rows })
  const frames: string[] = []
  stdout.on('data', chunk => frames.push(chunk.toString()))

  const view = renderSync(element, {
    stdout: stdout as unknown as NodeJS.WriteStream,
    stdin: new PassThrough() as unknown as NodeJS.ReadStream
  })

  view.unmount()
  view.cleanup()

  return stripAnsi(frames.join(''))
}

it('keeps running processes, ages finished ones out after the retention window, and carries the exit verdict', () => {
  const rows = buildProcessRows(
    [exited('old', PROCESS_RETAIN_SECONDS + 1), exited('fresh', 5, 1), running, exited('killed', 2)],
    NOW * 1000
  )

  expect(rows.map(r => r.id)).toEqual(['proc_run', 'killed', 'fresh'])
  expect(rows[0]).toMatchObject({ status: 'running', detail: 'last: bundled 300 modules', elapsedSeconds: 42 })
  expect(rows[2]).toMatchObject({ status: 'failed', detail: 'exit 1 · 5s ago', elapsedSeconds: 12 })
  // A checkpoint-recovered exit without a timestamp never lingers as a phantom row.
  expect(buildProcessRows([{ ...exited('x', 1), exited_at: null }], NOW * 1000)).toEqual([])
})

it('paints a Processes block under the agents without letting either block hide the other', () => {
  const agents = Array.from({ length: 6 }, (_, i) => agent(`child-${i}`))
  const processes = buildProcessRows([running, exited('fresh', 5)], NOW * 1000)
  const limit = dockRowLimit(30)
  const budget = splitDockBudget(limit, agents.length, processes.length)
  expect(budget.agents).toBeGreaterThanOrEqual(1)
  expect(budget.processes).toBeGreaterThanOrEqual(1)
  expect(budget.agents + budget.processes).toBeLessThanOrEqual(Math.max(limit, 2))

  const agentRows = buildAgentRows(agents, [], NOW * 1000, budget.agents)
  const block = buildProcessBlock(processes, budget.processes)
  const text = paint(<AgentsPanelView cols={80} {...agentRows} processes={block} t={DEFAULT_THEME} />)

  expect(text).toContain('npm run build')
  expect(text.indexOf('live agents')).toBeGreaterThanOrEqual(0)
  expect(text.indexOf('live agents')).toBeLessThan(text.indexOf('npm run build'))

  // Processes alone still surface the dock, with the expand/collapse controls on their heading.
  const alone = paint(
    <AgentsPanelView
      cols={80}
      {...buildAgentRows([], [], NOW * 1000)}
      processes={buildProcessBlock(processes, limit)}
      t={DEFAULT_THEME}
    />
  )

  expect(alone).toContain('npm run build')
  expect(alone).toContain('pytest tests/')

  const collapsed = paint(<AgentsPanelView collapsed cols={80} {...agentRows} processes={block} t={DEFAULT_THEME} />)

  expect(collapsed.trim().split('\n')).toHaveLength(1)
})

it('keeps waiting and ready off the success path and holds ready past the retain window', () => {
  const waiting: ProcessEntry = {
    ...running,
    session_id: 'proc_wait',
    command: 'deploy-web',
    attention: 'waiting',
    service_mode: 'await',
    uptime_seconds: 15,
    output_preview: 'fetching\nstep 2/4\n'
  }

  const ready: ProcessEntry = {
    session_id: 'proc_ready',
    command: 'pack-image',
    status: 'exited',
    exit_code: 0,
    attention: 'ready',
    service_mode: 'await',
    uptime_seconds: 40,
    exited_at: NOW - (PROCESS_RETAIN_SECONDS + 30),
    completion_reason: 'exited',
    output_preview: 'published\n'
  }

  const lost: ProcessEntry = {
    session_id: 'proc_lost',
    command: 'watcher',
    status: 'exited',
    exit_code: 0,
    completion_reason: 'lost',
    uptime_seconds: 8,
    exited_at: NOW - 3
  }

  const rows = buildProcessRows([ready, waiting, lost], NOW * 1000)
  const byId = Object.fromEntries(rows.map(row => [row.id, row]))

  expect(rows.map(row => row.status).sort()).toEqual(['lost', 'ready', 'waiting'])
  expect(byId.proc_wait?.detail).toContain('waiting')
  expect(byId.proc_wait?.detail).toContain('step 2/4')
  expect(byId.proc_ready?.detail).toBe('result ready')
  expect(byId.proc_ready?.detail.toLowerCase()).not.toContain('continuation queued')
  expect(byId.proc_lost?.status).not.toBe('done')

  const block = buildProcessBlock(rows, 5)

  const openBlock = buildProcessBlock(
    rows.filter(row => row.status === 'waiting' || row.status === 'ready'),
    5
  )

  expect(processSummary(openBlock)).not.toMatch(/done/)
  expect(processSummary(block)).toContain('2 running')

  const painted = paint(
    <AgentsPanelView cols={40} {...buildAgentRows([], [], NOW * 1000)} processes={block} t={DEFAULT_THEME} />
  )

  const wide = paint(
    <AgentsPanelView cols={80} {...buildAgentRows([], [], NOW * 1000)} processes={block} t={DEFAULT_THEME} />
  )

  expect(wide).toContain('deploy-web')
  expect(painted).toContain('deploy-')
  expect(painted).toContain('pack-image')
  expect(painted).toContain('result ready')
  expect(painted).toContain('waiting')
  expect(painted).not.toContain('✔')
  expect(painted.toLowerCase()).not.toContain('continuation queued')
})
