import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router'
import LoadingState from '@/atoms/LoadingState'
import { useAuth } from '@/features/auth/useAuth'

export default function RequireAuth({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) return <LoadingState label="Loading your session" />
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />
  return children
}
