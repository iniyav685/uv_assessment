import { api } from '@/services/api'

export interface PresignAttachmentPayload {
  filename: string
  content_type: string
  size: number
}

export interface PresignAttachmentResponse {
  id: string
  upload: { url: string; fields: Record<string, string> }
}

// --- POST ----------------------------------------------------------------

function presignUpload(
  ticketId: number,
  payload: PresignAttachmentPayload,
  signal?: AbortSignal,
) {
  return api.post<PresignAttachmentResponse>(`/tickets/${ticketId}/attachments/`, payload, {
    signal,
  })
}

export const attachmentService = {
  presignUpload,
}
