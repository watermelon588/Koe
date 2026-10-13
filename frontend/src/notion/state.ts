export function notionLink(value: string): string | undefined {
  try {
    const u = new URL(value)
    return u.protocol === 'https:' && !u.username && !u.password &&
      (['notion.so', 'www.notion.so', 'notion.com', 'www.notion.com', 'notion.site', 'www.notion.site'].includes(u.hostname)
        || u.hostname.endsWith('.notion.site')) ? u.href : undefined
  } catch { return undefined }
}

export function localDate() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export function inputDate(value: string, meeting: boolean) {
  if (!meeting) return value.slice(0, 10)
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? '' : new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}
