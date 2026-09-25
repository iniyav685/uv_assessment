import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { AuthContext, type AuthContextValue } from './AuthProvider'
import LoginPage from './LoginPage'

function renderLogin(login: AuthContextValue['login']) {
  const value: AuthContextValue = { user: null, isLoading: false, login, logout: vi.fn() }
  return renderWithProviders(
    <AuthContext.Provider value={value}>
      <LoginPage />
    </AuthContext.Provider>,
    { route: '/login' },
  )
}

describe('LoginPage', () => {
  it('shows validation errors and does not call the API when fields are empty', async () => {
    const login = vi.fn()
    renderLogin(login)

    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

    expect(screen.getByText('Username is required')).toBeInTheDocument()
    expect(screen.getByText('Password is required')).toBeInTheDocument()
    expect(login).not.toHaveBeenCalled()
  })

  it('disables the submit button while the request is in flight', async () => {
    let resolve!: () => void
    const login = vi.fn(() => new Promise<void>((r) => (resolve = r)))
    renderLogin(login)

    await userEvent.type(screen.getByLabelText(/username/i), 'agent1')
    await userEvent.type(screen.getByLabelText(/password/i), 'secret')
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }))

    expect(screen.getByRole('button', { name: /signing in/i })).toBeDisabled()
    expect(login).toHaveBeenCalledTimes(1)
    resolve()
  })
})
