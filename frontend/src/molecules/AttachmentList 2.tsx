import InsertDriveFile from '@mui/icons-material/InsertDriveFileOutlined'
import { Box, Chip, Stack } from '@mui/material'
import type { AttachmentItem } from '@/api/types'
import { formatBytes } from '@/utils/format'

/** Images as thumbnails, videos inline, everything else as download chips. */
export default function AttachmentList({ attachments }: { attachments: AttachmentItem[] }) {
  if (!attachments.length) return null
  const images = attachments.filter((a) => a.kind === 'image')
  const videos = attachments.filter((a) => a.kind === 'video')
  const files = attachments.filter((a) => a.kind === 'file')

  return (
    <Stack spacing={1} sx={{ mt: 1 }}>
      {images.length > 0 && (
        <Stack direction="row" useFlexGap spacing={1} sx={{ flexWrap: 'wrap' }}>
          {images.map((a) => (
            <Box
              key={a.id}
              component="a"
              href={a.url}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={`Open image ${a.name}`}
              sx={{ display: 'block', borderRadius: 1, overflow: 'hidden', border: 1, borderColor: 'divider' }}
            >
              <Box
                component="img"
                src={a.url}
                alt={a.name}
                loading="lazy"
                sx={{ display: 'block', width: 120, height: 90, objectFit: 'cover' }}
              />
            </Box>
          ))}
        </Stack>
      )}
      {videos.map((a) => (
        <Box
          key={a.id}
          component="video"
          src={a.url}
          controls
          preload="metadata"
          aria-label={a.name}
          sx={{ width: '100%', maxWidth: 420, borderRadius: 1, bgcolor: 'common.black' }}
        />
      ))}
      {files.length > 0 && (
        <Stack direction="row" useFlexGap spacing={1} sx={{ flexWrap: 'wrap' }}>
          {files.map((a) => (
            <Chip
              key={a.id}
              component="a"
              href={a.url}
              clickable
              icon={<InsertDriveFile />}
              label={`${a.name} · ${formatBytes(a.size)}`}
              variant="outlined"
            />
          ))}
        </Stack>
      )}
    </Stack>
  )
}
