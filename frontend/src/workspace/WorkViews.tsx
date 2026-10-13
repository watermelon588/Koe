import { useEffect, useState } from 'react'
import { calendarLayout, clockTime, type WorkCard } from './workState'
import { notionRequest, type Detail } from '../notion/api'
import { savedToken } from '../chat/api'
import './work.css'

// "Koe's view": Koe's own rendering of exactly what it read, proposed or wrote. `.lw-target` marks the one item
// the GSAP timeline in LiveWorkspace animates (the proposed/saved slot, row or record).

export function CalendarWork({ card }: { card: WorkCard }) {
  const { work, phase } = card
  const layout = calendarLayout(card)
  const hours = Array.from({ length: layout.to - layout.from + 1 }, (_, i) => layout.from + i)
  const proposal = work.operation === 'calendar_upsert_event'
  return <>
    <div className="work-context"><strong>{layout.date || 'Your calendar'}</strong><span>{layout.timezone}</span></div>
    {layout.allDay.length > 0 && <ul className="work-all-day">{layout.allDay.map(e => <li key={e.id}>All day · {e.title}</li>)}</ul>}
    {layout.items.length > 0 ? <>
      <div className="work-legend"><span>Calendar events</span><span>{proposal ? phase === 'saved' ? 'Confirmed slot' : phase === 'cancelled' ? 'Cancelled slot' : 'Proposed slot' : 'Free windows'}</span></div>
      <div className="work-timeline" style={{ height: (layout.to - layout.from) * 60 + 32 }} aria-label="Calendar day timeline">
        {hours.map(hour => <div className="work-hour" key={hour} style={{ top: (hour - layout.from) * 60 }}><time>{String(hour).padStart(2, '0')}:00</time><span /></div>)}
        {layout.items.map(item => {
          const busy = item.tone === 'busy'
          const left = busy ? item.lane * 49 / item.lanes : 51
          return <div key={item.id} className={`work-slot${item.id === 'proposal' ? ' lw-target' : ''}`} data-tone={item.tone} style={{
            top: item.start - layout.from * 60, height: Math.max(28, item.end - item.start),
            left: `calc(46px + (100% - 46px) * ${left / 100})`, width: `calc((100% - 46px) * ${(busy ? 49 / item.lanes : 49) / 100} - 3px)`,
          }} title={`${item.label} · ${item.time}`}><strong>{item.label}</strong><small>{item.time}</small>
            </div>
        })}
      </div>
    </> : phase === 'ready' && <p className="work-help">{work.operation === 'calendar_find_free' ? 'No free window matched this duration and range.' : 'No timed events returned for this date.'}</p>}
    {proposal && <div className="work-selection"><h3>{work.details.title}</h3>
      <p>{work.details.start && clockTime(work.details.start, layout.timezone)} – {work.details.end && clockTime(work.details.end, layout.timezone)}</p>
      <p>{work.details.attendees?.length ? `Attendees: ${work.details.attendees.join(', ')}` : work.details.event_id && work.details.attendees === undefined ? 'Existing attendees retained' : 'No attendees'}</p>
      <small>{phase === 'saved' ? 'Google confirmed the booking.' : phase === 'cancelled' ? 'This proposal was cancelled.' : 'Proposed change · availability is rechecked before saving.'}</small></div>}
    {work.operation === 'calendar_find_free' && <p className="work-help">{work.details.duration_min}-minute meeting · free windows are suggestions, not reservations.</p>}
    {work.truncated && <p className="work-help">Showing the first 100 of {work.total} results. Ask Koe for a narrower range.</p>}
  </>
}

