import Add from '@mui/icons-material/Add'
import {
  Alert,
  Box,
  Button,
  LinearProgress,
  Pagination,
  Snackbar,
  Stack,
  Tab,
  Tabs,
  Typography,
} from '@mui/material'
import { useCallback, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router'
import type { TicketDetail } from '../../api/types'
import EmptyState from '../../components/EmptyState'
import ErrorState from '../../components/ErrorState'
import LoadingState from '../../components/LoadingState'
import PageHeader from '../../components/PageHeader'
import { useAuth } from '../auth/useAuth'
import { useLookups, useTicketCounts, useTickets } from './api'
import CreateTicketDialog from './components/CreateTicketDialog'
import { EMPTY_FILTERS, type FilterValues } from './components/FiltersPopover'
import TicketCard from './components/TicketCard'
import TicketExpandedCard from './components/TicketExpandedCard'
import TicketToolbar from './components/TicketToolbar'
import { useTicketListParams, type Tab as TabValue } from './useTicketListParams'

export default function TicketListPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const { id } = useParams()
  const { params, update, activeFilterCount } = useTicketListParams()
  const tickets = useTickets(params)
  const counts = useTicketCounts(params)
  const lookups = useLookups()

  const [createOpen, setCreateOpen] = useState(false)
  const flash = (location.state as { flash?: string } | null)?.flash
  const expandedId = id && Number.isInteger(Number(id)) ? Number(id) : null

  // Collapse back to the plain list, keeping its search/filter query string.
  const collapse = useCallback(
    () => navigate({ pathname: '/tickets', search: location.search }),
    [navigate, location.search],
  )
  const handleLeftQueue = useCallback(
    (message: string) =>
      navigate({ pathname: '/tickets', search: location.search }, { state: { flash: message } }),
    [navigate, location.search],
  )

  const handleCreated = useCallback(
    (created: TicketDetail) => {
      setCreateOpen(false)
      navigate({ pathname: `/tickets/${created.id}`, search: location.search }, {
        state: { justCreated: true },
      })
    },
    [navigate, location.search],
  )

  const handleSearch = useCallback((search: string) => update({ search }), [update])

  const filters: FilterValues = {
    client: params.client,
    department: params.department,
    facility_manager: params.facility_manager,
    status: params.status,
  }
  const hasQuery = Boolean(params.search) || activeFilterCount > 0
  const data = tickets.data
  const expandedInResults = expandedId != null && data?.results.some((t) => t.id === expandedId)

  return (
    <>
      <PageHeader
        title="Tickets"
        actions={
          user?.can_create_ticket && (
            <Button
              variant="contained"
              startIcon={<Add />}
              onClick={() => setCreateOpen(true)}
              disabled={!lookups.data}
            >
              Create New Ticket
            </Button>
          )
        }
      />

      <Tabs
        value={params.tab}
        onChange={(_, tab: TabValue) => update({ tab })}
        aria-label="Ticket state"
        sx={{ mb: 2, borderBottom: 1, borderColor: 'divider' }}
      >
        <Tab value="open" label={`Open Tickets${counts.data ? ` (${counts.data.open})` : ''}`} />
        <Tab
          value="closed"
          label={`Closed Tickets${counts.data ? ` (${counts.data.closed})` : ''}`}
        />
      </Tabs>

      <TicketToolbar
        search={params.search}
        ordering={params.ordering}
        lookups={lookups.data}
        filters={filters}
        activeFilterCount={activeFilterCount}
        onSearch={handleSearch}
        onOrdering={(ordering) => update({ ordering })}
        onApplyFilters={(value) => update(value)}
      />

      {/* Thin progress bar for background refetches (page/filter change) keeps the list stable. */}
      <Box sx={{ height: 4, mb: 1 }}>
        {tickets.isFetching && data && <LinearProgress aria-label="Updating results" />}
      </Box>

      {/* Deep-linked or just-created ticket that isn't part of the current page/filter — shown
          standalone above the list until it loads (or naturally lands inline once it does). */}
      {expandedId != null && !expandedInResults && (
        <Box sx={{ mb: 1.5 }}>
          <TicketExpandedCard
            ticketId={expandedId}
            lookups={lookups.data}
            onCollapse={collapse}
            onLeftQueue={handleLeftQueue}
          />
        </Box>
      )}

      {tickets.isPending ? (
        <LoadingState label="Loading tickets" />
      ) : tickets.isError && !data ? (
        <ErrorState error={tickets.error} onRetry={() => tickets.refetch()} />
      ) : data && data.results.length === 0 ? (
        <EmptyState
          title={hasQuery ? 'No matching tickets' : `No ${params.tab} tickets`}
          description={
            hasQuery
              ? 'Try a different search term or clear the filters.'
              : params.tab === 'open'
                ? 'New tickets will appear here.'
                : 'Resolved and closed tickets will appear here.'
          }
          action={
            hasQuery && (
              <Button onClick={() => update({ search: '', ...EMPTY_FILTERS })}>
                Clear search and filters
              </Button>
            )
          }
        />
      ) : data ? (
        <>
          {tickets.isError && (
            <ErrorState error={tickets.error} onRetry={() => tickets.refetch()} />
          )}
          <Stack component="section" aria-label={`${params.tab} tickets`} spacing={1.5}>
            {data.results.map((ticket) =>
              ticket.id === expandedId ? (
                <TicketExpandedCard
                  key={ticket.id}
                  ticketId={ticket.id}
                  lookups={lookups.data}
                  onCollapse={collapse}
                  onLeftQueue={handleLeftQueue}
                />
              ) : (
                <TicketCard key={ticket.id} ticket={ticket} />
              ),
            )}
          </Stack>
          <Stack
            direction={{ xs: 'column', sm: 'row' }}
            spacing={1}
            sx={{ mt: 3, alignItems: 'center', justifyContent: 'space-between' }}
          >
            <Typography variant="body2" color="text.secondary" aria-live="polite">
              Showing {(data.page - 1) * data.page_size + 1}–
              {(data.page - 1) * data.page_size + data.results.length} of {data.count}
            </Typography>
            {data.total_pages > 1 && (
              <Pagination
                page={data.page}
                count={data.total_pages}
                onChange={(_, page) => {
                  update({ page })
                  window.scrollTo({ top: 0, behavior: 'smooth' })
                }}
                color="primary"
                shape="rounded"
                siblingCount={0}
                showFirstButton
                showLastButton
              />
            )}
          </Stack>
        </>
      ) : null}

      {lookups.data && (
        <CreateTicketDialog
          open={createOpen}
          lookups={lookups.data}
          onClose={() => setCreateOpen(false)}
          onCreated={handleCreated}
        />
      )}

      <Snackbar
        open={Boolean(flash)}
        autoHideDuration={5000}
        onClose={() => navigate({ search: location.search }, { replace: true, state: null })}
      >
        <Alert severity="info" variant="filled">
          {flash}
        </Alert>
      </Snackbar>
    </>
  )
}
