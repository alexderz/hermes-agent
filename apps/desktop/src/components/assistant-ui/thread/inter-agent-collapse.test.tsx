// Two contracts with no coverage before the invalidation-scoping work split
// AssistantMessage into InterAgentAssistantMessage + AssistantMessageBody:
//
// 1. The collapse gate. A reply to an inter-agent delivery renders collapsed
//    ("Replied to <sender>", expandable) ONLY once it settles — never while it
//    streams, because the user should see progress. That gate is the sole
//    remaining root-level `isRunning` subscription, so it is the thing most
//    likely to break if the split is revisited.
// 2. The streaming marker. `data-message-streaming` moved off the message root
//    onto a permanently-mounted hidden leaf, and
//    scripts/run-short-session-hang-repro.mjs derives its settled-row count by
//    subtracting `[data-message-streaming="true"]` markers from message roots.
//    Nothing in the app itself reads it, so without this test a delete would
//    look free and would silently regress that repro's response gate.
import { AssistantRuntimeProvider, type ThreadMessage, useExternalStoreRuntime } from '@assistant-ui/react'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { Thread } from '.'

const createdAt = new Date('2026-05-01T00:00:00.000Z')

class TestResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
vi.stubGlobal('ResizeObserver', TestResizeObserver)
vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) =>
  window.setTimeout(() => callback(performance.now()), 0)
)
vi.stubGlobal('cancelAnimationFrame', (id: number) => window.clearTimeout(id))
vi.stubGlobal('CSS', { escape: (str: string) => str })

Element.prototype.scrollTo = function scrollTo() {}

Element.prototype.animate = function animate() {
  return { cancel() {}, finished: Promise.resolve() } as unknown as Animation
}

afterEach(() => {
  cleanup()
})

const assistantMetadata = { unstable_state: null, unstable_annotations: [], unstable_data: [], steps: [], custom: {} }

function user(id: string, text: string): ThreadMessage {
  return {
    id,
    role: 'user',
    content: [{ type: 'text', text }],
    attachments: [],
    createdAt,
    metadata: { custom: {} }
  } as ThreadMessage
}

function assistant(id: string, text: string, running: boolean): ThreadMessage {
  return {
    id,
    role: 'assistant',
    content: text ? [{ type: 'text', text }] : [],
    status: running ? { type: 'running' } : { type: 'complete', reason: 'stop' },
    createdAt,
    metadata: assistantMetadata
  } as ThreadMessage
}

function assistantContent(id: string, content: ThreadMessage['content'], running = false): ThreadMessage {
  return {
    id,
    role: 'assistant',
    content,
    status: running ? { type: 'running' } : { type: 'complete', reason: 'stop' },
    createdAt,
    metadata: assistantMetadata
  } as ThreadMessage
}

const MESSAGE_ID = 'abcd1234'

function frame(label: string, gist?: string): string {
  const notice = gist ? `Message from 📡 bob (@bob): “${gist}”` : 'Message from 📡 bob (@bob):'

  return `${notice}\n📡 Not Sam · ${label} · hermes@bob says (session local-1 · message ${MESSAGE_ID}):\nPlease check the build.`
}

function summaryText(container: HTMLElement): string[] {
  return [...container.querySelectorAll('summary')].map(node => node.textContent ?? '')
}

function Harness({ messages }: { messages: ThreadMessage[] }) {
  const runtime = useExternalStoreRuntime<ThreadMessage>({
    messages,
    isRunning: messages.at(-1)?.status?.type === 'running',
    onNew: async () => {}
  })

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <Thread />
    </AssistantRuntimeProvider>
  )
}

const DELIVERY = 'Message from 🤖 Hermes (@hermes): please check the build'

/** This bot's own `message_agent` dispatch to a teammate (a Bot Chat turn). */
function dispatch(id: string, target: string): ThreadMessage {
  return {
    id,
    role: 'assistant',
    content: [
      {
        type: 'tool-call',
        toolCallId: `${id}-call`,
        toolName: 'message_agent',
        args: { target, message: 'send me the list' },
        argsText: JSON.stringify({ target, message: 'send me the list' })
      }
    ],
    status: { type: 'complete', reason: 'stop' },
    createdAt,
    metadata: assistantMetadata
  } as ThreadMessage
}

