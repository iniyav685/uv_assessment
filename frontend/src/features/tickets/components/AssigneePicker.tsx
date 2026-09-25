import Check from '@mui/icons-material/Check'
import Search from '@mui/icons-material/Search'
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  InputAdornment,
  List,
  ListItemAvatar,
  ListItemButton,
  ListItemText,
  Popover,
  TextField,
  Typography,
} from '@mui/material'
import { useState } from 'react'
import type { TicketDetail } from '../../../api/types'
import UserAvatar from '../../../components/UserAvatar'
import { useDebouncedValue } from '../../../hooks/useDebouncedValue'
import { describeActionError } from '../actionErrors'
import { useAssignableUsers, useLookups, useTicketAction } from '../api'

/**
 * Jira-style assignee field. For the Facility Manager (before forwarding) it's a
 * button that opens a searchable list of departments; for the Department POC
 * (after forwarding) it's a searchable list of the department's technicians.
 */
export default function AssigneePicker({ ticket }: { ticket: TicketDetail }) {
  if (ticket.available_actions.includes('forward_to_department')) {
    return <DepartmentPicker ticket={ticket} />
  }
  return <TechnicianPicker ticket={ticket} />
}

function CurrentAssignee({ user }: { user: TicketDetail['technician'] | TicketDetail['facility_manager'] }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 0 }}>
      <UserAvatar user={user} size="small" empty />
      <Typography variant="body2" noWrap color={user ? 'text.primary' : 'text.secondary'}>
        {user ? user.display_name : 'Unassigned'}
      </Typography>
    </Box>
  )
}

function TechnicianPicker({ ticket }: { ticket: TicketDetail }) {
  const canAssign = ticket.available_actions.includes('assign_worker')
  const [anchor, setAnchor] = useState<HTMLElement | null>(null)
  const [search, setSearch] = useState('')
  const debounced = useDebouncedValue(search.trim(), 250)
  const users = useAssignableUsers(ticket.id, debounced, Boolean(anchor))
  const assign = useTicketAction(ticket.id, 'assign-worker')

  // Before the FM forwards it, nobody's been assigned a technician yet, but showing plain
  // "Unassigned" would contradict the activity log's "auto-assigned to <FM>" entry.
  const current =
    ticket.technician ??
    (ticket.status === 'pending_facility_manager_review' ? ticket.facility_manager : null)

  if (!canAssign) return <CurrentAssignee user={current} />

  const close = () => {
    if (assign.isPending) return
    setAnchor(null)
    setSearch('')
    assign.reset()
  }

  return (
    <>
      <Button
        onClick={(e) => setAnchor(e.currentTarget)}
        color="inherit"
        aria-haspopup="dialog"
        aria-label={`Assignee: ${current ? current.display_name : 'Unassigned'}. Change assignee`}
        sx={{ justifyContent: 'flex-start', px: 1, mx: -1, textAlign: 'left', maxWidth: '100%' }}
      >
        <CurrentAssignee user={current} />
      </Button>
      <Popover
        open={Boolean(anchor)}
        anchorEl={anchor}
        onClose={close}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
        slotProps={{ paper: { sx: { width: 320, maxWidth: 'calc(100vw - 32px)' } } }}
      >
        <Box sx={{ p: 1.5 }}>
          <TextField
            autoFocus
            fullWidth
            size="small"
            placeholder="Search technicians"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            slotProps={{
              htmlInput: { 'aria-label': 'Search technicians' },
              input: {
                startAdornment: (
                  <InputAdornment position="start">
                    <Search fontSize="small" />
                  </InputAdornment>
                ),
                endAdornment: users.isFetching ? <CircularProgress size={16} /> : undefined,
              },
            }}
          />
        </Box>
        {assign.isError && (
          <Alert severity="error" sx={{ mx: 1.5, mb: 1 }}>
            {describeActionError(assign.error).message ??
              Object.values(describeActionError(assign.error).fields)[0]}
          </Alert>
        )}
        {users.isError && (
          <Alert severity="error" sx={{ mx: 1.5, mb: 1 }}>
            {describeActionError(users.error).message}
          </Alert>
        )}
        <List dense sx={{ maxHeight: 280, overflowY: 'auto', pt: 0 }} aria-label="Technicians">
          {users.data?.results.length === 0 && (
            <Typography variant="body2" color="text.secondary" sx={{ px: 2, py: 1.5 }}>
              No technicians match “{debounced}”.
            </Typography>
          )}
          {users.data?.results.map((user) => {
            const selected = user.id === current?.id
            return (
              <ListItemButton
                key={user.id}
                selected={selected}
                disabled={assign.isPending || selected}
                onClick={() => assign.mutate({ technician_id: user.id }, { onSuccess: close })}
              >
                <ListItemAvatar sx={{ minWidth: 40 }}>
                  <UserAvatar user={user} />
                </ListItemAvatar>
                <ListItemText primary={user.full_name} secondary={user.title} />
                {selected && <Check fontSize="small" color="primary" aria-label="Current assignee" />}
                {assign.isPending && assign.variables?.technician_id === user.id && (
                  <CircularProgress size={16} />
                )}
              </ListItemButton>
            )
          })}
        </List>
      </Popover>
    </>
  )
}

