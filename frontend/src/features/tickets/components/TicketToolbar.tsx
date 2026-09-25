import FilterList from '@mui/icons-material/FilterList'
import Search from '@mui/icons-material/Search'
import Sort from '@mui/icons-material/Sort'
import {
  Badge,
  Button,
  InputAdornment,
  ListItemText,
  Menu,
  MenuItem,
  Popover,
  Stack,
  TextField,
} from '@mui/material'
import { useEffect, useRef, useState } from 'react'
import type { Lookups } from '../../../api/types'
import { useDebouncedValue } from '../../../hooks/useDebouncedValue'
import type { Ordering } from '../useTicketListParams'
import FiltersPopover, { type FilterValues } from './FiltersPopover'

const SORT_OPTIONS: { value: Ordering; label: string }[] = [
  { value: '-created_at', label: 'Newest first' },
  { value: 'created_at', label: 'Oldest first' },
]

interface Props {
  search: string
  ordering: Ordering
  lookups: Lookups | undefined
  filters: FilterValues
  activeFilterCount: number
  onSearch: (value: string) => void
  onOrdering: (value: Ordering) => void
  onApplyFilters: (value: FilterValues) => void
}

export default function TicketToolbar({
  search,
  ordering,
  lookups,
  filters,
  activeFilterCount,
  onSearch,
  onOrdering,
  onApplyFilters,
}: Props) {
  // Local input state for instant typing; the URL (and the API) update after a pause.
  const [text, setText] = useState(search)
  const debounced = useDebouncedValue(text.trim())
  const [sortAnchor, setSortAnchor] = useState<HTMLElement | null>(null)
  const [filtersAnchor, setFiltersAnchor] = useState<HTMLElement | null>(null)

  // Last value we pushed to the URL, so our own update isn't mistaken for an external one.
  const sent = useRef(search)

  useEffect(() => {
    if (debounced !== sent.current) {
      sent.current = debounced
      onSearch(debounced)
    }
  }, [debounced, onSearch])

  // Sync the box when the URL changes externally (back button, "clear filters").
  useEffect(() => {
    if (search !== sent.current) {
      sent.current = search
      setText(search)
    }
  }, [search])

  return (
    <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ mb: 2 }}>
      <TextField
        type="search"
        size="small"
        fullWidth
        placeholder="Search by ticket #, issue, client or description"
        value={text}
        onChange={(e) => setText(e.target.value)}
        slotProps={{
          htmlInput: { 'aria-label': 'Search tickets' },
          input: {
            startAdornment: (
              <InputAdornment position="start">
                <Search fontSize="small" />
              </InputAdornment>
            ),
          },
        }}
      />
      <Stack direction="row" spacing={1.5}>
        <Badge color="primary" badgeContent={activeFilterCount} sx={{ flex: { xs: 1, sm: 'none' } }}>
          <Button
            variant="outlined"
            startIcon={<FilterList />}
            onClick={(e) => setFiltersAnchor(e.currentTarget)}
            disabled={!lookups}
            fullWidth
            aria-haspopup="dialog"
            aria-expanded={Boolean(filtersAnchor)}
            aria-label={`Filters${activeFilterCount ? ` (${activeFilterCount} active)` : ''}`}
          >
            Filters
          </Button>
        </Badge>
        <Button
          variant="outlined"
          startIcon={<Sort />}
          onClick={(e) => setSortAnchor(e.currentTarget)}
          aria-haspopup="menu"
          aria-expanded={Boolean(sortAnchor)}
          sx={{ flex: { xs: 1, sm: 'none' }, whiteSpace: 'nowrap' }}
        >
          Sort
        </Button>
        <Menu anchorEl={sortAnchor} open={Boolean(sortAnchor)} onClose={() => setSortAnchor(null)}>
          {SORT_OPTIONS.map((option) => (
            <MenuItem
              key={option.value}
              selected={option.value === ordering}
              onClick={() => {
                onOrdering(option.value)
                setSortAnchor(null)
              }}
            >
              <ListItemText>Created: {option.label}</ListItemText>
            </MenuItem>
          ))}
        </Menu>
        {lookups && (
          <Popover
            open={Boolean(filtersAnchor)}
            anchorEl={filtersAnchor}
            onClose={() => setFiltersAnchor(null)}
            anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
          >
            <FiltersPopover
              key={filtersAnchor ? 'open' : 'closed'}
              lookups={lookups}
              value={filters}
              onClose={() => setFiltersAnchor(null)}
              onApply={(value) => {
                onApplyFilters(value)
                setFiltersAnchor(null)
              }}
            />
          </Popover>
        )}
      </Stack>
    </Stack>
  )
}
