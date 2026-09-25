import NotificationsOutlined from '@mui/icons-material/NotificationsOutlined'
import {
  Badge,
  Box,
  Button,
  Divider,
  IconButton,
  ListItemText,
  Menu,
  MenuItem,
  Typography,
} from '@mui/material'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router'
import { notificationService } from '@/services/notification.service'
import { formatDateTime } from '@/utils/format'

const KEY = ['notifications'] as const

/** In-app notifications created by the Celery worker. */
export default function NotificationsBell() {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null)
  const navigate = useNavigate()
  const qc = useQueryClient()

  const { data } = useQuery({
    queryKey: KEY,
    queryFn: () => notificationService.getNotifications(8),
    // Light polling so notifications produced asynchronously show up without a reload.
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  })

  const markRead = useMutation({
    mutationFn: (id: number) => notificationService.markRead(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  })
  const markAll = useMutation({
    mutationFn: () => notificationService.markAllRead(),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  })

  const unread = data?.unread_count ?? 0

  return (
    <>
      <IconButton
        color="inherit"
        onClick={(e) => setAnchor(e.currentTarget)}
        aria-label={`Notifications${unread ? `, ${unread} unread` : ''}`}
        aria-haspopup="menu"
      >
        <Badge color="error" badgeContent={unread} max={99}>
          <NotificationsOutlined />
        </Badge>
      </IconButton>
      <Menu
        anchorEl={anchor}
        open={Boolean(anchor)}
        onClose={() => setAnchor(null)}
        slotProps={{ paper: { sx: { width: 360, maxWidth: 'calc(100vw - 32px)' } } }}
      >
        <Box sx={{ px: 2, py: 1, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Typography sx={{ fontWeight: 600 }}>Notifications</Typography>
          <Button size="small" disabled={!unread || markAll.isPending} onClick={() => markAll.mutate()}>
            Mark all read
          </Button>
        </Box>
        <Divider />
        {!data?.results.length && (
          <MenuItem disabled>
            <ListItemText>You're all caught up.</ListItemText>
          </MenuItem>
        )}
        {data?.results.map((n) => (
          <MenuItem
            key={n.id}
            onClick={() => {
              if (!n.is_read) markRead.mutate(n.id)
              setAnchor(null)
              navigate(`/tickets/${n.ticket}`)
            }}
            sx={{ whiteSpace: 'normal', alignItems: 'flex-start', bgcolor: n.is_read ? undefined : 'action.hover' }}
          >
            <ListItemText
              primary={n.message}
              secondary={formatDateTime(n.created_at)}
              slotProps={{ primary: { sx: { fontWeight: n.is_read ? 400 : 600, fontSize: 14 } } }}
            />
          </MenuItem>
        ))}
      </Menu>
    </>
  )
}
