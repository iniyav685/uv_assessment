import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormHelperText,
  Stack,
  TextField,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material'
import { useMemo, useState, type FormEvent } from 'react'
import { toApiError } from '../../../api/errors'
import type { IssueTypeOption, Lookups, OfficeOption, TicketDetail } from '../../../api/types'
import RichTextEditor from '../../../components/RichTextEditor'
import { useAuth } from '../../auth/useAuth'
import { useCreateTicket } from '../api'

const MAX_ISSUES = 5

type FieldErrors = Partial<
  Record<'office' | 'title' | 'issues' | 'floors' | 'description', string>
>

// Server field names -> form field names.
const SERVER_FIELDS: Record<string, keyof FieldErrors> = {
  client_office_id: 'office',
  title: 'title',
  issue_type_ids: 'issues',
  floor_ids: 'floors',
  description: 'description',
}

interface Props {
  open: boolean
  lookups: Lookups
  onClose: () => void
  onCreated: (ticket: TicketDetail) => void
}

export default function CreateTicketDialog({ open, lookups, onClose, onCreated }: Props) {
  const theme = useTheme()
  const fullScreen = useMediaQuery(theme.breakpoints.down('sm'))
  const create = useCreateTicket()

  const handleClose = () => {
    if (!create.isPending) onClose()
  }

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      fullScreen={fullScreen}
      fullWidth
      maxWidth="sm"
      aria-labelledby="create-ticket-title"
    >
      {/* Children unmount on close, so the form resets each time it opens. */}
      <CreateTicketForm
        lookups={lookups}
        mutation={create}
        onCancel={handleClose}
        onCreated={onCreated}
      />
    </Dialog>
  )
}

