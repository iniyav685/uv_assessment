const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/** "27-Oct-2025 11:40 AM" — the format used throughout the wireframe. */
export function formatDateTime(iso: string): string {
  const d = new Date(iso)
  const day = String(d.getDate()).padStart(2, '0')
  const hours24 = d.getHours()
  const hours = hours24 % 12 || 12
  const minutes = String(d.getMinutes()).padStart(2, '0')
  const suffix = hours24 < 12 ? 'AM' : 'PM'
  return `${day}-${MONTHS[d.getMonth()]}-${d.getFullYear()} ${hours}:${minutes} ${suffix}`
}
