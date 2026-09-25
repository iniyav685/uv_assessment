import { Stack, Typography } from '@mui/material'
import type { ReactNode } from 'react'

export default function PageHeader({ title, actions }: { title: string; actions?: ReactNode }) {
  return (
    <Stack
      direction={{ xs: 'column', sm: 'row' }}
      spacing={2}
      sx={{ mb: 3, justifyContent: 'space-between', alignItems: { xs: 'stretch', sm: 'center' } }}
    >
      <Typography variant="h1" component="h1">
        {title}
      </Typography>
      {actions}
    </Stack>
  )
}
