import AssignmentInd from '@mui/icons-material/AssignmentIndOutlined'
import CheckCircle from '@mui/icons-material/CheckCircleOutlined'
import SwapHoriz from '@mui/icons-material/SwapHoriz'
import TaskAlt from '@mui/icons-material/TaskAlt'
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Collapse,
  FormControl,
  FormControlLabel,
  FormHelperText,
  FormLabel,
  MenuItem,
  Paper,
  Radio,
  RadioGroup,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { useState, type FormEvent, type ReactNode } from 'react'
import type { AssessmentOutcome, Lookups, TicketDetail } from '@/api/types'
import ConfirmDialog from '@/molecules/ConfirmDialog'
import { formatDateTime } from '@/utils/format'
import { describeActionError, NO_ERROR, type ActionErrorState } from '@/features/tickets/actionErrors'
import { useTicketAction, type ActionResponse } from '@/features/tickets/api'

interface Props {
  ticket: TicketDetail
  lookups: Lookups | undefined
  justCreated: boolean
  onLeftQueue: (message: string) => void
}

/** Whether `ActionPanel` will render anything for this ticket (a CTA, or the closed banner). */
export function ticketHasActionPanel(ticket: TicketDetail): boolean {
  const actions = new Set(ticket.available_actions)
  return (
    actions.has('forward_to_department') ||
    actions.has('change_department') ||
    actions.has('close') ||
    actions.has('submit_assessment') ||
    actions.has('mark_resolved') ||
    Boolean(ticket.closed_at)
  )
}

/**
 * Role-specific CTA panel. What renders is driven entirely by the server's
 * `available_actions`, so the UI can never offer an action the API would reject.
 */
export default function ActionPanel({ ticket, lookups, justCreated, onLeftQueue }: Props) {
  const actions = new Set(ticket.available_actions)
  // Reassigning during an assessment is done from the Assignee field in the sidebar;
  // the CTA panel only appears when the POC is the one who must act.
  const isFm = actions.has('forward_to_department')
  const isPoc = actions.has('change_department') || actions.has('close')
  const isTechnician = actions.has('submit_assessment')
  const canResolve = actions.has('mark_resolved')

  if (!isFm && !isPoc && !isTechnician && !canResolve) {
    if (ticket.closed_at) {
      return (
        <Alert severity="success" icon={<TaskAlt />}>
          This ticket was {ticket.status === 'resolved' ? 'marked resolved' : 'closed'} on{' '}
          {formatDateTime(ticket.closed_at)}.
        </Alert>
      )
    }
    return null // e.g. a department POC before the FM has forwarded it: visibility only, no CTA
  }

  return (
    <Stack spacing={1.5}>
      {isFm && <FacilityManagerActions ticket={ticket} lookups={lookups} />}
      {isPoc && <PocActions ticket={ticket} lookups={lookups} onLeftQueue={onLeftQueue} />}
      {isTechnician && <TechnicianActions ticket={ticket} onLeftQueue={onLeftQueue} />}
      {canResolve && <ResolveAction ticket={ticket} justCreated={justCreated} />}
    </Stack>
  )
}

// --- Facility Manager --------------------------------------------------------

function FacilityManagerActions({
  ticket,
  lookups,
}: {
  ticket: TicketDetail
  lookups: Lookups | undefined
}) {
  const [open, setOpen] = useState(false)

  return (
    <PanelShell message="A new ticket has come in. Forward it to the right department.">
      <Button
        variant={open ? 'contained' : 'outlined'}
        startIcon={<SwapHoriz />}
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-controls="forward-to-department-form"
      >
        Forward to Department
      </Button>
      <Collapse in={open} unmountOnExit>
        <ForwardToDepartmentForm ticket={ticket} lookups={lookups} onDone={() => setOpen(false)} />
      </Collapse>
    </PanelShell>
  )
}

