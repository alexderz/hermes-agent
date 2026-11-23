import { JsonRpcGatewayError } from '@hermes/shared'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  $backgroundStatusBySession,
  dismissBackgroundProcess,
  isSessionGoneForBackgroundPolling,
  reconcileBackgroundProcesses,
  refreshBackgroundProcesses,
  resetBackgroundPollingGuard,
  resetSessionBackground,
  stopBackgroundProcess
} from './composer-status'
import { $gateway } from './gateway'
import { markSessionGone } from './runtime-gone'

vi.mock('./notifications', () => ({ notifyError: vi.fn() }))
import { notifyError } from './notifications'

vi.mock('./native-notifications', () => ({ dispatchNativeNotification: vi.fn() }))
import { dispatchNativeNotification } from './native-notifications'

const SID = 'sess-1'

const running = (id: string, command = `cmd ${id}`) => ({ command, session_id: id, status: 'running' })

const exited = (id: string, exit_code = 0, command = `cmd ${id}`) => ({
  command,
  exit_code,
  session_id: id,
  status: 'exited'
})

const items = () => $backgroundStatusBySession.get()[SID] ?? []

describe('reconcileBackgroundProcesses', () => {
  beforeEach(() => {
    // Fake timers so the success self-clear (a real setTimeout) is deterministic
    // and never leaks a pending timer between tests.
    vi.useFakeTimers()
    $backgroundStatusBySession.set({})
  })

  afterEach(() => {
    vi.clearAllTimers()
    vi.useRealTimers()
  })

  it('maps registry entries to status items', () => {
    reconcileBackgroundProcesses(SID, [running('a'), exited('b', 0), exited('c', 1)])

    expect(items().map(i => [i.id, i.state])).toEqual([
      ['a', 'running'],
      ['b', 'done'],
      ['c', 'failed']
    ])
    expect(items()[2]!.exitCode).toBe(1)
  })

  it('keeps row order stable when a process flips state or the snapshot reorders', () => {
    reconcileBackgroundProcesses(SID, [running('a'), running('b')])
    // Snapshot arrives reordered AND `a` has exited — rows must not move.
    reconcileBackgroundProcesses(SID, [running('b'), exited('a', 0)])

    expect(items().map(i => [i.id, i.state])).toEqual([
      ['a', 'done'],
      ['b', 'running']
    ])
  })

  it('appends new processes after existing rows', () => {
    reconcileBackgroundProcesses(SID, [running('a')])
    reconcileBackgroundProcesses(SID, [running('b'), running('a')])

    expect(items().map(i => i.id)).toEqual(['a', 'b'])
  })

  it('never resurrects a dismissed process while the registry still reports it', () => {
    reconcileBackgroundProcesses(SID, [exited('a', 0), running('b')])
    dismissBackgroundProcess(SID, 'a')

    reconcileBackgroundProcesses(SID, [exited('a', 0), running('b')])

    expect(items().map(i => i.id)).toEqual(['b'])
  })

  it('forgets a dismissal once the registry prunes the process', () => {
    reconcileBackgroundProcesses(SID, [exited('a', 0)])
    dismissBackgroundProcess(SID, 'a')

    // Registry pruned it…
    reconcileBackgroundProcesses(SID, [])
    // …so a future process reusing the id (new spawn) shows again.
    reconcileBackgroundProcesses(SID, [running('a')])

    expect(items().map(i => i.id)).toEqual(['a'])
  })

  it('drops the session key entirely when the last row goes away', () => {
    reconcileBackgroundProcesses(SID, [running('a')])
    reconcileBackgroundProcesses(SID, [])

    expect($backgroundStatusBySession.get()).toEqual({})
  })

  // The self-clear path calls dismissBackgroundProcess, which records the id in
  // the module-level dismissed set; use a fresh session per test so that record
  // can't bleed into another test's reconcile.
  const itemsOf = (sid: string) => $backgroundStatusBySession.get()[sid] ?? []

  it('self-clears a finished success after a short linger', () => {
    reconcileBackgroundProcesses('sess-clear', [exited('a', 0)])
    expect(itemsOf('sess-clear').map(i => i.id)).toEqual(['a'])

    vi.advanceTimersByTime(5_000)

    expect(itemsOf('sess-clear')).toEqual([])
  })

  it('self-clears a failed task too, but only after a longer linger', () => {
    reconcileBackgroundProcesses('sess-fail', [exited('a', 1)])

    // Still visible after the success window — the failure gets a longer one so
    // its exit code stays readable.
    vi.advanceTimersByTime(5_000)
    expect(itemsOf('sess-fail').map(i => [i.id, i.state])).toEqual([['a', 'failed']])

    vi.advanceTimersByTime(10_000)
    expect(itemsOf('sess-fail')).toEqual([])
  })

  it('never self-clears a still-running task', () => {
    reconcileBackgroundProcesses('sess-run', [running('a')])

    vi.advanceTimersByTime(60_000)

    expect(itemsOf('sess-run').map(i => i.id)).toEqual(['a'])
  })

  it('arms the self-clear only once a task finishes', () => {
    reconcileBackgroundProcesses('sess-arm', [running('a')])
    vi.advanceTimersByTime(60_000)
    // Still running after a minute — nothing scheduled yet.
    expect(itemsOf('sess-arm').map(i => i.id)).toEqual(['a'])

    reconcileBackgroundProcesses('sess-arm', [exited('a', 0)])
    vi.advanceTimersByTime(5_000)

    expect(itemsOf('sess-arm')).toEqual([])
  })

  it('dispatches rich backgroundDone notification: title + exit code + output tail', () => {
    // Start with running, then transition to exited with output
    reconcileBackgroundProcesses('sess-notify', [running('build-task', 'npm run build\nsome comment')])
    vi.clearAllMocks()

    const completedProc = {
      command: 'npm run build\nsome comment',
      exit_code: 0,
      output_tail: 'Building...\nCompilation successful\nOutput written to dist/',
      session_id: 'build-task',
      status: 'exited'
    }

    reconcileBackgroundProcesses('sess-notify', [completedProc])

    expect(dispatchNativeNotification).toHaveBeenCalledWith(
      expect.objectContaining({
        body: 'npm run build (exit 0)\nBuilding...\nCompilation successful\nOutput written to dist/',
        kind: 'backgroundDone'
      })
    )
  })

  it('omits exit code from notification body when undefined', () => {
    reconcileBackgroundProcesses('sess-no-exit', [running('task-x')])
    vi.clearAllMocks()

    reconcileBackgroundProcesses('sess-no-exit', [
      {
        command: 'task-x',
        output_tail: 'line1\nline2\nline3',
        session_id: 'task-x',
        status: 'exited'
      }
    ])

    expect(dispatchNativeNotification).toHaveBeenCalledWith(
      expect.objectContaining({
        body: 'task-x\nline1\nline2\nline3'
      })
    )
  })

  it('handles notification body when output is empty', () => {
    reconcileBackgroundProcesses('sess-empty', [running('quick-cmd')])
    vi.clearAllMocks()

    reconcileBackgroundProcesses('sess-empty', [
      {
        command: 'quick-cmd',
        exit_code: 1,
        session_id: 'quick-cmd',
        status: 'exited'
      }
    ])

    expect(dispatchNativeNotification).toHaveBeenCalledWith(
      expect.objectContaining({
        body: 'quick-cmd (exit 1)'
      })
    )
  })
})

