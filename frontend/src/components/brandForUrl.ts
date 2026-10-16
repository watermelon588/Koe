import type { Brand } from './BrandIcon'

export function brandForUrl(value: string | null | undefined): Brand | null {
  if (!value) return null
  try {
    const url = new URL(value), host = url.hostname
    if (host === 'github.com') return 'github'
    if (host === 'meet.google.com') return 'meet'
    if (host === 'notion.so' || host === 'www.notion.so' || host === 'notion.site' || host.endsWith('.notion.site')) return 'notion'
    if (host === 'calendar.google.com' || (host === 'www.google.com' && url.pathname.startsWith('/calendar'))) return 'calendar'
    if (host === 'docs.google.com') return url.pathname.startsWith('/spreadsheets') ? 'sheets' : 'docs'
    if (host === 'open.spotify.com') return 'spotify'
  } catch { /* Only already validated provider links reach the UI. */ }
  return null
}
