export interface Paginated<T> {
  count: number
  page: number
  page_size: number
  total_pages: number
  results: T[]
}

export type Role = 'client_poc' | 'facility_manager' | 'department_poc' | 'technician' | 'admin'

export interface UserSummary {
  id: number
  full_name: string
  title: string
  role: Role
  display_name: string
  initials: string
}

export interface Me extends UserSummary {
  username: string
  email: string
  role_label: string
  department_id: number | null
  can_create_ticket: boolean
}

export interface NamedRef {
  id: number
  name: string
}

export type TicketStatus =
  | 'pending_facility_manager_review'
  | 'pending_technician_assignment'
  | 'pending_technician_assessment'
  | 'pending_poc_review'
  | 'pending_blockage_resolution'
  | 'pending_client_confirmation'
  | 'resolved'
  | 'closed'

export type TicketAction =
  | 'forward_to_department'
  | 'assign_worker'
  | 'change_department'
  | 'submit_assessment'
  | 'close'
  | 'mark_resolved'
  | 'comment'
  | 'edit_description'

export type AssessmentOutcome = 'fully_resolved' | 'partially_resolved' | 'needs_reassignment'

export type ActivityKind =
  | 'created'
  | 'auto_assigned'
  | 'forwarded_to_department'
  | 'assigned_technician'
  | 'changed_department'
  | 'changed_status'
  | 'pending_client_confirmation'
  | 'resolved'
  | 'closed'
  | 'commented'
  | 'edited_description'

export interface IssueTag {
  id: number
  name: string
  primary: boolean
}

export interface TicketListItem {
  id: number
  number: string
  title: string
  status: TicketStatus
  status_label: string
  location: string
  /** Location (city – area) of the client office. */
  area: NamedRef
  /** Issue types as tags; the primary one decided the department. */
  tags: IssueTag[]
  client: NamedRef
  department: NamedRef
  facility_manager: UserSummary | null
  created_by: UserSummary
  created_at: string
  assignees: UserSummary[]
  action_required: boolean
}

export interface Activity {
  id: number
  kind: ActivityKind
  kind_label: string
  actor: UserSummary | null
  from_value: string
  to_value: string
  comment: TicketComment | null
  meta: { outcome?: AssessmentOutcome; outcome_label?: string; assignee_id?: number }
  is_comment: boolean
  created_at: string
}

export interface AttachmentItem {
  id: string
  name: string
  content_type: string
  size: number
  kind: 'image' | 'video' | 'file'
  /** Short-lived presigned URL; the bucket itself is private. */
  url: string
}

export interface TicketComment {
  id: number
  /** Server-sanitised HTML (sanitised again on render). */
  body_html: string
  body_text: string
  attachments: AttachmentItem[]
}

export interface TicketDetail extends TicketListItem {
  description: string
  office: { id: number; label: string }
  floors: { id: number; label: string }[]
  department_poc: UserSummary | null
  technician: UserSummary | null
  assessment_outcome: AssessmentOutcome | ''
  assessment_outcome_label: string
  closed_at: string | null
  available_actions: TicketAction[]
  activities: Activity[]
}

export interface OfficeOption {
  id: number
  label: string
  client: NamedRef
  floors: { id: number; label: string }[]
}

export interface IssueTypeOption {
  id: number
  name: string
  department_id: number
  is_quick: boolean
}

export interface Lookups {
  statuses: { value: TicketStatus; label: string }[]
  departments: NamedRef[]
  clients: NamedRef[]
  facility_managers: UserSummary[]
  issue_types: IssueTypeOption[]
  offices: OfficeOption[]
  technicians: (UserSummary & { department_id: number })[]
  department_pocs: (UserSummary & { department_id: number })[]
}

export interface NotificationItem {
  id: number
  ticket: number
  ticket_number: string
  message: string
  is_read: boolean
  created_at: string
}
