import { Paper, Typography } from '@mui/material'
import type { ReactNode } from 'react'

interface Props {
  message: string
  children: ReactNode
}

export default function PanelShell({ message, children }: Props) {
  return (
    <Paper
      variant="outlined"
      component="section"
      aria-label="Actions"
      sx={{ p: 2, bgcolor: 'action.hover', textAlign: 'center' }}
    >
      <Typography sx={{ fontWeight: 600, mb: 1.5 }}>{message}</Typography>
      {children}
    </Paper>
  )
}
