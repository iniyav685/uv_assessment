import { api } from '@/services/api'
import type { Me, Role } from '@/api/types'

export interface LoginPayload {
  username: string
  password: string
}

export interface LoginResponse {
  access: string
  refresh: string
}

export interface DemoAccounts {
  enabled: boolean
  password?: string
  accounts: { username: string; display_name: string; role: Role; role_label: string }[]
}

// --- GET ---------------------------------------------------------------

function getMe() {
  return api.get<Me>('/auth/me/')
}

function getDemoAccounts() {
  return api.get<DemoAccounts>('/auth/demo-accounts/')
}

// --- POST ----------------------------------------------------------------

function login(payload: LoginPayload) {
  return api.post<LoginResponse>('/auth/login/', payload)
}

export const authService = {
  getMe,
  getDemoAccounts,
  login,
}
