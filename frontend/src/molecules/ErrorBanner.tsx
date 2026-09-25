import { Alert } from '@mui/material'

interface Props {
  message: string | null
}

export default function ErrorBanner({ message }: Props) {
  if (!message) return null
  return (
    <Alert severity="error" role="alert" sx={{ mb: 1.5, textAlign: 'left' }}>
      {message}
    </Alert>
  )
}
