import { APP_LINK_SCHEMES } from '@hermes/shared'

/**
 * Chat links in allow-listed app schemes (`APP_LINK_SCHEMES`, e.g. `t3code://…`).
 *
 * GFM's autolink-literal only links `http(s)://`, `www.` and email, and the
 * Markdown sanitizer keeps only web schemes in `href`, so an app link an agent
 * writes rendered as plain text (bare) or as "[blocked]" (Markdown link). The
 * remark plugin below links bare app URLs; `appLinkSanitizeSchema` widens the
 * sanitizer's `href` protocols by exactly the allow-list. The click is opened by
 * the host through `externalUrlTarget` (kind `app`), which uses the same list.
 */

interface MdNode {
  children?: MdNode[]
  type: string
  url?: string
  value?: string
}

const SKIP = new Set(['link', 'linkReference', 'inlineCode', 'code', 'html', 'definition'])

function appLinkRe(): RegExp {
  const schemes = APP_LINK_SCHEMES.map(s => s.replace(/[^a-z0-9+.-]/gi, '')).join('|')

  // Trailing punctuation stays prose, like GFM's own autolinks.
  return new RegExp(`\\b(?:${schemes}):\\/\\/[^\\s<>"'\`]*[^\\s<>"'\`.,;:!?)\\]]`, 'gi')
}

function splitText(value: string): MdNode[] | null {
  const re = appLinkRe()
  const out: MdNode[] = []
  let last = 0
  let match: RegExpExecArray | null

  while ((match = re.exec(value)) !== null) {
    if (match.index > last) {
      out.push({ type: 'text', value: value.slice(last, match.index) })
    }

    out.push({ type: 'link', url: match[0], children: [{ type: 'text', value: match[0] }] })
    last = match.index + match[0].length
  }

  if (!out.length) {
    return null
  }

  if (last < value.length) {
    out.push({ type: 'text', value: value.slice(last) })
  }

  return out
}

function walk(node: MdNode): void {
  if (!node.children || SKIP.has(node.type)) {
    return
  }

  const next: MdNode[] = []

  for (const child of node.children) {
    if (child.type === 'text' && child.value) {
      const parts = splitText(child.value)

      if (parts) {
        next.push(...parts)

        continue
      }
    }

    walk(child)
    next.push(child)
  }

  node.children = next
}

/** remark plugin: link bare allow-listed app URLs in prose. */
export function remarkAppLinks() {
  return (tree: MdNode) => walk(tree)
}

interface SanitizeSchema {
  protocols?: Record<string, readonly string[] | undefined>
  [key: string]: unknown
}

/** The sanitizer schema with `href` also accepting the allow-listed app schemes. */
export function appLinkSanitizeSchema<T extends SanitizeSchema>(schema: T): T {
  const href = schema.protocols?.href ?? []

  return {
    ...schema,
    protocols: { ...schema.protocols, href: [...href, ...APP_LINK_SCHEMES.filter(s => !href.includes(s))] }
  }
}
