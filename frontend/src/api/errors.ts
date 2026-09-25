export type FieldErrors = Record<string, string[]>

/** Mirrors the backend envelope: { error: { code, message, details? } } */
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details?: FieldErrors

  constructor(status: number, code: string, message: string, details?: FieldErrors) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }

  get isValidation() {
    return this.status === 400 && this.code === 'validation_error'
  }
  get isUnauthorized() {
    return this.status === 401
  }
  get isForbidden() {
    return this.status === 403
  }
  get isNotFound() {
    return this.status === 404
  }
}

export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error
  if (error instanceof DOMException && error.name === 'TimeoutError') {
    return new ApiError(0, 'timeout', 'The server took too long to respond. Please try again.')
  }
  if (error instanceof DOMException && error.name === 'AbortError') {
    return new ApiError(0, 'aborted', 'The request was cancelled.')
  }
  if (error instanceof TypeError) {
    // fetch rejects with TypeError when the network is unreachable.
    return new ApiError(0, 'network_error', 'Unable to reach the server. Check your connection.')
  }
  return new ApiError(0, 'unknown_error', 'Something went wrong. Please try again.')
}
