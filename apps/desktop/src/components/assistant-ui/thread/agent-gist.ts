// Folded-row gist text.
//
// Inbound: a gist is only the first line `“…”` when the next line is the
// frame header (`📡 Not …`). An old frame, a frame with no gist, and a bot
// message whose body starts with “ stay on today's row.
//
// Reply: the `[REPLY <id>]` block for that header's message id. Its `Gist:`
// line, else the block's first sentence, else the last text part's first
// sentence. Empty or `[SILENT]` after that line is removed is "No reply".
// An ask or a "no reply needed" frame keeps today's reply row.

import { partText } from '@/components/assistant-ui/thread/content'

const FRAME_HEADER_RE = /^📡 Not /u
const MESSAGE_ID_RE = /^📡 Not [^\n]*message ([0-9a-f]{8})\):$/u
const QUOTED_LINE_RE = /^“(.+)”$/u
const SENTENCE_END_RE = /(?<!\be\.g)(?<!\bi\.e)(?<!\betc)[.!?](?=\s|$)/u
const NO_REPLY_LABEL = ' · no reply needed · '
const ASK_LABEL = ' · sender paused: use intercom reply · '
const SILENT = '[SILENT]'

function headerLine(body: string): string | null {
  for (const line of body.split(/\r?\n/u)) {
    if (FRAME_HEADER_RE.test(line)) {
      return line.trim()
    }
  }

  return null
}

/** Quoted gist on an intercom notice, or null when the row should stay as it is. */
export function inboundGist(body: string): { body: string; gist: string } | null {
  const lines = body.split(/\r?\n/u)
  const match = QUOTED_LINE_RE.exec((lines[0] ?? '').trim())

  if (!match) {
    return null
  }

  const gist = match[1].trim()

  if (!gist || !FRAME_HEADER_RE.test(lines[1] ?? '')) {
    return null
  }

  return { gist, body: lines.slice(1).join('\n').trim() }
}

/** Message id from the frame header (`message <8 hex>):`), or null. */
export function inboundMessageId(body: string): string | null {
  const header = headerLine(body)

  return header ? (MESSAGE_ID_RE.exec(header)?.[1] ?? null) : null
}

/** True when the reply row should show a gist instead of today's "Replied to" row. */
export function showReplyGist(body: string): boolean {
  const header = headerLine(body)

  if (!header || header.includes(NO_REPLY_LABEL) || header.includes(ASK_LABEL)) {
    return false
  }

  return true
}

/** First sentence of `text`, or its first non-empty line when nothing ends one. */
export function firstSentence(text: string): string {
  const line = text
    .split(/\r?\n/u)
    .map(part => part.trim())
    .find(part => part.length > 0)

  if (!line) {
    return ''
  }

  const match = SENTENCE_END_RE.exec(line)

  return match ? line.slice(0, match.index + 1) : line
}

// The first non-empty line, and only when it starts `Gist:` (case-sensitive).
// What remains is checked for silence, so a gist with no answer is "No reply".
function splitGist(text: string): { body: string; gist: string } {
  const lines = text.split(/\r?\n/u)
  let index = 0

  while (index < lines.length && lines[index].trim() === '') {
    index += 1
  }

  if (index >= lines.length) {
    return { gist: '', body: '' }
  }

  const line = lines[index].trim()

  if (!line.startsWith('Gist:')) {
    return { gist: '', body: text.trim() }
  }

  return {
    gist: line.slice('Gist:'.length).trim(),
    body: lines
      .slice(index + 1)
      .join('\n')
      .trim()
  }
}

function isSilent(text: string): boolean {
  const lines = text
    .trim()
    .split(/\r?\n/u)
    .map(line => line.trim())
    .filter(line => line.length > 0)

  if (lines.length === 0) {
    return true
  }

  return lines[0].toUpperCase() === SILENT || lines[lines.length - 1].toUpperCase() === SILENT
}

function textParts(parts: unknown): string[] {
  const rows = typeof parts === 'string' ? [parts] : Array.isArray(parts) ? parts : []

  return rows.map(part => partText(part)).filter(part => part.trim().length > 0)
}

function replyBlock(text: string, id: string): string | null {
  if (!/^[0-9a-f]{8}$/u.test(id)) {
    return null
  }

  const match = new RegExp(`\\[REPLY ${id}\\]([\\s\\S]*?)\\[/REPLY\\]`).exec(text)

  return match ? match[1].trim() : null
}

/** Gist for a settled reply: the matching block, else the last text part. "No reply" when nothing was sent. */
export function replyGist(parts: unknown, id: string | null): string {
  const texts = textParts(parts)
  const block = id ? replyBlock(texts.join('\n'), id) : null
  const chosen = block !== null ? block : (texts.at(-1) ?? '')
  const { gist, body } = splitGist(chosen)

  if (isSilent(body)) {
    return 'No reply'
  }

  return gist || firstSentence(body)
}
