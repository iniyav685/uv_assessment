import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/client'
import type {
  AssessmentOutcome,
  Lookups,
  Paginated,
  TicketDetail,
  TicketListItem,
  UserSummary,
} from '../../api/types'
import type { TicketListParams } from './useTicketListParams'

export const ticketKeys = {
  all: ['tickets'] as const,
  lists: () => [...ticketKeys.all, 'list'] as const,
  list: (params: TicketListParams) => [...ticketKeys.lists(), params] as const,
  counts: (params: Omit<TicketListParams, 'tab' | 'page'>) =>
    [...ticketKeys.all, 'counts', params] as const,
  detail: (id: number) => [...ticketKeys.all, 'detail', id] as const,
}

/** Converts UI params into the API's query string (CSV for multi-value filters). */
export function toQuery(params: Partial<TicketListParams>) {
  const q: Record<string, string | number> = {}
  if (params.tab) q.tab = params.tab
  if (params.page && params.page > 1) q.page = params.page
  if (params.search) q.search = params.search
  if (params.ordering && params.ordering !== '-created_at') q.ordering = params.ordering
  for (const key of ['client', 'department', 'facility_manager', 'status'] as const) {
    const values = params[key]
    if (values && values.length) q[key] = values.join(',')
  }
  return q
}

// --- Queries ---------------------------------------------------------------

export function useTickets(params: TicketListParams) {
  return useQuery({
    queryKey: ticketKeys.list(params),
    queryFn: () =>
      api
        .get<Paginated<TicketListItem>>('/tickets/', { params: toQuery(params) }),
    // Keep showing the current page while the next one loads — no flashing skeletons.
    placeholderData: keepPreviousData,
  })
}

export function useTicketCounts(params: TicketListParams) {
  const { tab: _tab, page: _page, ...filters } = params
  return useQuery({
    queryKey: ticketKeys.counts(filters),
    queryFn: () =>
      api
        .get<{ open: number; closed: number }>('/tickets/counts/', { params: toQuery(filters) }),
    placeholderData: keepPreviousData,
  })
}

export function useTicket(id: number) {
  return useQuery({
    queryKey: ticketKeys.detail(id),
    queryFn: () => api.get<TicketDetail>(`/tickets/${id}/`),
    enabled: Number.isInteger(id),
  })
}

export function useLookups() {
  return useQuery({
    queryKey: ['lookups'],
    queryFn: () => api.get<Lookups>('/lookups/'),
    staleTime: 10 * 60_000,
  })
}

export function useAssignableUsers(ticketId: number, search: string, enabled: boolean) {
  return useQuery({
    queryKey: [...ticketKeys.detail(ticketId), 'assignable-users', search],
    queryFn: ({ signal }) =>
      api.get<{ results: UserSummary[]; current_id: number | null }>(
        `/tickets/${ticketId}/assignable-users/`,
        { params: { search: search || undefined }, signal },
      ),
    enabled,
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  })
}

// --- Mutations -------------------------------------------------------------

export interface CreateTicketPayload {
  client_office_id?: number
  title: string
  /** Issue tags; the first one decides the department. */
  issue_type_ids: number[]
  floor_ids: number[]
  description: string
}

export function useCreateTicket() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: CreateTicketPayload) => api.post<TicketDetail>('/tickets/', payload),
    onSuccess: (ticket) => {
      qc.setQueryData(ticketKeys.detail(ticket.id), ticket)
      qc.invalidateQueries({ queryKey: ticketKeys.lists() })
      qc.invalidateQueries({ queryKey: [...ticketKeys.all, 'counts'] })
    },
  })
}

type ActionPayloads = {
  'forward-to-department': { department_id: number; note: string }
  'assign-worker': { technician_id: number }
  'change-department': { department_id: number; note: string }
  'submit-assessment': { outcome: AssessmentOutcome; comment: string }
  close: { note?: string }
  'mark-resolved': Record<string, never>
  comments: { body: string; attachment_ids: string[] }
  description: { description: string }
}

export type ActionResponse = TicketDetail | { id: number; visible: false }

export function useTicketAction<A extends keyof ActionPayloads>(ticketId: number, action: A) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: ActionPayloads[A]) =>
      api.post<ActionResponse>(`/tickets/${ticketId}/${action}/`, payload),
    onSuccess: (data) => {
      // The response is the fresh ticket: write it to the cache instead of refetching.
      if ('number' in data) qc.setQueryData(ticketKeys.detail(ticketId), data)
      else qc.removeQueries({ queryKey: ticketKeys.detail(ticketId) })
      qc.invalidateQueries({ queryKey: ticketKeys.lists() })
      qc.invalidateQueries({ queryKey: [...ticketKeys.all, 'counts'] })
      // setQueryData above only touches the exact detail key — the assignable-users
      // list is cached under a longer key (department-scoped) and must be invalidated
      // explicitly, otherwise a change-department action leaves stale, wrong-department
      // technicians in the picker for up to its staleTime.
      qc.invalidateQueries({ queryKey: [...ticketKeys.detail(ticketId), 'assignable-users'] })
    },
  })
}