function CreateTicketForm({
  lookups,
  mutation,
  onCancel,
  onCreated,
}: {
  lookups: Lookups
  mutation: ReturnType<typeof useCreateTicket>
  onCancel: () => void
  onCreated: (ticket: TicketDetail) => void
}) {
  const { user } = useAuth()
  const isClient = user?.role === 'client_poc'
  const offices = lookups.offices

  const [office, setOffice] = useState<OfficeOption | null>(offices.length === 1 ? offices[0] : null)
  const [title, setTitle] = useState('')
  const [issues, setIssues] = useState<IssueTypeOption[]>([])
  const [floorIds, setFloorIds] = useState<number[]>([])
  const [description, setDescription] = useState('')
  const [descriptionEmpty, setDescriptionEmpty] = useState(true)
  const [errors, setErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)

  const quickIssues = useMemo(() => lookups.issue_types.filter((i) => i.is_quick), [lookups])
  const hasMultipleFloors = (office?.floors.length ?? 0) > 1

  // "Tap to autofill": adds the tag, and fills the title if the user hasn't typed one.
  function toggleQuickIssue(issue: IssueTypeOption) {
    setErrors((e) => ({ ...e, issues: undefined, title: undefined }))
    const selected = issues.some((i) => i.id === issue.id)
    setIssues(
      selected ? issues.filter((i) => i.id !== issue.id) : [...issues, issue].slice(0, MAX_ISSUES),
    )
    if (!selected && !title.trim()) setTitle(issue.name)
  }

  function validate(): FieldErrors {
    const next: FieldErrors = {}
    if (!office) next.office = 'Select a client.'
    if (title.trim().length < 3) next.title = 'Give the ticket a short title (at least 3 characters).'
    if (!issues.length) next.issues = 'Add at least one issue tag.'
    if (hasMultipleFloors && !floorIds.length) next.floors = 'Select at least one floor.'
    if (!isClient && descriptionEmpty) next.description = 'Describe the issue.'
    return next
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (mutation.isPending) return // guard against double submit
    const next = validate()
    setErrors(next)
    setFormError(null)
    if (Object.values(next).some(Boolean)) return

    try {
      const ticket = await mutation.mutateAsync({
        client_office_id: office!.id,
        title: title.trim(),
        issue_type_ids: issues.map((i) => i.id),
        floor_ids: hasMultipleFloors ? floorIds : [],
        description: descriptionEmpty ? '' : description,
      })
      onCreated(ticket)
    } catch (err) {
      const apiError = toApiError(err)
      if (apiError.isValidation && apiError.details) {
        const mapped: FieldErrors = {}
        for (const [field, messages] of Object.entries(apiError.details)) {
          const key = SERVER_FIELDS[field]
          if (key) mapped[key] = messages[0]
          else setFormError(messages[0])
        }
        setErrors(mapped)
      } else {
        setFormError(apiError.isForbidden ? 'You are not allowed to create tickets.' : apiError.message)
      }
    }
  }

  const officeLabel = (o: OfficeOption) => `${o.client.name} — ${o.label}`
  const departmentName = (issue: IssueTypeOption) =>
    lookups.departments.find((d) => d.id === issue.department_id)?.name ?? 'its department'

  return (
    <Box component="form" noValidate onSubmit={handleSubmit}>
      <DialogTitle id="create-ticket-title">Create New Ticket</DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2.5}>
          {formError && (
            <Alert severity="error" role="alert">
              {formError}
            </Alert>
          )}

          {!isClient && offices.length > 1 && (
            <Autocomplete
              options={offices}
              value={office}
              onChange={(_, value) => {
                setOffice(value)
                setFloorIds([])
                setErrors((e) => ({ ...e, office: undefined, floors: undefined }))
              }}
              getOptionLabel={officeLabel}
              isOptionEqualToValue={(a, b) => a.id === b.id}
              renderInput={(params) => (
                <TextField
                  {...params}
                  label="Client"
                  required
                  placeholder="Type or search client"
                  error={Boolean(errors.office)}
                  helperText={errors.office}
                />
              )}
            />
          )}

          <Box component="fieldset" sx={{ border: 1, borderColor: 'divider', borderRadius: 1, p: 1.5, m: 0 }}>
            <Typography component="legend" variant="body2" sx={{ px: 0.5, fontWeight: 600 }}>
              Quick Issues{' '}
              <Typography component="span" variant="body2" color="text.secondary">
                — tap to autofill
              </Typography>
            </Typography>
            <Stack direction="row" useFlexGap spacing={1} sx={{ flexWrap: 'wrap' }}>
              {quickIssues.map((issue) => {
                const selected = issues.some((i) => i.id === issue.id)
                return (
                  <Chip
                    key={issue.id}
                    label={issue.name}
                    color={selected ? 'primary' : 'default'}
                    variant={selected ? 'filled' : 'outlined'}
                    onClick={() => toggleQuickIssue(issue)}
                    aria-pressed={selected}
                  />
                )
              })}
            </Stack>
          </Box>

          <TextField
            label="Title"
            required
            placeholder="e.g. AC blowing warm air on 3F"
            value={title}
            onChange={(e) => {
              setTitle(e.target.value)
              setErrors((er) => ({ ...er, title: undefined }))
            }}
            error={Boolean(errors.title)}
            helperText={errors.title}
            slotProps={{ htmlInput: { maxLength: 150 } }}
          />

          <Autocomplete
            multiple
            options={lookups.issue_types}
            value={issues}
            onChange={(_, value) => {
              setIssues(value.slice(0, MAX_ISSUES))
              setErrors((e) => ({ ...e, issues: undefined }))
            }}
            getOptionLabel={(o) => o.name}
            isOptionEqualToValue={(a, b) => a.id === b.id}
            filterSelectedOptions
            renderInput={(params) => (
              <TextField
                {...params}
                label="Issue tags"
                required
                placeholder={issues.length ? '' : 'Type or search issue'}
                error={Boolean(errors.issues)}
                helperText={
                  errors.issues ??
                  (issues.length > 1
                    ? `Routed to ${departmentName(issues[0])} (first tag).`
                    : 'The first tag decides which department handles the ticket.')
                }
              />
            )}
          />

          {hasMultipleFloors && office && (
            <Autocomplete
              multiple
              options={office.floors}
              value={office.floors.filter((f) => floorIds.includes(f.id))}
              onChange={(_, value) => {
                setFloorIds(value.map((f) => f.id))
                setErrors((e) => ({ ...e, floors: undefined }))
              }}
              getOptionLabel={(f) => f.label}
              isOptionEqualToValue={(a, b) => a.id === b.id}
              disableCloseOnSelect
              renderInput={(params) => (
                <TextField
                  {...params}
                  label="Floor(s)"
                  required
                  error={Boolean(errors.floors)}
                  helperText={
                    errors.floors ??
                    `${isClient ? 'Your' : 'This'} office has multiple floors — please select where the issue is.`
                  }
                />
              )}
            />
          )}

          <Box>
            <Typography variant="body2" sx={{ mb: 0.5, fontWeight: 600 }}>
              Description{!isClient && ' *'}
            </Typography>
            <RichTextEditor
              ariaLabel="Description"
              placeholder={isClient ? 'Describe the issue (optional)' : 'Describe the issue'}
              error={Boolean(errors.description)}
              onChange={(html, empty) => {
                setDescription(html)
                setDescriptionEmpty(empty)
                setErrors((er) => ({ ...er, description: undefined }))
              }}
              sx={{ '& .tiptap': { minHeight: 160, maxHeight: 360 } }}
            />
            {errors.description && <FormHelperText error>{errors.description}</FormHelperText>}
          </Box>
        </Stack>
      </DialogContent>
      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={onCancel} color="error" variant="outlined" disabled={mutation.isPending}>
          Cancel
        </Button>
        <Button
          type="submit"
          variant="contained"
          color="success"
          disabled={mutation.isPending}
          startIcon={mutation.isPending ? <CircularProgress size={16} color="inherit" /> : undefined}
        >
          {mutation.isPending ? 'Submitting…' : 'Submit'}
        </Button>
      </DialogActions>
    </Box>
  )
}
