import { useState, type KeyboardEvent, type ReactNode } from 'react'
import { ArrowClockwise, CalendarBlank, GitPullRequest, Pulse, SealCheck, type Icon } from '@phosphor-icons/react'
import { activityText, clockTime, isBusy, latencyStats, type Approval, type DashboardState, type Panel, type PullRequest } from './state'
import { usePending } from './useDashboard'

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
      <p>{action.summary}</p>
      {action.id !== currentApproval?.id && <small>Confirm or cancel in the conversation that asked.</small>}
    </div>
    {action.id === currentApproval?.id && decide && <div className="pair">
      <button className="ghost" onClick={() => decide(false)}>Reject</button>
      <button className="soft" onClick={() => decide(true)}>Approve</button>
    </div>}
  </li>)}</ul>
}

export function ActivityFeed({ data }: { data: DashboardState }) {
  const stats = latencyStats(data.latencies)
  return <>
    {!data.activity.length ? <p className="dash-empty">What Koe does (tool calls, approvals, alerts) shows up here.</p> :
      <ol className="feed">{data.activity.slice(0, 12).map((item) => <li key={item.id}>
        <time>{clockTime(item.ts)}</time><p>{activityText(item)}<small>{item.channel ?? 'Koe'}</small></p>
      </li>)}</ol>}
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

  const tabs: { id: Tab; label: string; icon: Icon; count?: number; busy?: boolean }[] = [
    { id: 'today', label: 'Today', icon: CalendarBlank, count: events.length, busy: busy('calendar_list') },
    { id: 'github', label: 'GitHub', icon: GitPullRequest, count: (reviews?.result.prs?.length ?? 0) + (prs?.result.prs?.length ?? 0),
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
