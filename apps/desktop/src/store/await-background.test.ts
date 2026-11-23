import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  $backgroundRunningSessionIds,
  $backgroundStatusBySession,
  reconcileBackgroundProcesses,
  resetSessionBackground
} from './composer-status'
import { $gateway } from './gateway'
import { $liveWorkRoster, setLiveWorkRosterSource } from './live-work-roster'

const SID = 'pane'

const items = () => $backgroundStatusBySession.get()[SID] ?? []

describe('required-result background rows', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(1_700_000_000_000)
    $backgroundStatusBySession.set({})
    $liveWorkRoster.set({})
    $gateway.set(null as never)
  })

  afterEach(() => {
    vi.clearAllTimers()
    vi.useRealTimers()
    $backgroundStatusBySession.set({})
    $liveWorkRoster.set({})
    $gateway.set(null as never)
  })

  it('keeps ordinary rows on the existing running/done/failed mapping', () => {
    reconcileBackgroundProcesses(SID, [
      { command: 'sleep 2', session_id: 'run', status: 'running' },
      { command: 'echo ok', exit_code: 0, session_id: 'ok', status: 'exited' },
      { command: 'echo bad', exit_code: 3, output_tail: 'nope', session_id: 'bad', status: 'exited' }
    ] as never)

    expect(items().map(item => [item.id, item.state])).toEqual([
      ['run', 'running'],
      ['ok', 'done'],
      ['bad', 'failed']
    ])

    vi.advanceTimersByTime(4_000)
    expect(items().map(item => item.id)).toEqual(['run', 'bad'])
    vi.advanceTimersByTime(8_000)
    expect(items().map(item => item.id)).toEqual(['run'])
  })

  it('maps await/ready/lost/unknown without treating them as settled success', () => {
    reconcileBackgroundProcesses(SID, [
      {
        attention: 'waiting',
        command: 'deploy-web',
        output_tail: 'fetching\nstep 2/4\n',
        service_mode: 'await',
        session_id: 'wait',
        started_epoch: 1_700_000_000,
        status: 'running',
        uptime_seconds: 12
      },
      {
        attention: 'ready',
        command: 'pack-image',
        exit_code: 0,
        output_tail: 'published',
        service_mode: 'await',
        session_id: 'ready',
        started_epoch: 1_699_999_000,
        status: 'exited',
        uptime_seconds: 40
      },
      {
        command: 'await-only',
        service_mode: 'await',
        session_id: 'await-only',
        status: 'running'
      },
      {
        command: 'notify-job',
        service_mode: 'notify',
        session_id: 'notify',
        status: 'running'
      },
      {
        attention: 'mystery',
        command: 'odd',
        session_id: 'odd',
        status: 'running'
      },
      {
        command: 'vanished',
        completion_reason: 'lost',
        exit_code: 0,
        session_id: 'lost',
        status: 'exited'
      },
      {
        command: 'stopped',
        completion_reason: 'killed',
        exit_code: 0,
        session_id: 'killed',
        status: 'exited'
      }
    ] as never)

    const byId = Object.fromEntries(items().map(item => [item.id, item]))

    expect(byId.wait?.state).toBe('waiting')
    expect(byId.wait?.output).toBe('fetching\nstep 2/4\n')
    expect(byId.wait?.startedEpochMs).toBe(1_700_000_000_000)
    expect(byId.wait?.uptimeSeconds).toBe(12)
    expect(byId.ready?.state).toBe('ready')
    expect(byId['await-only']?.state).toBe('waiting')
    expect(byId.notify?.state).toBe('running')
    expect(byId.odd?.state).toBe('unknown')
    expect(byId.lost?.state).toBe('lost')
    expect(byId.killed?.state).toBe('failed')

    expect($backgroundRunningSessionIds.get()).toEqual(expect.arrayContaining([SID]))

    vi.advanceTimersByTime(5_000)
    expect(items().map(item => item.id)).toEqual(
      expect.arrayContaining(['wait', 'ready', 'await-only', 'notify', 'odd', 'lost', 'killed'])
    )

    vi.advanceTimersByTime(8_000)
    const held = items().map(item => item.id)
    expect(held).toEqual(expect.arrayContaining(['wait', 'ready', 'await-only', 'notify']))
    expect(held).not.toContain('odd')
    expect(held).not.toContain('lost')
    expect(held).not.toContain('killed')
  })

  it('drops ready only after a later snapshot says the receipt settled', () => {
    reconcileBackgroundProcesses(SID, [
      {
        attention: 'ready',
        command: 'pack-image',
        exit_code: 0,
        session_id: 'ready',
        status: 'exited'
      }
    ] as never)
    expect(items()[0]?.state).toBe('ready')

    reconcileBackgroundProcesses(SID, [
      { command: 'pack-image', exit_code: 0, session_id: 'ready', status: 'exited' }
    ] as never)
    expect(items()[0]?.state).toBe('done')

    vi.advanceTimersByTime(4_000)
    expect(items()).toEqual([])
  })

  it('holds an offscreen session from the roster background count after reload', () => {
    setLiveWorkRosterSource('ambient', [{ session_id: 'reloaded', subagents: 0, background: 1 }], 2_000)

    expect($backgroundRunningSessionIds.get()).toContain('reloaded')
  })

  it('lets a newer roster zero clear a ready row the hidden pane stopped refreshing', () => {
    reconcileBackgroundProcesses(SID, [
      { attention: 'ready', command: 'pack-image', exit_code: 0, session_id: 'ready-hold', status: 'exited' }
    ] as never)
    expect({ ids: $backgroundRunningSessionIds.get(), state: items()[0]?.state }).toEqual({
      ids: [SID],
      state: 'ready'
    })

    setLiveWorkRosterSource('ambient', [], 1_700_000_000_000 + 5_000, [SID])

    expect($backgroundRunningSessionIds.get()).not.toContain(SID)
  })

  it('kills a waiting process when the session background is reset', async () => {
    const request = vi.fn(async () => ({}))
    $gateway.set({ request } as never)
    reconcileBackgroundProcesses(SID, [
      { attention: 'waiting', command: 'deploy-web', session_id: 'wait', status: 'running' }
    ] as never)

    resetSessionBackground(SID)
    await request.mock.results[0]!.value
    await Promise.resolve()

    expect(request).toHaveBeenCalledWith('process.kill', { process_id: 'wait', session_id: SID })
    // `{}` is a resolved RPC with no killed/already_exited snapshot, so the
    // waiting row stays. A confirmed kill is covered in composer-status.test.ts.
    expect(items()).toEqual([expect.objectContaining({ id: 'wait', state: 'waiting' })])
  })
})
