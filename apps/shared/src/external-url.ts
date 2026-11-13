/**
 * Which URLs Desktop hands to a browser when asked to open something
 * externally. Electron's `openExternalUrl` (shell.openExternal) and the
 * browser-hosted bridge (window.open) share this one rule, so an agent- or
 * tool-supplied `javascript:` or custom-scheme link is refused on both hosts.
 *
 * `file:` is its own kind: only a host with a local file opener may act on it.
 */

const WEB_PROTOCOLS = new Set(['http:', 'https:', 'mailto:'])

/**
 * Custom URL schemes registered by apps the operator uses, which a chat link may
 * hand to the OS (Android / desktop route them to the app). An explicit allow-list:
 * `javascript:`, `data:`, `vbscript:` and every unlisted scheme stay refused.
 * - `t3code`: the T3 Code app (`t3code://threads/<env>/<thread>[/files/<path>]`).
 */
export const APP_LINK_SCHEMES: readonly string[] = ['t3code']

const APP_PROTOCOLS = new Set(APP_LINK_SCHEMES.map(scheme => `${scheme}:`))

export interface ExternalUrlTarget {
  kind: 'app' | 'file' | 'web'
  /** `web`: the normalized URL. `file` / `app`: the trimmed input, left for the host to hand on. */
  url: string
}

/** Classify an external URL; null for empty, malformed or unsupported-scheme input. */
export function externalUrlTarget(rawUrl: string): ExternalUrlTarget | null {
  const raw = String(rawUrl || '').trim()

  if (!raw) {
    return null
  }

  let parsed: URL

  try {
    parsed = new URL(raw)
  } catch {
    return null
  }

  if (parsed.protocol === 'file:') {
    return { kind: 'file', url: raw }
  }

  if (APP_PROTOCOLS.has(parsed.protocol.toLowerCase())) {
    return { kind: 'app', url: raw }
  }

  return WEB_PROTOCOLS.has(parsed.protocol) ? { kind: 'web', url: parsed.toString() } : null
}
