import PersonOutlined from '@mui/icons-material/PersonOutlined'
import { Avatar } from '@mui/material'
import type { UserSummary } from '../api/types'

const SIZES = { small: 24, medium: 32 }

/**
 * Initials avatar. `user = null` renders the "System" actor, or an empty person
 * icon when `empty` is set (e.g. "Unassigned").
 */
export default function UserAvatar({
  user,
  size = 'medium',
  empty = false,
}: {
  user: UserSummary | null
  size?: keyof typeof SIZES
  empty?: boolean
}) {
  const px = SIZES[size]
  if (!user && empty) {
    return (
      <Avatar aria-hidden sx={{ width: px, height: px, bgcolor: 'action.selected', color: 'text.secondary' }}>
        <PersonOutlined sx={{ fontSize: px * 0.7 }} />
      </Avatar>
    )
  }
  return (
    <Avatar
      aria-hidden
      sx={{
        width: px,
        height: px,
        fontSize: px * 0.42,
        fontWeight: 600,
        bgcolor: user ? 'primary.light' : 'grey.500',
        color: 'common.white',
      }}
    >
      {user ? user.initials : 'S'}
    </Avatar>
  )
}
