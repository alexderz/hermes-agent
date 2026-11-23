import { atom, computed } from 'nanostores'

import { translateNow } from '@/i18n'
import { stableArray } from '@/lib/stable-array'
import { type TodoItem, type TodoStatus, todoTree } from '@/lib/todos'

import { $gateway } from './gateway'
import { $goalsBySession, type GoalStatus } from './goals'
import { $liveWorkRoster, noteEventFed, rosterLiveIds, rosterSaysIdle } from './live-work-roster'
import { dispatchNativeNotification } from './native-notifications'
import { notifyError } from './notifications'
import { isSessionGone, isSessionGoneForBackgroundPolling, markSessionGone, noteRuntimeAlive } from './runtime-gone'
import { $sessions, lineageAliases } from './session'
import { ambientRequestFor } from './session-gone-latch'
import { $sessionStates, requestForOwnedSession } from './session-states'
import { $subagentsBySession, type SubagentProgress } from './subagents'
import { $todosBySession } from './todos'

export {
  isSessionGone,
  isSessionGoneForBackgroundPolling,
  markSessionGone,
  resetBackgroundPollingGuard
} from './runtime-gone'

/** Composer status stack feed — merged todos, subagents, background per session. */
export type StatusItemState = 'done' | 'failed' | 'lost' | 'ready' | 'running' | 'unknown' | 'waiting'
export type StatusItemType = 'background' | 'goal' | 'subagent' | 'todo'

export interface ComposerStatusItem {
  /** background: non-zero exit shown inline when failed. */
  exitCode?: number
  /** subagent: active tool label shown on the right. */
  currentTool?: string
  /** todo: nesting depth (0 = top-level) for indented subtask rows. */
  depth?: number
  /** goal: active | paused | waiting | done. */
  goalStatus?: GoalStatus
  id: string
  /** background process: captured stdout/stderr tail for the inline viewer. */
  output?: string
  /** Unix milliseconds the process started. Elapsed is derived while it is live. */
  startedEpochMs?: number
  /** Snapshot age in seconds once the process is no longer ticking. */
  uptimeSeconds?: number
  /** subagent: its own stored session id — row click opens that session window
   *  (livestreamed by the gateway's child-session mirror). */
  sessionId?: string
  state: StatusItemState
  title: string
  /** todo: the full four-state status driving the row's checkmark glyph. */
  todoStatus?: TodoStatus
  type: StatusItemType
}

// Writable source for background work, synced from the gateway's process
// registry (`terminal(background=true)` spawns) via `process.list`.
export const $backgroundStatusBySession = atom<Record<string, ComposerStatusItem[]>>({})
// When the backend snapshot behind each list arrived: the freshness the
// live-work roster compares against. Local removals (dismiss, auto-clear) carry
// the snapshot's stamp forward; they are not new backend data.
const backgroundWrittenAt = new WeakMap<readonly ComposerStatusItem[], number>()

// Stored session ids that still have background work the sidebar should mark
// with a hollow dot — waiting, running, ready, or a failure that has not
// lingered out. Distinct from the filled dot of an active LLM turn.
const PENDING_BACKGROUND_STATES = new Set<StatusItemState>(['failed', 'lost', 'ready', 'running', 'unknown', 'waiting'])

function sessionHasPendingBackground(items: readonly ComposerStatusItem[]): boolean {
  return items.some(item => PENDING_BACKGROUND_STATES.has(item.state))
}

