import { Button, Card, CardContent } from '@mui/material'
import { memo } from 'react'
import { Link, useLocation } from 'react-router'
import type { TicketListItem } from '@/api/types'
import TicketSummary from '@/features/tickets/components/TicketSummary'

function TicketCard({ ticket }: { ticket: TicketListItem }) {
  const { search } = useLocation()
  return (
    <Card
      component="article"
      variant="outlined"
      aria-labelledby={`ticket-${ticket.id}-title`}
      sx={{ borderColor: ticket.action_required ? 'warning.main' : undefined }}
    >
      <CardContent sx={{ '&:last-child': { pb: 2 } }}>
        <TicketSummary
          ticket={ticket}
          headingId={`ticket-${ticket.id}-title`}
          action={
            <Button
              component={Link}
              to={{ pathname: `/tickets/${ticket.id}`, search }}
              variant="contained"
              color="success"
              size="small"
              aria-label={`View ticket ${ticket.number}: ${ticket.title}`}
            >
              View
            </Button>
          }
        />
      </CardContent>
    </Card>
  )
}

// Rows re-render only when their own ticket object changes.
export default memo(TicketCard)
