import { api } from '../../api/client'
import type { Me as User, Role } from '../../api/types'

export interface LoginPayload {
  username: string
  password: string
}

export interface DemoAccounts {
  enabled: boolean
  password?: string
  accounts: { username: string; display_name: string; role: Role; role_label: string }[]
}

export const authApi = {
  login: (payload: LoginPayload) =>
    api.post<{ access: string; refresh: string }>('/auth/login/', payload),
  me: () => api.get<User>('/auth/me/'),
  demoAccounts: () => api.get<DemoAccounts>('/auth/demo-accounts/'),
}