//
// $backgroundStatusBySession is keyed by RUNTIME session id (gateway events
// and process.list both speak that); the sidebar row knows only the STORED id.
// $sessionStates bridges the two: runtime id → state.storedSessionId, then
// lineageAliases covers whichever tip of that conversation a surface holds.
// Perf: recomputes on every $sessionStates change (message deltas, tens/sec),
// but the background-running set rarely moves. `stableArray` keeps the prior
// reference when unchanged so rows reading this don't re-render per token.
let backgroundRunningIds: readonly string[] = []
export const $backgroundRunningSessionIds = computed(
  [$backgroundStatusBySession, $sessionStates, $sessions, $liveWorkRoster],
  (bg, states, sessions, roster) => {
    const ids = new Set<string>()
    const eventFedAt = new Map<string, number>()

    for (const [runtimeId, items] of Object.entries(bg)) {
      if (items.length === 0) {
        continue
      }

      // Same fresh-chat fallback as the working/attention projections: before a
      // conversation is persisted its runtime id is the id surfaces key on.
      const aliases = lineageAliases(states[runtimeId]?.storedSessionId ?? runtimeId, sessions)
      const writtenAt = backgroundWrittenAt.get(items) ?? -Infinity
      noteEventFed(eventFedAt, aliases, writtenAt)

      if (sessionHasPendingBackground(items) && !rosterSaysIdle(roster, 'background', aliases, writtenAt)) {
        for (const alias of aliases) {
          ids.add(alias)
        }
      }
    }

    // Rows no current event feed speaks for (off screen, every row after a reload).
    for (const alias of rosterLiveIds(roster, 'background', eventFedAt, sessions)) {
      ids.add(alias)
    }

    return (backgroundRunningIds = stableArray(backgroundRunningIds, [...ids]))
  }
)

// Rows the user X-ed away. The registry keeps finished processes around for a
// while, so without this every refresh would resurrect a dismissed row.
const dismissedBySession = new Map<string, Set<string>>()

// Settled tasks self-clear. Success goes quick; failure lingers longer so its
// exit code stays readable (the output also lives in the transcript). Waiting
// and ready stay until a later snapshot says they settled. A manual X still
// drops a finished row at once.
const SUCCESS_LINGER_MS = 4_000
const FAILURE_LINGER_MS = 12_000

function autoDismissDelay(state: StatusItemState): number | null {
  if (state === 'running' || state === 'waiting' || state === 'ready') {
    return null
  }

  if (state === 'failed' || state === 'lost' || state === 'unknown') {
    return FAILURE_LINGER_MS
  }

  return SUCCESS_LINGER_MS
}

function releasedLiveWork(previous: StatusItemState | undefined, state: StatusItemState): boolean {
  const wasLive = previous === 'running' || previous === 'waiting'
  const stillLive = state === 'running' || state === 'waiting'

  return wasLive && !stillLive
}

function nativeBackgroundTitle(
  state: StatusItemState
): 'notifications.native.backgroundDoneTitle' | 'notifications.native.backgroundFailedTitle' {
  if (state === 'failed' || state === 'lost' || state === 'unknown') {
    return 'notifications.native.backgroundFailedTitle'
  }

  return 'notifications.native.backgroundDoneTitle'
}

const autoClearTimers = new Map<string, Map<string, ReturnType<typeof setTimeout>>>()

function scheduleAutoDismiss(sid: string, id: string, delayMs: number) {
  let timers = autoClearTimers.get(sid)

  if (timers?.has(id)) {
    return
  }

  if (!timers) {
    timers = new Map()
    autoClearTimers.set(sid, timers)
  }

  timers.set(
    id,
    setTimeout(() => {
      autoClearTimers.get(sid)?.delete(id)
      dismissBackgroundProcess(sid, id)
    }, delayMs)
  )
}

function cancelAutoDismiss(sid: string, id: string) {
  const timers = autoClearTimers.get(sid)

  if (!timers) {
    return
  }

  const timer = timers.get(id)

  if (timer !== undefined) {
    clearTimeout(timer)
    timers.delete(id)
  }
}

function cancelAllAutoDismiss(sid: string) {
  const timers = autoClearTimers.get(sid)

  if (!timers) {
    return
  }

  for (const timer of timers.values()) {
    clearTimeout(timer)
  }

  autoClearTimers.delete(sid)
}

const subToItem = (s: SubagentProgress): ComposerStatusItem => ({
  currentTool: s.currentTool,
  id: s.id,
  sessionId: s.sessionId,
  state: 'running',
  title: s.goal,
  type: 'subagent'
})

