import { beforeEach, expect, it, vi } from 'vitest'

beforeEach(() => {
  localStorage.clear()
  vi.resetModules()
})

it('defaults off and persists across reloads independently of haptics', async () => {
  const visual = await import('./session-switch-visual')
  const haptics = await import('./haptics')
  expect(visual.$sessionSwitchVisual.get()).toBe(false)
  visual.setSessionSwitchVisual(true)
  haptics.setSessionSwitchHaptics(false)
  haptics.setHapticsMuted(true)
  expect(localStorage.getItem('hermes.desktop.sessionSwitchVisual')).toBe('true')
  vi.resetModules()
  const reloaded = await import('./session-switch-visual')
  expect(reloaded.$sessionSwitchVisual.get()).toBe(true)
})

it('adopts another window’s choice and removal', async () => {
  const visual = await import('./session-switch-visual')
  localStorage.setItem('hermes.desktop.sessionSwitchVisual', 'true')
  window.dispatchEvent(new StorageEvent('storage', { key: 'hermes.desktop.sessionSwitchVisual' }))
  expect(visual.$sessionSwitchVisual.get()).toBe(true)
  localStorage.removeItem('hermes.desktop.sessionSwitchVisual')
  window.dispatchEvent(new StorageEvent('storage', { key: 'hermes.desktop.sessionSwitchVisual' }))
  expect(visual.$sessionSwitchVisual.get()).toBe(false)
})
