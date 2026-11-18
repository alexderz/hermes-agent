import { describe, expect, it } from 'vitest'

import { firstSentence, inboundGist, inboundMessageId, replyGist, showReplyGist } from './agent-gist'

const ID = 'abcd1234'
const HEADER = `📡 Not Sam · reply requested · hermes@bob says (session local-1 · message ${ID}):`

describe('inboundGist', () => {
  it('reads a quoted gist when the next line is the frame header', () => {
    expect(inboundGist(`“Third review round passed.”\n${HEADER}\nWhich month did the format change?`)).toEqual({
      gist: 'Third review round passed.',
      body: `${HEADER}\nWhich month did the format change?`
    })
  })

  it('ignores an old frame whose body starts at the header', () => {
    expect(inboundGist(`${HEADER}\nWhich month did the format change?`)).toBeNull()
  })

  it('ignores a frame whose first line is not a quoted gist', () => {
    expect(inboundGist(`Hello there.\n${HEADER}\nWhich month?`)).toBeNull()
    expect(inboundGist(`"Hello there."\n${HEADER}`)).toBeNull()
  })

  it('ignores a quoted line when the next line is not a frame header', () => {
    expect(inboundGist('“Hi” she said the build failed')).toBeNull()
    expect(inboundGist('“Hi”')).toBeNull()
    expect(inboundGist(`“Hi” she said\n${HEADER}`)).toBeNull()
  })

  it('ignores a blank quoted line', () => {
    expect(inboundGist(`“   ”\n${HEADER}`)).toBeNull()
  })
})

describe('inboundMessageId', () => {
  it('reads the id from the header, including when a gist line precedes it', () => {
    expect(inboundMessageId(`“Ready.”\n${HEADER}\nbody`)).toBe(ID)
    expect(inboundMessageId(`${HEADER}\nbody`)).toBe(ID)
  })

  it('uses the message id at the end of the header, not a reply-to id', () => {
    const header =
      '📡 Not Sam · reply optional · hermes@bob says (session local-1 · reply to your message 11111111 · message abcd1234):'

    expect(inboundMessageId(header)).toBe(ID)
  })

  it('returns null without an 8-hex frame header', () => {
    expect(inboundMessageId('please check the build')).toBeNull()
    expect(inboundMessageId('📡 Not Sam · reply requested · hermes@bob says (message 3f2a9c):')).toBeNull()
  })
})

describe('showReplyGist', () => {
  it('is true for a frame that can carry a reply', () => {
    expect(showReplyGist(HEADER)).toBe(true)
    expect(
      showReplyGist(
        '📡 Not Sam · interrupt asked · reply requested · hermes@bob says (session local-1 · message abcd1234):'
      )
    ).toBe(true)
  })

  it("keeps today's row when nothing is sent back, for an ask, and for a bot message", () => {
    expect(showReplyGist('📡 Not Sam · no reply needed · hermes@script nightly says (message abcd1234):')).toBe(false)
    expect(
      showReplyGist(
        '📡 Not Sam · sender paused: use intercom reply · hermes@bob says (session local-1 · message abcd1234):'
      )
    ).toBe(false)
    expect(showReplyGist('please check the build')).toBe(false)
    expect(showReplyGist('“Hi” she said the build failed')).toBe(false)
  })
})

describe('firstSentence', () => {
  it('cuts at the first sentence end and keeps abbreviations intact', () => {
    expect(firstSentence('All green. More detail.')).toBe('All green.')
    expect(firstSentence('Ready? Ship it.')).toBe('Ready?')
    expect(firstSentence('See e.g. the note. Then stop.')).toBe('See e.g. the note.')
    expect(firstSentence('See i.e. the note. Then stop.')).toBe('See i.e. the note.')
    expect(firstSentence('See etc. the note. Then stop.')).toBe('See etc. the note.')
    expect(firstSentence('Wrote 3.2 GB. Done.')).toBe('Wrote 3.2 GB.')
  })

  it('uses the whole first line when nothing ends the sentence', () => {
    expect(firstSentence('no sentence end\nsecond line.')).toBe('no sentence end')
  })

  it('returns empty for blank text', () => {
    expect(firstSentence('  \n  ')).toBe('')
  })
})

describe('replyGist', () => {
  it("uses the matching block's Gist line and not another block's", () => {
    const parts = [
      `[REPLY 11111111]\nGist: Wrong block.\nNo.\n[/REPLY]\n[REPLY ${ID}]\nGist: Third review passed.\nAll green.\n[/REPLY]`
    ]

    expect(replyGist(parts, ID)).toBe('Third review passed.')
  })

  it("falls back to the matching block's first sentence", () => {
    const parts = [`[REPLY 11111111]\nGist: Wrong.\nNo.\n[/REPLY]\n[REPLY ${ID}]All green. More detail.[/REPLY]`]

    expect(replyGist(parts, ID)).toBe('All green.')
  })

  it('falls back to the last text part when there is no matching block', () => {
    const parts = [
      { type: 'reasoning', text: 'Thinking about the old plan entirely.' },
      { type: 'text', text: 'I will look first. Not this.' },
      { type: 'tool-call', toolName: 'x' },
      { type: 'text', text: 'The build is green. Extra follows.' }
    ]

    expect(replyGist(parts, ID)).toBe('The build is green.')
    expect(replyGist(parts, null)).toBe('The build is green.')
  })

  it('says No reply for silence or an empty body, including a Gist line with nothing after it', () => {
    expect(replyGist([`Looking.\n[REPLY ${ID}][SILENT][/REPLY]`], ID)).toBe('No reply')
    expect(replyGist([`[REPLY ${ID}]\n[/REPLY]`], ID)).toBe('No reply')
    expect(replyGist([`[REPLY ${ID}]\nGist: Nothing new.\n[SILENT]\n[/REPLY]`], ID)).toBe('No reply')
    expect(replyGist([`[REPLY ${ID}]\nGist: Nothing new.\n[/REPLY]`], ID)).toBe('No reply')
    expect(replyGist(['[SILENT]'], null)).toBe('No reply')
    expect(replyGist([], null)).toBe('No reply')
  })

  it('takes a leading Gist line off a no-block reply before the silence check', () => {
    expect(replyGist(['Gist: Ready to merge.\nThe third review passed. Ship it.'], null)).toBe('Ready to merge.')
    expect(replyGist(['  Gist: Ready to merge.\nThe third review passed.'], null)).toBe('Ready to merge.')
  })

  it('does not treat a lowercase gist line as a gist', () => {
    expect(replyGist([`[REPLY ${ID}]gist: not a label. The build passed.[/REPLY]`], ID)).toBe('gist: not a label.')
  })
})
