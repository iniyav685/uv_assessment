import { Avatar, Box, Chip, Paper, Stack, Tab, Tabs, Typography } from '@mui/material'
import { memo, useMemo, useState } from 'react'
import type { Activity, ActivityKind } from '../../../api/types'
import AttachmentList from '../../../components/AttachmentList'
import RichTextContent from '../../../components/RichTextContent'
import UserAvatar from '../../../components/UserAvatar'
import { formatDateTime } from '../../../utils/format'

type Filter = 'all' | 'actions' | 'comments'

const VERB_COLOR: Record<ActivityKind, string> = {
  created: 'error.main',
  auto_assigned: 'secondary.main',
  forwarded_to_department: 'secondary.main',
  assigned_technician: 'secondary.main',
  changed_department: 'warning.dark',
  changed_status: 'info.main',
  pending_client_confirmation: 'warning.main',
  resolved: 'success.main',
  closed: 'success.main',
  commented: 'text.primary',
  edited_description: 'text.primary',
}

const initialsOf = (name: string) =>
  name
    .replace(/\(.*\)/, '')
    .trim()
    .split(/\s+/)
    .map((p) => p[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()

function ActivityFeed({ activities }: { activities: Activity[] }) {
  const [filter, setFilter] = useState<Filter>('all')
  const visible = useMemo(
    () =>
      activities.filter((a) =>
        filter === 'all' ? true : filter === 'comments' ? Boolean(a.comment) : !a.is_comment,
      ),
    [activities, filter],
  )

  return (
    <Paper variant="outlined" component="section" aria-labelledby="activity-heading" sx={{ p: 2 }}>
      <Stack
        direction="row"
        spacing={1}
        useFlexGap
        sx={{ alignItems: 'center', flexWrap: 'wrap', justifyContent: 'space-between' }}
      >
        <Stack direction="row" spacing={1} sx={{ alignItems: 'baseline' }}>
          <Typography id="activity-heading" component="h2" variant="overline" sx={{ fontSize: 14 }}>
            Activity
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {activities.length} {activities.length === 1 ? 'event' : 'events'}
          </Typography>
        </Stack>
        <Tabs
          value={filter}
          onChange={(_, v: Filter) => setFilter(v)}
          aria-label="Filter activity"
          sx={{ minHeight: 36, '& .MuiTab-root': { minHeight: 36, py: 0.5 } }}
        >
          <Tab value="all" label="All" />
          <Tab value="actions" label="Actions" />
          <Tab value="comments" label="Comments" />
        </Tabs>
      </Stack>

      {visible.length === 0 ? (
        <Typography color="text.secondary" sx={{ py: 3, textAlign: 'center' }}>
          {filter === 'comments' ? 'No comments yet.' : 'Nothing to show.'}
        </Typography>
      ) : (
        <Stack component="ol" spacing={2.5} sx={{ listStyle: 'none', p: 0, m: 0, mt: 2 }}>
          {visible.map((activity) => (
            <ActivityItem key={activity.id} activity={activity} />
          ))}
        </Stack>
      )}
    </Paper>
  )
}

function ActivityItem({ activity }: { activity: Activity }) {
  const actorName = activity.actor ? activity.actor.display_name : 'System'
  const hasHistory = Boolean(activity.from_value || activity.to_value)
  const isAssignment = activity.kind === 'auto_assigned' || activity.kind === 'assigned_technician'

  return (
    <Box component="li" sx={{ display: 'flex', gap: 1.5 }}>
      <UserAvatar user={activity.actor} />
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography component="p" sx={{ lineHeight: 1.5 }}>
          <Box component="span" sx={{ fontWeight: 600 }}>
            {actorName}
          </Box>{' '}
          <Box
            component="span"
            sx={{ color: VERB_COLOR[activity.kind], fontWeight: activity.is_comment ? 400 : 600 }}
          >
            {activity.kind_label}
          </Box>
          {activity.kind === 'created' || activity.is_comment ? '' : '.'}{' '}
          <Chip
            size="small"
            variant="outlined"
            component="time"
            dateTime={activity.created_at}
            label={formatDateTime(activity.created_at)}
            sx={{ ml: 0.5, height: 22, fontSize: 12 }}
          />
        </Typography>

        {hasHistory && (
          <Stack direction="row" spacing={1} useFlexGap sx={{ mt: 0.75, alignItems: 'center', flexWrap: 'wrap' }}>
            <Chip size="small" label="History" sx={{ height: 20, fontSize: 11 }} />
            <Typography variant="body2" color="text.secondary">
              {activity.from_value}
            </Typography>
            <Typography aria-label="changed to" color="text.secondary">
              →
            </Typography>
            {isAssignment && (
              <Avatar aria-hidden sx={{ width: 22, height: 22, fontSize: 10, bgcolor: 'primary.light' }}>
                {initialsOf(activity.to_value)}
              </Avatar>
            )}
            <Typography variant="body2" sx={{ fontWeight: 600 }}>
              {activity.to_value}
            </Typography>
          </Stack>
        )}

        {activity.meta.outcome_label && (
          <Chip
            size="small"
            color="info"
            variant="outlined"
            label={`Assessment: ${activity.meta.outcome_label}`}
            sx={{ mt: 1 }}
          />
        )}

        {activity.comment && (
          <Box sx={{ mt: 1 }}>
            {!activity.is_comment && (
              <Chip size="small" label="Comment" sx={{ height: 20, fontSize: 11, mb: 0.5 }} />
            )}
            {activity.comment.body_html && (
              <Paper variant="outlined" sx={{ p: 1.25, bgcolor: 'background.default' }}>
                <RichTextContent html={activity.comment.body_html} />
              </Paper>
            )}
            <AttachmentList attachments={activity.comment.attachments} />
          </Box>
        )}
      </Box>
    </Box>
  )
}

export default memo(ActivityFeed)
