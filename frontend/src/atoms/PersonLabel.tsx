import { Box, Typography } from '@mui/material'
import type { UserSummary } from '@/api/types'
import UserAvatar from '@/atoms/UserAvatar'

interface Props {
  user: UserSummary | null
  /** Shown in place of a name when `user` is null. */
  fallback?: string
}

export default function PersonLabel({ user, fallback = 'None' }: Props) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 0 }}>
      <UserAvatar user={user} size="small" empty />
      <Typography variant="body2" noWrap color={user ? 'text.primary' : 'text.secondary'}>
        {user ? user.display_name : fallback}
      </Typography>
    </Box>
  )
}
