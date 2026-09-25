import { Box, CircularProgress, Typography } from '@mui/material'

export default function LoadingState({ label = 'Loading' }: { label?: string }) {
  return (
    <Box
      role="status"
      aria-live="polite"
      sx={{ py: 8, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}
    >
      <CircularProgress aria-hidden />
      <Typography color="text.secondary">{label}…</Typography>
    </Box>
  )
}
