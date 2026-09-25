import { Button, CircularProgress } from '@mui/material'

interface Props {
  pending: boolean
  label: string
}

export default function SubmitButton({ pending, label }: Props) {
  return (
    <Button
      type="submit"
      variant="contained"
      color="success"
      disabled={pending}
      startIcon={pending ? <CircularProgress size={16} color="inherit" /> : undefined}
      sx={{ minWidth: 88, flexShrink: 0 }}
    >
      {pending ? 'Saving…' : label}
    </Button>
  )
}
