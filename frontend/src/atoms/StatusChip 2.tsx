import CheckCircleOutline from '@mui/icons-material/CheckCircleOutlined'
import ErrorOutline from '@mui/icons-material/ErrorOutlineOutlined'
import Schedule from '@mui/icons-material/Schedule'
import { Chip, type ChipProps } from '@mui/material'
import type { TicketStatus } from '@/api/types'

const COLOR: Record<TicketStatus, ChipProps['color']> = {
  pending_facility_manager_review: 'secondary',
  pending_technician_assignment: 'error',
  pending_technician_assessment: 'warning',
  pending_poc_review: 'info',
  pending_blockage_resolution: 'error',
  pending_client_confirmation: 'warning',
  resolved: 'success',
  closed: 'success',
}

export default function StatusChip({ status, label }: { status: TicketStatus; label: string }) {
  const done = status === 'resolved' || status === 'closed'
  const Icon = done
    ? CheckCircleOutline
    : status === 'pending_blockage_resolution'
      ? ErrorOutline
      : Schedule
  return (
    <Chip
      size="small"
      variant="outlined"
      color={COLOR[status]}
      icon={<Icon fontSize="small" />}
      label={label}
      sx={{ fontWeight: 500 }}
    />
  )
}
