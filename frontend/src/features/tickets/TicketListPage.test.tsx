import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import { api } from '@/services/api'
import { lookups, makeMe, makeTicket } from '@/test/fixtures'
import { renderWithProviders } from '@/test/renderWithProviders'
import { AuthContext } from '@/features/auth/AuthProvider'
import TicketListPage from '@/features/tickets/TicketListPage'

vi.mock('@/services/api', () => ({ api: { get: vi.fn(), post: vi.fn() } }))
const get = vi.mocked(api.get)

function mockApi(results = [makeTicket()], total = results.length) {
  get.mockImplementation((url: string) => {
    if (url === '/tickets/counts/') return Promise.resolve({ open: total, closed: 3 })
    if (url === '/lookups/') return Promise.resolve(lookups)
    return Promise.resolve({
      count: total,
      page: 1,
      page_size: 10,
      total_pages: Math.ceil(total / 10),
      results,
    })
  })
}

function renderPage(route = '/tickets') {
  return renderWithProviders(
    <AuthContext.Provider
      value={{ user: makeMe(), isLoading: false, login: vi.fn(), logout: vi.fn() }}
    >
      <TicketListPage />
    </AuthContext.Provider>,
    { route },
  )
}

const listCalls = () => get.mock.calls.filter(([url]) => url === '/tickets/')

describe('TicketListPage', () => {
  beforeEach(() => {
    get.mockReset()
  })

  it('renders tickets from the API with tab counts', async () => {
    mockApi([makeTicket({ action_required: true })], 1)
    renderPage()

    const card = await screen.findByRole('article', { name: 'AC not cooling' })
    expect(within(card).getByText('#TKT-1042')).toBeInTheDocument()
    expect(within(card).getByText('Action Required')).toBeInTheDocument()
    expect(within(card).getByRole('link', { name: /view ticket tkt-1042/i })).toHaveAttribute(
      'href',
      '/tickets/42',
    )
    expect(screen.getByRole('tab', { name: 'Open Tickets (1)' })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    expect(listCalls()[0][1]).toEqual({ params: { tab: 'open' } })
  })

  it('sends sorting and tab changes to the API as query params', async () => {
    mockApi()
    renderPage()
    await screen.findByRole('article', { name: 'AC not cooling' })

    await userEvent.click(screen.getByRole('button', { name: /^sort$/i }))
    await userEvent.click(screen.getByRole('menuitem', { name: /oldest first/i }))
    await waitFor(() =>
      expect(listCalls().at(-1)?.[1]).toEqual({ params: { tab: 'open', ordering: 'created_at' } }),
    )

    await userEvent.click(screen.getByRole('tab', { name: /closed tickets/i }))
    await waitFor(() =>
      expect(listCalls().at(-1)?.[1]).toEqual({
        params: { tab: 'closed', ordering: 'created_at' },
      }),
    )
  })

  it('restores filters from the URL and offers to clear them when nothing matches', async () => {
    mockApi([], 0)
    renderPage('/tickets?department=2&search=lift')

    expect(await screen.findByText('No matching tickets')).toBeInTheDocument()
    expect(listCalls()[0][1]).toEqual({
      params: { tab: 'open', search: 'lift', department: '2' },
    })
    expect(screen.getByRole('button', { name: 'Filters (1 active)' })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /clear search and filters/i }))
    await waitFor(() => expect(listCalls().at(-1)?.[1]).toEqual({ params: { tab: 'open' } }))
  })
})
