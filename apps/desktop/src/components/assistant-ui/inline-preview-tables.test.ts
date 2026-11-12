import { afterEach, describe, expect, it } from 'vitest'

import { INLINE_TABLE_SCRIPT_SOURCE, TABLE_PREVIEW_ROWS } from './inline-preview-tables'

function table(bodyRows: number, opts: { thead?: boolean; attrs?: string } = {}): string {
  const head = '<tr><th>Id</th><th>Tok/s</th></tr>'
  const rows = Array.from({ length: bodyRows }, (_, i) => `<tr><td>case-${i}</td><td>${i}</td></tr>`).join('')

  return opts.thead
    ? `<table ${opts.attrs ?? ''}><thead>${head}</thead><tbody>${rows}</tbody></table>`
    : `<table ${opts.attrs ?? ''}>${head}${rows}</table>`
}

function run(html: string): void {
  document.body.innerHTML = html
  // The same source the frame runs, executed against this document.
  new Function(INLINE_TABLE_SCRIPT_SOURCE)()
}

const visibleBodyRows = (t: HTMLTableElement) => [...t.rows].filter(r => r.cells[0]?.tagName === 'TD' && !r.hidden)

afterEach(() => {
  document.body.innerHTML = ''
  document.head.innerHTML = ''
})

describe('inline preview table enhancer', () => {
  it('wraps every table in its own horizontal scroller', () => {
    run(`<div class="wrap">${table(3)}</div>`)
    const t = document.querySelector('table')!

    expect(t.parentElement?.className).toBe('hx-table-scroll')
    expect(t.parentElement?.parentElement?.hasAttribute('data-hx-table')).toBe(true)
    expect(t.closest('.wrap')).not.toBeNull()
    // Short table: no buttons.
    expect(document.querySelector('[data-hx-toggle]')).toBeNull()
  })

  it('folds a long table to its first rows, keeps the header, and expands on demand', () => {
    run(table(300))
    const t = document.querySelector('table')!
    const more = document.querySelector<HTMLButtonElement>('[data-hx-more]')!

    expect(visibleBodyRows(t)).toHaveLength(TABLE_PREVIEW_ROWS)
    expect(t.rows[0].hidden).toBe(false)
    expect(more.textContent).toBe('Show all 300')

    more.click()
    expect(visibleBodyRows(t)).toHaveLength(300)
    expect(more.textContent).toBe(`Show first ${TABLE_PREVIEW_ROWS}`)
  })

  it('hides and shows the whole table', () => {
    run(table(30, { thead: true }))
    const toggle = document.querySelector<HTMLButtonElement>('[data-hx-toggle]')!
    const scroll = document.querySelector<HTMLElement>('.hx-table-scroll')!

    expect(toggle.textContent).toContain('30 rows')
    toggle.click()
    expect(scroll.hidden).toBe(true)
    expect(document.querySelector<HTMLButtonElement>('[data-hx-more]')!.hidden).toBe(true)
    toggle.click()
    expect(scroll.hidden).toBe(false)
  })

  it('wraps long cells in a tap-to-open clamp', () => {
    run(`<table><tr><th>Id</th><th>Note</th></tr><tr><td>a</td><td>${'word '.repeat(30)}</td></tr></table>`)
    const clamp = document.querySelector<HTMLElement>('td.hx-long > .hx-clamp')!

    expect(clamp.textContent).toContain('word word')
    expect(document.querySelectorAll('.hx-clamp')).toHaveLength(1)
    clamp.click()
    expect(clamp.classList.contains('hx-open')).toBe(true)
  })

  it('is idempotent and honours both opt-outs', () => {
    run(table(30) + table(30, { attrs: 'data-hx-skip' }))
    new Function(INLINE_TABLE_SCRIPT_SOURCE)()

    expect(document.querySelectorAll('[data-hx-table]')).toHaveLength(1)
    expect(document.querySelectorAll('[data-hx-toggle]')).toHaveLength(1)

    document.head.innerHTML = '<meta name="hermes-tables" content="native">'
    run(table(30))
    expect(document.querySelector('[data-hx-table]')).toBeNull()
  })
})
