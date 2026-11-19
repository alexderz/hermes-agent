import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { stubThreadEnvironment, ThreadRuntime, userMessage } from '../test-utils'

import { AGENT_MESSAGE_RE } from './user-message'

import { Thread } from '.'

stubThreadEnvironment()
afterEach(cleanup)

const ID = 'abcd1234'
const HEADER = `📡 Not Sam · reply requested · hermes@bob says (session local-1 · message ${ID}):`

function renderNote(text: string) {
  return render(
    <ThreadRuntime messages={[userMessage('u1', text)]}>
      <Thread />
    </ThreadRuntime>
  )
}

// Agent-to-agent deliveries render as a compact attributed timeline notice,
// not a user bubble. This pins the detection contract: the Bot Mode prefix
// ("Message from 🤖 <sender>: …"), the handle-carrying form
// ("Message from 🤖 <sender> (@<handle>): …"), and the legacy bracket form
// all match; human prose that merely mentions the phrase does not.
describe('agent message detection', () => {
  it('matches the Bot Mode delivery prefix with sender and body', () => {
    const m = AGENT_MESSAGE_RE.exec('Message from 🤖 Hermes: hello there')

    expect(m?.[1]?.trim()).toBe('Hermes')
    expect(m?.[4]).toBe('hello there')
  })

  it('captures the @handle when present', () => {
    const m = AGENT_MESSAGE_RE.exec('Message from 🤖 Eats Tests (@mr-tester): run them all')

    expect(m?.[1]?.trim()).toBe('Eats Tests')
    expect(m?.[2]).toBe('mr-tester')
    expect(m?.[4]).toBe('run them all')
  })

  it('recognizes a relayed sender re-stamped @handle@connection, keeping the bare handle for the avatar', () => {
    // The receiving gateway re-stamps a relayed "@hermes" as "@hermes@<connection>"
    // (#103731) — still an agent notice, and the avatar resolves by profile handle.
    const m = AGENT_MESSAGE_RE.exec('Message from 🤖 hermes (@hermes@Cloud-1): status?')

    expect(m?.[1]?.trim()).toBe('hermes')
    expect(m?.[2]).toBe('hermes')
    expect(m?.[4]).toBe('status?')
  })

  it('matches without the robot emoji', () => {
    const m = AGENT_MESSAGE_RE.exec('Message from Turquoise: ready to work')

    expect(m?.[1]?.trim()).toBe('Turquoise')
    expect(m?.[4]).toBe('ready to work')
  })

  it('matches the legacy bracket form', () => {
    const m = AGENT_MESSAGE_RE.exec("[Message from agent 'turqoise'] ping")

    expect(m?.[3]).toBe('turqoise')
    expect(m?.[4]).toBe('ping')
  })

  it('spans multi-line bodies', () => {
    const m = AGENT_MESSAGE_RE.exec('Message from 🤖 Dev: line one\nline two')

    expect(m?.[4]).toBe('line one\nline two')
  })

  it('does not match prose that merely contains the phrase', () => {
    expect(AGENT_MESSAGE_RE.test('I got a Message from 🤖 Hermes: earlier')).toBe(false)
    expect(AGENT_MESSAGE_RE.test('can you explain what Message from means?')).toBe(false)
  })

  it('keeps the sender groups when a quoted gist sits ahead of the frame header', () => {
    const m = AGENT_MESSAGE_RE.exec(`Message from 📡 bob (@bob): “Third review round passed.”\n${HEADER}\nbody`)

    expect(m?.[1]?.trim()).toBe('📡 bob')
    expect(m?.[2]).toBe('bob')
    expect(m?.[4]?.startsWith('“Third review round passed.”')).toBe(true)
  })
})

describe('agent message gist row', () => {
  it('shows the sender, the gist and an opener, and opens the frame without the gist line', async () => {
    const { container } = renderNote(
      `Message from 📡 bob (@bob): “Third review round passed.”\n${HEADER}\nWhich month did the format change?`
    )

    const note = (await screen.findByText('bob')).closest('[data-slot="aui_agent-message-note"]')

    expect(note?.textContent).toContain('🤖')
    expect(screen.getByText('“Third review round passed.”')).toBeTruthy()
    expect(screen.getByText('▸')).toBeTruthy()
    expect(screen.queryByText('show message')).toBeNull()
    expect(screen.queryByText(/Message from/)).toBeNull()

    const details = note?.querySelector('details') as HTMLDetailsElement
    const panel = details.querySelector('div')

    expect(panel?.textContent).toContain('Which month did the format change?')
    expect(panel?.textContent).toContain('📡 Not Sam')
    expect(panel?.textContent).not.toContain('Third review round passed')

    fireEvent.click(details.querySelector('summary')!)
    expect(details.open).toBe(true)
    expect(container.querySelector('[data-slot="aui_agent-message-note"] summary')?.textContent).toContain('▸')
  })

  it("keeps an old intercom frame on today's row", async () => {
    renderNote(`Message from 📡 bob (@bob):\n${HEADER}\nWhich month did the format change?`)

    expect(await screen.findByText(/Message from/)).toBeTruthy()
    expect(screen.getByText('show message')).toBeTruthy()
    expect(screen.queryByText('▸')).toBeNull()
  })

  it("keeps a frame without a gist on today's row", async () => {
    renderNote(`Message from 📡 bob (@bob): Hello there\n${HEADER}\nWhich month?`)

    expect(await screen.findByText(/Message from/)).toBeTruthy()
    expect(screen.getByText('show message')).toBeTruthy()
    expect(screen.queryByText('▸')).toBeNull()
  })

  it("keeps a bot message on today's row, including one whose body starts with a curly quote", async () => {
    const { unmount } = renderNote('Message from 🤖 Hermes (@hermes): “Hi” she said the build failed')

    expect(await screen.findByText(/Message from Hermes/)).toBeTruthy()
    expect(screen.getByText('show message')).toBeTruthy()
    expect(screen.queryByText('▸')).toBeNull()
    unmount()

    renderNote('Message from 🤖 Hermes (@hermes): “Hi”')

    expect(await screen.findByText(/Message from Hermes/)).toBeTruthy()
    expect(screen.getByText('show message')).toBeTruthy()
    expect(screen.queryByText('▸')).toBeNull()
  })
})
