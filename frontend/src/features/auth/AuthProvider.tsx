import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { AUTH_LOGOUT_EVENT } from '@/services/api'
import { tokenStorage } from '@/api/tokenStorage'
import type { Me as User } from '@/api/types'
import { authService, type LoginPayload } from '@/services/auth.service'

export interface AuthContextValue {
  user: User | null
  isLoading: boolean
  login: (payload: LoginPayload) => Promise<void>
  logout: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export const ME_QUERY_KEY = ['auth', 'me'] as const

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [hasToken, setHasToken] = useState(() => Boolean(tokenStorage.getAccess()))

  const meQuery = useQuery({
    queryKey: ME_QUERY_KEY,
    queryFn: authService.getMe,
    enabled: hasToken,
    staleTime: Infinity,
  })

  const logout = useCallback(() => {
    tokenStorage.clear()
    setHasToken(false)
    queryClient.clear()
  }, [queryClient])

  useEffect(() => {
    window.addEventListener(AUTH_LOGOUT_EVENT, logout)
    return () => window.removeEventListener(AUTH_LOGOUT_EVENT, logout)
  }, [logout])

  const login = useCallback(
    async (payload: LoginPayload) => {
      const tokens = await authService.login(payload)
      tokenStorage.set(tokens.access, tokens.refresh)
      const me = await authService.getMe()
      queryClient.setQueryData(ME_QUERY_KEY, me)
      setHasToken(true)
    },
    [queryClient],
  )

  const value = useMemo<AuthContextValue>(
    () => ({
      user: hasToken ? (meQuery.data ?? null) : null,
      isLoading: hasToken && meQuery.isPending,
      login,
      logout,
    }),
    [hasToken, meQuery.data, meQuery.isPending, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
