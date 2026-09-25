import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router'
import type { TicketStatus } from '../../api/types'

export type Tab = 'open' | 'closed'
export type Ordering = '-created_at' | 'created_at'

export interface TicketListParams {
  tab: Tab
  page: number
  search: string
  ordering: Ordering
  client: number[]
  department: number[]
  facility_manager: number[]
  status: TicketStatus[]
}

export type FilterKey = 'client' | 'department' | 'facility_manager' | 'status'
export const FILTER_KEYS: FilterKey[] = ['client', 'department', 'facility_manager', 'status']

const ids = (raw: string | null) =>
  raw
    ? raw
        .split(',')
        .map(Number)
        .filter((n) => Number.isInteger(n) && n > 0)
    : []

/**
 * The URL is the single source of truth for list state: filters survive reloads,
 * are shareable, and back/forward work as expected.
 */
export function useTicketListParams() {
  const [searchParams, setSearchParams] = useSearchParams()

  const params = useMemo<TicketListParams>(() => {
    const page = Number(searchParams.get('page'))
    return {
      tab: searchParams.get('tab') === 'closed' ? 'closed' : 'open',
      page: Number.isInteger(page) && page > 0 ? page : 1,
      search: searchParams.get('search') ?? '',
      ordering: searchParams.get('ordering') === 'created_at' ? 'created_at' : '-created_at',
      client: ids(searchParams.get('client')),
      department: ids(searchParams.get('department')),
      facility_manager: ids(searchParams.get('facility_manager')),
      status: (searchParams.get('status')?.split(',').filter(Boolean) ?? []) as TicketStatus[],
    }
  }, [searchParams])

  /** Merge changes; any change other than the page itself resets to page 1. */
  const update = useCallback(
    (changes: Partial<TicketListParams>) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          for (const [key, value] of Object.entries(changes)) {
            const str = Array.isArray(value) ? value.join(',') : String(value ?? '')
            const isDefault =
              !str ||
              (key === 'tab' && str === 'open') ||
              (key === 'ordering' && str === '-created_at') ||
              (key === 'page' && str === '1')
            if (isDefault) next.delete(key)
            else next.set(key, str)
          }
          if (!('page' in changes)) next.delete('page')
          return next
        },
        { replace: true },
      )
    },
    [setSearchParams],
  )

  const activeFilterCount = FILTER_KEYS.reduce((n, k) => n + (params[k].length ? 1 : 0), 0)

  return { params, update, activeFilterCount }
}
