import { useCallback, useEffect, useRef, useState } from 'react'
import { toApiError } from '@/api/errors'
import { uploadToStorage } from '@/api/uploadToStorage'
import { attachmentService } from '@/services/attachment.service'

// Mirrors the server allow-list (settings.ATTACHMENT_ALLOWED_TYPES).
export const ALLOWED_TYPES = [
  'image/jpeg', 'image/png', 'image/webp', 'image/gif',
  'video/mp4', 'video/webm', 'video/quicktime',
  'application/pdf',
]
export const MAX_BYTES = 25 * 1024 * 1024
export const MAX_FILES = 10

export interface PendingUpload {
  localId: string
  file: File
  progress: number
  status: 'uploading' | 'done' | 'error'
  attachmentId?: string
  error?: string
}

/**
 * Two-step upload: ask the API for a presigned POST, then send the file
 * straight to S3/MinIO (never through Django). The attachment id is later
 * submitted with the comment, which is when the server links it.
 */
export function useAttachmentUploads(ticketId: number) {
  const [uploads, setUploads] = useState<PendingUpload[]>([])
  const controllers = useRef(new Map<string, AbortController>())

  const patch = useCallback((localId: string, changes: Partial<PendingUpload>) => {
    setUploads((list) => list.map((u) => (u.localId === localId ? { ...u, ...changes } : u)))
  }, [])

  const start = useCallback(
    async (item: PendingUpload) => {
      const controller = new AbortController()
      controllers.current.set(item.localId, controller)
      try {
        const data = await attachmentService.presignUpload(
          ticketId,
          { filename: item.file.name, content_type: item.file.type, size: item.file.size },
          controller.signal,
        )
        const form = new FormData()
        Object.entries(data.upload.fields).forEach(([k, v]) => form.append(k, v))
        form.append('file', item.file) // must be the last field for S3
        await uploadToStorage(data.upload.url, form, {
          signal: controller.signal,
          onProgress: (progress) => patch(item.localId, { progress }),
        })
        patch(item.localId, { status: 'done', progress: 100, attachmentId: data.id })
      } catch (err) {
        if (controller.signal.aborted) return
        const apiError = toApiError(err)
        const detail = apiError.details && Object.values(apiError.details)[0]?.[0]
        patch(item.localId, { status: 'error', error: detail ?? 'Upload failed. Remove and try again.' })
      } finally {
        controllers.current.delete(item.localId)
      }
    },
    [ticketId, patch],
  )

  /** Validates, queues and starts uploads. Returns messages for rejected files. */
  const addFiles = useCallback(
    (files: FileList | File[]): string[] => {
      const rejected: string[] = []
      const accepted: PendingUpload[] = []
      const room = MAX_FILES - uploads.length
      Array.from(files).forEach((file, i) => {
        if (i >= room) rejected.push(`${file.name}: at most ${MAX_FILES} files per comment.`)
        else if (!ALLOWED_TYPES.includes(file.type))
          rejected.push(`${file.name}: only images, videos (MP4/WebM/MOV) and PDFs are allowed.`)
        else if (file.size > MAX_BYTES) rejected.push(`${file.name}: files must be under 25 MB.`)
        else accepted.push({ localId: crypto.randomUUID(), file, progress: 0, status: 'uploading' })
      })
      if (accepted.length) {
        setUploads((list) => [...list, ...accepted])
        accepted.forEach(start)
      }
      return rejected
    },
    [uploads.length, start],
  )

  const remove = useCallback((localId: string) => {
    controllers.current.get(localId)?.abort()
    setUploads((list) => list.filter((u) => u.localId !== localId))
  }, [])

  const reset = useCallback(() => setUploads([]), [])

  // Abort in-flight uploads if the composer unmounts (e.g. navigating away).
  useEffect(() => {
    const map = controllers.current
    return () => map.forEach((c) => c.abort())
  }, [])

  return {
    uploads,
    addFiles,
    remove,
    reset,
    isUploading: uploads.some((u) => u.status === 'uploading'),
    hasErrors: uploads.some((u) => u.status === 'error'),
    attachmentIds: uploads.filter((u) => u.status === 'done').map((u) => u.attachmentId!),
  }
}
