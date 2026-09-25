import { AppBar, Box, Button, Chip, Container, Toolbar, Typography } from '@mui/material'
import { Link, Outlet } from 'react-router'
import { useAuth } from '@/features/auth/useAuth'
import NotificationsBell from '@/features/notifications/NotificationsBell'

export default function AppLayout() {
  const { user, logout } = useAuth()

  return (
    <Box sx={{ minHeight: '100dvh', display: 'flex', flexDirection: 'column' }}>
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <AppBar
        position="sticky"
        color="default"
        elevation={0}
        sx={{ borderBottom: 1, borderColor: 'divider', bgcolor: 'background.paper' }}
      >
        <Toolbar component="nav" aria-label="Main" sx={{ gap: 1 }}>
          <Typography
            component={Link}
            to="/tickets"
            variant="h6"
            sx={{ color: 'inherit', textDecoration: 'none', flexGrow: 1, fontWeight: 700 }}
          >
            Helpdesk
          </Typography>
          {user && (
            <>
              <Box sx={{ display: { xs: 'none', sm: 'flex' }, alignItems: 'center', gap: 1 }}>
                <Typography variant="body2">{user.full_name}</Typography>
                <Chip size="small" label={user.title || user.role_label} />
              </Box>
              <NotificationsBell />
              <Button onClick={logout} color="inherit">
                Sign out
              </Button>
            </>
          )}
        </Toolbar>
      </AppBar>
      <Container
        component="main"
        id="main"
        tabIndex={-1}
        maxWidth="lg"
        sx={{ py: { xs: 2, sm: 3 }, flexGrow: 1, outline: 'none' }}
      >
        <Outlet />
      </Container>
    </Box>
  )
}
