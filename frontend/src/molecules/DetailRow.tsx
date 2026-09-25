import { Box, Typography } from '@mui/material'
import type { ReactNode } from 'react'

interface Props {
  label: string
  children: ReactNode
}

/** One label/value pair in a `<dl>`-based details grid. */
export default function DetailRow({ label, children }: Props) {
  return (
    <>
      <Typography component="dt" variant="body2" color="text.secondary">
        {label}
      </Typography>
      <Box component="dd" sx={{ m: 0, minWidth: 0 }}>
        {children}
      </Box>
    </>
  )
}
