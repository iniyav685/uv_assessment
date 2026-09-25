import { api } from '@/services/api'
import type {
  AssessmentOutcome,
  Paginated,
  TicketDetail,
  TicketListItem,
  UserSummary,
} from '@/api/types'

export interface TicketQuery {
  [key: string]: string | number | undefined
  tab?: string
  page?: number
  search?: string
  ordering?: string
  client?: string | number
  department?: string | number
  facility_manager?: string | number
  status?: string
}

export interface CreateTicketPayload {
  client_office_id?: number
  title: string
  /** Issue tags; the first one decides the department. */
  issue_type_ids: number[]
  floor_ids: number[]
  description: string
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

export type TicketAction = keyof ActionPayloads
export type TicketActionResponse = TicketDetail | { id: number; visible: false }

// --- GET ---------------------------------------------------------------

function getTickets(query: TicketQuery, signal?: AbortSignal) {
  return api.get<Paginated<TicketListItem>>('/tickets/', { params: query, signal })
}

function getTicketCounts(query: Omit<TicketQuery, 'tab' | 'page'>, signal?: AbortSignal) {
  return api.get<{ open: number; closed: number }>('/tickets/counts/', { params: query, signal })
}

function getTicket(id: number, signal?: AbortSignal) {
  return api.get<TicketDetail>(`/tickets/${id}/`, { signal })
}

function getAssignableUsers(ticketId: number, search: string, signal?: AbortSignal) {
  return api.get<{ results: UserSummary[]; current_id: number | null }>(
    `/tickets/${ticketId}/assignable-users/`,
    { params: { search: search || undefined }, signal },
  )
}

// --- POST ----------------------------------------------------------------

function createTicket(payload: CreateTicketPayload) {
  return api.post<TicketDetail>('/tickets/', payload)
}

function postTicketAction<A extends TicketAction>(
  ticketId: number,
  action: A,
  payload: ActionPayloads[A],
) {
  return api.post<TicketActionResponse>(`/tickets/${ticketId}/${action}/`, payload)
}

export const ticketService = {
  getTickets,
  getTicketCounts,
  getTicket,
  getAssignableUsers,
  createTicket,
  postTicketAction,
}
