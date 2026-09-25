import { ApiError } from '@/api/errors'

/**
 * POSTs a multipart form straight to object storage (a presigned S3 POST).
 * Uses XMLHttpRequest because fetch cannot report upload progress. No API
 * credentials are attached — the presigned policy is the authorisation.
 */
export function uploadToStorage(
  url: string,
  form: FormData,
  { onProgress, signal }: { onProgress?: (percent: number) => void; signal?: AbortSignal } = {},
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', url)
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress?.(Math.round((e.loaded / e.total) * 100))
    }
    xhr.onload = () =>
      xhr.status >= 200 && xhr.status < 300
        ? resolve()
        : reject(new ApiError(xhr.status, 'upload_failed', 'The file could not be uploaded.'))
    xhr.onerror = () =>
      reject(new ApiError(0, 'network_error', 'Upload failed. Check your connection.'))
    xhr.onabort = () => reject(new DOMException('Upload cancelled', 'AbortError'))
    signal?.addEventListener('abort', () => xhr.abort(), { once: true })
    xhr.send(form)
  })
}
