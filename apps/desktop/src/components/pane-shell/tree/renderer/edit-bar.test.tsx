import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { $layoutEditMode } from '../../edit-mode'

import { TreeEditBar } from './edit-bar'

vi.mock('./layout-picker', () => ({ LayoutPicker: () => <div>Picker</div> }))

afterEach(() => {
  cleanup()
  $layoutEditMode.set(false)
})

describe('layout edit bar', () => {
  it('reserves touch on the real header while keeping actions operable', () => {
    $layoutEditMode.set(true)
    const { container } = render(<TreeEditBar />)
    const header = container.querySelector('header')!

    expect(header.style.touchAction).toBe('none')
    expect(screen.getByText('Picker')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /done/i }))
    expect($layoutEditMode.get()).toBe(false)
  })
})
