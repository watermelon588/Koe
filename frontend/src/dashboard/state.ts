import { providerLink, type ActionDisplay } from '../approvals/presentation.ts'
export type Approval = { id: string; summary: string; display?: ActionDisplay; expires_ts: string; session_id?: string; channel?: string }
export type CalendarEvent = { id: string; title: string; start: { dateTime?: string; date?: string }; end: { dateTime?: string; date?: string }; url?: string }
export type PullRequest = { repo: string; number: number; title: string; url?: string; ci?: string; review?: string; conflicts?: string; draft?: boolean }
export type Panel = { ts: string; date: string; timezone: string; result: { error?: { message: string }; events?: CalendarEvent[]; prs?: PullRequest[] } }
export type Activity = { id: string; ts: string; type?: string; kind?: string; summary?: string; channel?: string; session_id?: string;
  name?: string; phase?: string; ok?: boolean; ms?: number; action?: Approval; display?: ActionDisplay; audit_summary?: string; url?: string;
  result?: { status?: string; summary?: string; display?: ActionDisplay; url?: string; error?: { message: string } } & Record<string, unknown> }
export type Metric = { id: string; ts: string; ms: number }
export type DashboardState = { panels: Record<string, Panel>; activity: Activity[]; pending: Approval[]; latencies: Metric[]; storage: string }
export const emptyState: DashboardState = { panels: {}, activity: [], pending: [], latencies: [], storage: '' }
type Event = Activity & { panels?: Record<string, Panel>; activity?: Activity[]; pending?: Approval[]; latencies?: Metric[];
  storage?: string; name?: string; date?: string; timezone?: string; action_id?: string; clear?: boolean }

export function reduceEvent(state: DashboardState, event: Event): DashboardState {
  if (event.type === 'snapshot') return { panels: event.panels ?? {}, activity: event.activity ?? [],
    pending: event.pending ?? [], latencies: event.latencies ?? [], storage: event.storage ?? '' }
  if (event.type === 'panel' && event.name) return { ...state, panels: { ...state.panels, [event.name]: event as unknown as Panel } }
  if (event.type === 'latency' && typeof event.ms === 'number') return { ...state,
    latencies: [...state.latencies.filter((m) => m.id !== event.id), event as Metric].slice(-100) }
  if (!['tool', 'alert', 'approval_pending', 'approval_progress', 'approval_result'].includes(event.type ?? '')) return state
  let pending = state.pending
  if (event.type === 'approval_pending' && event.action) pending = [...pending.filter((p) => p.id !== event.action!.id),
    { ...event.action, session_id: event.session_id, channel: event.channel }]
  if (event.type === 'approval_result' && event.clear) pending = pending.filter((p) => p.id !== event.action_id)
  return { ...state, pending, activity: [event, ...state.activity.filter((e) => e.id !== event.id)].slice(0, 100) }
}

export function latencyStats(metrics: Metric[]) {
  const sorted = metrics.map((m) => m.ms).filter((ms) => Number.isFinite(ms) && ms >= 0).sort((a, b) => a - b)
  if (!sorted.length) return null
  const middle = Math.floor(sorted.length / 2)
  return { count: sorted.length, p50: sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2,
    p95: sorted[Math.ceil(sorted.length * 0.95) - 1] }
}

export function activityText(item: Activity): string {
  const display = item.display ?? item.result?.display ?? item.action?.display
  const error = item.result?.error?.message
  if (error) return error
  if (display) {
    const status = item.type === 'approval_pending' ? 'proposed' : item.type === 'approval_progress' ? 'approved'
      : item.result?.status ?? (item.kind === 'approval' ? item.summary : '')
    const label = ({ proposed: 'Proposed', approved: 'Approved', executed: 'Executed', rejected: 'Cancelled',
      expired: 'Expired', failed: 'Failed' } as Record<string, string>)[status ?? ''] ?? 'Review'
    return `${label} · ${display.title}`
  }
  if (item.summary) return item.summary.replace(/https:\/\/[^\s]+/g, '').replaceAll('_', ' ').replace(/\s+/g, ' ').trim().slice(0, 160)
  if (item.type === 'approval_pending') return `Proposed: ${item.action?.summary ?? 'Requested change'}`
  if (item.type === 'approval_result') return item.result?.error?.message ?? `Action ${item.result?.status ?? 'resolved'}`
  const name = item.name?.replaceAll('_', ' ') ?? 'Tool'
  return item.phase === 'start' ? `Started ${name}` : `${name}: ${item.ok ? 'completed' : 'failed'} (${item.ms ?? 0} ms)`
}

