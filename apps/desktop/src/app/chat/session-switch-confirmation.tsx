import { type ThreadMessage, useAuiState, useThreadRuntime } from '@assistant-ui/react'
import { useStore } from '@nanostores/react'
import { useEffect, useMemo } from 'react'

import { appViewForPath } from '@/app/routes'
import { sessionShouldHaveTranscript } from '@/app/session/hooks/use-session-actions/utils'
import {
  $sessionSwitchIntent,
  cancelSessionSwitch,
  confirmSessionSwitch,
  sessionSwitchIdentity
} from '@/app/session/session-switch'
import { usePaneVisible } from '@/components/pane-shell/pane-visibility'
import type { ChatMessage } from '@/lib/chat-messages'
import { useStoreSelector } from '@/lib/use-session-slice'
import { $gatewayState, $sessions, sessionMatchesStoredId } from '@/store/session'
import { $focusedTreePaneId } from '@/store/session-focus'
import { $sessionStates, runtimeSessionOwner } from '@/store/session-states'

import { useSessionView } from './session-view'

interface SessionSwitchConfirmationProps {
  expectedHead: ThreadMessage | null
  messages: ChatMessage[]
  pathname: string
  suppressed: boolean
}

/** Runs under the actual assistant runtime, after its transcript commit. */
export function SessionSwitchConfirmation({
  expectedHead,
  messages,
  pathname,
  suppressed
}: SessionSwitchConfirmationProps) {
  const intent = useStore($sessionSwitchIntent)
  const view = useSessionView()
  const storedId = useStore(view.$storedId)
  const runtimeId = useStore(view.$runtimeId)
  const visible = usePaneVisible()
  const focusedPane = useStore($focusedTreePaneId)
  const gatewayState = useStore($gatewayState)
  const sessions = useStore($sessions)

  const transcriptStoredId = useStoreSelector($sessionStates, states =>
    runtimeId ? states[runtimeId]?.storedSessionId : null
  )

  const paneId = view.kind === 'primary' ? 'workspace' : `session-tile:${storedId}`
  const target = intent?.storedSessionId === storedId && intent.paneId === paneId
  const foreground = visible && (!focusedPane || focusedPane === paneId) && appViewForPath(pathname) === 'chat'
  // Match the normalized active-branch head by reference: database row ids
  // can repeat across profiles, and tool/branch folding omits raw source rows.
  // An empty destination must also wait for the old runtime rows to retire.
  const committedMessages = useAuiState(state => state.thread.messages)
  const runtime = useThreadRuntime()

  // Selectors expose tracked proxies. Read raw objects for identity, but key
  // the check on the subscribed snapshot, not the stable runtime handle.
  const committed = useMemo(() => {
    const current = runtime.getState().messages

    return (
      current.length === committedMessages.length &&
      (expectedHead ? current.some(message => message === expectedHead) : current.length === 0)
    )
  }, [committedMessages, expectedHead, runtime])

  useEffect(() => {
    if (!intent || !target) {
      return
    }

    if (!foreground) {
      cancelSessionSwitch(storedId ?? undefined)

      return
    }

    const knownHistory = sessions.some(
      session => storedId && sessionMatchesStoredId(session, storedId) && sessionShouldHaveTranscript(session)
    )

    if (
      suppressed ||
      !runtimeId ||
      !storedId ||
      transcriptStoredId !== storedId ||
      gatewayState !== 'open' ||
      !committed ||
      (knownHistory && messages.length === 0)
    ) {
      return
    }

    const owner = runtimeSessionOwner(runtimeId)

    const identity = sessionSwitchIdentity(
      storedId,
      typeof owner === 'string' ? { profile: owner } : (owner ?? undefined)
    )

    if (identity !== intent.identity) {
      cancelSessionSwitch(storedId)

      return
    }

    confirmSessionSwitch(intent, identity)
  }, [
    committed,
    committedMessages,
    foreground,
    gatewayState,
    intent,
    messages,
    runtimeId,
    sessions,
    storedId,
    suppressed,
    target,
    transcriptStoredId
  ])

  return null
}
