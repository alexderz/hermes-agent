import { afterEach, describe, expect, it, vi } from 'vitest'

import { startPointerDrag } from './pointer-drag'

const event = (type: string) => new Event(type) as PointerEvent

afterEach(() => vi.restoreAllMocks())

describe('pointer drag', () => {
  it('cancels without committing and removes all listeners', () => {
    const move = vi.fn()
    const end = vi.fn()
    const cancel = vi.fn()
    const remove = vi.spyOn(window, 'removeEventListener')

    startPointerDrag(move, end, cancel)
    window.dispatchEvent(event('pointermove'))
    window.dispatchEvent(event('pointercancel'))
    window.dispatchEvent(event('pointermove'))
    window.dispatchEvent(event('pointerup'))
    window.dispatchEvent(event('pointercancel'))

    expect(move).toHaveBeenCalledTimes(1)
    expect(end).not.toHaveBeenCalled()
    expect(cancel).toHaveBeenCalledTimes(1)
    expect(remove.mock.calls.map(call => call[0])).toEqual(
      expect.arrayContaining(['pointermove', 'pointerup', 'pointercancel'])
    )
  })

  it('commits on release and disposes without firing callbacks', () => {
    const end = vi.fn()
    const cancel = vi.fn()
    startPointerDrag(vi.fn(), end, cancel)
    window.dispatchEvent(event('pointerup'))
    window.dispatchEvent(event('pointercancel'))
    expect(end).toHaveBeenCalledTimes(1)
    expect(cancel).not.toHaveBeenCalled()

    const dispose = startPointerDrag(vi.fn(), end, cancel)
    dispose()
    window.dispatchEvent(event('pointerup'))
    window.dispatchEvent(event('pointercancel'))
    expect(end).toHaveBeenCalledTimes(1)
    expect(cancel).not.toHaveBeenCalled()
  })
})
