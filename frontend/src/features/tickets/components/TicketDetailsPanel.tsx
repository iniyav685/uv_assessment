import { Box, Chip, Divider, Stack, Tooltip, Typography } from '@mui/material'
import type { TicketDetail } from '@/api/types'
import PersonLabel from '@/atoms/PersonLabel'
import { formatDateTime } from '@/utils/format'
import AssigneePicker from '@/features/tickets/components/AssigneePicker'
import DetailRow from '@/molecules/DetailRow'
import StatusChip from '@/atoms/StatusChip'

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
        <DetailRow label="Status">
          <StatusChip status={ticket.status} label={ticket.status_label} />
        </DetailRow>
        <DetailRow label="Assignee">
          <AssigneePicker ticket={ticket} />
        </DetailRow>
        <DetailRow label="Reporter">
          <PersonLabel user={ticket.created_by} />
        </DetailRow>
        <DetailRow label="Tags">
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
        </DetailRow>
        <DetailRow label="Department">
          <Typography variant="body2">{ticket.department.name}</Typography>
        </DetailRow>
        <DetailRow label="Client">
          <Typography variant="body2">{ticket.client.name}</Typography>
        </DetailRow>
        <DetailRow label="Location">
          <Typography variant="body2">
            {ticket.area.name}
            <Typography component="span" variant="body2" color="text.secondary" sx={{ display: 'block' }}>
              {ticket.location}
            </Typography>
          </Typography>
        </DetailRow>
        <DetailRow label="Created">
          <Typography variant="body2" component="time" dateTime={ticket.created_at}>
            {formatDateTime(ticket.created_at)}
          </Typography>
        </DetailRow>
        {ticket.closed_at && (
          <DetailRow label={ticket.status === 'resolved' ? 'Resolved' : 'Closed'}>
            <Typography variant="body2" component="time" dateTime={ticket.closed_at}>
              {formatDateTime(ticket.closed_at)}
            </Typography>
          </DetailRow>
        )}
      </Box>
    </Box>
  )
}
