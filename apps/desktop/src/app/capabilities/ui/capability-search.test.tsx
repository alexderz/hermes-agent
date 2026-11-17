import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { CapabilitySearch } from './capability-search'

afterEach(cleanup)

describe('capability search with management actions', () => {
  it('keeps scoped search and clear independent of management actions', () => {
    const action = vi.fn()
    function Harness() {
      const [query, setQuery] = useState('')
      return (
        <CapabilitySearch
          actions={<button onClick={action}>Install from Git</button>}
          hints={['Try memory']}
          onChange={setQuery}
          placeholder="Search plugins"
          scope="Plugins"
          value={query}
        />
      )
    }
    render(<Harness />)
    const input = screen.getByRole<HTMLInputElement>('textbox', { name: 'Search plugins' })
    expect(screen.getByText('Plugins')).toBeTruthy()
    fireEvent.change(input, { target: { value: 'memory' } })
    expect(input.value).toBe('memory')
    fireEvent.click(screen.getByRole('button', { name: 'Install from Git' }))
    expect(action).toHaveBeenCalledOnce()
    expect(input.value).toBe('memory')
    fireEvent.click(screen.getByRole('button', { name: 'Clear search' }))
    expect(input.value).toBe('')
    expect(action).toHaveBeenCalledOnce()
  })

  it('supports search without an action toolbar', () => {
    const onChange = vi.fn()
    render(<CapabilitySearch onChange={onChange} placeholder="Search tools" scope="Tools" value="" />)
    fireEvent.change(screen.getByRole('textbox', { name: 'Search tools' }), { target: { value: 'files' } })
    expect(onChange).toHaveBeenCalledExactlyOnceWith('files')
    expect(screen.queryByRole('button')).toBeNull()
  })
})
