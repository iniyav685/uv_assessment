import type { Lookups, Me, TicketDetail, TicketListItem, UserSummary } from '../api/types'

export const poc: UserSummary = {
  id: 4,
  full_name: 'Dhananjaya Murthy',
  title: 'Technical Manager',
  role: 'department_poc',
  display_name: 'Dhananjaya Murthy (Technical Manager)',
  initials: 'DM',
}

export const client: UserSummary = {
  id: 14,
  full_name: 'Chaitanya M',
  title: 'Client POC',
  role: 'client_poc',
  display_name: 'Chaitanya M (Client POC)',
  initials: 'CM',
}

export function makeMe(overrides: Partial<Me> = {}): Me {
  return {
    ...client,
    username: 'client.acme',
    email: 'client.acme@example.com',
    role_label: 'Client POC',
    department_id: null,
    can_create_ticket: true,
    ...overrides,
  }
}

export function makeTicket(overrides: Partial<TicketListItem> = {}): TicketListItem {
  return {
    id: 42,
    number: 'TKT-1042',
    title: 'AC not cooling',
    status: 'pending_technician_assignment',
    status_label: 'Pending Technician Assignment',
    location: 'Harness-1317; 2F, 3F',
    area: { id: 1, name: 'Bengaluru – Koramangala' },
    tags: [{ id: 1, name: 'AC not cooling', primary: true }],
    client: { id: 1, name: 'Acme Corp' },
    department: { id: 1, name: 'Technical' },
    facility_manager: null,
    created_by: client,
    created_at: '2025-10-27T11:40:00Z',
    assignees: [poc],
    action_required: false,
    ...overrides,
  }
}

export function makeDetail(overrides: Partial<TicketDetail> = {}): TicketDetail {
  return {
    ...makeTicket(),
    description: 'The AC units are blowing warm air.',
    office: { id: 1, label: 'Harness-1317' },
    floors: [],
    department_poc: poc,
    technician: null,
    assessment_outcome: '',
    assessment_outcome_label: '',
    closed_at: null,
    available_actions: ['comment'],
    activities: [],
    ...overrides,
  }
}

export const lookups: Lookups = {
  statuses: [{ value: 'pending_technician_assignment', label: 'Pending Technician Assignment' }],
  departments: [
    { id: 1, name: 'Technical' },
    { id: 2, name: 'IT' },
  ],
  clients: [{ id: 1, name: 'Acme Corp' }],
  facility_managers: [],
  issue_types: [{ id: 1, name: 'AC not cooling', department_id: 1, is_quick: true }],
  offices: [],
  technicians: [
    {
      id: 8,
      full_name: 'Prakash Kumar',
      title: 'Technician',
      role: 'technician',
      display_name: 'Prakash Kumar (Technician)',
      initials: 'PK',
      department_id: 1,
    },
  ],
  department_pocs: [],
}