const todoToItem = (t: TodoItem, depth: number): ComposerStatusItem => ({
  depth,
  id: `todo:${t.id}`,
  state: t.status === 'in_progress' ? 'running' : 'done',
  title: t.content,
  todoStatus: t.status,
  type: 'todo'
})

const goalToItem = (goal: { detail?: string; status: GoalStatus; title: string }): ComposerStatusItem => ({
  currentTool: goal.detail,
  goalStatus: goal.status,
  id: 'goal:standing',
  state: goal.status === 'active' || goal.status === 'waiting' ? 'running' : 'done',
  title: goal.title,
  type: 'goal'
})

// The single thing the stack reads: a typed, merged item list per session.
//
// Identity contract: this computed's inputs churn constantly during a turn (a
// subagent tick, a 5s background poll, a todo update — in ANY session), but
// the merged output for most sessions is unchanged. Rebuilding fresh arrays
// and item objects every time handed every mounted composer stack a new
// reference per recompute — cross-session churn × open tiles. Stabilize both
// levels: an unchanged session keeps its previous array (and item objects),
// and a fully-unchanged map keeps its previous reference so `computed` skips
// the notify entirely ("preserve reference identity on no-ops").
const sameStatusItem = (a: ComposerStatusItem, b: ComposerStatusItem) =>
  a.id === b.id &&
  a.type === b.type &&
  a.state === b.state &&
  a.title === b.title &&
  a.output === b.output &&
  a.exitCode === b.exitCode &&
  a.startedEpochMs === b.startedEpochMs &&
  a.uptimeSeconds === b.uptimeSeconds &&
  a.currentTool === b.currentTool &&
  a.goalStatus === b.goalStatus &&
  a.todoStatus === b.todoStatus &&
  a.depth === b.depth &&
  a.sessionId === b.sessionId

const stabilizeItems = (prev: ComposerStatusItem[] | undefined, next: ComposerStatusItem[]): ComposerStatusItem[] => {
  if (!prev) {
    return next
  }

  const merged = next.map((item, i) => (prev[i] && sameStatusItem(prev[i], item) ? prev[i] : item))

  return merged.length === prev.length && merged.every((item, i) => item === prev[i]) ? prev : merged
}

let prevStatusItems: Record<string, ComposerStatusItem[]> = {}

export const $statusItemsBySession = computed(
  [$goalsBySession, $subagentsBySession, $backgroundStatusBySession, $todosBySession],
  (goals, subs, background, todos) => {
    const out: Record<string, ComposerStatusItem[]> = {}

    const push = (sid: string, items: ComposerStatusItem[]) => {
      if (items.length > 0) {
        out[sid] = out[sid] ? [...out[sid], ...items] : items
      }
    }

    for (const [sid, list] of Object.entries(todos)) {
      push(
        sid,
        todoTree(list).map(([t, depth]) => todoToItem(t, depth))
      )
    }

    for (const [sid, goal] of Object.entries(goals)) {
      push(sid, [goalToItem(goal)])
    }

    for (const [sid, list] of Object.entries(subs)) {
      push(sid, list.filter(s => s.status === 'running' || s.status === 'queued').map(subToItem))
    }

    for (const [sid, list] of Object.entries(background)) {
      push(sid, list)
    }

    let unchanged = Object.keys(prevStatusItems).length === Object.keys(out).length

    for (const sid of Object.keys(out)) {
      out[sid] = stabilizeItems(prevStatusItems[sid], out[sid]!)
      unchanged &&= out[sid] === prevStatusItems[sid]
    }

    return (prevStatusItems = unchanged ? prevStatusItems : out)
  }
)

// Fixed render order for the groups in the stack (top → bottom, above queue).
const TYPE_ORDER: readonly StatusItemType[] = ['goal', 'todo', 'subagent', 'background']

export interface StatusGroup {
  items: ComposerStatusItem[]
  type: StatusItemType
}

