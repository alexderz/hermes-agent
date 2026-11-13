import { APP_LINK_SCHEMES, externalUrlTarget } from '@hermes/shared'
import { describe, expect, it } from 'vitest'

import { appLinkSanitizeSchema } from './app-links'

describe('app link allow-list', () => {
  it('classifies allow-listed app schemes as app targets, untouched', () => {
    expect(APP_LINK_SCHEMES).toContain('t3code')
    expect(externalUrlTarget('t3code://threads/e/t/files/a%2Fb.md')).toEqual({
      kind: 'app',
      url: 't3code://threads/e/t/files/a%2Fb.md'
    })
  })

  it('keeps refusing script and unlisted schemes', () => {
    expect(externalUrlTarget('javascript:alert(1)')).toBeNull()
    expect(externalUrlTarget('data:text/html,x')).toBeNull()
    expect(externalUrlTarget('otherapp://x')).toBeNull()
    expect(externalUrlTarget('https://example.com')?.kind).toBe('web')
  })

  it('widens only the sanitizer href protocols, by exactly the allow-list', () => {
    const schema = { protocols: { href: ['http', 'https'], src: ['http'] }, tagNames: ['a'] }
    const out = appLinkSanitizeSchema(schema)

    expect(out.protocols.href).toEqual(['http', 'https', ...APP_LINK_SCHEMES])
    expect(out.protocols.src).toEqual(['http'])
    expect(out.tagNames).toEqual(['a'])
    expect(schema.protocols.href).toEqual(['http', 'https'])
  })
})
