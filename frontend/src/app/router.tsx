import { createBrowserRouter, Navigate } from 'react-router'
import AppLayout from '../components/AppLayout'
import NotFoundPage from '../components/NotFoundPage'
import LoginPage from '../features/auth/LoginPage'
import RequireAuth from '../features/auth/RequireAuth'
import TicketListPage from '../features/tickets/TicketListPage'

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    element: (
      <RequireAuth>
        <AppLayout />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <Navigate to="/tickets" replace /> },
      {
        path: 'tickets',
        // A ticket opens as an accordion card in place, within the list (Jira-style);
        // both routes render the same page, which expands the :id ticket if present.
        children: [
          { index: true, element: <TicketListPage /> },
          { path: ':id', element: <TicketListPage /> },
        ],
      },
    ],
  },
  { path: '*', element: <NotFoundPage /> },
])