export function SheetsWork({ card }: { card: WorkCard }) {
  const { work, phase } = card
  const d = work.details
  const saved = phase === 'saved' && work.row
  return <>
    <div className="work-context"><strong>{d.sheet_name || 'Configured timesheet'}</strong><span>{saved ? `Row ${work.row}` : 'Row preview'}</span></div>
    <div className="work-sheet-scroll"><table className="work-sheet"><caption>{saved ? 'Google confirmed this appended row' : phase === 'cancelled' ? 'Cancelled row · not saved'
      : phase === 'error' ? 'Not confirmed by Google · check the sheet before proposing again' : 'Proposed row · not saved yet'}</caption>
      <thead><tr><th scope="col">Row</th><th scope="col">A · Date</th><th scope="col">B · Client</th><th scope="col">C · Hours</th><th scope="col">D · Note</th></tr></thead>
      <tbody>
        {saved && work.row! > 2 && <tr className="work-earlier"><th scope="row">{work.row! > 3 ? `2–${work.row! - 1}` : 2}</th><td colSpan={4}>Earlier entries</td></tr>}
        <tr className="lw-target" data-phase={phase}><th scope="row">{saved ? work.row : '—'}</th><td>{d.date}</td><td>{d.client}</td><td className="num">{d.hours}</td><td>{d.note || '—'}</td></tr>
      </tbody>
    </table></div>
    {saved && work.range && <p className="work-help">Saved to {work.range}. The row includes Koe’s approval ID for auditing.</p>}
    <p className="work-help">One timesheet entry per approval. Values are written as literal text; formulas in notes are not executed.</p>
  </>
}

// A saved record is re-read from Notion (GET /api/notion/records/{id}) so this shows Notion's copy, not Koe's memory.
export function NotionWork({ card }: { card: WorkCard }) {
  const { work, phase } = card
  const d = work.details
  const log = work.operation === 'notion_log'
  const id = phase === 'saved' && !log ? work.page_id : undefined
  const [detail, setDetail] = useState<{ id: string; data?: Detail; error?: string } | null>(null)
  useEffect(() => {
    if (!id) return
    let live = true
    notionRequest<Detail>(savedToken(), `/records/${encodeURIComponent(id)}`)
      .then(data => { if (live) setDetail({ id, data }) })
      .catch((e: unknown) => { if (live) setDetail({ id, error: e instanceof Error ? e.message : String(e) }) })
    return () => { live = false }
  }, [id])
  const shown = detail?.id === id ? detail : null
  const title = shown?.data?.page.title || work.title || d.title || (log ? `Daily log · ${d.date}` : 'Untitled')
  const when = (shown?.data?.page.date?.start || work.date || d.date || '').replace('T', ' ').slice(0, 16)
  const status = shown?.data?.page.status || work.record_status || d.status
  const kind = shown?.data?.page.kind || work.kind || d.kind || (log ? 'Daily log' : 'Note')
  const verb = work.operation === 'notion_archive' ? 'Move to trash' : d.page_id ? 'Update' : log ? 'Append' : 'Create'
  return <>
    <div className="work-context"><strong>{phase === 'saved' ? (work.operation === 'notion_archive' ? 'Moved to Notion trash' : 'Saved in Notion') : `${verb} · proposed`}</strong>
      <span>{phase === 'saved' ? 'Notion confirmed' : 'Not saved yet'}</span></div>
    <article className="lw-record lw-target" data-phase={phase}>
      <h3>{title}</h3>
      <dl>
        <div><dt>Type</dt><dd>{kind}</dd></div>
        {status && <div><dt>Status</dt><dd>{status}</dd></div>}
        {when && <div><dt>Date</dt><dd><time>{when}</time></dd></div>}
        {log && work.added !== undefined && <div><dt>Added</dt><dd className="num">{work.added} new</dd></div>}
      </dl>
      {log && d.entries && <ul className="lw-entries">{d.entries.map((e, i) => <li key={i}>{e}</li>)}</ul>}
      {shown?.data ? shown.data.blocks.length > 0 && <div className="lw-blocks">{shown.data.blocks.slice(0, 8).map(b => <p key={b.id}>{b.text || `(${b.type})`}</p>)}
        {shown.data.blocks.length > 8 && <small>{shown.data.blocks.length - 8} more blocks in Notion</small>}</div>
        : !log && d.body && <div className="lw-blocks"><p>{d.body}</p></div>}
      {shown?.error && <small className="lw-muted">Couldn’t re-read the page from Notion: {shown.error}</small>}
    </article>
    {phase !== 'saved' && kind === 'Meeting' && <p className="work-help">Meeting record only; no Calendar slot is booked.</p>}
    {log && <p className="work-help">Your own daily log is append-only; exact repeats are skipped, so it needs no separate approval.</p>}
  </>
}
