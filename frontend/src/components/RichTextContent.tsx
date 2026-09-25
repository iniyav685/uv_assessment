import { Box } from '@mui/material'
import DOMPurify from 'dompurify'
import { useMemo } from 'react'

// Mirrors the server allow-list (apps/common/richtext.py).
const ALLOWED_TAGS = [
  'p', 'br', 'strong', 'b', 'em', 'i', 'u', 's', 'code', 'pre', 'blockquote',
  'ul', 'ol', 'li', 'a', 'h2', 'h3',
]

DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node.tagName === 'A') {
    node.setAttribute('target', '_blank')
    node.setAttribute('rel', 'noopener noreferrer nofollow')
  }
})

/** Renders stored rich text. The server already sanitised it; this is defence in depth. */
export default function RichTextContent({ html }: { html: string }) {
  const clean = useMemo(
    () => DOMPurify.sanitize(html, { ALLOWED_TAGS, ALLOWED_ATTR: ['href', 'target', 'rel'] }),
    [html],
  )
  return (
    <Box
      sx={{
        typography: 'body2',
        wordBreak: 'break-word',
        '& p': { m: 0 },
        '& p + p': { mt: 0.75 },
        '& ul, & ol': { my: 0.5, pl: 3 },
        '& blockquote': { borderLeft: 3, borderColor: 'divider', m: 0, pl: 1.5, color: 'text.secondary' },
        '& code': { bgcolor: 'action.hover', px: 0.5, borderRadius: 0.5, fontSize: '0.85em' },
        '& a': { color: 'primary.main' },
      }}
      dangerouslySetInnerHTML={{ __html: clean }}
    />
  )
}