function DepartmentPicker({ ticket }: { ticket: TicketDetail }) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null)
  const [search, setSearch] = useState('')
  const lookups = useLookups()
  const forward = useTicketAction(ticket.id, 'forward-to-department')

  const current = ticket.facility_manager
  const pocs = (lookups.data?.department_pocs ?? []).filter((p) =>
    p.full_name.toLowerCase().includes(search.trim().toLowerCase()),
  )
  const departmentName = (departmentId: number) =>
    lookups.data?.departments.find((d) => d.id === departmentId)?.name

  const close = () => {
    if (forward.isPending) return
    setAnchor(null)
    setSearch('')
    forward.reset()
  }

  return (
    <>
      <Button
        onClick={(e) => setAnchor(e.currentTarget)}
        color="inherit"
        aria-haspopup="dialog"
        aria-label={`Assignee: ${current ? current.display_name : 'Unassigned'}. Forward to a department`}
        sx={{ justifyContent: 'flex-start', px: 1, mx: -1, textAlign: 'left', maxWidth: '100%' }}
      >
        <CurrentAssignee user={current} />
      </Button>
      <Popover
        open={Boolean(anchor)}
        anchorEl={anchor}
        onClose={close}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
        slotProps={{ paper: { sx: { width: 320, maxWidth: 'calc(100vw - 32px)' } } }}
      >
        <Box sx={{ p: 1.5 }}>
          <TextField
            autoFocus
            fullWidth
            size="small"
            placeholder="Search department POCs"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            slotProps={{
              htmlInput: { 'aria-label': 'Search department POCs' },
              input: {
                startAdornment: (
                  <InputAdornment position="start">
                    <Search fontSize="small" />
                  </InputAdornment>
                ),
              },
            }}
          />
        </Box>
        {forward.isError && (
          <Alert severity="error" sx={{ mx: 1.5, mb: 1 }}>
            {describeActionError(forward.error).message ??
              Object.values(describeActionError(forward.error).fields)[0]}
          </Alert>
        )}
        <List dense sx={{ maxHeight: 280, overflowY: 'auto', pt: 0 }} aria-label="Department POCs">
          {pocs.length === 0 && (
            <Typography variant="body2" color="text.secondary" sx={{ px: 2, py: 1.5 }}>
              No department POCs match “{search}”.
            </Typography>
          )}
          {pocs.map((poc) => {
            const suggested = poc.department_id === ticket.department.id
            return (
              <ListItemButton
                key={poc.id}
                disabled={forward.isPending}
                onClick={() =>
                  forward.mutate(
                    { department_id: poc.department_id, note: '' },
                    { onSuccess: close },
                  )
                }
              >
                <ListItemAvatar sx={{ minWidth: 40 }}>
                  <UserAvatar user={poc} />
                </ListItemAvatar>
                <ListItemText
                  primary={poc.full_name}
                  secondary={
                    suggested
                      ? `${poc.title} · Suggested from the primary issue tag`
                      : `${poc.title} · ${departmentName(poc.department_id) ?? ''}`
                  }
                />
                {forward.isPending && forward.variables?.department_id === poc.department_id && (
                  <CircularProgress size={16} />
                )}
              </ListItemButton>
            )
          })}
        </List>
      </Popover>
    </>
  )
}