export function groupStatusItems(items: readonly ComposerStatusItem[]): StatusGroup[] {
  const byType = new Map<StatusItemType, ComposerStatusItem[]>()

  for (const item of items) {
    const list = byType.get(item.type)

    if (list) {
      list.push(item)
    } else {
      byType.set(item.type, [item])
    }
  }

  return TYPE_ORDER.filter(type => byType.has(type)).map(type => ({ items: byType.get(type)!, type }))
}

const writeBackground = (sid: string, items: ComposerStatusItem[], snapshotAt: number | undefined) => {
  const current = $backgroundStatusBySession.get()
  const next = { ...current }

  if (items.length > 0) {
    next[sid] = items

    if (snapshotAt !== undefined) {
      backgroundWrittenAt.set(items, snapshotAt)
    }
  } else {
    delete next[sid]
  }

  $backgroundStatusBySession.set(next)
}

// `process.list` entry. `attention` and `service_mode` are optional until the
// shared generated contract publishes them. Rows that omit both keep the
// historic running / exit-code mapping.
interface GatewayProcessEntry {
  attention?: string
  command?: string
  completion_reason?: string
  exit_code?: number
  output_tail?: string
  service_mode?: string
  session_id?: string
  started_epoch?: number
  status?: string
  uptime_seconds?: number
}

function namedAttention(value: string | undefined): StatusItemState | null {
  if (value === 'waiting' || value === 'running' || value === 'ready' || value === 'failed' || value === 'lost') {
    return value
  }

  return value ? 'unknown' : null
}

function unsettledService(proc: GatewayProcessEntry, exitCode: number | undefined): boolean {
  if (proc.service_mode !== 'await' && proc.service_mode !== 'notify') {
    return false
  }

  if (exitCode !== undefined) {
    return false
  }

  return (proc.completion_reason ?? '') !== 'exited'
}

function completionState(proc: GatewayProcessEntry, exitCode: number | undefined): StatusItemState {
  if (proc.completion_reason === 'lost') {
    return 'lost'
  }

  if (proc.completion_reason === 'killed') {
    return 'failed'
  }

  if (exitCode) {
    return 'failed'
  }

  return unsettledService(proc, exitCode) ? 'unknown' : 'done'
}

function backgroundState(proc: GatewayProcessEntry, exitCode: number | undefined): StatusItemState {
  const attention = namedAttention(proc.attention)

  if (attention) {
    return attention
  }

  if (proc.status !== 'exited') {
    return proc.service_mode === 'await' ? 'waiting' : 'running'
  }

  return completionState(proc, exitCode)
}

function startedEpochMs(epoch: number | undefined): number | undefined {
  return typeof epoch === 'number' && epoch > 0 ? epoch * 1000 : undefined
}

function snapshotUptime(seconds: number | undefined): number | undefined {
  return typeof seconds === 'number' && seconds >= 0 ? seconds : undefined
}

const toBackgroundItem = (proc: GatewayProcessEntry): ComposerStatusItem => {
  const exitCode = typeof proc.exit_code === 'number' ? proc.exit_code : undefined

  return {
    exitCode,
    id: proc.session_id ?? '',
    output: proc.output_tail || undefined,
    startedEpochMs: startedEpochMs(proc.started_epoch),
    state: backgroundState(proc, exitCode),
    title: (proc.command ?? '').split('\n')[0]!.trim() || 'background process',
    type: 'background',
    uptimeSeconds: snapshotUptime(proc.uptime_seconds)
  }
}

const sameItem = (a: ComposerStatusItem, b: ComposerStatusItem) =>
  a.state === b.state &&
  a.title === b.title &&
  a.output === b.output &&
  a.exitCode === b.exitCode &&
  a.startedEpochMs === b.startedEpochMs &&
  a.uptimeSeconds === b.uptimeSeconds

/**
 * Layout-stable sync of the registry snapshot into the store: existing rows
 * keep their position (status flips happen in place, never reorder), new
 * processes append, dismissed ids stay gone, and unchanged rows keep their
 * object identity so memoised rows skip re-rendering.
 */