// ── Dead-session polling guard (#94219 fallout) ──────────────────────────────
// The status stack polls `process.list` every 5s while a background row is on
// screen. `process.list` is session-scoped: against a runtime id the gateway no
// longer holds it returns 4001 "session not found". That failure was swallowed
// as "transient socket loss", so the poll re-sent the SAME dead id every 5s for
// the life of the window — 18,614 rejections against a single runtime id in one
// day on a real machine, and the log line the user reads as "session not found".
//
// A gone session is terminal, not transient: stop polling it.
describe('refreshBackgroundProcesses dead-session guard', () => {
  beforeEach(() => {
    $backgroundStatusBySession.set({})
    resetBackgroundPollingGuard()
  })

  afterEach(() => {
    $gateway.set(null as never)
    resetBackgroundPollingGuard()
  })

  it('classifies a 4001 session-not-found as gone, and a timeout as transient', () => {
    expect(isSessionGoneForBackgroundPolling(new Error('session not found'))).toBe(true)
    expect(isSessionGoneForBackgroundPolling(new Error('4001 session not found'))).toBe(true)
    expect(isSessionGoneForBackgroundPolling(new Error('Session Not Found'))).toBe(true)

    // Transient failures must NOT latch the guard — the session may still be alive.
    expect(isSessionGoneForBackgroundPolling(new Error('request timed out after 30s: process.list'))).toBe(false)
    expect(isSessionGoneForBackgroundPolling(new Error('not connected'))).toBe(false)
  })

  it('stops re-polling a session after the gateway reports it gone', async () => {
    const request = vi.fn(async () => {
      throw new Error('session not found')
    })

    $gateway.set({ request } as never)

    // First poll discovers the session is gone.
    await refreshBackgroundProcesses(SID)
    expect(request).toHaveBeenCalledTimes(1)

    // Every subsequent tick must be suppressed. Before the fix these all went
    // to the wire and each produced another gateway-side 4001.
    await refreshBackgroundProcesses(SID)
    await refreshBackgroundProcesses(SID)
    await refreshBackgroundProcesses(SID)

    expect(request).toHaveBeenCalledTimes(1)
  })

  it('keeps polling after a transient failure', async () => {
    const request = vi.fn(async () => {
      throw new Error('request timed out after 30s: process.list')
    })

    $gateway.set({ request } as never)

    await refreshBackgroundProcesses(SID)
    await refreshBackgroundProcesses(SID)

    // A timeout is not proof of death — the poll must retry.
    expect(request).toHaveBeenCalledTimes(2)
  })

  it('does not suppress a different, healthy session', async () => {
    const request = vi.fn(async (_method: string, params?: Record<string, unknown>) => {
      if (params?.session_id === SID) {
        throw new Error('session not found')
      }

      return { processes: [] }
    })

    $gateway.set({ request } as never)

    await refreshBackgroundProcesses(SID)
    await refreshBackgroundProcesses(SID)
    await refreshBackgroundProcesses('sess-healthy')
    await refreshBackgroundProcesses('sess-healthy')

    const targets = request.mock.calls.map(c => (c[1] as { session_id?: string } | undefined)?.session_id)
    expect(targets.filter(t => t === SID)).toHaveLength(1)
    expect(targets.filter(t => t === 'sess-healthy')).toHaveLength(2)
  })

  it('resumes polling a session that comes back (guard cleared on rebind)', async () => {
    const request = vi.fn(async () => {
      throw new Error('session not found')
    })

    $gateway.set({ request } as never)

    await refreshBackgroundProcesses(SID)
    await refreshBackgroundProcesses(SID)
    expect(request).toHaveBeenCalledTimes(1)

    // A fresh runtime bound to this session id clears the guard.
    resetBackgroundPollingGuard(SID)
    await refreshBackgroundProcesses(SID)

    expect(request).toHaveBeenCalledTimes(2)
  })

  it('keeps a stale process visible as unknown when Stop is clicked after the runtime is gone', async () => {
    reconcileBackgroundProcesses(SID, [running('stale')])
    markSessionGone(SID)
    const request = vi.fn()
    $gateway.set({ request } as never)
    vi.mocked(notifyError).mockClear()

    await stopBackgroundProcess(SID, 'stale')

    expect(items()).toEqual([expect.objectContaining({ id: 'stale', state: 'unknown' })])
    expect(request).not.toHaveBeenCalled()
    expect(notifyError).toHaveBeenCalledWith(expect.any(Error), 'Could not stop the process')
  })

  it('keeps a gone session row visible as unknown while the gateway is disconnected', async () => {
    reconcileBackgroundProcesses(SID, [running('disconnected')])
    markSessionGone(SID)
    $gateway.set(null as never)
    vi.mocked(notifyError).mockClear()

    await stopBackgroundProcess(SID, 'disconnected')

    expect(items()).toEqual([expect.objectContaining({ id: 'disconnected', state: 'unknown' })])
    expect(notifyError).toHaveBeenCalledWith(expect.any(Error), 'Could not stop the process')
  })

  it('keeps the row and reports failure when the gateway is disconnected', async () => {
    reconcileBackgroundProcesses(SID, [running('unreachable')])
    $gateway.set(null as never)
    vi.mocked(notifyError).mockClear()

    await stopBackgroundProcess(SID, 'unreachable')

    expect(items()).toEqual([expect.objectContaining({ id: 'unreachable', state: 'unknown' })])
    expect(notifyError).toHaveBeenCalledWith(expect.any(Error), 'Could not stop the process')
  })

  it('keeps the row as unknown and latches when Stop discovers the runtime is gone', async () => {
    const request = vi.fn(async () => {
      throw new Error('session not found')
    })

    reconcileBackgroundProcesses(SID, [running('rejected')])
    $gateway.set({ request } as never)
    vi.mocked(notifyError).mockClear()

    await stopBackgroundProcess(SID, 'rejected')
    await stopBackgroundProcess(SID, 'rejected')

    expect(items()).toEqual([expect.objectContaining({ id: 'rejected', state: 'unknown' })])
    expect(request).toHaveBeenCalledTimes(1)
    expect(notifyError).toHaveBeenCalledWith(expect.any(Error), 'Could not stop the process')
  })
})

