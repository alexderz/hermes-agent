import { atom } from 'nanostores'

import { persistStore } from '@/lib/persist-store'
import { persistBoolean, storedBoolean } from '@/lib/storage'

const HAPTICS_MUTED_STORAGE_KEY = 'hermes.desktop.hapticsMuted'
const SESSION_SWITCH_HAPTICS_STORAGE_KEY = 'hermes.desktop.sessionSwitchHaptics'

// Device-local, like the global mute; no session/profile data is persisted.
export const $sessionSwitchHaptics = atom(storedBoolean(SESSION_SWITCH_HAPTICS_STORAGE_KEY, true))
persistStore(
  $sessionSwitchHaptics,
  (enabled, options) => persistBoolean(SESSION_SWITCH_HAPTICS_STORAGE_KEY, enabled, options),
  true
)

export function setSessionSwitchHaptics(enabled: boolean) {
  $sessionSwitchHaptics.set(enabled)
}

export const $hapticsMuted = atom(storedBoolean(HAPTICS_MUTED_STORAGE_KEY, false))

persistStore($hapticsMuted, (muted, options) => persistBoolean(HAPTICS_MUTED_STORAGE_KEY, muted, options), false)

// Keep automatic cues quiet in every open window, not just the settings window.
if (typeof window !== 'undefined') {
  window.addEventListener('storage', event => {
    if (event.key === HAPTICS_MUTED_STORAGE_KEY) {
      $hapticsMuted.set(storedBoolean(HAPTICS_MUTED_STORAGE_KEY, false))
    }

    if (event.key === SESSION_SWITCH_HAPTICS_STORAGE_KEY) {
      $sessionSwitchHaptics.set(storedBoolean(SESSION_SWITCH_HAPTICS_STORAGE_KEY, true))
    }
  })
}

export function setHapticsMuted(muted: boolean) {
  $hapticsMuted.set(muted)
}

export function toggleHapticsMuted() {
  $hapticsMuted.set(!$hapticsMuted.get())
}
