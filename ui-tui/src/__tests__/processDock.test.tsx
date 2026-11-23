import { PassThrough } from 'node:stream'

import { renderSync } from '@hermes/ink'
import React from 'react'
import stripAnsi from 'strip-ansi'
import { expect, it } from 'vitest'

import {
  $processSnapshot,
  applyProcessSnapshot,
  buildProcessRows,
  PROCESS_RETAIN_SECONDS,
  type ProcessEntry,
  processIsOpen
} from '../app/processRoster.js'
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

it('holds a pending failed or lost receipt until the snapshot settles, and reads killed before stale attention', () => {
  // Frontend process.list input only. This does not prove the server's admission settlement.
  const old = PROCESS_RETAIN_SECONDS + 30

  const receipt = (
    id: string,
    attention: 'failed' | 'lost',
    exitedAt: number | null,
    pending?: boolean
  ): ProcessEntry => ({
    session_id: id,
    command: id,
    status: 'exited',
    exit_code: attention === 'failed' ? 1 : 0,
    attention,
    service_mode: attention === 'lost' ? 'await' : 'notify',
    completion_reason: attention === 'lost' ? 'lost' : 'exited',
    ...(pending === undefined ? {} : { admission_pending: pending }),
    uptime_seconds: 12,
    exited_at: exitedAt,
    output_preview: 'boom\n'
  })

  const rowsOf = (entries: readonly ProcessEntry[]) => buildProcessRows(entries, NOW * 1000)

  const ids = (entries: readonly ProcessEntry[]) =>
    rowsOf(entries)
      .map(row => row.id)
      .sort()

  const pending = [
    receipt('fail-null', 'failed', null, true),
    receipt('fail-zero', 'failed', 0, true),
    receipt('fail-old', 'failed', NOW - old, true),
    receipt('lost-null', 'lost', null, true),
    receipt('lost-zero', 'lost', 0, true),
    receipt('lost-old', 'lost', NOW - old, true)
  ]

  const held = rowsOf(pending)

  expect(ids(pending)).toEqual(['fail-null', 'fail-old', 'fail-zero', 'lost-null', 'lost-old', 'lost-zero'])
  expect(held.find(row => row.id === 'fail-old')).toMatchObject({
    status: 'failed',
    detail: `exit 1 · ${old}s ago`,
    sinceExitSeconds: old
  })
  expect(held.find(row => row.id === 'fail-zero')).toMatchObject({
    status: 'failed',
    detail: 'exit 1 · 0s ago',
    sinceExitSeconds: 0
  })
  expect(held.find(row => row.id === 'lost-null')).toMatchObject({
    status: 'lost',
    detail: 'lost · 0s ago',
    sinceExitSeconds: 0
  })
  expect(held.every(row => row.status === 'failed' || row.status === 'lost')).toBe(true)
  expect(held.every(row => !processIsOpen(row.status))).toBe(true)
  expect(buildProcessBlock(held, 10)).toMatchObject({ running: 0, total: held.length })
  expect(processIsOpen('running')).toBe(true)
  expect(processIsOpen('waiting')).toBe(true)
  expect(processIsOpen('ready')).toBe(true)
  expect(processIsOpen('failed')).toBe(false)
  expect(processIsOpen('lost')).toBe(false)
  expect(processIsOpen('killed')).toBe(false)
  expect(processIsOpen('done')).toBe(false)

  const legacyFresh: ProcessEntry = {
    session_id: 'fail-fresh',
    command: 'echo fresh',
    status: 'exited',
    exit_code: 4,
    completion_reason: 'exited',
    uptime_seconds: 8,
    exited_at: NOW - 5
  }

  const legacyOld: ProcessEntry = {
    session_id: 'fail-old-settled',
    command: 'echo settled',
    status: 'exited',
    exit_code: 2,
    completion_reason: 'exited',
    uptime_seconds: 8,
    exited_at: NOW - old
  }

  const legacyAbsent: ProcessEntry = {
    session_id: 'fail-absent',
    command: 'echo phantom',
    status: 'exited',
    exit_code: 3,
    completion_reason: 'exited',
    uptime_seconds: 8,
    exited_at: null
  }

  const settled: ProcessEntry[] = [
    legacyFresh,
    legacyOld,
    legacyAbsent,
    receipt('fail-false', 'failed', NOW - old, false),
    receipt('fail-omit', 'failed', NOW - old)
  ]

  const donePending: ProcessEntry = {
    session_id: 'done-pending',
    command: 'echo ok',
    status: 'exited',
    exit_code: 0,
    completion_reason: 'exited',
    admission_pending: true,
    uptime_seconds: 4,
    exited_at: NOW - old
  }

  expect(ids(settled)).toEqual(['fail-fresh'])
  expect(rowsOf([legacyFresh])[0]).toMatchObject({ status: 'failed', detail: 'exit 4 · 5s ago' })
  expect(ids([receipt('fail-false-fresh', 'failed', NOW - 5, false)])).toEqual(['fail-false-fresh'])
  expect(ids([donePending])).toEqual([])

  const killed = (exitedAt: number | null): ProcessEntry => ({
    session_id: 'stopped',
    command: 'sleep 30',
    status: 'exited',
    exit_code: 0,
    attention: 'ready',
    service_mode: 'await',
    completion_reason: 'killed',
    admission_pending: true,
    uptime_seconds: 9,
    exited_at: exitedAt
  })

  expect(rowsOf([killed(NOW - old), killed(0), killed(null)])).toEqual([])
  expect(rowsOf([killed(NOW - 2)])).toMatchObject([
    { id: 'stopped', status: 'killed', detail: 'killed · 2s ago', sinceExitSeconds: 2 }
  ])

  applyProcessSnapshot(null)
  applyProcessSnapshot('dock', [
    receipt('fail-settle', 'failed', NOW - old, true),
    receipt('lost-settle', 'lost', 0, true)
  ])
  expect(ids($processSnapshot.get().processes)).toEqual(['fail-settle', 'lost-settle'])

  applyProcessSnapshot('dock', [receipt('fail-settle', 'failed', NOW - old, false)])
  expect($processSnapshot.get().processes.map(entry => entry.session_id)).toEqual(['fail-settle'])
  expect(ids($processSnapshot.get().processes)).toEqual([])

  applyProcessSnapshot('dock', [receipt('fail-settle', 'failed', NOW - 5, false)])
  expect(ids($processSnapshot.get().processes)).toEqual(['fail-settle'])
  expect(rowsOf($processSnapshot.get().processes)[0]?.status).toBe('failed')

  applyProcessSnapshot('dock', [])
  expect($processSnapshot.get().processes).toEqual([])
  expect(ids($processSnapshot.get().processes)).toEqual([])
  applyProcessSnapshot(null)
})
