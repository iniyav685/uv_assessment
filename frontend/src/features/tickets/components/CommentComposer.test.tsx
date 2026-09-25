import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import { api } from '@/services/api'
import { uploadToStorage } from '@/api/uploadToStorage'
import { makeDetail } from '@/test/fixtures'
import { renderWithProviders } from '@/test/renderWithProviders'
import CommentComposer from '@/features/tickets/components/CommentComposer'

vi.mock('@/services/api', () => ({ api: { get: vi.fn(), post: vi.fn() } }))
vi.mock('../../../api/uploadToStorage', () => ({ uploadToStorage: vi.fn() }))

const apiPost = vi.mocked(api.post)
const storagePost = vi.mocked(uploadToStorage)

function fileInput() {
  return document.querySelector('input[type="file"]') as HTMLInputElement
}

describe('CommentComposer', () => {
  beforeEach(() => {
    apiPost.mockReset()
    storagePost.mockReset()
  })

  it('rejects unsupported file types without uploading', async () => {
    renderWithProviders(<CommentComposer ticketId={42} />)
    const exe = new File(['x'], 'setup.exe', { type: 'application/x-msdownload' })

    await userEvent.upload(fileInput(), exe, { applyAccept: false })

    expect(screen.getByText(/setup\.exe: only images, videos/i)).toBeInTheDocument()
    expect(apiPost).not.toHaveBeenCalled()
  })

  it('uploads directly to storage (not via the API), then posts the attachment id', async () => {
    let finishUpload!: () => void
    apiPost.mockImplementation((url: string) =>
      url.endsWith('/attachments/')
        ? Promise.resolve({
            id: 'att-1',
            upload: { url: 'http://s3.test/bucket', fields: { key: 'tickets/42/a/photo.png' } },
          })
        : Promise.resolve(makeDetail()),
    )
    storagePost.mockImplementation(
      () => new Promise<void>((resolve) => (finishUpload = () => resolve())),
    )

    renderWithProviders(<CommentComposer ticketId={42} />)
    const photo = new File(['png'], 'photo.png', { type: 'image/png' })
    await userEvent.upload(fileInput(), photo)

    // Posting is blocked while the file is still uploading.
    const post = await screen.findByRole('button', { name: 'Uploading…' })
    expect(post).toBeDisabled()
    await waitFor(() => expect(storagePost).toHaveBeenCalledTimes(1))
    const [url, form] = storagePost.mock.calls[0]
    expect(url).toBe('http://s3.test/bucket')
    expect(form.get('key')).toBe('tickets/42/a/photo.png')
    expect(form.get('file')).toBe(photo)

    finishUpload()
    await userEvent.click(await screen.findByRole('button', { name: 'Post' }))

    await waitFor(() =>
      expect(apiPost).toHaveBeenCalledWith('/tickets/42/comments/', {
        body: '',
        attachment_ids: ['att-1'],
      }),
    )
  })
})
