import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { MarkdownTextContent } from './markdown-text'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const THREAD = 't3code://threads/env-1/thread-2'
const FILE = 't3code://threads/env-1/thread-2/files/docs%2Fplan.md'

// Allow-listed app schemes (APP_LINK_SCHEMES) become real links in chat, both
// bare and as Markdown links; every other non-web scheme stays blocked.
describe('MarkdownTextContent app-scheme links', () => {
  it('links a bare app URL and leaves trailing punctuation as prose', () => {
    render(<MarkdownTextContent isRunning={false} text={`Open ${THREAD}. Or the file ${FILE}`} />)
    const hrefs = screen.getAllByRole('link').map(l => l.getAttribute('href'))

    expect(hrefs).toEqual([THREAD, FILE])
  })

  it('keeps a Markdown link to an app URL instead of blocking it', () => {
    render(<MarkdownTextContent isRunning={false} text={`Open [the thread](${THREAD}).`} />)
    const link = screen.getByRole('link')

    expect(link.getAttribute('href')).toBe(THREAD)
    expect(link.textContent).toContain('the thread')
  })

  it('still blocks javascript: and unlisted schemes', () => {
    const { container } = render(
      <MarkdownTextContent isRunning={false} text={'[x](javascript:alert(1)) [y](otherapp://z) otherapp://bare'} />
    )

    expect(screen.queryAllByRole('link')).toHaveLength(0)
    expect(container.innerHTML).not.toContain('javascript:')
  })

  it('does not link an app URL inside inline code', () => {
    render(<MarkdownTextContent isRunning={false} text={`Run \`${THREAD}\` later.`} />)

    expect(screen.queryAllByRole('link')).toHaveLength(0)
  })

  it('hands a click to the host opener', () => {
    const openExternal = vi.fn()
    vi.stubGlobal('hermesDesktop', { openExternal })
    window.hermesDesktop = { openExternal } as unknown as typeof window.hermesDesktop
    render(<MarkdownTextContent isRunning={false} text={`Open ${THREAD}`} />)
    fireEvent.click(screen.getByRole('link'))

    expect(openExternal).toHaveBeenCalledWith(THREAD)
  })
})
