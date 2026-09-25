import InboxOutlined from '@mui/icons-material/InboxOutlined'
import { Box, Typography } from '@mui/material'
import type { ReactNode } from 'react'

interface Props {
  title: string
  description?: string
  action?: ReactNode
}

export default function EmptyState({ title, description, action }: Props) {
  return (
    <Box sx={{ py: 8, textAlign: 'center' }}>
      <InboxOutlined sx={{ fontSize: 48, color: 'text.disabled' }} aria-hidden />
      <Typography variant="h2" component="p" sx={{ mt: 1 }}>
        {title}
      </Typography>
      {description && (
        <Typography color="text.secondary" sx={{ mt: 1 }}>
          {description}
        </Typography>
      )}
      {action && <Box sx={{ mt: 3 }}>{action}</Box>}
    </Box>
  )
}
