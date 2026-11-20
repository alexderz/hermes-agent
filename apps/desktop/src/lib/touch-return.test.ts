import { afterEach, expect, it } from 'vitest'

import { $touchPointer, isTouchNewline } from './touch-interaction'

const enter = { key: 'Enter', altKey: false, ctrlKey: false, metaKey: false }
afterEach(() => $touchPointer.set(false))

it('keeps plain Return native only on the touch layout and reads the current pointer state', () => {
  $touchPointer.set(false)
  expect(isTouchNewline(enter)).toBe(false)
  $touchPointer.set(true)
  expect(isTouchNewline(enter)).toBe(true)
  $touchPointer.set(false)
  expect(isTouchNewline(enter)).toBe(false)
})

it.each(['altKey', 'ctrlKey', 'metaKey'] as const)('preserves the explicit %s+Enter shortcut', modifier => {
  $touchPointer.set(true)
  expect(isTouchNewline({ ...enter, [modifier]: true })).toBe(false)
})

it('does not intercept other mobile keys', () => {
  $touchPointer.set(true)
  expect(isTouchNewline({ ...enter, key: 'Tab' })).toBe(false)
})
