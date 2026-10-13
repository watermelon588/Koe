import type { ReactNode } from 'react'
import { ArrowClockwise, ArrowRight, CalendarBlank, ChartBar, Eye, GitPullRequest, Pulse, SealCheck, type Icon } from '@phosphor-icons/react'
import { ActivityFeed, ApprovalList, GitHubStats, PRList, TodayList } from './Dashboard'
import { clockTime, isBusy, type Approval, type DashboardState } from './state'
import { usePending } from './useDashboard'
import './dashboard.css'

type Props = {
  data: DashboardState; connected: boolean; status: string; refresh: () => void
  currentApproval?: Approval | null; decide?: (approve: boolean) => void
  children?: ReactNode // the access-token row, when this device isn't connected yet
}

const today = () => new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long' })

// The Dashboard page (#dashboard): your day as a grid of panels, stacked on phones. It reads the same
// /ws/events connection as Home (held in App), so opening it never starts a second socket.
export function DashboardPage({ data, connected, status, refresh, currentApproval, decide, children }: Props) {
  const { calendar, reviews, prs } = data.panels
  const pending = usePending(data, currentApproval)
  return (
    <main className="dash-page" id="main-content" tabIndex={-1}>
      <header className="dash-page-head">
        <div>
          <h1>Dashboard</h1>
          <p>{today()}{calendar ? ` · ${calendar.timezone}` : ''}</p>
        </div>
        <div className="dash-live">
          <span className="live-dot" data-on={connected} aria-hidden="true" />
          <span role="status">{connected ? 'Live' : 'Offline'}</span>
          <button className="ghost" disabled={!connected} onClick={refresh}><ArrowClockwise size={16} />Refresh</button>
        </div>
      </header>
      {children}
      {!connected && !children && <p className="note dash-page-status">{status}</p>}

      <div className="dash-grid">
        <Tile area="today" icon={CalendarBlank} title="Today" count={calendar?.result.events?.length} busy={isBusy(data, 'calendar_list')}
          meta={calendar ? `Updated ${clockTime(calendar.ts)}` : undefined}>
          <TodayList calendar={calendar} />
        </Tile>
        <Tile area="approvals" icon={SealCheck} title="Approvals" count={pending.length} attention={pending.length > 0}>
          <ApprovalList pending={pending} currentApproval={currentApproval} decide={decide} />
        </Tile>
        <Tile area="reviews" icon={Eye} title="Waiting for your review" count={reviews?.result.prs?.length} busy={isBusy(data, 'github_review_queue')}>
          <PRList panel={reviews} label="No reviews waiting on you." />
        </Tile>
        <Tile area="prs" icon={GitPullRequest} title="Your pull requests" count={prs?.result.prs?.length} busy={isBusy(data, 'github_my_prs')}>
          <PRList panel={prs} label="No open pull requests." />
        </Tile>
        <Tile area="github" icon={ChartBar} title="GitHub stats" busy={isBusy(data, 'github_activity') || isBusy(data, 'github_contributions')}>
          <GitHubStats data={data} />
        </Tile>
        <Tile area="activity" icon={Pulse} title="Activity">
          <ActivityFeed data={data} />
        </Tile>
      </div>
    </main>
  )
}

function Tile({ area, icon: TileIcon, title, count, busy, meta, attention, children }: {
  area: string; icon: Icon; title: string; count?: number; busy?: boolean; meta?: string; attention?: boolean; children: ReactNode
}) {
  return (
    <section className="dash-tile" style={{ gridArea: area }} data-area={area} data-attention={attention || undefined} aria-labelledby={`tile-${area}`}>
      <header>
        <TileIcon size={17} data-busy={busy || undefined} aria-hidden="true" />
        <h2 id={`tile-${area}`}>{title}</h2>
        {!!count && <span className="count">{count}</span>}
        {meta && <small>{meta}</small>}
      </header>
      <div className="dash-tile-body">{children}</div>
    </section>
  )
}

// Home's slim view of the day: the next few events and what's waiting, with a way into the full Dashboard.
export function TodaySummary({ data, connected }: { data: DashboardState; connected: boolean }) {
  const { calendar, reviews } = data.panels
  const pending = usePending(data)
  const events = calendar?.result.events ?? []
  const waiting = [
    reviews?.result.prs?.length ? `${reviews.result.prs.length} ${reviews.result.prs.length === 1 ? 'review' : 'reviews'} waiting` : '',
    pending.length ? `${pending.length} ${pending.length === 1 ? 'approval' : 'approvals'} pending` : '',
  ].filter(Boolean).join(' · ')
  return (
    <section className="today" aria-labelledby="today-title">
      <header>
        <h2 id="today-title">Today</h2>
        <span className="live-dot" data-on={connected} aria-hidden="true" />
        <span className="visually-hidden">{connected ? 'Live' : 'Offline'}</span>
        <a className="today-link" href="#dashboard">Open dashboard<ArrowRight size={14} /></a>
      </header>
      <TodayList calendar={calendar} limit={3} />
      {(events.length > 3 || waiting) && <p className="today-foot">
        {events.length > 3 && <span>{events.length - 3} more today</span>}
        {waiting && <span>{waiting}</span>}
      </p>}
    </section>
  )
}
