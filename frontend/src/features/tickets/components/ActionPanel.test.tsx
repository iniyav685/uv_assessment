import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import { api } from '@/services/api'
import { ApiError } from '@/api/errors'
import { lookups, makeDetail } from '@/test/fixtures'
import { renderWithProviders } from '@/test/renderWithProviders'
import ActionPanel from '@/features/tickets/components/ActionPanel'

vi.mock('@/services/api', () => ({ api: { get: vi.fn(), post: vi.fn() } }))
const post = vi.mocked(api.post)

function renderPanel(ticket = makeDetail()) {
  return renderWithProviders(
    <ActionPanel ticket={ticket} lookups={lookups} justCreated={false} onLeftQueue={vi.fn()} />,
  )
}

describe('ActionPanel', () => {
  beforeEach(() => {
    post.mockReset()
  })

  it('renders nothing for users without actions (e.g. facility manager)', () => {
    const { container } = renderPanel(makeDetail({ available_actions: ['comment'] }))
    expect(container).toBeEmptyDOMElement()
  })

  it('lets the department POC assign a worker, validating the selection first', async () => {
    post.mockResolvedValue(makeDetail({ status: 'pending_technician_assessment' }))
    renderPanel(makeDetail({ available_actions: ['assign_worker', 'change_department', 'comment'] }))

    expect(screen.getByText(/a new ticket has been assigned to you/i)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Assign Worker' }))
    await userEvent.click(screen.getByRole('button', { name: 'Ok' }))
    expect(screen.getByText('Select a worker.')).toBeInTheDocument()
    expect(post).not.toHaveBeenCalled()

    await userEvent.click(screen.getByRole('combobox', { name: /select worker/i }))
    await userEvent.click(screen.getByRole('option', { name: 'Prakash Kumar (Technician)' }))
    await userEvent.click(screen.getByRole('button', { name: 'Ok' }))

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/tickets/42/assign-worker/', { technician_id: 8 }),
    )
  })

  it('requires a comment when the technician reports a partial resolution', async () => {
    renderPanel(
      makeDetail({ status: 'pending_technician_assessment', available_actions: ['submit_assessment', 'comment'] }),
    )

    await userEvent.click(screen.getByRole('button', { name: 'Submit Assessment' }))
    await userEvent.click(screen.getByRole('radio', { name: /mark partially resolved/i }))
    await userEvent.click(screen.getByRole('button', { name: 'Submit' }))

    expect(screen.getByText(/explain what is pending/i)).toBeInTheDocument()
    expect(post).not.toHaveBeenCalled()
  })

  it('shows the server message when a transition is rejected', async () => {
    const rejection = new ApiError(
      409,
      'invalid_transition',
      "Cannot submit an assessment while the ticket is 'Closed'.",
    )
    post.mockImplementation(() => Promise.reject(rejection))
    renderPanel(
      makeDetail({ status: 'pending_technician_assessment', available_actions: ['submit_assessment', 'comment'] }),
    )

    await userEvent.click(screen.getByRole('button', { name: 'Submit Assessment' }))
    await userEvent.click(screen.getByRole('radio', { name: /mark fully resolved/i }))
    await userEvent.click(screen.getByRole('button', { name: 'Submit' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/while the ticket is 'Closed'/)
    expect(post).toHaveBeenCalledTimes(1)
  })
})