export function reconcileBackgroundProcesses(sid: string, procs: GatewayProcessEntry[]) {
  const dismissed = dismissedBySession.get(sid)

  const fresh = new Map(
    procs
      .filter(proc => proc.session_id && !dismissed?.has(proc.session_id))
      .map(proc => [proc.session_id!, toBackgroundItem(proc)])
  )

  const prev = $backgroundStatusBySession.get()[sid] ?? []

  // running → exited since the last snapshot = a background process just finished.
  const prevState = new Map(prev.map(item => [item.id, item.state]))

  for (const [id, item] of fresh) {
    const previous = prevState.get(id)

    if (releasedLiveWork(previous, item.state)) {
      let body = item.title

      if (item.exitCode !== undefined) {
        body += ` (exit ${item.exitCode})`
      }

      if (item.output) {
        const tailLines = item.output.trim().split('\n').slice(-3)

        if (tailLines.length > 0) {
          body += '\n' + tailLines.join('\n')
        }
      }

      dispatchNativeNotification({
        body,
        kind: 'backgroundDone',
        sessionId: sid,
        title: translateNow(nativeBackgroundTitle(item.state))
      })
    }
  }

  const kept = prev.flatMap(old => {
    const next = fresh.get(old.id)
    fresh.delete(old.id)

    return next ? [sameItem(old, next) ? old : next] : []
  })

  const next = [...kept, ...fresh.values()]

  // Dismissals only need remembering while the registry still reports the id.
  if (dismissed) {
    const reported = new Set(procs.map(proc => proc.session_id))

    for (const id of dismissed) {
      if (!reported.has(id)) {
        dismissed.delete(id)
      }
    }
  }

  // Waiting and ready stay until the server drops them. Lost and unknown use
  // the failure linger; a settled exit still uses the short success linger.
  const finishedDelay = new Map(
    next.flatMap(item => {
      const delay = autoDismissDelay(item.state)

      return delay === null ? [] : [[item.id, delay] as const]
    })
  )

  for (const [id, delay] of finishedDelay) {
    scheduleAutoDismiss(sid, id, delay)
  }

  for (const id of [...(autoClearTimers.get(sid)?.keys() ?? [])]) {
    if (!finishedDelay.has(id)) {
      cancelAutoDismiss(sid, id)
    }
  }

  if (next.length === prev.length && next.every((item, i) => item === prev[i])) {
    return
  }

  writeBackground(sid, next, Date.now())
}

/** Pull the session's live process snapshot from the gateway. */
export async function refreshBackgroundProcesses(sid: string): Promise<void> {
  const gateway = $gateway.get()

  if (!sid || !gateway || isSessionGone(sid)) {
    return
  }

  try {
    const result = await requestForOwnedSession<{ processes?: GatewayProcessEntry[] }>(
      sid,
      ambientRequestFor(gateway),
      'process.list',
      { session_id: sid }
    )

    reconcileBackgroundProcesses(sid, result?.processes ?? [])
    // The binding answered, so it is healthy: refund the stored session's
    // recovery budget (a heal that stuck must not count against the next one).
    noteRuntimeAlive(sid)
  } catch (error) {
    // A gone session never comes back under this runtime id: stop polling it,
    // or the 5s timer hammers the gateway with 4001s for the window's lifetime.
    if (isSessionGoneForBackgroundPolling(error)) {
      markSessionGone(sid)

      return
    }

    // Transient socket loss — the next trigger (event or poll) retries.
  }
}

/** X on a finished row: drop it now and keep it dropped across refreshes. */
export function dismissBackgroundProcess(sid: string, id: string) {
  cancelAutoDismiss(sid, id)

  const dismissed = dismissedBySession.get(sid) ?? new Set<string>()
  dismissed.add(id)
  dismissedBySession.set(sid, dismissed)

  const list = $backgroundStatusBySession.get()[sid] ?? []

  writeBackground(
    sid,
    list.filter(item => item.id !== id),
    backgroundWrittenAt.get(list)
  )
}

