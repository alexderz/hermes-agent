import { Fragment, memo, type ReactNode } from 'react'

import { openAgentTerminal } from '@/app/right-sidebar/terminal/terminals'
import { formatElapsed, useElapsedSeconds } from '@/components/chat/activity-timer'
import { StatusPendingIcon } from '@/components/chat/status-pending-icon'
import { StatusRow } from '@/components/chat/status-row'
import { Codicon } from '@/components/ui/codicon'
import { GlyphSpinner } from '@/components/ui/glyph-spinner'
import { type Translations, useI18n } from '@/i18n'
import { capitalize } from '@/lib/text'
import type { TodoStatus } from '@/lib/todos'
import { cn } from '@/lib/utils'
import type { ComposerStatusItem, StatusItemState } from '@/store/composer-status'

const toolLabel = (name: string) => name.split('_').filter(Boolean).map(capitalize).join(' ') || name

export function lastBackgroundOutputLine(output: string | undefined): string {
  if (!output) {
    return ''
  }

  const lines = output.split('\n')

  for (let index = lines.length - 1; index >= 0; index -= 1) {
    const text = lines[index]!.replace(/\s+/g, ' ').trim()

    if (text) {
      return text
    }
  }

  return ''
}

export function backgroundStatusPhrase(item: ComposerStatusItem, s: Translations['statusStack']): string | null {
  switch (item.state) {
    case 'waiting':
      return s.waitingFor(item.title)

    case 'ready':
      return s.resultReady

    case 'failed':
      return s.failed

    case 'lost':
      return s.lost

    case 'unknown':
      return s.unknown

    case 'running':
      return s.running

    default:
      return null
  }
}

function backgroundElapsed(item: ComposerStatusItem, ticking: number): number | null {
  const live = item.state === 'running' || item.state === 'waiting'

  if (live && typeof item.startedEpochMs === 'number') {
    return ticking
  }

  if (typeof item.uptimeSeconds === 'number') {
    return item.uptimeSeconds
  }

  return live ? ticking : null
}

function isStoppableBackground(item: ComposerStatusItem): boolean {
  return item.type === 'background' && (item.state === 'running' || item.state === 'waiting')
}

function hasLiveBackgroundClock(item: ComposerStatusItem): boolean {
  return (
    item.type === 'background' &&
    (item.state === 'running' || item.state === 'waiting') &&
    typeof item.startedEpochMs === 'number'
  )
}

function backgroundFailureTone(state: StatusItemState): boolean {
  return state === 'failed' || state === 'lost' || state === 'unknown'
}

function backgroundDotClass(state: StatusItemState): string {
  if (state === 'failed' || state === 'lost' || state === 'unknown') {
    return 'size-1.5 rounded-full bg-destructive/80'
  }

  if (state === 'waiting' || state === 'ready') {
    return 'size-1.5 rounded-full border border-(--ui-text-tertiary)'
  }

  return 'size-1.5 rounded-full bg-emerald-500/70'
}

// Todo rows speak checkbox, not spinner-and-dot: a dashed ring while the item
// is still open (pending), codicons once it resolves, a live spinner only on
// the in-progress item.
const TODO_GLYPHS: Record<Exclude<TodoStatus, 'in_progress' | 'pending'>, { icon: string; tone: string }> = {
  cancelled: { icon: 'circle-slash', tone: 'text-muted-foreground/45' },
  completed: { icon: 'pass-filled', tone: 'text-emerald-500/80' }
}

// Left slot: braille spinner while running, otherwise a small status dot
// (green = done, red = failed) so the slot is always filled and rows align.
function leadingGlyph(item: ComposerStatusItem, s: Translations['statusStack'], historical = false): ReactNode {
  if (item.type === 'goal') {
    if (item.goalStatus === 'paused') {
      return <Codicon className="text-muted-foreground/60" name="debug-pause" size="0.8rem" />
    }

    if (item.goalStatus === 'done') {
      return <Codicon className="text-emerald-500/80" name="pass-filled" size="0.8rem" />
    }

    return (
      <GlyphSpinner
        ariaLabel={s.running}
        className="text-[0.85rem] leading-none text-emerald-500/80"
        spinner="braille"
      />
    )
  }

  if (item.todoStatus === 'pending' || (historical && item.todoStatus === 'in_progress')) {
    return <StatusPendingIcon />
  }

  if (item.todoStatus && item.todoStatus !== 'in_progress') {
    const glyph = TODO_GLYPHS[item.todoStatus]

    return <Codicon className={glyph.tone} name={glyph.icon} size="0.8rem" />
  }

  if (item.type === 'background' && item.state !== 'running') {
    return <span aria-hidden className={backgroundDotClass(item.state)} data-state={item.state} />
  }

  if (item.state === 'running') {
    return (
      <GlyphSpinner
        ariaLabel={s.running}
        className="text-[0.85rem] leading-none text-muted-foreground/80"
        spinner="braille"
      />
    )
  }

  return (
    <span
      aria-hidden
      className={cn('size-1.5 rounded-full', item.state === 'failed' ? 'bg-destructive/80' : 'bg-emerald-500/70')}
    />
  )
}

