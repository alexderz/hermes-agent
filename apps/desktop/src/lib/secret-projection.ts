import type { ChatMessage, ChatMessagePart } from '@/lib/chat-messages'
import type { SecretRequest } from '@/store/prompts'

interface Anchor {
  messageId: string
  toolCallId: string
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

/** Bind once, not on each streaming delta. No secret input ever enters this projection. */
export function projectSecret(messages: ChatMessage[], request: SecretRequest, source = messages): ChatMessage[] {
  const key = keyOf(request)
  let anchor = anchors.get(key)
  if (!anchor) {
    for (let i = source.length - 1; i >= 0 && !anchor; i -= 1) {
      const message = source[i]
      const part = [...message.parts].reverse().find(item => matchesSecret(item, request))
      if (part?.type === 'tool-call' && part.toolCallId) {
        anchor = { messageId: message.id, toolCallId: part.toolCallId, synthetic: false }
      }
    }
    if (!anchor) {
      const lastUser = source.findLastIndex(item => item.role === 'user' && (!item.id.startsWith('user-queued-') || item.queuedTurnStarted))
      const message = source.slice(lastUser + 1).findLast(item => item.role === 'assistant')
      anchor = message
        ? { messageId: message.id, toolCallId: `secret:${request.requestId}`, synthetic: true }
        : { messageId: `secret-message:${request.requestId}`, toolCallId: `secret:${request.requestId}`, synthetic: true, newMessage: true, afterId: source[lastUser]?.id ?? null }
    }
    anchors.set(key, anchor)
  }
  const target = anchor
  if (target.newMessage) {
    const at = target.afterId ? messages.findIndex(message => message.id === target.afterId) : -1
    if (target.afterId && at < 0) {
      return messages
    }
    const part = { type: 'tool-call' as const, toolName: 'clarify', toolCallId: target.toolCallId, args: {}, argsText: '{}', clarifyRequestId: request.requestId }
    const row: ChatMessage = { id: target.messageId, role: 'assistant', pending: true, parts: [part] }
    return [...messages.slice(0, at + 1), row, ...messages.slice(at + 1)]
  }
  const index = messages.findIndex(message => message.id === target.messageId)
  if (index < 0) {
    return messages
  }
  const message = messages[index]
  const parts = target.synthetic
    ? [...message.parts, { type: 'tool-call' as const, toolName: 'clarify', toolCallId: target.toolCallId, args: {}, argsText: '{}', clarifyRequestId: request.requestId }]
    : message.parts.map(part => part.type === 'tool-call' && part.toolCallId === target.toolCallId
      ? { ...part, clarifyRequestId: request.requestId } : part)
  const next = [...messages]
  next[index] = { ...message, parts }
  return next
}
