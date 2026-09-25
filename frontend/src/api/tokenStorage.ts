const ACCESS_KEY = 'helpdesk.access'
const REFRESH_KEY = 'helpdesk.refresh'

// Storage can throw (private mode, blocked site data); treat failures as "no token".
function read(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function write(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key)
    else localStorage.setItem(key, value)
  } catch {
    /* ignore */
  }
}

export const tokenStorage = {
  getAccess: () => read(ACCESS_KEY),
  getRefresh: () => read(REFRESH_KEY),
  set(access: string, refresh?: string) {
    write(ACCESS_KEY, access)
    if (refresh) write(REFRESH_KEY, refresh)
  },
  clear() {
    write(ACCESS_KEY, null)
    write(REFRESH_KEY, null)
  },
}
