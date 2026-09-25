import { ApiError, toApiError } from './errors'
import { tokenStorage } from './tokenStorage'

/**
 * Minimal fetch-based API client. React Query owns caching, retries and request
 * state; this layer only adds the base URL, JSON handling, the bearer token, a
 * transparent token refresh and the ApiError mapping.
 */

export const AUTH_LOGOUT_EVENT = 'auth:logout'

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api'
const TIMEOUT_MS = 15_000

type Params = Record<string, string | number | undefined>

interface RequestOptions {
  params?: Params
  signal?: AbortSignal
}

function buildUrl(path: string, params?: Params) {
  const query = new URLSearchParams()
  Object.entries(params ?? {}).forEach(([k, v]) => {
    if (v !== undefined && v !== '') query.set(k, String(v))
  })
  const qs = query.toString()
  return `${BASE_URL}${path}${qs ? `?${qs}` : ''}`
}

function withTimeout(signal?: AbortSignal) {
  const timeout = AbortSignal.timeout(TIMEOUT_MS)
  return signal && 'any' in AbortSignal ? AbortSignal.any([signal, timeout]) : (signal ?? timeout)
}

async function parse(response: Response) {
  if (response.status === 204) return undefined
  const text = await response.text()
  return text ? JSON.parse(text) : undefined
}

// Single in-flight refresh shared by every request that hits a 401 at the same time.
let refreshPromise: Promise<string> | null = null

async function refreshAccessToken(): Promise<string> {
  const refresh = tokenStorage.getRefresh()
  if (!refresh) throw new Error('No refresh token')
  const response = await fetch(buildUrl('/auth/refresh/'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh }),
  })
  if (!response.ok) throw new Error('Refresh failed')
  const { access } = (await response.json()) as { access: string }
  tokenStorage.set(access)
  return access
}

async function request<T>(
  method: 'GET' | 'POST',
  path: string,
  body: unknown,
  options: RequestOptions = {},
  retried = false,
): Promise<T> {
  const token = tokenStorage.getAccess()
  let response: Response
  try {
    response = await fetch(buildUrl(path, options.params), {
      method,
      headers: {
        Accept: 'application/json',
        ...(body !== undefined && { 'Content-Type': 'application/json' }),
        ...(token && { Authorization: `Bearer ${token}` }),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: withTimeout(options.signal),
    })
  } catch (err) {
    throw toApiError(err)
  }

  if (response.status === 401 && !retried && !path.startsWith('/auth/')) {
    try {
      refreshPromise ??= refreshAccessToken().finally(() => {
        refreshPromise = null
      })
      await refreshPromise
      return request<T>(method, path, body, options, true)
    } catch {
      tokenStorage.clear()
      window.dispatchEvent(new Event(AUTH_LOGOUT_EVENT))
    }
  }

  const data = await parse(response).catch(() => undefined)
  if (!response.ok) {
    const envelope = data?.error
    throw new ApiError(
      response.status,
      envelope?.code ?? 'error',
      envelope?.message ?? 'Something went wrong. Please try again.',
      envelope?.details,
    )
  }
  return data as T
}

export const api = {
  get: <T>(path: string, options?: RequestOptions) => request<T>('GET', path, undefined, options),
  post: <T>(path: string, body: unknown = {}, options?: RequestOptions) =>
    request<T>('POST', path, body, options),
}
