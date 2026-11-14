import { createContext } from 'react'

import type { SecretRequest } from '@/store/prompts'

// Undefined means an isolated tool test without a runtime boundary.
export const SecretRequestContext = createContext<SecretRequest | null | undefined>(undefined)