describe('inter-agent collapse gate', () => {
  it('keeps the report after a relayed answer to this bot\u2019s own dispatch expanded', async () => {
    // Bot Mode round trip seen from the DISPATCHING bot: it messaged @hermes,
    // the answer came back as an inbound "Message from" row, and the next
    // assistant message is its report to the human — not a reply to hermes.
    render(
      <Harness
        messages={[
          user('u1', 'ask hermes for the list'),
          dispatch('a0', '@Hermes'),
          user('u2', DELIVERY),
          assistant('a1', 'here is the list hermes sent', false)
        ]}
      />
    )

    await screen.findByText('here is the list hermes sent')
    expect(screen.queryByText(/Replied to/)).toBeNull()
    expect(screen.queryByText('show reply')).toBeNull()
  })

  it('still collapses the reply to an unsolicited delivery (dispatch went to another teammate)', async () => {
    render(
      <Harness messages={[dispatch('a0', 'scribe'), user('u2', DELIVERY), assistant('a1', 'build is green', false)]} />
    )

    expect(await screen.findByText(/Replied to/)).toBeTruthy()
    expect(screen.getByText('show reply')).toBeTruthy()
  })

  it('collapses the reply to a LATER unsolicited delivery from a teammate dispatched to earlier', async () => {
    // One dispatch exempts only the answer that follows it. Turns later, the
    // same teammate messages in on its own — that exchange had no dispatch,
    // so the deliberate fold (#85884) must still apply.
    render(
      <Harness
        messages={[
          user('u1', 'ask hermes for the list'),
          dispatch('a0', '@Hermes'),
          user('u2', DELIVERY),
          assistant('a1', 'here is the list hermes sent', false),
          user('u3', 'ok thanks'),
          assistant('a2', 'anytime', false),
          user('u4', 'Message from 🤖 Hermes (@hermes): unsolicited: build broke'),
          assistant('a3', 'on it, checking the build', false)
        ]}
      />
    )

    expect(await screen.findByText(/Replied to/)).toBeTruthy()
    expect(screen.getAllByText(/Replied to/)).toHaveLength(1)
    expect(screen.getByText('show reply')).toBeTruthy()
  })

  it('collapses a settled reply to an inter-agent delivery', async () => {
    render(<Harness messages={[user('u1', DELIVERY), assistant('a1', 'build is green', false)]} />)

    expect(await screen.findByText(/Replied to/)).toBeTruthy()
    expect(screen.getByText('show reply')).toBeTruthy()
  })

  it('does NOT collapse while that reply is still streaming', async () => {
    const { container } = render(<Harness messages={[user('u1', DELIVERY), assistant('a1', 'working on it', true)]} />)

    await screen.findByText('working on it')
    expect(screen.queryByText('show reply')).toBeNull()
    // Expanded => the full body root, which carries the streaming marker.
    expect(container.querySelector('[data-message-streaming="true"]')).toBeTruthy()
  })

  it('leaves an ordinary reply expanded', async () => {
    render(<Harness messages={[user('u1', 'ordinary question'), assistant('a1', 'ordinary answer', false)]} />)

    await screen.findByText('ordinary answer')
    expect(screen.queryByText(/Replied to/)).toBeNull()
  })

  it("shows the matching block's Gist on the reply row", async () => {
    const { container } = render(
      <Harness
        messages={[
          user('u1', frame('reply requested', 'Third review round passed.')),
          assistant(
            'a1',
            `[REPLY 11111111]\nGist: Wrong block.\nNo.\n[/REPLY]\n[REPLY ${MESSAGE_ID}]\nGist: Third review passed.\nAll green.\n[/REPLY]`,
            false
          )
        ]}
      />
    )

    expect(await screen.findByText('Third review passed.')).toBeTruthy()
    expect(screen.getByText('Replied')).toBeTruthy()
    expect(screen.queryByText('show reply')).toBeNull()
    expect(screen.queryByText(/Replied to/)).toBeNull()
    const summaries = summaryText(container)

    expect(summaries.some(text => text.includes('Third review passed.'))).toBe(true)
    expect(summaries.some(text => text.includes('Wrong block.'))).toBe(false)
  })

  it("shows the block's first sentence when the block has no Gist line", async () => {
    const { container } = render(
      <Harness
        messages={[
          user('u1', frame('reply requested')),
          assistant('a1', `[REPLY ${MESSAGE_ID}]All green. More detail later.[/REPLY]`, false)
        ]}
      />
    )

    expect(await screen.findByText('All green.')).toBeTruthy()
    expect(screen.getByText('show message')).toBeTruthy()
    expect(screen.queryByText('show reply')).toBeNull()
    expect(summaryText(container).some(text => text.includes('All green.'))).toBe(true)
  })

  it("shows the last text part's first sentence when there is no matching block", async () => {
    const { container } = render(
      <Harness
        messages={[
          user('u1', frame('reply requested')),
          assistantContent('a1', [
            { type: 'reasoning', text: 'Thinking about the old plan entirely.' },
            { type: 'text', text: 'I will look first. Not this.' },
            { type: 'text', text: 'The build is green. Extra follows.' }
          ])
        ]}
      />
    )

    expect(await screen.findByText('The build is green.')).toBeTruthy()
    const summaries = summaryText(container)

    expect(summaries.some(text => text.includes('The build is green.'))).toBe(true)
    expect(summaries.some(text => text.includes('I will look first'))).toBe(false)
    expect(summaries.some(text => text.includes('Thinking about the old plan'))).toBe(false)
  })

  it('shows No reply for a silent block and for an empty reply', async () => {
    const { unmount } = render(
      <Harness
        messages={[
          user('u1', frame('reply requested')),
          assistant('a1', `[REPLY ${MESSAGE_ID}][SILENT][/REPLY]`, false)
        ]}
      />
    )

    expect(await screen.findByText('No reply')).toBeTruthy()
    expect(screen.queryByText('show reply')).toBeNull()
    unmount()

    render(<Harness messages={[user('u1', frame('reply requested')), assistant('a1', '', false)]} />)

    expect(await screen.findByText('No reply')).toBeTruthy()
    expect(screen.queryByText('show reply')).toBeNull()
  })

  it('leaves the row after a no reply needed frame unchanged', async () => {
    const { container } = render(
      <Harness
        messages={[
          user('u1', frame('no reply needed')),
          assistant('a1', 'The build is green. I wrote this anyway.', false)
        ]}
      />
    )

    expect(await screen.findByText(/Replied to/)).toBeTruthy()
    expect(screen.getByText('show reply')).toBeTruthy()
    expect(screen.getByText('show message')).toBeTruthy()
    expect(summaryText(container).some(text => text.includes('The build is green'))).toBe(false)
  })

  it('leaves the row after an ask frame unchanged', async () => {
    const { container } = render(
      <Harness
        messages={[
          user(
            'u1',
            'Message from 📡 bob (@bob):\n📡 Not Sam · sender paused: use intercom reply · hermes@bob says (session local-1 · message abcd1234):\nIs the window still 22:00?'
          ),
          assistant('a1', 'Yes, 22:00 still holds. I checked the calendar.', false)
        ]}
      />
    )

    expect(await screen.findByText(/Replied to/)).toBeTruthy()
    expect(screen.getByText('show reply')).toBeTruthy()
    expect(summaryText(container).some(text => text.includes('Yes, 22:00 still holds'))).toBe(false)
  })

  it("keeps today's reply row for a bot message whose body starts with a curly quote", async () => {
    render(
      <Harness
        messages={[
          user('u1', 'Message from 🤖 Hermes (@hermes): “Hi” she said the build failed'),
          assistant('a1', 'The build is green. I checked.', false)
        ]}
      />
    )

    expect(await screen.findByText(/Replied to/)).toBeTruthy()
    expect(screen.getByText('show reply')).toBeTruthy()
    expect(screen.queryByText('▸')).toBeNull()
  })

  it('does not collapse a streaming reply to an intercom frame', async () => {
    render(
      <Harness
        messages={[user('u1', frame('reply requested', 'Check the build')), assistant('a1', 'working on it', true)]}
      />
    )

    await screen.findByText('working on it')
    expect(screen.queryByText('show reply')).toBeNull()
    expect(screen.queryByText('Replied')).toBeNull()
  })
})
