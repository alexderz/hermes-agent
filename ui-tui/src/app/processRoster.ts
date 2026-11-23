import { useStore } from '@nanostores/react'
import { atom } from 'nanostores'
import { useMemo } from 'react'

import { $uiState } from './uiStore.js'

// Background `terminal(background=true)` processes owned by this session, as the
// gateway's `process.list` reports them. Session-local presentation only.

export interface ProcessEntry {
  session_id: string
  command?: string
  status?: string
  uptime_seconds?: number | null
  exit_code?: number | null
  exited_at?: number | null
  completion_reason?: string | null
  output_preview?: string
  /** Optional until process.list publishes it on the shared contract. */
  attention?: string | null
  /** Optional until process.list publishes it on the shared contract. */
  service_mode?: string | null
  /** Strict wire flag. Omitted on a settled or legacy row. */
  admission_pending?: boolean | null
}

export interface ProcessRow {
  command: string
  /** Latest non-empty output line while running; the exit verdict once finished. */
  detail: string
  elapsedSeconds: number
  id: string
  /** Seconds since exit; 0 while running. */
  sinceExitSeconds: number
  status: 'done' | 'failed' | 'killed' | 'lost' | 'ready' | 'running' | 'unknown' | 'waiting'
}

/** A finished process stays on the dock long enough to read its exit line, then
 * leaves; the completion notification in the transcript is the durable record. */
export const PROCESS_RETAIN_SECONDS = 60

export const $processSnapshot = atom<{ sid: string | null; processes: ProcessEntry[] }>({ sid: null, processes: [] })

export function applyProcessSnapshot(sid: string | null, processes: ProcessEntry[] = []) {
  const previous = $processSnapshot.get()

  if (previous.sid !== sid || JSON.stringify(previous.processes) !== JSON.stringify(processes)) {
    $processSnapshot.set({ sid, processes })
  }
}

const REASON_STATUS: Record<string, ProcessRow['status']> = { killed: 'killed', lost: 'lost' }
const NAMED_ATTENTION = new Set<ProcessRow['status']>(['failed', 'lost', 'ready', 'running', 'waiting'])

const namedAttention = (value: string | null | undefined): ProcessRow['status'] | null => {
  if (value && NAMED_ATTENTION.has(value as ProcessRow['status'])) {
    return value as ProcessRow['status']
  }

  return value ? 'unknown' : null
}

const unsettledService = (entry: ProcessEntry): boolean => {
  if (entry.service_mode !== 'await' && entry.service_mode !== 'notify') {
    return false
  }

  if (entry.exit_code !== undefined && entry.exit_code !== null) {
    return false
  }

  return (entry.completion_reason ?? '') !== 'exited'
}

export const processIsOpen = (status: ProcessRow['status']): boolean =>
  status === 'running' || status === 'waiting' || status === 'ready'

const PENDING_OUTCOMES = new Set<ProcessRow['status']>(['failed', 'lost'])

/** A failed or lost receipt stays until admission settles. Omitted and false keep the retain window. */
const pendingOutcome = (entry: ProcessEntry, status: ProcessRow['status']): boolean =>
  entry.admission_pending === true && PENDING_OUTCOMES.has(status)

export const processStatus = (entry: ProcessEntry): ProcessRow['status'] => {
  // Killed is not an attention value. Read it before attention so a stop is
  // not painted ready, waiting, or failed from a stale attention field.
  if ((entry.completion_reason ?? '') === 'killed') {
    return 'killed'
  }

  const attention = namedAttention(entry.attention)

  if (attention) {
    return attention
  }

  if (entry.status !== 'exited') {
    return entry.service_mode === 'await' ? 'waiting' : 'running'
  }

  return (
    REASON_STATUS[entry.completion_reason ?? ''] ??
    (entry.exit_code ? 'failed' : unsettledService(entry) ? 'unknown' : 'done')
  )
}

const lastOutputLine = (preview: string | undefined): string => {
  for (const line of (preview ?? '').split('\n').reverse()) {
    const text = line.replace(/\s+/g, ' ').trim()

    if (text) {
      return text
    }
  }

  return ''
}

export const processVerdict = (row: ProcessRow, exitCode: number | null | undefined): string => {
  if (row.status === 'running' || row.status === 'waiting') {
    const tail = row.detail ? `last: ${row.detail}` : 'starting'

    return row.status === 'waiting' ? `waiting · ${tail}` : tail
  }

  if (row.status === 'ready') {
    return 'result ready'
  }

  if (row.status === 'unknown') {
    return 'unknown'
  }

  const verdict = row.status === 'killed' || row.status === 'lost' ? row.status : `exit ${exitCode ?? '?'}`

  return `${verdict} · ${row.sinceExitSeconds}s ago`
}

/** Running processes first (longest running first), then recently exited ones
 * newest-exit first. Exits older than the retention window are dropped, except a
 * failed or lost row that is still admission-pending. */
export const buildProcessRows = (processes: readonly ProcessEntry[], nowMs: number): ProcessRow[] => {
  const nowS = nowMs / 1000
  const rows: ProcessRow[] = []

  for (const entry of processes) {
    const status = processStatus(entry)
    const open = processIsOpen(status)
    const pending = pendingOutcome(entry, status)
    const exitedAt = open ? 0 : (entry.exited_at ?? 0)
    const sinceExitSeconds = exitedAt ? Math.max(0, Math.floor(nowS - exitedAt)) : 0

    if (!open && !pending && (!exitedAt || sinceExitSeconds > PROCESS_RETAIN_SECONDS)) {
      continue
    }

    const row: ProcessRow = {
      command: (entry.command ?? '').replace(/\s+/g, ' ').trim() || 'background process',
      detail: lastOutputLine(entry.output_preview),
      elapsedSeconds: Math.max(0, entry.uptime_seconds ?? 0) - sinceExitSeconds,
      id: entry.session_id,
      sinceExitSeconds,
      status
    }

    row.detail = processVerdict(row, entry.exit_code)
    rows.push(row)
  }

  return rows.sort((a, b) => {
    const aOpen = processIsOpen(a.status)
    const bOpen = processIsOpen(b.status)

    if (aOpen !== bOpen) {
      return aOpen ? -1 : 1
    }

    return aOpen ? b.elapsedSeconds - a.elapsedSeconds : a.sinceExitSeconds - b.sinceExitSeconds
  })
}

export function useProcessRows(nowMs: number): ProcessRow[] {
  const snapshot = useStore($processSnapshot)
  const { sid } = useStore($uiState)

  return useMemo(() => buildProcessRows(snapshot.sid === sid ? snapshot.processes : [], nowMs), [snapshot, sid, nowMs])
}