// process.kill's JSON-RPC result is registry.kill_process's dict. Transport
// success is not a stopped worker: legacy confirms only status killed or
// already_exited without scope_stop_failed. A service stop confirms only when
// that same killed snapshot comes back; running and unresolved leave it live.
describe('stopBackgroundProcess kill outcomes', () => {
  // dismissedBySession survives the store reset, so each case gets its own session.
  let owner = ''

  const waiting = (id: string) => ({
    attention: 'waiting',
    command: id,
    service_mode: 'await',
    session_id: id,
    status: 'running'
  })

  const rows = () => $backgroundStatusBySession.get()[owner] ?? []

  beforeEach(() => {
    owner = `stop-${Math.random().toString(16).slice(2)}`
    $backgroundStatusBySession.set({})
    resetBackgroundPollingGuard()
    vi.mocked(notifyError).mockClear()
  })

  afterEach(() => {
    $gateway.set(null as never)
    resetBackgroundPollingGuard()
  })

  async function stopWith(id: string, result: unknown) {
    const request = vi.fn(async () => result)
    $gateway.set({ request } as never)
    reconcileBackgroundProcesses(owner, [waiting(id)])
    await stopBackgroundProcess(owner, id)

    return request
  }

  it('keeps the row when a resolved kill is unresolved', async () => {
    await stopWith('unresolved', {
      error: 'service stop did not record a durable outcome',
      exit_code: null,
      note: 'service stop did not record a durable outcome',
      process_running: true,
      service: 'await',
      service_invocation_id: 'inv',
      session_id: 'unresolved',
      status: 'unresolved'
    })

    expect(rows()).toEqual([expect.objectContaining({ id: 'unresolved', state: 'waiting' })])
    expect(notifyError).toHaveBeenCalledWith(
      expect.objectContaining({ message: 'service stop did not record a durable outcome' }),
      'Could not stop the process'
    )
    reconcileBackgroundProcesses(owner, [waiting('unresolved')])
    expect(rows()).toEqual([expect.objectContaining({ id: 'unresolved', state: 'waiting' })])
  })

  it('keeps the row when a resolved kill says the service is still running', async () => {
    await stopWith('still-running', {
      exit_code: null,
      process_running: true,
      service: 'await',
      session_id: 'still-running',
      status: 'running'
    })

    expect(rows()).toEqual([expect.objectContaining({ id: 'still-running', state: 'waiting' })])
    expect(notifyError).toHaveBeenCalledWith(
      expect.objectContaining({ message: 'Stop was not confirmed' }),
      'Could not stop the process'
    )
  })

  it('keeps the row when a resolved kill reports an error', async () => {
    await stopWith('survivors', {
      error: 'Kill incomplete: 1 process(es) still alive (42); session running',
      process_running: true,
      session_id: 'survivors',
      status: 'error',
      survivors: [42]
    })

    expect(rows()).toEqual([expect.objectContaining({ id: 'survivors', state: 'waiting' })])
    expect(notifyError).toHaveBeenCalledWith(
      expect.objectContaining({ message: 'Kill incomplete: 1 process(es) still alive (42); session running' }),
      'Could not stop the process'
    )
  })

  it('keeps the row when the kill status is unknown or not found', async () => {
    await stopWith('mystery', { error: 'stop outcome unknown', status: 'unknown' })
    expect(rows()).toEqual([expect.objectContaining({ id: 'mystery', state: 'waiting' })])

    const request = vi.fn(async () => ({ error: 'No process with ID missing', status: 'not_found' }))
    $gateway.set({ request } as never)
    reconcileBackgroundProcesses(owner, [waiting('mystery'), waiting('missing')])
    await stopBackgroundProcess(owner, 'missing')

    expect(rows().map(row => [row.id, row.state])).toEqual([
      ['mystery', 'waiting'],
      ['missing', 'waiting']
    ])
  })

  it('dismisses a legacy killed result and does not resurrect it from a later list', async () => {
    await stopWith('legacy', {
      completion_reason: 'killed',
      output: '',
      session_id: 'legacy',
      status: 'killed',
      termination_source: 'process.kill'
    })

    expect(rows()).toEqual([])
    expect(notifyError).not.toHaveBeenCalled()
    reconcileBackgroundProcesses(owner, [waiting('legacy')])
    expect(rows()).toEqual([])
  })

  it('dismisses already_exited without a failed scope stop, and keeps one that failed', async () => {
    await stopWith('gone-child', {
      command: 'gone-child',
      completion_reason: 'exited',
      exit_code: 0,
      output: '',
      status: 'already_exited',
      termination_source: null
    })
    expect(rows()).toEqual([])

    await stopWith('scope', {
      exit_code: 0,
      output: '',
      scope_stop_failed: 'hermes-job.scope',
      status: 'already_exited'
    })
    expect(rows()).toEqual([expect.objectContaining({ id: 'scope', state: 'waiting' })])
    expect(notifyError).toHaveBeenCalledWith(
      expect.objectContaining({ message: 'Stop was not confirmed' }),
      'Could not stop the process'
    )
  })

  it('dismisses a service kill that recorded a killed snapshot', async () => {
    await stopWith('service-dead', {
      command: 'deploy-web',
      completion_reason: 'killed',
      exit_code: -15,
      output: '',
      session_id: 'service-dead',
      status: 'killed',
      termination_source: 'process.kill'
    })

    expect(rows()).toEqual([])
    expect(notifyError).not.toHaveBeenCalled()
  })

  it('drops an unconfirmed row once a later snapshot no longer reports it', async () => {
    await stopWith('settled', {
      error: 'service invocation does not match; it was not signalled',
      exit_code: null,
      process_running: true,
      status: 'unresolved'
    })
    expect(rows()).toEqual([expect.objectContaining({ id: 'settled', state: 'waiting' })])

    reconcileBackgroundProcesses(owner, [])
    expect(rows()).toEqual([])
  })

  it('keeps a waiting service on rewind when Stop is unresolved, and still drops a settled row', async () => {
    const request = vi.fn(async () => ({
      error: 'service stop intent could not be stored; it was not signalled',
      exit_code: null,
      process_running: true,
      status: 'unresolved'
    }))

    $gateway.set({ request } as never)
    reconcileBackgroundProcesses(owner, [
      waiting('live'),
      { command: 'legacy-build', exit_code: 0, session_id: 'done-row', status: 'exited' }
    ])

    resetSessionBackground(owner)
    await request.mock.results[0]!.value
    await Promise.resolve()

    expect(request).toHaveBeenCalledTimes(1)
    expect(request).toHaveBeenCalledWith('process.kill', { process_id: 'live', session_id: owner })
    expect(rows()).toEqual([expect.objectContaining({ id: 'live', state: 'waiting' })])
    expect(notifyError).toHaveBeenCalledWith(
      expect.objectContaining({ message: 'service stop intent could not be stored; it was not signalled' }),
      'Could not stop the process'
    )
  })

  it('drops a rewind Stop once the kill is confirmed', async () => {
    const request = vi.fn(async () => ({
      completion_reason: 'killed',
      output: '',
      session_id: 'live',
      status: 'killed',
      termination_source: 'process.kill'
    }))

    $gateway.set({ request } as never)
    reconcileBackgroundProcesses(owner, [waiting('live')])

    resetSessionBackground(owner)
    await request.mock.results[0]!.value
    await Promise.resolve()

    expect(rows()).toEqual([])
    expect(notifyError).not.toHaveBeenCalled()
  })

  it('keeps the row when a rewind Stop fails', async () => {
    const request = vi.fn(async () => {
      throw new Error('socket closed')
    })

    $gateway.set({ request } as never)
    reconcileBackgroundProcesses(owner, [running('live')])

    resetSessionBackground(owner)
    await request.mock.results[0]!.value.catch(() => undefined)

    expect(rows()).toEqual([expect.objectContaining({ id: 'live', state: 'running' })])
    expect(notifyError).toHaveBeenCalledWith(expect.any(Error), 'Could not stop the process')
  })
})