export const clockTime = (value: string, timezone?: string) =>
  new Date(value).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23', timeZone: timezone ?? 'Asia/Kolkata' })

export function activityLink(item: Activity): string {
  const direct = item.url ?? item.result?.url ?? item.display?.url ?? item.result?.display?.url ?? item.action?.display?.url
  const legacy = (item.summary ?? item.action?.summary ?? '').match(/https:\/\/[^\s]+/)?.[0]?.replace(/[.,;)]+$/, '')
  return providerLink(direct) || providerLink(legacy)
}

export function activityAudit(item: Activity): string {
  return item.audit_summary ?? item.action?.summary ?? item.result?.summary ?? item.summary ?? ''
}

export function activityDay(value: string, now = new Date()): string {
  const date = new Date(value)
  if (!Number.isFinite(date.getTime())) return 'Earlier'
  const key = (d: Date) => d.toLocaleDateString('en-CA', { timeZone: 'Asia/Kolkata' })
  const today = key(now)
  const yesterday = new Date(`${today}T12:00:00Z`)
  yesterday.setUTCDate(yesterday.getUTCDate() - 1)
  if (key(date) === today) return 'Today'
  if (key(date) === yesterday.toISOString().slice(0, 10)) return 'Yesterday'
  return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'Asia/Kolkata' })
}

// A tool is running right now (its start arrived without an end yet).
export const isBusy = (data: DashboardState, name: string) => data.activity.find((item) => item.name === name)?.phase === 'start'

// GitHub stats come only from a real github_activity / github_contributions result in this session's activity feed
// (backend/koe/tools/github_stats.py). Nothing is fetched automatically; null means unknown, never zero.
export type GitHubActivity = { since: string; prs?: { repo: string; number: number; title: string; url?: string }[]; until: string; end_exclusive?: boolean; timezone: string; partial?: boolean
  commits?: { repo: string; sha: string; title: string; url: string; date: string }[]; as_of?: string; scope?: string; unavailable_repositories?: string[]
  totals: { commits: number | null; merged_prs: number | null }; totals_are_complete?: boolean
  by_repository?: { repo: string; commits: number | null; merged_prs: number | null }[]
  lines?: { additions: number | null; deletions: number | null; net: number | null; commits_analyzed?: number; commits_in_history?: number; partial?: boolean; note?: string } }
export type GitHubContributions = { window_start: string; window_end: string; total_contributions: number | null; active_days: number | null
  current_streak: number | null; current_streak_may_extend_before_window?: boolean; streak_ends_on?: string | null
  longest_streak_in_window: number | null; note?: string }

export function latestResult<T>(data: DashboardState, name: string): { ts: string; result: T } | null {
  const item = data.activity.find((e) => e.type === 'tool' && e.phase === 'end' && e.name === name && e.ok && e.result && !e.result.error)
  return item ? { ts: item.ts, result: item.result as unknown as T } : null
}

export function githubActivityView(data: DashboardState): { result?: GitHubActivity; error?: string; label: string } {
  const panel = data.panels.github_yesterday
  const conversation = latestResult<GitHubActivity>(data, 'github_activity')
  if (conversation && (!panel || Date.parse(conversation.ts) > Date.parse(panel.ts))) return { ...conversation, label: 'Requested activity' }
  if (panel?.result.error) return { error: panel.result.error.message, label: 'Yesterday' }
  if (panel) return { result: panel.result as unknown as GitHubActivity, label: 'Yesterday' }
  return { label: 'Yesterday' }
}
