import { type ChatMessage, type ChatMessagePart, chatMessageText } from '@/lib/chat-messages'
import type { SecretRequest } from '@/store/prompts'

interface RowIdentity {
  id: string
  rowId?: number
  userText?: string
}

interface Anchor {
  message: RowIdentity
  turn?: RowIdentity
  precedingTurn?: RowIdentity
  toolCallId: string
  hostToolCallId?: string
  synthetic: boolean
  afterId?: string | null
  newMessage?: boolean
}

const anchors = new Map<string, Anchor>()
const keyOf = (request: SecretRequest) => JSON.stringify([request.connectionId ?? '', request.profile ?? '', request.sessionId, request.requestId])

export function forgetSecretAnchor(request: SecretRequest) {
  anchors.delete(keyOf(request))
}

function matchesSecret(part: ChatMessagePart, request: SecretRequest): boolean {
  if (part.type !== 'tool-call' || part.toolName !== 'clarify' || part.result !== undefined) {
    return false
  }

  const args = part.args ?? {}

  if (args.secret_env === request.envVar) {
    return true
  }

  const file = args.secret_file

  return typeof file === 'object' && file !== null && 'name' in file && file.name === request.envVar
}

const isStartedUser = (message: ChatMessage) =>
  message.role === 'user' && (!message.id.startsWith('user-queued-') || message.queuedTurnStarted)

const identityOf = (message: ChatMessage): RowIdentity => ({
  id: message.id,
  rowId: message.rowId,
  ...(message.role === 'user' ? { userText: chatMessageText(message) } : {})
})

function sameRow(message: ChatMessage, identity: RowIdentity): boolean {
  return identity.rowId !== undefined && message.rowId !== undefined
    ? message.rowId === identity.rowId : message.id === identity.id
}

function findTurn(source: ChatMessage[], turn?: RowIdentity, hostToolCallId?: string, precedingTurn?: RowIdentity): number {
  const hostIndex = hostToolCallId ? source.findIndex(message => message.parts.some(part =>
    part.type === 'tool-call' && part.toolCallId === hostToolCallId)) : -1

  if (hostIndex >= 0) {
    return source.slice(0, hostIndex).findLastIndex(isStartedUser)
  }

  if (!turn) {
    return source.findLastIndex(isStartedUser)
  }

  const exact = source.findIndex(message => isStartedUser(message) && sameRow(message, turn))

  if (exact >= 0) {
    return exact
  }

  if (turn.rowId !== undefined) {
    return -2
  }

  const precedingIndex = precedingTurn ? source.findIndex(message => isStartedUser(message) && sameRow(message, precedingTurn)) : -1

  if (precedingTurn && precedingIndex < 0) {
    return -2
  }

  // An unpersisted turn can gain a new durable identity, but rows already
  // preceding it cannot become it. Client/server clocks need not agree.
  const candidates = source.flatMap((message, index) => index > precedingIndex && isStartedUser(message) &&
    chatMessageText(message) === turn.userText ? [index] : [])

  return candidates.length === 1 ? candidates[0] : -2
}

