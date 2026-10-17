import { useEffect, useState, type KeyboardEvent, type ReactNode, type ComponentType } from 'react'
import { ArrowClockwise, Pulse, SealCheck } from '@phosphor-icons/react'
import { activityAudit, activityDay, activityLink, activityText, clockTime, githubActivityView, isBusy, latencyStats, latestResult, type Activity, type Approval, type DashboardState,
  type GitHubContributions, type Panel, type PullRequest } from './state'
import { usePending } from './useDashboard'
import { CalendarIcon, GitHubIcon } from '../components/BrandIcon'
import { ApprovalPreview, AuditDetails } from '../approvals/ApprovalPreview'

// Your day. The pieces below (TodayList, PRList, ApprovalList, ActivityFeed) are shared by two layouts:
// the compact four-tab card in the call's Day view (Dashboard) and the full Dashboard page (DashboardPage.tsx).
type Tab = 'today' | 'github' | 'approvals' | 'activity'

function SafeLink({ url, children }: { url?: string; children: ReactNode }) {
  return url?.startsWith('https://') ? <a href={url} target="_blank" rel="noreferrer">{children}</a> : <span>{children}</span>
}
function Empty({ panel, label }: { panel?: Panel; label: string }) {
  return <p className="dash-empty">{panel?.result.error?.message ?? (panel ? label : 'Connect to load this.')}</p>
}

export function TodayList({ calendar, limit }: { calendar?: Panel; limit?: number }) {
  const events = calendar?.result.events ?? []
  if (!events.length || calendar?.result.error) return <Empty panel={calendar} label="Nothing on your calendar today." />
  return <ul className="rows">{events.slice(0, limit).map((event) => <li key={event.id}>
    <time>{event.start.dateTime ? clockTime(event.start.dateTime, calendar!.timezone) : 'All day'}</time>
    <SafeLink url={event.url}>{event.title}</SafeLink>
    <small>{event.end.dateTime ? `until ${clockTime(event.end.dateTime, calendar!.timezone)}` : ''}</small>
  </li>)}</ul>
}

export function PRList({ panel, label }: { panel?: Panel; label: string }) {
  const prs = panel?.result.prs ?? []
  if (panel?.result.error || !prs.length) return <Empty panel={panel} label={label} />
  return <ul className="rows">{prs.map((pr: PullRequest) => <li key={`${pr.repo}/${pr.number}`}>
    <span className="num">#{pr.number}</span>
    <div><SafeLink url={pr.url}>{pr.title}</SafeLink><small>{pr.repo}</small></div>
    <small className={pr.ci === 'failing' || pr.conflicts === 'yes' ? 'flag' : ''}>
      {pr.ci ? `${pr.draft ? 'Draft · ' : ''}CI ${pr.ci}${pr.conflicts === 'yes' ? ' · conflicts' : ''}` : 'Review'}
    </small></li>)}</ul>
}

export function ApprovalList({ pending, currentApproval, decide }: { pending: Approval[]; currentApproval?: Approval | null; decide?: (approve: boolean) => void }) {
  if (!pending.length) return <p className="dash-empty">Nothing waiting on you. Koe asks here before it writes anything.</p>
  return <ul className="asks">{pending.map((action) => <li key={action.id}>
    <div>
      <small>{action.channel ?? 'Current call'} · expires {clockTime(action.expires_ts)}</small>
      <ApprovalPreview action={action} />
      {action.id !== currentApproval?.id && <small>Confirm or cancel in the conversation that asked.</small>}
    </div>
    {action.id === currentApproval?.id && decide && <div className="pair">
      <button className="ghost" onClick={() => decide(false)}>Reject</button>
      <button className="soft" onClick={() => decide(true)}>Approve</button>
    </div>}
  </li>)}</ul>
}

const known = (n: number | null | undefined) => typeof n === 'number' ? n.toLocaleString('en-IN') : 'unknown'
const Stat = ({ n, unit = '' }: { n: number | null | undefined; unit?: string }) =>
  typeof n === 'number' ? <>{known(n)}{unit && <small> {unit}</small>}</> : <small>unknown</small>

