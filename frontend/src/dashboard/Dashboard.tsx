import { useEffect, useState, type ReactNode } from 'react'
import { activityText, latencyStats, type Approval, type DashboardState, type Panel, type PullRequest } from './state'

function SafeLink({ url, children }: { url?: string; children: ReactNode }) {
  return url?.startsWith('https://') ? <a href={url} target="_blank" rel="noreferrer">{children}</a> : <span>{children}</span>
}
function updated(panel?: Panel) {
  return panel ? `Updated ${new Date(panel.ts).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}` : 'Waiting for data'
}
function Empty({ panel, label }: { panel?: Panel; label: string }) {
  return <p className="panel-empty">{panel?.result.error?.message ?? (panel ? label : 'Connect the dashboard to load this panel.')}</p>
}
function PRList({ panel, label }: { panel?: Panel; label: string }) {
  const prs = panel?.result.prs ?? []
  if (panel?.result.error || !prs.length) return <Empty panel={panel} label={label} />
  return <ul className="rows">{prs.map((pr: PullRequest) => <li key={`${pr.repo}/${pr.number}`}>
    <span className="num">#{pr.number}</span><div><SafeLink url={pr.url}>{pr.title}</SafeLink><small className="repo">{pr.repo}</small></div>
    <small className={pr.ci === 'failing' || pr.conflicts === 'yes' ? 'flag' : ''}>
      {pr.ci ? `${pr.draft ? 'Draft · ' : ''}CI ${pr.ci} · ${pr.review}${pr.conflicts === 'yes' ? ' · conflicts' : ''}` : 'Review requested'}
    </small></li>)}</ul>
}

export function Dashboard({ data, connected, currentApproval, decide, refresh }: {
  data: DashboardState; connected: boolean; currentApproval?: Approval | null; decide?: (approve: boolean) => void; refresh: () => void
}) {
  const [clock, setClock] = useState(Date.now)
  useEffect(() => { const timer = setInterval(() => setClock(Date.now()), 1000); return () => clearInterval(timer) }, [])
  const { calendar, reviews, prs } = data.panels
  const pending = data.pending.filter((p) => new Date(p.expires_ts).getTime() > clock)
  // The current call card can arrive before the separate events socket.
  if (currentApproval && new Date(currentApproval.expires_ts).getTime() > clock && !pending.some((p) => p.id === currentApproval.id)) pending.push(currentApproval)
  const stats = latencyStats(data.latencies)
  const time = (value: string, timezone?: string) => new Date(value).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', timeZone: timezone })
  const busy = (name: string) => {
    const latest = data.activity.find((item) => item.name === name)
    return latest?.phase === 'start'
  }
  return <div className="dashboard" aria-label="Your day">
    <div className="dashboard-bar"><span>{connected ? 'Live' : 'Offline · data may be stale'}</span>
      <button className="chip" onClick={refresh} disabled={!connected}>Refresh</button></div>
    <section className="block" data-busy={busy('calendar_list')}>
      <h2>Today <small>{updated(calendar)}</small></h2>
      {calendar && <p className="panel-meta">{calendar.date} · {calendar.timezone}</p>}
      {!calendar?.result.events?.length || calendar.result.error ? <Empty panel={calendar} label="No events today." /> :
        <ul className="rows">{calendar.result.events.map((event) => <li key={event.id}>
          <time>{event.start.dateTime ? time(event.start.dateTime, calendar.timezone) : 'All day'}</time>
          <SafeLink url={event.url}>{event.title}</SafeLink>
          <small>{event.end.dateTime ? `until ${time(event.end.dateTime, calendar.timezone)}` : 'All day'}</small>
        </li>)}</ul>}
    </section>
    <section className="block" data-busy={busy('github_review_queue')}>
      <h2>Waiting for your review <small>{updated(reviews)}</small></h2><PRList panel={reviews} label="No reviews waiting on you." />
    </section>
    <section className="block" data-busy={busy('github_my_prs')}>
      <h2>Your pull requests <small>{updated(prs)}</small></h2><PRList panel={prs} label="No open pull requests." />
    </section>
    <section className="block wide">
      <h2>Waiting on you</h2>
      {!pending.length ? <p className="panel-empty">No pending approvals.</p> : <ul className="asks">{pending.map((action) => <li key={action.id}>
        <div><small>{action.channel ?? 'Current call'} · expires {time(action.expires_ts)}</small><p>{action.summary}</p>
          {action.id !== currentApproval?.id && <small>Confirm or cancel in the original conversation.</small>}</div>
        {action.id === currentApproval?.id && decide && <div className="pair">
          <button className="ghost" onClick={() => decide(false)}>Reject</button><button className="soft" onClick={() => decide(true)}>Approve</button>
        </div>}
      </li>)}</ul>}
    </section>
    <section className="block wide">
      <h2>Activity</h2><p className="panel-meta">{data.storage || 'Connect to load saved activity.'}</p>
      {!data.activity.length ? <p className="panel-empty">Tool calls, approvals and alerts will appear here.</p> :
        <ol className="activity-feed">{data.activity.slice(0, 30).map((item) => <li key={item.id}>
          <time>{time(item.ts)}</time><p>{activityText(item)}<small>{item.channel ?? 'Koe'}</small></p>
        </li>)}</ol>}
    </section>
    <section className="block wide"><h2>Response latency</h2>
      {stats ? <><p className="latency-metrics"><span>p50 <b>{Math.round(stats.p50)} ms</b></span><span>p95 <b>{Math.round(stats.p95)} ms</b></span><span>{stats.count} turns</span></p>
        <p className="panel-meta">Speech end or typed submit to first audio · latest {stats.count} measured turns · p95 uses nearest rank.</p></> :
        <p className="panel-empty">Measured after Koe answers an audio or typed turn.</p>}
    </section>
  </div>
}
