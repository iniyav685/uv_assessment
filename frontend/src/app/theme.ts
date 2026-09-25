import { createTheme } from '@mui/material/styles'

export const theme = createTheme({
  palette: {
    mode: 'light',
    primary: { main: '#1f5eff' },
    secondary: { main: '#7b3fe4' },
    success: { main: '#2e7d32' },
    background: { default: '#f6f7f9' },
  },
  shape: { borderRadius: 8 },
  typography: {
    fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
    h1: { fontSize: '1.75rem', fontWeight: 600 },
    h2: { fontSize: '1.375rem', fontWeight: 600 },
    button: { textTransform: 'none', fontWeight: 600 },
  },
  components: {
    MuiButton: { defaultProps: { disableElevation: true } },
    MuiCssBaseline: {
      styleOverrides: {
        '.skip-link': {
          position: 'absolute',
          left: 8,
          top: -48,
          zIndex: 2000,
          padding: '8px 12px',
          background: '#1f5eff',
          color: '#fff',
          borderRadius: 4,
        },
        '.skip-link:focus': { top: 8 },
      },
    },
  },
})
