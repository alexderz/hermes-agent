import { afterEach, expect, it, vi } from 'vitest'

import { createServerRequestHandler } from '../app/createServerRequestHandler.js'
import { $overlayState, resetOverlayState } from '../app/overlayStore.js'
import { hasOpenServerRequest, resetServerRequestsForTests } from '../app/serverRequestStore.js'

// A `clarify(secret_file=...)` card goes to every viewer of the session. The Ink masked prompt shows only the
// agent's text, so it must not open for one; nor may it answer (a skip from here would settle the card for the
// Webapp or desktop app too). The request is left open for them.

const secretRequest = (metadata: Record<string, unknown>) => ({
  fail: vi.fn(),
  id: 'secret-1',
  method: 'secret',
  params: { env_var: 'XYZ API key', metadata, prompt: 'Will be saved to /srv/example/xyz-key (0600, hermes:hermes)' },
  respond: vi.fn()
})

afterEach(() => {
  resetOverlayState()
  resetServerRequestsForTests()
})

it('leaves a secret file card unanswered, opens no masked prompt and says where to answer it', () => {
  const ringPromptBell = vi.fn()
  const setStatus = vi.fn()
  const request = secretRequest({ destination: { kind: 'file', mode: '0600', path: '/srv/example/xyz-key' } })

  expect(createServerRequestHandler({ ringPromptBell, setStatus })(request as never)).toBe(true)

  expect($overlayState.get().secret).toBeFalsy()
  expect(request.respond).not.toHaveBeenCalled()
  expect(request.fail).not.toHaveBeenCalled()
  expect(hasOpenServerRequest('secret-1')).toBe(false)
  expect(ringPromptBell).not.toHaveBeenCalled()
  expect(setStatus).toHaveBeenCalledExactlyOnceWith(
    'secret for /srv/example/xyz-key: enter it in the Hermes Webapp or desktop app'
  )
})

it('still opens the masked prompt for a .env secret', () => {
  const request = secretRequest({ source: 'agent' })

  createServerRequestHandler({ ringPromptBell: vi.fn(), setStatus: vi.fn() })(request as never)

  expect($overlayState.get().secret).toMatchObject({ envVar: 'XYZ API key', requestId: 'secret-1' })
  expect(request.respond).not.toHaveBeenCalled()
})
