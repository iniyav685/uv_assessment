import AttachFile from '@mui/icons-material/AttachFile'
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  FormHelperText,
  IconButton,
  Stack,
  Tooltip,
} from '@mui/material'
import { useRef, useState, type FormEvent } from 'react'
import RichTextEditor, { type RichTextEditorHandle } from '../../../components/RichTextEditor'
import { formatBytes } from '../../../utils/format'
import { describeActionError, NO_ERROR, type ActionErrorState } from '../actionErrors'
import { useTicketAction } from '../api'
import { ALLOWED_TYPES, useAttachmentUploads } from '../useAttachmentUploads'

/** Rich-text comment composer with media attachments, shown under the activity feed in the ticket modal's left column. */
export default function CommentComposer({ ticketId }: { ticketId: number }) {
  const editorRef = useRef<RichTextEditorHandle>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const [html, setHtml] = useState('')
  const [isEmpty, setIsEmpty] = useState(true)
  const [error, setError] = useState<ActionErrorState>(NO_ERROR)
  const [rejected, setRejected] = useState<string[]>([])
  const post = useTicketAction(ticketId, 'comments')
  const files = useAttachmentUploads(ticketId)

  const canPost = !post.isPending && !files.isUploading && !files.hasErrors

  function submit(e?: FormEvent) {
    e?.preventDefault()
    if (!canPost) return
    if (isEmpty && !files.attachmentIds.length) {
      setError({ fields: { body: 'Write a comment or attach a file.' }, message: null })
      return
    }
    post.mutate(
      { body: isEmpty ? '' : html, attachment_ids: files.attachmentIds },
      {
        onSuccess: () => {
          editorRef.current?.clear()
          files.reset()
          setError(NO_ERROR)
          setRejected([])
        },
        onError: (err) => setError(describeActionError(err)),
      },
    )
  }

  const attachButton = (
    <Tooltip title="Attach images, videos or PDFs (max 25 MB each)">
      <span>
        <IconButton
          size="small"
          aria-label="Attach files"
          onClick={() => fileInput.current?.click()}
          disabled={post.isPending}
        >
          <AttachFile />
        </IconButton>
      </span>
    </Tooltip>
  )

  const fieldError = error.fields.body || error.fields.attachment_ids

  return (
    <Box component="form" noValidate onSubmit={submit} aria-label="Add a comment">
      {error.message && (
        <Alert severity="error" sx={{ mb: 1 }}>
          {error.message}
        </Alert>
      )}
      <input
        ref={fileInput}
        type="file"
        hidden
        multiple
        accept={ALLOWED_TYPES.join(',')}
        onChange={(e) => {
          if (e.target.files?.length) setRejected(files.addFiles(e.target.files))
          e.target.value = '' // allow re-selecting the same file
        }}
      />

      <RichTextEditor
        ref={editorRef}
        ariaLabel="Comment"
        placeholder="Write a comment"
        error={Boolean(fieldError)}
        disabled={post.isPending}
        onChange={(value, empty) => {
          setHtml(value)
          setIsEmpty(empty)
          if (error.fields.body) setError(NO_ERROR)
        }}
        onSubmitShortcut={() => submit()}
        toolbarEnd={attachButton}
      />
      {fieldError && <FormHelperText error>{fieldError}</FormHelperText>}

      {rejected.map((msg) => (
        <FormHelperText key={msg} error>
          {msg}
        </FormHelperText>
      ))}

      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        spacing={1}
        sx={{ mt: 1, alignItems: { sm: 'center' }, justifyContent: 'space-between' }}
      >
        <Stack direction="row" useFlexGap spacing={1} sx={{ flexWrap: 'wrap', minWidth: 0 }}>
          {files.uploads.map((u) => (
            <Chip
              key={u.localId}
              size="small"
              color={u.status === 'error' ? 'error' : 'default'}
              variant={u.status === 'done' ? 'filled' : 'outlined'}
              icon={
                u.status === 'uploading' ? (
                  <CircularProgress size={14} variant="determinate" value={u.progress} />
                ) : undefined
              }
              label={
                u.status === 'error'
                  ? `${u.file.name} — ${u.error}`
                  : `${u.file.name} · ${u.status === 'uploading' ? `${u.progress}%` : formatBytes(u.file.size)}`
              }
              onDelete={() => files.remove(u.localId)}
              aria-label={`Attachment ${u.file.name}, ${u.status}`}
              sx={{ maxWidth: 280 }}
            />
          ))}
        </Stack>
        <Box sx={{ alignSelf: { xs: 'flex-end', sm: 'auto' } }}>
          <Button
            type="submit"
            variant="contained"
            disabled={!canPost}
            startIcon={post.isPending ? <CircularProgress size={16} color="inherit" /> : undefined}
          >
            {files.isUploading ? 'Uploading…' : 'Post'}
          </Button>
        </Box>
      </Stack>
    </Box>
  )
}
