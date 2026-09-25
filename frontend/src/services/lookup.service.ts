import { api } from '@/services/api'
import type { Lookups } from '@/api/types'

// --- GET ---------------------------------------------------------------

function getLookups() {
  return api.get<Lookups>('/lookups/')
}

export const lookupService = {
  getLookups,
}