function BackgroundCopy({
  elapsed,
  failed,
  item,
  s
}: {
  elapsed: number | null
  failed: boolean
  item: ComposerStatusItem
  s: Translations['statusStack']
}) {
  const phrase = backgroundStatusPhrase(item, s)
  const output = lastBackgroundOutputLine(item.output)

  return (
    <div className="min-w-0 flex-1">
      <div className="flex min-w-0 flex-wrap items-baseline gap-x-1.5">
        <span className="min-w-0 break-words text-[0.73rem] leading-4 text-foreground/92">{item.title}</span>
        {phrase && (
          <span
            className={cn(
              'min-w-0 break-words text-[0.62rem] leading-4',
              failed ? 'text-destructive/90' : 'text-muted-foreground/80'
            )}
          >
            {phrase}
          </span>
        )}
        {elapsed !== null && (
          <span className="shrink-0 text-[0.62rem] leading-4 text-muted-foreground/70 tabular-nums">
            {formatElapsed(elapsed)}
          </span>
        )}
      </div>
      {output && (
        <div className="line-clamp-2 break-words text-[0.62rem] leading-4 text-muted-foreground/70">{output}</div>
      )}
    </div>
  )
}

function statusItemBody(
  item: ComposerStatusItem,
  ticking: number,
  failed: boolean,
  s: Translations['statusStack']
): ReactNode {
  if (item.type === 'background') {
    return (
      <BackgroundCopy
        elapsed={backgroundElapsed(item, ticking)}
        failed={backgroundFailureTone(item.state)}
        item={item}
        s={s}
      />
    )
  }

  return (
    <span
      className={cn(
        'min-w-0 flex-1 truncate text-[0.73rem] leading-4',
        failed
          ? 'text-destructive/90'
          : item.todoStatus && item.todoStatus !== 'in_progress'
            ? 'text-muted-foreground/75'
            : 'text-foreground/92'
      )}
    >
      {item.title}
    </span>
  )
}

interface StatusItemRowProps {
  item: ComposerStatusItem
  /** Render a retained, non-running task snapshot. */
  historical?: boolean
  /** Clear a finished background task from the stack. */
  onDismiss?: (id: string) => void
  /** Open the subagent's own session window, livestreamed by the gateway's
   *  child-session mirror (Agents view fallback for older gateways). */
  onOpen?: () => void
  /** Cancel a running background task. */
  onStop?: (id: string) => void
}

/**
 * Renders one {@link ComposerStatusItem} into the shared {@link StatusRow}.
 * Memoised + keyed by id so parent re-renders never remount it (the spinner
 * keeps ticking instead of resetting).
 */
export const StatusItemRow = memo(function StatusItemRow({
  historical = false,
  item,
  onDismiss,
  onOpen,
  onStop
}: StatusItemRowProps) {
  const { t } = useI18n()
  const s = t.statusStack
  const failed = item.state === 'failed'
  const stoppable = isStoppableBackground(item)
  const ticking = useElapsedSeconds(hasLiveBackgroundClock(item), item.id, item.startedEpochMs)

  const action =
    item.type === 'background'
      ? stoppable
        ? onStop && { label: s.stop, onClick: () => onStop(item.id) }
        : onDismiss && { label: s.dismiss, onClick: () => onDismiss(item.id) }
      : null

  const canOpen = item.type === 'subagent' && !!onOpen

  // Background rows link to their read-only terminal tab; subagents open their session.
  const onActivate =
    item.type === 'background' ? () => openAgentTerminal(item.id, item.title) : canOpen ? onOpen : undefined

  return (
    <Fragment>
      <StatusRow
        depth={Math.min(item.depth ?? 0, 4)}
        dismiss={action ? { label: action.label, onDismiss: action.onClick } : undefined}
        leading={leadingGlyph(item, s, historical)}
        onActivate={onActivate}
        trailing={
          canOpen ? (
            <Codicon aria-hidden className="text-muted-foreground/55" name="link-external" size="0.85rem" />
          ) : undefined
        }
      >
        {statusItemBody(item, ticking, failed, s)}
        {item.type === 'subagent' && item.currentTool && (
          <span className="shrink-0 truncate text-[0.62rem] leading-4 text-muted-foreground/70">
            {toolLabel(item.currentTool)}
          </span>
        )}
        {item.type === 'goal' && item.currentTool && (
          <span className="shrink-0 truncate text-[0.62rem] leading-4 text-muted-foreground/70">
            {item.currentTool}
          </span>
        )}
        {failed && typeof item.exitCode === 'number' && item.exitCode !== 0 && (
          <span className="shrink-0 rounded bg-destructive/15 px-1 text-[0.58rem] font-semibold text-destructive tabular-nums">
            {s.exit(item.exitCode)}
          </span>
        )}
      </StatusRow>
    </Fragment>
  )
})