function ForwardToDepartmentForm({
  ticket,
  lookups,
  onDone,
}: {
  ticket: TicketDetail
  lookups: Lookups | undefined
  onDone: () => void
}) {
  const departments = lookups?.departments ?? []
  // Pre-selected from the ticket's primary issue tag; the FM can override it.
  const [departmentId, setDepartmentId] = useState<number | ''>(ticket.department.id)
  const [note, setNote] = useState('')
  const [error, setError] = useState<ActionErrorState>(NO_ERROR)
  const forward = useTicketAction(ticket.id, 'forward-to-department')

  function submit(e: FormEvent) {
    e.preventDefault()
    if (forward.isPending) return
    if (departmentId === '') {
      setError({ fields: { department_id: 'Select a department.' }, message: null })
      return
    }
    forward.mutate(
      { department_id: departmentId, note: note.trim() },
      { onSuccess: onDone, onError: (err) => setError(describeActionError(err)) },
    )
  }

  return (
    <Box component="form" id="forward-to-department-form" noValidate onSubmit={submit} sx={{ mt: 2 }}>
      <ErrorBanner error={error} />
      <Stack spacing={1.5} sx={{ textAlign: 'left' }}>
        <TextField
          select
          size="small"
          label="Department"
          required
          value={departmentId}
          onChange={(e) => {
            setDepartmentId(Number(e.target.value))
            setError((er) => ({ ...er, fields: { ...er.fields, department_id: '' } }))
          }}
          error={Boolean(error.fields.department_id)}
          helperText={error.fields.department_id ?? "Suggested from the ticket's primary issue tag."}
        >
          {departments.map((d) => (
            <MenuItem key={d.id} value={d.id}>
              {d.name}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          size="small"
          label="Note (optional)"
          multiline
          minRows={2}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          slotProps={{ htmlInput: { maxLength: 2000 } }}
        />
        <Box sx={{ textAlign: 'right' }}>
          <SubmitButton pending={forward.isPending} label="Forward" />
        </Box>
      </Stack>
    </Box>
  )
}

function PanelShell({ message, children }: { message: string; children: ReactNode }) {
  return (
    <Paper
      variant="outlined"
      component="section"
      aria-label="Actions"
      sx={{ p: 2, bgcolor: 'action.hover', textAlign: 'center' }}
    >
      <Typography sx={{ fontWeight: 600, mb: 1.5 }}>{message}</Typography>
      {children}
    </Paper>
  )
}

function ErrorBanner({ error }: { error: ActionErrorState }) {
  if (!error.message) return null
  return (
    <Alert severity="error" role="alert" sx={{ mb: 1.5, textAlign: 'left' }}>
      {error.message}
    </Alert>
  )
}

// --- Client / creator -------------------------------------------------------

function ResolveAction({ ticket, justCreated }: { ticket: TicketDetail; justCreated: boolean }) {
  const [confirming, setConfirming] = useState(false)
  const [error, setError] = useState<ActionErrorState>(NO_ERROR)
  const resolve = useTicketAction(ticket.id, 'mark-resolved')

  const message = justCreated
    ? 'Ticket created successfully. If the issue is resolved, you can mark it as resolved.'
    : ticket.status === 'pending_client_confirmation'
      ? 'The department has marked this ticket resolved. Confirm below to fully close it.'
      : 'If the issue no longer persists, you can mark it as resolved.'

  return (
    <PanelShell message={message}>
      <ErrorBanner error={error} />
      <Button
        variant="outlined"
        color="success"
        startIcon={<CheckCircle />}
        onClick={() => setConfirming(true)}
      >
        Mark Resolved
      </Button>
      <ConfirmDialog
        open={confirming}
        title="Mark ticket resolved?"
        description="The ticket will move to Closed Tickets and no further action will be taken."
        confirmLabel="Mark Resolved"
        pending={resolve.isPending}
        onClose={() => setConfirming(false)}
        onConfirm={() =>
          resolve.mutate(
            {},
            {
              onSuccess: () => setConfirming(false),
              onError: (e) => {
                setError(describeActionError(e))
                setConfirming(false)
              },
            },
          )
        }
      />
    </PanelShell>
  )
}

// --- Department POC ---------------------------------------------------------

type PocForm = 'assign' | 'department' | null

function pocMessage(ticket: TicketDetail) {
  switch (ticket.status) {
    case 'pending_poc_review':
      return 'The technician marked this ticket fully resolved. Review it and mark it resolved (the client must still confirm before it fully closes), or reassign it.'
    case 'pending_blockage_resolution':
      return `The technician reported: ${ticket.assessment_outcome_label}. Reassign a worker or change the department.`
    default:
      return 'A new ticket has been assigned to you. Review it and take the next action.'
  }
}

function PocActions({
  ticket,
  lookups,
  onLeftQueue,
}: {
  ticket: TicketDetail
  lookups: Lookups | undefined
  onLeftQueue: (message: string) => void
}) {
  const [form, setForm] = useState<PocForm>(null)
  const [closing, setClosing] = useState(false)
  const actions = new Set(ticket.available_actions)
  const toggle = (next: PocForm) => setForm((f) => (f === next ? null : next))

  return (
    <PanelShell message={pocMessage(ticket)}>
      <Stack direction="row" spacing={1} useFlexGap sx={{ justifyContent: 'center', flexWrap: 'wrap' }}>
        {actions.has('assign_worker') && (
          <Button
            variant={form === 'assign' ? 'contained' : 'outlined'}
            startIcon={<AssignmentInd />}
            onClick={() => toggle('assign')}
            aria-expanded={form === 'assign'}
            aria-controls="assign-worker-form"
          >
            Assign Worker
          </Button>
        )}
        {actions.has('change_department') && (
          <Button
            variant={form === 'department' ? 'contained' : 'outlined'}
            startIcon={<SwapHoriz />}
            onClick={() => toggle('department')}
            aria-expanded={form === 'department'}
            aria-controls="change-department-form"
          >
            Change Department
          </Button>
        )}
        {actions.has('close') && (
          <Button variant="outlined" color="success" startIcon={<TaskAlt />} onClick={() => setClosing(true)}>
            Close Ticket
          </Button>
        )}
      </Stack>

      <Collapse in={form === 'assign'} unmountOnExit>
        <AssignWorkerForm ticket={ticket} lookups={lookups} onDone={() => setForm(null)} />
      </Collapse>
      <Collapse in={form === 'department'} unmountOnExit>
        <ChangeDepartmentForm ticket={ticket} lookups={lookups} onLeftQueue={onLeftQueue} />
      </Collapse>
      {closing && <CloseDialog ticket={ticket} onClose={() => setClosing(false)} />}
    </PanelShell>
  )
}

function AssignWorkerForm({
  ticket,
  lookups,
  onDone,
}: {
  ticket: TicketDetail
  lookups: Lookups | undefined
  onDone: () => void
}) {
  const technicians = (lookups?.technicians ?? []).filter(
    (t) => t.department_id === ticket.department.id && t.id !== ticket.technician?.id,
  )
  const [technicianId, setTechnicianId] = useState<number | ''>('')
  const [error, setError] = useState<ActionErrorState>(NO_ERROR)
  const assign = useTicketAction(ticket.id, 'assign-worker')

  function submit(e: FormEvent) {
    e.preventDefault()
    if (assign.isPending) return
    if (technicianId === '') {
      setError({ fields: { technician_id: 'Select a worker.' }, message: null })
      return
    }
    assign.mutate(
      { technician_id: technicianId },
      { onSuccess: onDone, onError: (err) => setError(describeActionError(err)) },
    )
  }

  return (
    <Box component="form" id="assign-worker-form" noValidate onSubmit={submit} sx={{ mt: 2 }}>
      <ErrorBanner error={error} />
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ alignItems: 'flex-start' }}>
        <TextField
          select
          size="small"
          label="Select worker"
          required
          fullWidth
          value={technicianId}
          onChange={(e) => {
            setTechnicianId(Number(e.target.value))
            setError(NO_ERROR)
          }}
          error={Boolean(error.fields.technician_id)}
          helperText={
            error.fields.technician_id ??
            (technicians.length ? undefined : 'No other technicians in this department.')
          }
          sx={{ textAlign: 'left' }}
        >
          {technicians.map((t) => (
            <MenuItem key={t.id} value={t.id}>
              {t.display_name}
            </MenuItem>
          ))}
        </TextField>
        <SubmitButton pending={assign.isPending} label="Ok" />
      </Stack>
      <FormHelperText sx={{ textAlign: 'left', mt: 1 }}>
        The worker will be added to Current Assignee(s) and start seeing this ticket.
      </FormHelperText>
    </Box>
  )
}

function ChangeDepartmentForm({
  ticket,
  lookups,
  onLeftQueue,
}: {
  ticket: TicketDetail
  lookups: Lookups | undefined
  onLeftQueue: (message: string) => void
}) {
  const departments = (lookups?.departments ?? []).filter((d) => d.id !== ticket.department.id)
  const [departmentId, setDepartmentId] = useState<number | ''>('')
  const [note, setNote] = useState('')
  const [error, setError] = useState<ActionErrorState>(NO_ERROR)
  const change = useTicketAction(ticket.id, 'change-department')

  function submit(e: FormEvent) {
    e.preventDefault()
    if (change.isPending) return
    const fields: Record<string, string> = {}
    if (departmentId === '') fields.department_id = 'Select a department.'
    if (!note.trim()) fields.note = 'Add a forwarding note for the new department.'
    if (Object.keys(fields).length) {
      setError({ fields, message: null })
      return
    }
    change.mutate(
      { department_id: departmentId as number, note: note.trim() },
      {
        onSuccess: (data: ActionResponse) => {
          if (!('number' in data)) {
            const name = departments.find((d) => d.id === departmentId)?.name
            onLeftQueue(`#${ticket.number} was moved to ${name}.`)
          }
        },
        onError: (err) => setError(describeActionError(err)),
      },
    )
  }

  return (
    <Box component="form" id="change-department-form" noValidate onSubmit={submit} sx={{ mt: 2 }}>
      <ErrorBanner error={error} />
      <Stack spacing={1.5} sx={{ textAlign: 'left' }}>
        <TextField
          select
          size="small"
          label="Select department"
          required
          value={departmentId}
          onChange={(e) => {
            setDepartmentId(Number(e.target.value))
            setError((er) => ({ ...er, fields: { ...er.fields, department_id: '' } }))
          }}
          error={Boolean(error.fields.department_id)}
          helperText={error.fields.department_id}
        >
          {departments.map((d) => (
            <MenuItem key={d.id} value={d.id}>
              {d.name}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          size="small"
          label="Add forwarding note"
          required
          multiline
          minRows={2}
          value={note}
          onChange={(e) => {
            setNote(e.target.value)
            setError((er) => ({ ...er, fields: { ...er.fields, note: '' } }))
          }}
          error={Boolean(error.fields.note)}
          helperText={error.fields.note}
          slotProps={{ htmlInput: { maxLength: 2000 } }}
        />
        <Box sx={{ textAlign: 'right' }}>
          <SubmitButton pending={change.isPending} label="Ok" />
        </Box>
      </Stack>
    </Box>
  )
}

function CloseDialog({ ticket, onClose }: { ticket: TicketDetail; onClose: () => void }) {
  const [note, setNote] = useState('')
  const [error, setError] = useState<ActionErrorState>(NO_ERROR)
  const close = useTicketAction(ticket.id, 'close')
  return (
    <ConfirmDialog
      open
      title="Close this ticket?"
      description="Confirm the issue has been fixed. The ticket will wait for the client to confirm before it's fully closed."
      confirmLabel="Close Ticket"
      pending={close.isPending}
      onClose={onClose}
      onConfirm={() =>
        close.mutate(
          { note: note.trim() },
          { onSuccess: onClose, onError: (e) => setError(describeActionError(e)) },
        )
      }
    >
      <ErrorBanner error={error} />
      <TextField
        label="Closing note (optional)"
        fullWidth
        multiline
        minRows={2}
        value={note}
        onChange={(e) => setNote(e.target.value)}
        sx={{ mt: 2 }}
        slotProps={{ htmlInput: { maxLength: 2000 } }}
      />
    </ConfirmDialog>
  )
}

// --- Technician ------------------------------------------------------------

const OUTCOMES: { value: AssessmentOutcome; label: string; description: string }[] = [
  {
    value: 'fully_resolved',
    label: 'Mark Fully Resolved',
    description: 'The issue has been fully resolved. No further action is needed.',
  },
  {
    value: 'partially_resolved',
    label: 'Mark Partially Resolved',
    description: "I've resolved my part of the issue, but it also involves another department/worker's scope.",
  },
  {
    value: 'needs_reassignment',
    label: 'Suggest Department/Worker Change',
    description: 'The issue is outside my scope. Please assign it to the correct department/worker.',
  },
]

function TechnicianActions({
  ticket,
  onLeftQueue,
}: {
  ticket: TicketDetail
  onLeftQueue: (message: string) => void
}) {
  const [open, setOpen] = useState(false)
  const [outcome, setOutcome] = useState<AssessmentOutcome | ''>('')
  const [comment, setComment] = useState('')
  const [error, setError] = useState<ActionErrorState>(NO_ERROR)
  const submitAssessment = useTicketAction(ticket.id, 'submit-assessment')
  const commentRequired = outcome !== '' && outcome !== 'fully_resolved'

  function submit(e: FormEvent) {
    e.preventDefault()
    if (submitAssessment.isPending) return
    const fields: Record<string, string> = {}
    if (!outcome) fields.outcome = 'Choose an outcome.'
    if (commentRequired && !comment.trim())
      fields.comment = 'Explain what is pending or who should take this.'
    if (Object.keys(fields).length) {
      setError({ fields, message: null })
      return
    }
    submitAssessment.mutate(
      { outcome: outcome as AssessmentOutcome, comment: comment.trim() },
      {
        onSuccess: (data: ActionResponse) => {
          // Fully resolved unassigns the technician, who then leaves their own queue.
          if (!('number' in data)) {
            onLeftQueue(`#${ticket.number} was marked fully resolved and is now unassigned.`)
          }
        },
        onError: (err) => setError(describeActionError(err)),
      },
    )
  }

  return (
    <PanelShell message="You have been assigned this ticket. Take action.">
      <Button
        variant={open ? 'contained' : 'outlined'}
        startIcon={<TaskAlt />}
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-controls="assessment-form"
      >
        Submit Assessment
      </Button>
      <Collapse in={open} unmountOnExit>
        <Box
          component="form"
          id="assessment-form"
          noValidate
          onSubmit={submit}
          sx={{ mt: 2, textAlign: 'left' }}
        >
          <ErrorBanner error={error} />
          <FormControl error={Boolean(error.fields.outcome)} required fullWidth>
            <FormLabel id="outcome-label">Assessment outcome</FormLabel>
            <RadioGroup
              aria-labelledby="outcome-label"
              value={outcome}
              onChange={(e) => {
                setOutcome(e.target.value as AssessmentOutcome)
                setError(NO_ERROR)
              }}
            >
              {OUTCOMES.map((o) => (
                <FormControlLabel
                  key={o.value}
                  value={o.value}
                  control={<Radio />}
                  sx={{ alignItems: 'flex-start', my: 0.5 }}
                  label={
                    <Box sx={{ pt: 1 }}>
                      <Typography sx={{ fontWeight: 600 }}>{o.label}</Typography>
                      <Typography variant="body2" color="text.secondary">
                        {o.description}
                      </Typography>
                    </Box>
                  }
                />
              ))}
            </RadioGroup>
            {error.fields.outcome && <FormHelperText>{error.fields.outcome}</FormHelperText>}
          </FormControl>
          <TextField
            label={commentRequired ? 'Comment' : 'Comment (optional)'}
            required={commentRequired}
            fullWidth
            multiline
            minRows={2}
            value={comment}
            onChange={(e) => {
              setComment(e.target.value)
              setError((er) => ({ ...er, fields: { ...er.fields, comment: '' } }))
            }}
            error={Boolean(error.fields.comment)}
            helperText={error.fields.comment}
            sx={{ mt: 2 }}
            slotProps={{ htmlInput: { maxLength: 2000 } }}
          />
          <Box sx={{ textAlign: 'right', mt: 1.5 }}>
            <SubmitButton pending={submitAssessment.isPending} label="Submit" />
          </Box>
        </Box>
      </Collapse>
    </PanelShell>
  )
}

function SubmitButton({ pending, label }: { pending: boolean; label: string }) {
  return (
    <Button
      type="submit"
      variant="contained"
      color="success"
      disabled={pending}
      startIcon={pending ? <CircularProgress size={16} color="inherit" /> : undefined}
      sx={{ minWidth: 88, flexShrink: 0 }}
    >
      {pending ? 'Saving…' : label}
    </Button>
  )
}
