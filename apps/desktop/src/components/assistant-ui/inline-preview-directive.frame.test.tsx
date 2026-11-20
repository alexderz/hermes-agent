import { act, cleanup, fireEvent, render, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { InlinePreviewDirective } from './inline-preview-directive'

const original = window.hermesDesktop

// The frame reads its file through the desktop bridge, as it does in the app.
beforeEach(() => {
  window.hermesDesktop = {
    ...original,
    readFileText: async (path: string) => ({
      path,
      text: '<html><body><div style="width:300px">card</div></body></html>'
    })
  }
})

afterEach(() => {
  cleanup()
  window.hermesDesktop = original
})

async function mountFrame() {
  const { container } = render(<InlinePreviewDirective attrs={{ file: '/work/card.html' }} streaming={false} />)

  const iframe = await waitFor(() => {
    const node = container.querySelector('iframe')

    if (!node?.parentElement) {
      throw new Error('preview frame not mounted yet')
    }

    return node
  })

  const token = /var t="([^"]+)"/.exec(iframe.getAttribute('srcdoc') ?? '')?.[1]
  expect(token).toBeDefined()

  const report = (size: { height: number; vw?: number; width?: number }) =>
    act(() => {
      window.dispatchEvent(new MessageEvent('message', { data: { type: 'hermes-inline-preview-size', token, ...size } }))
    })

  return { box: iframe.parentElement, container, iframe, report }
}

describe('inline preview frame width and collapse', () => {
  it('shrink-wraps a fixed widget to its first width, capped at the column', async () => {
    const { box, container, report } = await mountFrame()

    await report({ height: 400, width: 300 })

    expect(box?.style.height).toBe('400px')
    expect(box?.style.width).toBe('300px')
    expect(box?.classList.contains('max-w-full')).toBe(true)
    expect(container.querySelector('.max-w-160')).not.toBeNull()
    expect(box?.parentElement?.style.maxWidth).toBe('')

    await report({ height: 400, width: 2000 })

    expect(box?.style.width).toBe('300px')
  })

  it('caps the first report when the content is wider than the column', async () => {
    const { box, report } = await mountFrame()

    await report({ height: 400, width: 900 })

    expect(box?.style.width).toBe('640px')
  })

  it('keeps a fluid page full-bleed inside the column instead of freezing a pixel width', async () => {
    const { box, container, report } = await mountFrame()

    await report({ height: 400, vw: 412, width: 412 })

    expect(box?.style.width).toBe('100%')
    expect(box?.style.height).toBe('400px')
    expect(container.querySelector('.max-w-160')).not.toBeNull()
    expect(box?.closest('[style*="max-width: 960px"]')).toBeNull()
  })

  it('collapses the frame without unmounting it, then expands it again', async () => {
    const { container, iframe, report } = await mountFrame()

    await report({ height: 400, width: 300 })

    const toggle = container.querySelector('[data-slot="inline-preview-toggle"]')
    expect(toggle?.getAttribute('aria-expanded')).toBe('true')
    expect(iframe.isConnected).toBe(true)

    fireEvent.click(toggle!)

    expect(toggle?.getAttribute('aria-expanded')).toBe('false')
    expect(iframe.parentElement?.parentElement?.hasAttribute('hidden')).toBe(true)
    expect(iframe.isConnected).toBe(true)
    expect(iframe.parentElement?.style.width).toBe('300px')

    fireEvent.click(toggle!)

    expect(toggle?.getAttribute('aria-expanded')).toBe('true')
    expect(iframe.parentElement?.parentElement?.hasAttribute('hidden')).toBe(false)
  })
})
