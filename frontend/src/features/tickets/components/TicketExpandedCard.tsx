import Close from '@mui/icons-material/Close'
import { Alert, Box, Card, Chip, Divider, IconButton, Paper, Stack, Typography } from '@mui/material'
import { useLocation } from 'react-router'
import { ApiError, toApiError } from '../../../api/errors'
import type { Lookups } from '../../../api/types'
import ErrorState from '../../../components/ErrorState'
import LoadingState from '../../../components/LoadingState'
import { useTicket } from '../api'
import ActionPanel, { ticketHasActionPanel } from './ActionPanel'
import ActivityFeed from './ActivityFeed'
import CommentComposer from './CommentComposer'
import IssueDescriptionCard from './IssueDescriptionCard'
import StatusChip from './StatusChip'
import TicketDetailsPanel from './TicketDetailsPanel'

interface LocationState {
  justCreated?: boolean
}

interface Props {
  ticketId: number
  lookups: Lookups | undefined
  onCollapse: () => void
  onLeftQueue: (message: string) => void
}

/**
 * Jira-style accordion card: expands in place within the ticket list, replacing
 * TicketCard at that position. Header stays visible; on md+ the left (description,
 * CTA panel, activity feed, then a pinned comment composer) and right (details/
 * assignee) columns scroll independently within a bounded height.
 */
export default function TicketExpandedCard({ ticketId, lookups, onCollapse, onLeftQueue }: Props) {
  const location = useLocation()
  const state = (location.state ?? {}) as LocationState
  const ticket = useTicket(ticketId)
  const data = ticket.data

  return (
    <Card
      component="article"
      variant="outlined"
      aria-labelledby="ticket-expanded-title"
      sx={{ borderColor: 'primary.main', overflow: 'visible' }}
    >
      <Box sx={{ p: { xs: 2, md: 3 }, pb: 1.5, position: 'relative' }}>
        <Stack
          direction="row"
          spacing={1}
          useFlexGap
          sx={{ alignItems: 'center', flexWrap: 'wrap', mb: 0.5, pr: 5 }}
        >
          {data && (
            <>
              <Chip size="small" label={`#${data.number}`} sx={{ fontFamily: 'monospace' }} />
              <StatusChip status={data.status} label={data.status_label} />
              {data.action_required && (
                <Chip size="small" color="warning" label="Action Required" sx={{ fontWeight: 600 }} />
              )}
            </>
          )}
        </Stack>
        <Typography id="ticket-expanded-title" component="h2" variant="h2" sx={{ fontSize: '1.3rem' }}>
          {data?.title ?? (ticket.isError ? 'Ticket' : 'Loading ticket…')}
        </Typography>
        <IconButton
          aria-label="Collapse ticket"
          onClick={onCollapse}
          sx={{ position: 'absolute', right: 12, top: 12 }}
        >
          <Close />
        </IconButton>
      </Box>
      <Divider />

      <Box sx={{ bgcolor: 'background.default', p: { xs: 2, md: 3 } }}>
        {!Number.isInteger(ticketId) ? (
          <ErrorState error={new ApiError(404, 'not_found', 'Not found.')} />
        ) : ticket.isPending ? (
          <LoadingState label="Loading ticket" />
        ) : ticket.isError ? (
          <ErrorState
            error={ticket.error}
            onRetry={toApiError(ticket.error).isNotFound ? undefined : () => ticket.refetch()}
          />
        ) : data ? (
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', md: 'minmax(0, 1fr) 320px' },
              gap: 2,
              alignItems: 'stretch',
              height: { md: 620 },
              maxHeight: { md: '70vh' },
              minHeight: { md: 0 },
            }}
          >
            <Box
              sx={{
                minWidth: 0,
                minHeight: 0,
                order: { xs: 2, md: 1 },
                display: 'flex',
                flexDirection: 'column',
              }}
            >
              <Stack
                spacing={1.5}
                sx={{
                  minHeight: 0,
                  flex: '1 1 auto',
                  overflowY: { md: 'auto' },
                  pr: { md: 0.5 },
                }}
              >
                <IssueDescriptionCard ticket={data} />
                {ticketHasActionPanel(data) && (
                  <ActionPanel
                    ticket={data}
                    lookups={lookups}
                    justCreated={Boolean(state.justCreated)}
                    onLeftQueue={onLeftQueue}
                  />
                )}
                <ActivityFeed activities={data.activities} />
              </Stack>

              {/* Pinned footer: always visible at the bottom of the left column, never scrolls away. */}
              {data.available_actions.includes('comment') ? (
                <Paper
                  variant="outlined"
                  sx={{ p: 2, mt: 1.5, flexShrink: 0 }}
                  aria-label="Add a comment section"
                >
                  <CommentComposer ticketId={data.id} />
                </Paper>
              ) : (
                data.closed_at && (
                  <Alert severity="info" sx={{ mt: 1.5, flexShrink: 0 }}>
                    This ticket is {data.status === 'resolved' ? 'resolved' : 'closed'}; comments are disabled.
                  </Alert>
                )
              )}
            </Box>
            <Box sx={{ order: { xs: 1, md: 2 }, minHeight: 0, height: { md: '100%' }, overflowY: { md: 'auto' } }}>
              <TicketDetailsPanel ticket={data} />
            </Box>
          </Box>
        ) : null}
      </Box>
    </Card>
  )
}
