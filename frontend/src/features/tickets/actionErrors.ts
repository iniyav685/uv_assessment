import { toApiError } from '../../api/errors'

export interface ActionErrorState {
  fields: Record<string, string>
  message: string | null
}

/** Splits an API error into per-field messages and a banner message. */
export function describeActionError(error: unknown): ActionErrorState {
  const apiError = toApiError(error)
  if (apiError.isValidation && apiError.details) {
    const fields: Record<string, string> = {}
    let message: string | null = null
    for (const [key, messages] of Object.entries(apiError.details)) {
      if (key === 'non_field_errors') message = messages[0]
      else fields[key] = messages[0]
    }
    return { fields, message }
  }
  // 403 (not allowed) and 409 (invalid transition) carry a precise server message.
  return { fields: {}, message: apiError.message }
}

export const NO_ERROR: ActionErrorState = { fields: {}, message: null }