// kill_all's own confirmed-stop predicate: status killed or already_exited, and
// no scope_stop_failed. A service stop confirms only by returning that killed
// snapshot. running, unresolved, error, not_found, and unknown are not a stop.
const CONFIRMED_STOP_STATUSES = new Set(['already_exited', 'killed'])
const STOP_FAILED = 'Could not stop the process'

function killConfirmed(result: unknown): boolean {
  if (!result || typeof result !== 'object') {
    return false
  }

  const status = (result as { status?: unknown }).status

  if (typeof status !== 'string' || !CONFIRMED_STOP_STATUSES.has(status)) {
    return false
  }

  return !Object.prototype.hasOwnProperty.call(result, 'scope_stop_failed')
}

function stopFailure(result: unknown): Error {
  if (result && typeof result === 'object') {
    const row = result as { error?: unknown; note?: unknown }
    const detail = typeof row.error === 'string' ? row.error : typeof row.note === 'string' ? row.note : ''

    if (detail) {
      return new Error(detail)
    }
  }

  return new Error('Stop was not confirmed')
}

function paintUnknown(sid: string, id: string): void {
  const list = $backgroundStatusBySession.get()[sid] ?? []
  let changed = false

  const next = list.map(item => {
    if (item.id !== id || item.state === 'unknown') {
      return item
    }

    changed = true

    return { ...item, state: 'unknown' as const }
  })

  if (!changed) {
    return
  }

  writeBackground(sid, next, backgroundWrittenAt.get(list))
}

function holdUnconfirmedStop(sid: string, id: string, error: unknown): void {
  paintUnknown(sid, id)
  notifyError(error, STOP_FAILED)
}

function applyKillOutcome(sid: string, id: string, result: unknown): void {
  if (killConfirmed(result)) {
    dismissBackgroundProcess(sid, id)

    return
  }

  notifyError(stopFailure(result), STOP_FAILED)
}

function awaitsStopConfirmation(state: StatusItemState): boolean {
  return state === 'running' || state === 'waiting' || state === 'unknown'
}

async function settleBackgroundStop(sid: string, id: string): Promise<void> {
  const gateway = $gateway.get()

  if (isSessionGone(sid) || !gateway) {
    holdUnconfirmedStop(sid, id, new Error(isSessionGone(sid) ? 'Gateway session is gone' : 'Gateway is not connected'))

    return
  }

  try {
    applyKillOutcome(
      sid,
      id,
      await requestForOwnedSession(sid, ambientRequestFor(gateway), 'process.kill', {
        process_id: id,
        session_id: sid
      })
    )
  } catch (err) {
    if (isSessionGoneForBackgroundPolling(err)) {
      markSessionGone(sid)
      holdUnconfirmedStop(sid, id, err)

      return
    }

    notifyError(err, STOP_FAILED)
  }
}

/** X on a waiting or running row. Drop it only after process.kill returns a
 *  confirmed terminal snapshot. A resolved running/unresolved/error result, a
 *  disconnected gateway, or a gone runtime leaves the row up. */
export async function stopBackgroundProcess(sid: string, id: string): Promise<void> {
  await settleBackgroundStop(sid, id)
}

/**
 * Rewind cleanup. Settled rows leave with the discarded turns. A waiting,
 * running, or unknown row stays until its own process.kill confirms a stop
 * or a later snapshot drops it. Rewind itself does not wait on that kill.
 */
export function resetSessionBackground(sid: string) {
  if (!sid) {
    return
  }

  cancelAllAutoDismiss(sid)

  const list = $backgroundStatusBySession.get()[sid] ?? []
  const dismissed = dismissedBySession.get(sid) ?? new Set<string>()
  const kept: ComposerStatusItem[] = []

  for (const item of list) {
    if (!awaitsStopConfirmation(item.state)) {
      dismissed.add(item.id)

      continue
    }

    kept.push(item)
  }

  dismissedBySession.set(sid, dismissed)
  writeBackground(sid, kept, backgroundWrittenAt.get(list))

  for (const item of kept) {
    void settleBackgroundStop(sid, item.id)
  }
}
