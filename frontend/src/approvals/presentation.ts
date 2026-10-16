export type ActionDisplay = { title: string; lines: string[]; url?: string }
export type ReviewAction = { summary: string; display?: ActionDisplay }

const HOSTS = new Set(['calendar.google.com', 'www.google.com', 'docs.google.com', 'github.com',
  'notion.so', 'www.notion.so', 'app.notion.com'])
export function providerLink(value?: string): string {
  try {
    const url = new URL(value || '')
    return url.protocol === 'https:' && HOSTS.has(url.hostname) && !url.username && !url.password && !url.port ? value! : ''
  } catch { return '' }
}

// Only remove the exact duplicate appended by text_agent._reply; the original message stays stored intact.
export function approvalMessageText(value: string, action?: ReviewAction): string {
  const suffix = action && `\nPending: ${action.summary}. Confirm with yes or cancel with no.`
  return suffix && value.endsWith(suffix) ? value.slice(0, -suffix.length) : value
}
