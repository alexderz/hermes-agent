import { act, cleanup, render } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

import { openSession } from '@/app/open-session'
import { group } from '@/components/pane-shell/tree/model'
import { $layoutTree, noteActiveTreeGroup } from '@/components/pane-shell/tree/store'
import {
  $selectedStoredSessionId,
  $sessionResumeRequest,
  requestSessionResume,
  setSelectedStoredSessionId
} from '@/store/session'
import { _resetUserSessionOpenForTests } from '@/store/session-open-intent'
import { $sessionTiles } from '@/store/session-states'

import { useRouteResume } from './use-route-resume'

function Harness(props: Parameters<typeof useRouteResume>[0]) {
  useRouteResume(props)

  return null
}

function resumeProps(): Parameters<typeof useRouteResume>[0] {
  const selected = { current: null as string | null }

  return {
    activeSessionId: null,
    activeSessionIdRef: { current: null },
    creatingSessionRef: { current: false },
    currentView: 'settings',
    freshDraftReady: false,
    gatewayState: 'open',
    locationPathname: '/settings',
    resumeSession: vi.fn(async (id: string) => {
      setSelectedStoredSessionId(id)
      selected.current = id
    }),
    resumeFailedSessionId: null,
    resumeExhaustedSessionId: null,
    sessionResumeRequest: null,
    routedSessionId: null,
    runtimeIdByStoredSessionIdRef: { current: new Map() },
    selectedStoredSessionId: null,
    selectedStoredSessionIdRef: selected,
    startFreshSessionDraft: vi.fn()
  }
}

function restoredTab() {
  $layoutTree.set(group(['workspace', 'session-tile:B'], { active: 'session-tile:B', id: 'main' }))
  $sessionTiles.set([{ storedSessionId: 'B' }])
  noteActiveTreeGroup(null)
}

function activePane() {
  const tree = $layoutTree.get()

  return tree?.type === 'group' ? tree.active : null
}

beforeEach(() => {
  _resetUserSessionOpenForTests()
  $sessionResumeRequest.set(null)
})
afterEach(() => {
  cleanup()
  $sessionTiles.set([])
  $selectedStoredSessionId.set(null)
  $layoutTree.set(null)
})

it.each([true, false])(
  'fronts the requested session on the first navigation from settings (resume request: %s)',
  hasRequest => {
    const props = resumeProps()
    const { rerender } = render(<Harness {...props} />)
    restoredTab()
    let path = '/'
    act(() => {
      if (hasRequest) {
        requestSessionResume('C')
      }

      openSession('C', to => {
        path = to
      })
    })
    rerender(
      <Harness
        {...props}
        currentView="chat"
        locationPathname={path}
        routedSessionId="C"
        sessionResumeRequest={hasRequest ? $sessionResumeRequest.get() : null}
      />
    )
    expect($selectedStoredSessionId.get()).toBe('C')
    expect(activePane()).toBe('workspace')
  }
)

it('preserves the persisted active tab on a genuine cold-start route resume', () => {
  restoredTab()
  render(<Harness {...resumeProps()} currentView="chat" locationPathname="/C" routedSessionId="C" />)
  expect($selectedStoredSessionId.get()).toBe('C')
  expect(activePane()).toBe('session-tile:B')
})

it('does not mistake an unrelated user open or a background resume request for this route’s intent', () => {
  const props = resumeProps()
  const { rerender } = render(<Harness {...props} />)
  restoredTab()
  act(() => {
    openSession('D', () => undefined)
    requestSessionResume('C')
  })
  rerender(
    <Harness
      {...props}
      currentView="chat"
      locationPathname="/C"
      routedSessionId="C"
      sessionResumeRequest={$sessionResumeRequest.get()}
    />
  )
  expect($selectedStoredSessionId.get()).toBe('C')
  expect(activePane()).toBe('session-tile:B')
})
