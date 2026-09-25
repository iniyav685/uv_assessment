import { Alert, AlertTitle, Button } from '@mui/material'
import { toApiError } from '../api/errors'

interface Props {
  error: unknown
  onRetry?: () => void
}

/** Maps API errors to user-facing copy for permission, not-found and unexpected failures. */
export default function ErrorState({ error, onRetry }: Props) {
  const apiError = toApiError(error)

  let title = 'Something went wrong'
  let message = apiError.message
  if (apiError.isForbidden) {
    title = 'Access denied'
    message = "You don't have permission to view this."
  } else if (apiError.isNotFound) {
    title = 'Not found'
    message = "We couldn't find what you were looking for."
  }

  const canRetry = onRetry && !apiError.isForbidden && !apiError.isNotFound

  return (
    <Alert
      severity={apiError.isForbidden ? 'warning' : 'error'}
      role="alert"
      sx={{ my: 2 }}
      action={
        canRetry ? (
          <Button color="inherit" size="small" onClick={onRetry}>
            Retry
          </Button>
        ) : undefined
      }
    >
      <AlertTitle>{title}</AlertTitle>
      {message}
    </Alert>
  )
}
