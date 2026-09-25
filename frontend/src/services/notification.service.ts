import { api } from '@/services/api'
import type { NotificationItem, Paginated } from '@/api/types'

export type NotificationPage = Paginated<NotificationItem> & { unread_count: number }

// --- GET ---------------------------------------------------------------

function getNotifications(pageSize: number) {
  return api.get<NotificationPage>('/notifications/', { params: { page_size: pageSize } })
}

// --- POST ----------------------------------------------------------------

function markRead(id: number) {
  return api.post(`/notifications/${id}/read/`)
}

function markAllRead() {
  return api.post('/notifications/read-all/')
}

export const notificationService = {
  getNotifications,
  markRead,
  markAllRead,
}
