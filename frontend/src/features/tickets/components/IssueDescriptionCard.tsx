import EditOutlined from '@mui/icons-material/EditOutlined'
import { Alert, Box, Button, IconButton, Paper, Stack, Tooltip, Typography } from '@mui/material'
import { useState } from 'react'
import type { TicketDetail } from '../../../api/types'
import RichTextContent from '../../../components/RichTextContent'
import RichTextEditor from '../../../components/RichTextEditor'
import { describeActionError, NO_ERROR, type ActionErrorState } from '../actionErrors'
import { useTicketAction } from '../api'

/** Issue description, editable in place — click it (or the pencil) to switch to a rich text editor. */
export default function IssueDescriptionCard({ ticket }: { ticket: TicketDetail }) {
  const canEdit = ticket.available_actions.includes('edit_description')
  const [editing, setEditing] = useState(false)
  const [html, setHtml] = useState(ticket.description)
  const [isEmpty, setIsEmpty] = useState(!ticket.description)
  const [error, setError] = useState<ActionErrorState>(NO_ERROR)
  const save = useTicketAction(ticket.id, 'description')

  function startEditing() {
    if (!canEdit || editing) return
    setHtml(ticket.description)
    setIsEmpty(!ticket.description)
    setError(NO_ERROR)
    setEditing(true)
  }

  function cancel() {
    if (save.isPending) return
    setEditing(false)
    setError(NO_ERROR)
  }

  function submit() {
    if (save.isPending) return
    save.mutate(
      { description: isEmpty ? '' : html },
      {
        onSuccess: () => setEditing(false),
        onError: (err) => setError(describeActionError(err)),
      },
    )
  }

  return (
    <Paper variant="outlined" component="section" aria-labelledby="description-heading" sx={{ p: 2 }}>
      <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography id="description-heading" component="h2" variant="overline" sx={{ fontSize: 14 }}>
          Issue Description
        </Typography>
        {canEdit && !editing && (
          <Tooltip title="Edit description">
            <IconButton size="small" aria-label="Edit description" onClick={startEditing}>
              <EditOutlined fontSize="small" />
            </IconButton>
          </Tooltip>
        )}
      </Stack>

      {editing ? (
        <Box sx={{ mt: 1 }}>
          {error.message && (
            <Alert severity="error" sx={{ mb: 1 }}>
              {error.message}
            </Alert>
          )}
          <RichTextEditor
            ariaLabel="Issue description"
            placeholder="Describe the issue"
            content={ticket.description}
            disabled={save.isPending}
            error={Boolean(error.fields.description)}
            onChange={(value, empty) => {
              setHtml(value)
              setIsEmpty(empty)
              if (error.fields.description) setError(NO_ERROR)
            }}
            onSubmitShortcut={submit}
            sx={{ '& .tiptap': { minHeight: 100, maxHeight: 320 } }}
          />
          <Stack direction="row" spacing={1} sx={{ mt: 1, justifyContent: 'flex-end' }}>
            <Button size="small" onClick={cancel} disabled={save.isPending}>
              Cancel
            </Button>
            <Button size="small" variant="contained" onClick={submit} disabled={save.isPending}>
              {save.isPending ? 'Saving…' : 'Save'}
            </Button>
          </Stack>
        </Box>
      ) : (
        <Box
          onClick={startEditing}
          role={canEdit ? 'button' : undefined}
          tabIndex={canEdit ? 0 : undefined}
          onKeyDown={(e) => {
            if (canEdit && (e.key === 'Enter' || e.key === ' ')) {
              e.preventDefault()
              startEditing()
            }
          }}
          sx={{
            mt: 0.5,
            borderRadius: 1,
            cursor: canEdit ? 'pointer' : 'default',
            ...(canEdit && { mx: -0.5, px: 0.5, '&:hover': { bgcolor: 'action.hover' } }),
          }}
        >
          {ticket.description ? (
            <RichTextContent html={ticket.description} />
          ) : (
            <Typography color="text.secondary">
              No description provided.{canEdit && ' Click to add one.'}
            </Typography>
          )}
        </Box>
      )}
    </Paper>
  )
}