function resolveAnchor(source: ChatMessage[], request: SecretRequest, previous?: Anchor): Anchor | undefined {
  const start = findTurn(source, previous?.turn, previous?.hostToolCallId, previous?.precedingTurn)

  if (start === -2) {
    return undefined
  }

  const nextUser = source.findIndex((message, index) => index > start && message.role === 'user')
  const turn = source.slice(start + 1, nextUser < 0 ? source.length : nextUser)
  const turnIdentity = start >= 0 ? identityOf(source[start]) : undefined
  const preceding = source.slice(0, Math.max(start, 0)).findLast(isStartedUser)
  const precedingTurn = preceding ? { id: preceding.id, rowId: preceding.rowId } : undefined
  const common = { turn: turnIdentity, precedingTurn, toolCallId: `secret:${request.requestId}`, synthetic: true }

  if (previous) {
    const host = turn.find(message => sameRow(message, previous.message) ||
      message.parts.some(part => part.type === 'tool-call' && part.toolCallId === previous.hostToolCallId))

    if (host) {
      return { ...previous, turn: turnIdentity, precedingTurn, message: identityOf(host) }
    }

    if (previous.newMessage && source[start]?.id === previous.afterId) {
      return { ...previous, turn: turnIdentity, precedingTurn }
    }
  }

  // Replay can precede the in-flight snapshot. Completed history alone cannot
  // identify this request's turn. Keep a request-local row until active rows
  // arrive. Established anchors above remain valid when a skill result settles.
  const hasLiveTurn = turn.some(message => message.pending && !message.interrupted)
    || (source[start]?.id.startsWith('user-') && !turn.length)

  if (!previous && !hasLiveTurn) {
    return undefined
  }

  for (const message of [...turn].reverse()) {
    const part = [...message.parts].reverse().find(item => matchesSecret(item, request))

    if (part?.type === 'tool-call' && part.toolCallId) {
      return { ...common, message: identityOf(message), toolCallId: part.toolCallId, hostToolCallId: part.toolCallId, synthetic: false }
    }
  }

  const message = turn.findLast(item => item.role === 'assistant')
  const hostPart = message?.parts.findLast(part => part.type === 'tool-call')

  return message
    ? { ...common, message: identityOf(message), hostToolCallId: hostPart?.type === 'tool-call' ? hostPart.toolCallId : undefined }
    : { ...common, message: { id: `secret-message:${request.requestId}` }, newMessage: true, afterId: source[start]?.id ?? null }
}

function fallback(messages: ChatMessage[], request: SecretRequest): ChatMessage[] {
  const queued = messages.findIndex(message => message.role === 'user' && !isStartedUser(message))
  const insertion = queued >= 0 ? queued : messages.length

  const row: ChatMessage = {
    id: `secret-message:${request.requestId}`,
    role: 'assistant',
    pending: true,
    parts: [{ type: 'tool-call', toolName: 'clarify', toolCallId: `secret:${request.requestId}`, args: {}, argsText: '{}', clarifyRequestId: request.requestId }]
  }

  return [...messages.slice(0, insertion), row, ...messages.slice(insertion)]
}

/** Keep the live host stable, but resolve its durable identity after hydration.
 * No secret input ever enters this projection. */
export function projectSecret(messages: ChatMessage[], request: SecretRequest, source = messages): ChatMessage[] {
  const key = keyOf(request)
  const target = resolveAnchor(source, request, anchors.get(key))

  if (!target) {
    return fallback(messages, request)
  }

  // Only resolved turn identities are retained; uncertain history uses the
  // request-local row without fixing its place in a stale turn.
  if (source.length) {
    anchors.set(key, target)
  }

  const secretPart: ChatMessagePart = { type: 'tool-call', toolName: 'clarify', toolCallId: target.toolCallId, args: {}, argsText: '{}', clarifyRequestId: request.requestId }

  if (target.newMessage) {
    const at = target.afterId ? messages.findIndex(message => message.id === target.afterId) : -1

    if (target.afterId && at < 0) {
      return fallback(messages, request)
    }

    const row: ChatMessage = { id: target.message.id, role: 'assistant', pending: true, parts: [secretPart] }

    return [...messages.slice(0, at + 1), row, ...messages.slice(at + 1)]
  }

  const index = messages.findIndex(message => message.id === target.message.id)

  if (index < 0) {
    return fallback(messages, request)
  }

  const message = messages[index]
  const hostIndex = message.parts.findIndex(part => part.type === 'tool-call' && part.toolCallId === target.hostToolCallId)
  const insertAt = hostIndex < 0 ? message.parts.length : hostIndex + 1

  const parts = target.synthetic
    ? [...message.parts.slice(0, insertAt), secretPart, ...message.parts.slice(insertAt)]
    : message.parts.map(part => part.type === 'tool-call' && part.toolCallId === target.toolCallId
      ? { ...part, clarifyRequestId: request.requestId } : part)

  const next = [...messages]
  next[index] = { ...message, parts }

  return next
}