// ── Review-thread hardenings on the guard (#94950) ───────────────────────────
describe('refreshBackgroundProcesses dead-session guard hardenings', () => {
  beforeEach(() => {
    $backgroundStatusBySession.set({})
    resetBackgroundPollingGuard()
  })

  afterEach(() => {
    $gateway.set(null as never)
    resetBackgroundPollingGuard()
  })

  it('matches the structured 4001 code, not a message substring, when a code is present', () => {
    // Structured gateway rejection: the code decides, both directions.
    expect(isSessionGoneForBackgroundPolling(new JsonRpcGatewayError('session not found', { code: 4001 }))).toBe(true)
    expect(isSessionGoneForBackgroundPolling(new JsonRpcGatewayError('gone', { code: 4001 }))).toBe(true)

    // An unrelated coded error whose text merely MENTIONS the phrase must not
    // latch — that would freeze the status stack on a healthy session.
    expect(
      isSessionGoneForBackgroundPolling(
        new JsonRpcGatewayError('tool failed: upstream said session not found', { code: 5007 })
      )
    ).toBe(false)

    // Codeless errors keep the message fallback (legacy frames).
    expect(isSessionGoneForBackgroundPolling(new JsonRpcGatewayError('session not found'))).toBe(true)
  })

  it('a full guard reset (runtime re-mint) resumes polling every latched session', async () => {
    const request = vi.fn(async () => {
      throw new JsonRpcGatewayError('session not found', { code: 4001 })
    })

    $gateway.set({ request } as never)

    await refreshBackgroundProcesses(SID)
    await refreshBackgroundProcesses('sess-2')
    await refreshBackgroundProcesses(SID)
    await refreshBackgroundProcesses('sess-2')
    expect(request).toHaveBeenCalledTimes(2)

    // Gateway reconnect re-mints runtimes: the no-arg reset (wired at the
    // reconnect seams) must clear every latched id, not just one.
    resetBackgroundPollingGuard()
    await refreshBackgroundProcesses(SID)
    await refreshBackgroundProcesses('sess-2')

    expect(request).toHaveBeenCalledTimes(4)
  })
})
