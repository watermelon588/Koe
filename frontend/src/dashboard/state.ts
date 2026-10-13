export type Approval = { id: string; summary: string; expires_ts: string; session_id?: string; channel?: string }
export type CalendarEvent = { id: string; title: string; start: { dateTime?: string; date?: string }; end: { dateTime?: string; date?: string }; url?: string }
export type PullRequest = { repo: string; number: number; title: string; url?: string; ci?: string; review?: string; conflicts?: string; draft?: boolean }
export type Panel = { ts: string; date: string; timezone: string; result: { error?: { message: string }; events?: CalendarEvent[]; prs?: PullRequest[] } }
export type Activity = { id: string; ts: string; type?: string; kind?: string; summary?: string; channel?: string; session_id?: string;
  name?: string; phase?: string; ok?: boolean; ms?: number; action?: Approval; result?: { status?: string; error?: { message: string } } & Record<string, unknown> }
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
  if (item.summary) return item.summary
  if (item.type === 'approval_pending') return `Proposed: ${item.action?.summary ?? 'Requested change'}`
  if (item.type === 'approval_result') return item.result?.error?.message ?? `Action ${item.result?.status ?? 'resolved'}`
  const name = item.name?.replaceAll('_', ' ') ?? 'Tool'
  return item.phase === 'start' ? `Started ${name}` : `${name}: ${item.ok ? 'completed' : 'failed'} (${item.ms ?? 0} ms)`
}

export const clockTime = (value: string, timezone?: string) =>
  new Date(value).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', timeZone: timezone })

// A tool is running right now (its start arrived without an end yet).
export const isBusy = (data: DashboardState, name: string) => data.activity.find((item) => item.name === name)?.phase === 'start'

// GitHub stats come only from a real github_activity / github_contributions result in this session's activity feed
// (backend/koe/tools/github_stats.py). Nothing is fetched automatically; null means unknown, never zero.
export type GitHubActivity = { since: string; prs?: { repo: string; number: number; title: string; url?: string }[]; until: string; end_exclusive?: boolean; timezone: string; partial?: boolean
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
