import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import { api } from '@/services/api'
import { lookups, makeDetail } from '@/test/fixtures'
import { renderWithProviders } from '@/test/renderWithProviders'
import AssigneePicker from '@/features/tickets/components/AssigneePicker'

vi.mock('@/services/api', () => ({ api: { get: vi.fn(), post: vi.fn() } }))
const get = vi.mocked(api.get)
const post = vi.mocked(api.post)

const prakash = lookups.technicians[0]

describe('AssigneePicker', () => {
  beforeEach(() => {
    get.mockReset()
    post.mockReset()
  })

  it('is read-only for users who cannot assign', () => {
    renderWithProviders(<AssigneePicker ticket={makeDetail({ available_actions: ['comment'] })} />)
    expect(screen.getByText('Unassigned')).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('lets the POC search technicians and assign one', async () => {
    get.mockResolvedValue({ results: [prakash], current_id: null })
    post.mockResolvedValue(makeDetail({ technician: prakash }))
    renderWithProviders(
      <AssigneePicker ticket={makeDetail({ available_actions: ['assign_worker', 'comment'] })} />,
    )

    await userEvent.click(screen.getByRole('button', { name: /assignee: unassigned/i }))
    await userEvent.type(screen.getByRole('textbox', { name: 'Search technicians' }), 'prak')

    // Search is debounced and done server-side.
    await waitFor(() =>
      expect(get).toHaveBeenLastCalledWith('/tickets/42/assignable-users/', {
        params: { search: 'prak' },
        signal: expect.any(AbortSignal),
      }),
    )
    await userEvent.click(await screen.findByRole('button', { name: /Prakash Kumar/ }))

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/tickets/42/assign-worker/', { technician_id: 8 }),
    )
  })
})
