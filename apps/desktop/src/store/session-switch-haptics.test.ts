import { beforeEach, expect, it, vi } from 'vitest'

beforeEach(() => {
  localStorage.clear()
  vi.resetModules()
})

it('defaults session-switch haptics on and persists the choice independently of global mute', async () => {
  const prefs = await import('./haptics')
  expect(prefs.$sessionSwitchHaptics.get()).toBe(true)
  prefs.setSessionSwitchHaptics(false)
  expect(localStorage.getItem('hermes.desktop.sessionSwitchHaptics')).toBe('false')
  prefs.setHapticsMuted(true)
  prefs.setHapticsMuted(false)
  expect(prefs.$sessionSwitchHaptics.get()).toBe(false)
  vi.resetModules()
  const reloaded = await import('./haptics')
  expect(reloaded.$sessionSwitchHaptics.get()).toBe(false)
  reloaded.setSessionSwitchHaptics(true)
  expect(reloaded.$hapticsMuted.get()).toBe(false)
})

it('adopts another window’s session-switch choice without changing global mute', async () => {
  const prefs = await import('./haptics')
  prefs.setHapticsMuted(true)
  localStorage.setItem('hermes.desktop.sessionSwitchHaptics', 'false')
  window.dispatchEvent(new StorageEvent('storage', { key: 'hermes.desktop.sessionSwitchHaptics' }))
  expect(prefs.$sessionSwitchHaptics.get()).toBe(false)
  expect(prefs.$hapticsMuted.get()).toBe(true)
  localStorage.removeItem('hermes.desktop.sessionSwitchHaptics')
  window.dispatchEvent(new StorageEvent('storage', { key: 'hermes.desktop.sessionSwitchHaptics' }))
  expect(prefs.$sessionSwitchHaptics.get()).toBe(true)
})