// Only what Koe actually read this session: commits and merged PRs stay separate, unknown is never shown as zero,
// and lines are "changed lines in analyzed commits", not a total.
export function GitHubStats({ data }: { data: DashboardState }) {
  const view = githubActivityView(data)
  const activity = view.result
  const streaks = latestResult<GitHubContributions>(data, 'github_contributions')?.result
  if (!activity && !streaks) return <p className="dash-empty">{view.error ?? 'Loading yesterday’s activity. Connect GitHub and choose repositories in Settings.'}</p>
  return <>
    {view.error && <p className="dash-empty" role="status">{view.error}</p>}
    {activity && <div className="gh-stats">
      <h3>{view.label}</h3>
      <dl className="gh-totals">
        <div><dt>Commits</dt><dd><Stat n={activity.totals.commits} /></dd></div>
        <div><dt>Merged PRs</dt><dd><Stat n={activity.totals.merged_prs} /></dd></div>
        {activity.lines && <div><dt>Changed lines in analyzed commits</dt><dd>{activity.lines.additions == null ? <small>unavailable</small>
          : `+${known(activity.lines.additions)} / −${known(activity.lines.deletions)}`}</dd></div>}
      </dl>
      {!!activity.by_repository?.length && <ul className="rows">{activity.by_repository.map((r) => <li key={r.repo}>
        <span>{r.repo}</span><small>{known(r.commits)} commits · {known(r.merged_prs)} merged</small></li>)}</ul>}
      {!!activity.prs?.length && <ul className="rows">{activity.prs.slice(0, 5).map((pr) => <li key={`${pr.repo}#${pr.number}`}>
        <SafeLink url={pr.url}>{pr.title}</SafeLink><small>merged · {pr.repo}#{pr.number}</small></li>)}</ul>}
      {!!activity.commits?.length && <ul className="rows">{activity.commits.slice(0, 10).map(commit => <li key={`${commit.repo}:${commit.sha}`}>
        <div><SafeLink url={commit.url}>{commit.title}</SafeLink><small>{commit.repo} · {commit.sha.slice(0, 7)}</small></div>
        <time dateTime={commit.date}>{clockTime(commit.date, activity.timezone)}</time>
      </li>)}</ul>}
      {(activity.commits?.length ?? 0) > 10 && <p className="dash-meta">Showing 10 of {activity.commits!.length} commits. Ask Koe for the full summary.</p>}
      {!!activity.unavailable_repositories?.length && <p className="dash-meta">Could not read: {activity.unavailable_repositories.join(', ')}</p>}
      <p className="dash-meta">{activity.scope}{activity.as_of && ` · Checked ${clockTime(activity.as_of, activity.timezone)}`}</p>
      <p className="dash-meta">{activity.since} to {activity.until}{activity.end_exclusive ? ' (end not included)' : ''} · {activity.timezone}
        {(activity.partial || activity.totals_are_complete === false) && ' · partial: some data could not be read'}
        {activity.lines && ` · lines from ${activity.lines.commits_analyzed ?? '?'} analyzed commits${activity.lines.partial ? ' (partial)' : ''}`}</p>
    </div>}
    {streaks && <div className="gh-stats">
      <dl className="gh-totals">
        <div><dt>Contributions</dt><dd><Stat n={streaks.total_contributions} /></dd></div>
        <div><dt>Active days</dt><dd><Stat n={streaks.active_days} /></dd></div>
        <div><dt>Current streak</dt><dd>{streaks.current_streak_may_extend_before_window && streaks.current_streak != null && <small>at least </small>}
          <Stat n={streaks.current_streak} unit="days" /></dd></div>
        <div><dt>Longest in window</dt><dd><Stat n={streaks.longest_streak_in_window} unit="days" /></dd></div>
      </dl>
      <p className="dash-meta">{streaks.window_start} to {streaks.window_end}{streaks.note ? ` · ${streaks.note}` : ''}</p>
    </div>}
  </>
}

export function ActivityFeed({ data }: { data: DashboardState }) {
  const stats = latencyStats(data.latencies)
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 60_000)
    return () => clearInterval(timer)
  }, [])
  const groups = new Map<string, Activity[]>()
  for (const item of [...data.activity].sort((a, b) => Date.parse(b.ts) - Date.parse(a.ts)).slice(0, 12)) {
    const day = activityDay(item.ts, now)
    groups.set(day, [...(groups.get(day) ?? []), item])
  }
  return <>
    {!data.activity.length ? <p className="dash-empty">What Koe does (tool calls, approvals, alerts) shows up here.</p> :
      [...groups].map(([day, items]) => <section className="feed-group" key={day} aria-label={day}>
        <h3>{day}</h3><ol className="feed">{items.map((item) => {
          const url = activityLink(item), audit = activityAudit(item), label = activityText(item)
          return <li key={item.id}>
            <time dateTime={item.ts}>{clockTime(item.ts)}</time><div className="feed-copy">
              <p>{label}</p><small>{item.channel ?? 'Koe'}{url && <> · <a href={url} target="_blank" rel="noreferrer">Open ↗</a></>}</small>
              {audit && audit !== label && <AuditDetails summary={audit} />}
            </div>
          </li>
        })}</ol>
      </section>)}
    <p className="dash-meta foot">{stats
      ? <>Response time: p50 <b>{Math.round(stats.p50)} ms</b> · p95 <b>{Math.round(stats.p95)} ms</b> · {stats.count} turns</>
      : 'Response time appears after Koe answers.'}</p>
  </>
}

