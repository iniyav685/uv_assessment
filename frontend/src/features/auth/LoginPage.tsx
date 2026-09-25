import { Alert, Box, Button, CircularProgress, Paper, Stack, TextField, Typography } from '@mui/material'
import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router'
import { toApiError } from '../../api/errors'
import DemoAccounts from './DemoAccounts'
import { useAuth } from './useAuth'

type Errors = Partial<Record<'username' | 'password', string>>

export default function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: Location } | null)?.from?.pathname ?? '/tickets'

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<Errors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (user) return <Navigate to={from} replace />

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (submitting) return

    const next: Errors = {}
    if (!username.trim()) next.username = 'Username is required'
    if (!password) next.password = 'Password is required'
    setErrors(next)
    if (Object.keys(next).length) return

    setSubmitting(true)
    setFormError(null)
    try {
      await login({ username: username.trim(), password })
      navigate(from, { replace: true })
    } catch (err) {
      const apiError = toApiError(err)
      setFormError(
        apiError.isUnauthorized ? 'Invalid username or password.' : apiError.message,
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Box
      component="main"
      sx={{ minHeight: '100dvh', display: 'grid', placeItems: 'center', px: 2 }}
    >
      <Paper variant="outlined" sx={{ p: { xs: 3, sm: 4 }, width: '100%', maxWidth: 440 }}>
        <Stack component="form" spacing={2} noValidate onSubmit={handleSubmit}>
          <Typography variant="h1" component="h1">
            Sign in
          </Typography>
          {formError && (
            <Alert severity="error" role="alert">
              {formError}
            </Alert>
          )}
          <TextField
            label="Username"
            name="username"
            autoComplete="username"
            autoFocus
            required
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            error={Boolean(errors.username)}
            helperText={errors.username}
          />
          <TextField
            label="Password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            error={Boolean(errors.password)}
            helperText={errors.password}
          />
          <Button
            type="submit"
            variant="contained"
            size="large"
            disabled={submitting}
            startIcon={submitting ? <CircularProgress size={18} color="inherit" /> : undefined}
          >
            {submitting ? 'Signing in…' : 'Sign in'}
          </Button>
        </Stack>
        <DemoAccounts
          onPick={(u, p) => {
            setUsername(u)
            setPassword(p)
            setErrors({})
            setFormError(null)
          }}
        />
      </Paper>
    </Box>
  )
}
