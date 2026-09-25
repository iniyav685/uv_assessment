import CalendarToday from '@mui/icons-material/CalendarTodayOutlined'
import PersonOutline from '@mui/icons-material/PersonOutlined'
import { Box, Chip, Stack, Typography } from '@mui/material'
import type { ReactNode } from 'react'
import type { TicketListItem } from '@/api/types'
import { formatDateTime } from '@/utils/format'
import StatusChip from '@/atoms/StatusChip'

interface Props {
  ticket: TicketListItem
  /** Heading level: cards in a list use h2, the detail page uses h1. */
  headingComponent?: 'h1' | 'h2'
  headingId?: string
  action?: ReactNode
}

/** The ticket header shared by list cards and the detail page. */
export default function TicketSummary({
  ticket,
  headingComponent = 'h2',
  headingId,
  action,
}: Props) {
  return (
    <Stack spacing={1}>
      <Stack
        direction="row"
        spacing={1}
        useFlexGap
        sx={{ alignItems: 'center', flexWrap: 'wrap', justifyContent: 'space-between' }}
      >
        <Stack direction="row" spacing={1} useFlexGap sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
          <Typography
            component={headingComponent}
            id={headingId}
            sx={{ fontSize: '1.05rem', fontWeight: 600, lineHeight: 1.3 }}
          >
            {ticket.title}
          </Typography>
          <Chip size="small" label={`#${ticket.number}`} sx={{ fontFamily: 'monospace' }} />
          <StatusChip status={ticket.status} label={ticket.status_label} />
          {ticket.action_required && (
            <Chip size="small" color="warning" label="Action Required" sx={{ fontWeight: 600 }} />
          )}
        </Stack>
        {action}
      </Stack>

      <Typography variant="body2" color="text.secondary">
        {ticket.client.name} · {ticket.location}
      </Typography>

      <Stack direction="row" useFlexGap spacing={0.75} sx={{ flexWrap: 'wrap' }} aria-label="Issue tags">
        {ticket.tags.map((tag) => (
          <Chip
            key={tag.id}
            size="small"
            label={tag.name}
            variant={tag.primary ? 'filled' : 'outlined'}
            color={tag.primary ? 'primary' : 'default'}
            sx={{ height: 22, fontSize: 12 }}
          />
        ))}
      </Stack>

      <Stack
        direction={{ xs: 'column', md: 'row' }}
        spacing={{ xs: 0.5, md: 3 }}
        sx={{ typography: 'body2', color: 'text.secondary' }}
      >
        <Box sx={{ display: 'flex', gap: 0.75, alignItems: 'center' }}>
          <CalendarToday sx={{ fontSize: 16 }} aria-hidden />
          <span>
            Created <time dateTime={ticket.created_at}>{formatDateTime(ticket.created_at)}</time>{' '}
            by {ticket.created_by.display_name}
          </span>
        </Box>
        <Box sx={{ display: 'flex', gap: 0.75, alignItems: 'center' }}>
          <PersonOutline sx={{ fontSize: 18 }} aria-hidden />
          <span>
            Current Assignee(s):{' '}
            {ticket.assignees.length
              ? ticket.assignees.map((a) => a.display_name).join(', ')
              : 'Unassigned'}
          </span>
        </Box>
      </Stack>
    </Stack>
  )
}