export function Dashboard({ data, connected, currentApproval, decide, refresh }: {
  data: DashboardState; connected: boolean; currentApproval?: Approval | null; decide?: (approve: boolean) => void; refresh: () => void
}) {
  const [tab, setTab] = useState<Tab>('today')
  const { calendar, reviews, prs } = data.panels
  const pending = usePending(data, currentApproval)
  const busy = (name: string) => isBusy(data, name)
  const events = calendar?.result.events ?? []

  const tabs: { id: Tab; label: string; icon: ComponentType<{ size?: number }>; count?: number; busy?: boolean }[] = [
    { id: 'today', label: 'Today', icon: CalendarIcon, count: events.length, busy: busy('calendar_list') },
    { id: 'github', label: 'GitHub', icon: GitHubIcon, count: (reviews?.result.prs?.length ?? 0) + (prs?.result.prs?.length ?? 0),
      busy: busy('github_review_queue') || busy('github_my_prs') },
    { id: 'approvals', label: 'Approvals', icon: SealCheck, count: pending.length },
    { id: 'activity', label: 'Activity', icon: Pulse },
  ]
  function onTabKey(e: KeyboardEvent) { // arrow keys move between tabs (WAI-ARIA tabs pattern)
    const step = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0
    if (!step) return
    const next = tabs[(tabs.findIndex((t) => t.id === tab) + step + tabs.length) % tabs.length].id
    setTab(next)
    document.getElementById(`dash-tab-${next}`)?.focus()
  }

  return <section className="dash" aria-label="Your day">
    <div className="dash-head">
      <div className="dash-tabs" role="tablist" aria-label="Your day" onKeyDown={onTabKey}>
        {tabs.map(({ id, label, icon: TabIcon, count, busy: working }) => (
          <button key={id} id={`dash-tab-${id}`} role="tab" aria-selected={tab === id} aria-controls="dash-panel"
            tabIndex={tab === id ? 0 : -1} data-busy={working || undefined} onClick={() => setTab(id)}
            aria-label={count ? `${label}, ${count}` : label}>
            <TabIcon size={17} /><span>{label}</span>{!!count && <span className="count">{count}</span>}
          </button>
        ))}
      </div>
      <div className="dash-live">
        <span className="live-dot" data-on={connected} aria-hidden="true" />
        <span>{connected ? 'Live' : 'Offline'}</span>
        <button className="icon-btn" aria-label="Refresh" title="Refresh" disabled={!connected} onClick={refresh}><ArrowClockwise size={16} /></button>
      </div>
    </div>

    <div className="dash-body" role="tabpanel" id="dash-panel" aria-labelledby={`dash-tab-${tab}`}>
      {tab === 'today' && <>
        {calendar && <p className="dash-meta">Updated {clockTime(calendar.ts)} · {calendar.timezone}</p>}
        <TodayList calendar={calendar} />
      </>}

      {tab === 'github' && <>
        <GitHubStats data={data} />
        <h3>Waiting for your review</h3>
        <PRList panel={reviews} label="No reviews waiting on you." />
        <h3>Your pull requests</h3>
        <PRList panel={prs} label="No open pull requests." />
      </>}

      {tab === 'approvals' && <ApprovalList pending={pending} currentApproval={currentApproval} decide={decide} />}

      {tab === 'activity' && <ActivityFeed data={data} />}
    </div>
  </section>
}
