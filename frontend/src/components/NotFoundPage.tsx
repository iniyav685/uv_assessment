import { Button, Container } from '@mui/material'
import { Link } from 'react-router'
import EmptyState from '@/molecules/EmptyState'

export default function NotFoundPage() {
  return (
    <Container component="main" maxWidth="sm">
      <EmptyState
        title="Page not found"
        description="The page you're looking for doesn't exist."
        action={
          <Button component={Link} to="/" variant="contained">
            Go home
          </Button>
        }
      />
    </Container>
  )
}
