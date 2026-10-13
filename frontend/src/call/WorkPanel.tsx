import { ArrowSquareOut, CalendarBlank, Table } from '@phosphor-icons/react'
import { calendarLayout, clockTime, googleLink, type Phase, type Service, type WorkCard } from './workState'
import './work.css'

const PHASE: Record<Phase, string> = { working: 'Checking', preparing: 'Preparing preview', ready: 'Checked',
  waiting: 'Waiting for your confirmation', saving: 'Confirming and saving', saved: 'Saved', cancelled: 'Cancelled', error: 'Needs attention' }

export function WorkPanel({ service, card }: { service: Service; card?: WorkCard }) {
  const Icon = service === 'calendar' ? CalendarBlank : Table
  const label = service === 'calendar' ? 'Google Calendar' : 'Google Sheets'
  if (!card) return <section className="call-work work-empty" aria-label={label}>
    <Icon size={32} /><h2>{label}</h2><p>{service === 'calendar' ? 'Ask Koe to check your calendar, find a free slot or prepare a booking.' : 'Ask Koe to log hours for a client. The exact row appears here before you confirm.'}</p>
  </section>
  const { work, phase } = card
  const url = googleLink(work.url, service)
  return <section className="call-work" aria-label={`${label} work window`}>
    <header className="work-heading"><div><Icon size={23} /><h2>{label}</h2></div>
      {url && <a href={url} target="_blank" rel="noreferrer" aria-label={`Open ${label}`}><ArrowSquareOut size={18} /></a>}</header>
    <p className="work-phase" data-phase={phase} role="status"><span aria-hidden="true" />{PHASE[phase]}</p>
    {work.error && <div className="work-error" role="alert"><p>{work.error.message}</p>{work.error.hint && <p>{work.error.hint}</p>}</div>}
    {service === 'calendar' ? <CalendarWork card={card} /> : <SheetsWork card={card} />}
    {phase === 'waiting' && <p className="work-help">Review the full proposal below. Say yes/no, or use Confirm/Cancel. Nothing has been saved yet.</p>}
    {phase === 'saving' && <p className="work-help">Koe is checking your decision and the service response. Waiting for confirmation from Google.</p>}
  </section>
}

function CalendarWork({ card }: { card: WorkCard }) {
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
          return <div key={item.id} className="work-slot" data-tone={item.tone} style={{
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

function SheetsWork({ card }: { card: WorkCard }) {
  const { work, phase } = card
  const d = work.details
  return <>
    <div className="work-context"><strong>{d.sheet_name || 'Configured timesheet'}</strong><span>{phase === 'saved' && work.row ? `Row ${work.row}` : 'Row preview'}</span></div>
    <div className="work-sheet-scroll"><table className="work-sheet"><caption>{phase === 'saved' ? 'Google confirmed this appended row' : phase === 'cancelled' ? 'Cancelled row · not saved' : 'Proposed row · not saved yet'}</caption>
      <thead><tr><th scope="col">Row</th><th scope="col">A · Date</th><th scope="col">B · Client</th><th scope="col">C · Hours</th><th scope="col">D · Note</th></tr></thead>
      <tbody><tr data-phase={phase}><th scope="row">{phase === 'saved' ? work.row : '—'}</th><td>{d.date}</td><td>{d.client}</td><td>{d.hours}</td><td>{d.note || '—'}</td></tr></tbody>
    </table></div>
    {phase === 'saved' && work.range && <p className="work-help">Saved to {work.range}. The row includes Koe’s approval ID for auditing.</p>}
    <p className="work-help">One timesheet entry per approval. Values are written as literal text; formulas in notes are not executed.</p>
  </>
}
