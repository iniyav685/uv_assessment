import { Box, Button, Stack, Typography } from '@mui/material'
import { useState } from 'react'
import type { Lookups, TicketStatus } from '@/api/types'
import MultiSelect from '@/atoms/MultiSelect'
import type { FilterKey, TicketListParams } from '@/features/tickets/useTicketListParams'

export type FilterValues = Pick<TicketListParams, FilterKey>

export const EMPTY_FILTERS: FilterValues = {
  client: [],
  department: [],
  facility_manager: [],
  status: [],
}

interface Props {
  lookups: Lookups
  value: FilterValues
  onClose: () => void
  onApply: (value: FilterValues) => void
}

export default function FiltersPopover({ lookups, value, onClose, onApply }: Props) {
  // Edit a draft; the list only refetches once the user applies. Re-seeded from `value`
  // each time the popover opens, via `key` on the mount in TicketToolbar.
  const [draft, setDraft] = useState<FilterValues>(value)
  const set = <K extends FilterKey>(key: K) => (v: FilterValues[K]) =>
    setDraft((d) => ({ ...d, [key]: v }))

  return (
    <Box
      component="form"
      noValidate
      onSubmit={(e) => {
        e.preventDefault()
        onApply(draft)
      }}
      sx={{ p: 2, width: 320, maxWidth: 'calc(100vw - 32px)' }}
    >
      <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1.5 }}>
        Filters
      </Typography>
      <Stack spacing={2}>
        <MultiSelect
          label="Client name"
          options={lookups.clients.map((c) => ({ value: c.id, label: c.name }))}
          value={draft.client}
          onChange={set('client')}
        />
        <MultiSelect
          label="Concerned department"
          options={lookups.departments.map((d) => ({ value: d.id, label: d.name }))}
          value={draft.department}
          onChange={set('department')}
        />
        <MultiSelect
          label="Concerned facility manager"
          options={lookups.facility_managers.map((u) => ({ value: u.id, label: u.full_name }))}
          value={draft.facility_manager}
          onChange={set('facility_manager')}
        />
        <MultiSelect<TicketStatus>
          label="Ticket status"
          options={lookups.statuses.map((s) => ({ value: s.value, label: s.label }))}
          value={draft.status}
          onChange={set('status')}
        />
      </Stack>
      <Stack direction="row" spacing={1} sx={{ mt: 2.5, justifyContent: 'space-between' }}>
        <Button onClick={() => setDraft(EMPTY_FILTERS)}>Clear all</Button>
        <Stack direction="row" spacing={1}>
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="contained">
            Apply
          </Button>
        </Stack>
      </Stack>
    </Box>
  )
}
