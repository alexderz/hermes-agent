import { atom } from 'nanostores'

import { persistStore } from '@/lib/persist-store'
import { persistBoolean, storedBoolean } from '@/lib/storage'

const STORAGE_KEY = 'hermes.desktop.sessionSwitchVisual'

export const $sessionSwitchVisual = atom(storedBoolean(STORAGE_KEY, false))
persistStore($sessionSwitchVisual, (enabled, options) => persistBoolean(STORAGE_KEY, enabled, options), false)

export function setSessionSwitchVisual(enabled: boolean) {
  $sessionSwitchVisual.set(enabled)
}

if (typeof window !== 'undefined') {
  window.addEventListener('storage', event => {
    if (event.key === STORAGE_KEY) {
      $sessionSwitchVisual.set(storedBoolean(STORAGE_KEY, false))
    }
  })
}
