import { Box, Chip, Divider, Stack, Tooltip, Typography } from '@mui/material'
import type { ReactNode } from 'react'
import type { TicketDetail, UserSummary } from '../../../api/types'
import UserAvatar from '../../../components/UserAvatar'
import { formatDateTime } from '../../../utils/format'
import AssigneePicker from './AssigneePicker'
import StatusChip from './StatusChip'

/** Jira-style right-hand details column of the ticket modal. */
export default function TicketDetailsPanel({ ticket }: { ticket: TicketDetail }) {
  return (
    <Box
      component="aside"
      aria-label="Ticket details"
      sx={{ border: 1, borderColor: 'divider', borderRadius: 1, bgcolor: 'background.paper' }}
    >
      <Typography component="h2" variant="subtitle2" sx={{ px: 2, py: 1.25, fontWeight: 600 }}>
        Details
      </Typography>
      <Divider />
      <Box
        component="dl"
        sx={{
          m: 0,
          px: 2,
          py: 1.5,
          display: 'grid',
          gridTemplateColumns: '112px minmax(0, 1fr)',
          columnGap: 1.5,
          rowGap: 1.5,
          alignItems: 'center',
        }}
      >
        <Row label="Status">
          <StatusChip status={ticket.status} label={ticket.status_label} />
        </Row>
        <Row label="Assignee">
          <AssigneePicker ticket={ticket} />
        </Row>
        <Row label="Reporter">
          <Person user={ticket.created_by} />
        </Row>
        <Row label="Tags">
          <Stack direction="row" useFlexGap spacing={0.75} sx={{ flexWrap: 'wrap' }}>
            {ticket.tags.map((tag) => (
              <Tooltip
                key={tag.id}
                title={tag.primary ? 'Primary issue — decides the department' : ''}
              >
                <Chip
                  size="small"
                  label={tag.name}
                  color={tag.primary ? 'primary' : 'default'}
                  variant={tag.primary ? 'filled' : 'outlined'}
                />
              </Tooltip>
            ))}
          </Stack>
        </Row>
        <Row label="Department">
          <Typography variant="body2">{ticket.department.name}</Typography>
        </Row>
        <Row label="Client">
          <Typography variant="body2">{ticket.client.name}</Typography>
        </Row>
        <Row label="Location">
          <Typography variant="body2">
            {ticket.area.name}
            <Typography component="span" variant="body2" color="text.secondary" sx={{ display: 'block' }}>
              {ticket.location}
            </Typography>
          </Typography>
        </Row>
        <Row label="Created">
          <Typography variant="body2" component="time" dateTime={ticket.created_at}>
            {formatDateTime(ticket.created_at)}
          </Typography>
        </Row>
        {ticket.closed_at && (
          <Row label={ticket.status === 'resolved' ? 'Resolved' : 'Closed'}>
            <Typography variant="body2" component="time" dateTime={ticket.closed_at}>
              {formatDateTime(ticket.closed_at)}
            </Typography>
          </Row>
        )}
      </Box>
    </Box>
  )
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <Typography component="dt" variant="body2" color="text.secondary">
        {label}
      </Typography>
      <Box component="dd" sx={{ m: 0, minWidth: 0 }}>
        {children}
      </Box>
    </>
  )
}

function Person({ user }: { user: UserSummary | null }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 0 }}>
      <UserAvatar user={user} size="small" empty />
      <Typography variant="body2" noWrap color={user ? 'text.primary' : 'text.secondary'}>
        {user ? user.display_name : 'None'}
      </Typography>
    </Box>
  )
}
