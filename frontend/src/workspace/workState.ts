// The live workspace's state (SPEC §2 'Live workspace'): one card per service, fed by /ws/call events in a call and by
// the chat API's `workspace` list in the app chat (same event shape, built by backend/koe/call_work.py).
export type Service = 'calendar' | 'sheets' | 'notion'
export const SERVICES: Service[] = ['calendar', 'sheets', 'notion']
export type Phase = 'working' | 'preparing' | 'ready' | 'waiting' | 'saving' | 'saved' | 'cancelled' | 'error'
type When = { dateTime?: string; date?: string }
export type Work = {
  service: Service; operation: string; action_id?: string; timezone?: string; date?: string
  details: { date?: string; title?: string; start?: string; end?: string; attendees?: string[]; event_id?: string;
    duration_min?: number; client?: string; hours?: number; note?: string; sheet_name?: string
    kind?: string; status?: string; body?: string; page_id?: string; entries?: string[] }
  events?: { id: string; title: string; start: When; end: When; url?: string }[]
  slots?: { start: string; end: string }[]; total?: number; truncated?: boolean
  row?: number; range?: string; url?: string; title?: string; start?: string; end?: string
  page_id?: string; kind?: string; record_status?: string; added?: number; message?: string
  error?: { message: string; hint?: string }
}
export type WorkCard = { work: Work; phase: Phase; operationId?: string }
export type WorkState = { active: Service | null; revision: number; calendar?: WorkCard; sheets?: WorkCard; notion?: WorkCard }
export const emptyWork: WorkState = { active: null, revision: 0 }
export type WorkEvent = { type: string; phase?: string; status?: string; operation_id?: string; work?: Work }
const dateOf = (w: Work) => w.date || w.details.date || w.details.start?.slice(0, 10) || ''

export function reduceWork(state: WorkState, event: WorkEvent): WorkState {
  const w = event.work
  if (!w || !SERVICES.includes(w.service) || !['tool', 'approval_pending', 'approval_progress', 'approval_result'].includes(event.type)) return state
  const old = state[w.service]
  if (event.type === 'tool' && event.phase === 'end' && old?.operationId && event.operation_id !== old.operationId) return state
  if (event.type === 'approval_result' && old?.work.action_id && w.action_id !== old.work.action_id) return state
  const reading = ['calendar_list', 'calendar_find_free'].includes(w.operation)
  const sameDay = old && dateOf(old.work) === dateOf(w)
  const keepContext = sameDay && !(event.type === 'tool' && event.phase === 'start' && reading)
  const work = { ...(keepContext ? { events: old.work.events, slots: old.work.slots } : {}), ...w }
  const phase: Phase = w.error ? 'error' : event.type === 'approval_pending' ? 'waiting'
    : event.type === 'approval_progress' ? 'saving' : event.type === 'approval_result'
      ? event.status === 'executed' ? 'saved' : event.status === 'rejected' ? 'cancelled' : 'error'
      : event.phase === 'start' ? 'working' : reading ? 'ready'
        : w.operation === 'notion_log' ? 'saved' : 'preparing' // the own daily log is the one write with no approval (SPEC §3)
  if (phase === 'saved' && w.service === 'calendar') {
    work.slots = [] // Availability was read before the write; never show it as still current.
    work.events = work.events?.filter(e => e.id !== work.details.event_id)
  }
  return { ...state, active: w.service, revision: state.revision + 1,
    [w.service]: { work, phase, operationId: event.operation_id ?? old?.operationId } }
}

const HOSTS: Record<Service, string[]> = { calendar: ['calendar.google.com', 'www.google.com'], sheets: ['docs.google.com'],
  notion: ['notion.so', 'www.notion.so', 'app.notion.com'] }
// Only https links to the service's own hosts are ever rendered or framed (the backend checks the same list).
export function serviceLink(value: string | undefined, service: Service): string {
  try {
    const url = new URL(value || '')
    return url.protocol === 'https:' && !url.username && !url.password && HOSTS[service].includes(url.hostname) ? url.href : ''
  } catch { return '' }
}

export type Account = { timesheet: string; google: string } // from GET /api/connections; never a token
// The "Live view" URL, or '' when the provider can't be framed. Checked with curl on 2026-10-13 (docs/DECISIONS.md):
// Sheets /edit and the Calendar embed send no X-Frame-Options or frame-ancestors; Notion sends X-Frame-Options:
// SAMEORIGIN, so it never frames. `rm=minimal` (Sheets without menus) is an observed, undocumented parameter: if
// Google ignores it, the full editor shows instead. Calendar embed: https://support.google.com/calendar/answer/41207
export function liveUrl(service: Service, work: Work | undefined, account: Account): string {
  if (service === 'sheets') {
    const id = /^https:\/\/docs\.google\.com\/spreadsheets\/d\/([A-Za-z0-9_-]+)\//.exec(serviceLink(work?.url, 'sheets') || serviceLink(account.timesheet, 'sheets'))?.[1]
    return id ? `https://docs.google.com/spreadsheets/d/${id}/edit?rm=minimal` : ''
  }
  if (service === 'calendar' && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(account.google)) { // a calendar ID; encoded below
    return `https://calendar.google.com/calendar/embed?src=${encodeURIComponent(account.google)}&ctz=${encodeURIComponent(work?.timezone || 'Asia/Kolkata')}&mode=WEEK`
  }
  return ''
}

export const LABEL: Record<Service, string> = { calendar: 'Google Calendar', sheets: 'Google Sheets', notion: 'Notion' }

// One polite sentence for screen readers when a card changes; '' for in-between states.
export function announce(service: Service, card?: WorkCard): string {
  if (!card) return ''
  const { work, phase } = card
  const d = work.details
  const what = service === 'sheets' ? `${d.hours} hours for ${d.client} on ${d.date}`
    : service === 'calendar' ? `${work.title || d.title || 'calendar'}${d.start ? ` at ${clockTime(d.start, work.timezone)}` : ''}`
      : work.title || d.title || (d.entries ? `${d.entries.length} daily log entries` : 'record')
  if (phase === 'error') return `${LABEL[service]} needs attention: ${(work.error?.message ?? 'the action did not complete').replace(/\.$/, '')}.`
  if (phase === 'cancelled') return `Cancelled. Nothing was changed in ${LABEL[service]}.`
  if (phase === 'waiting') return `Proposed in ${LABEL[service]}: ${what}. Not saved yet. Confirm or cancel.`
  if (phase === 'saved') return `Saved in ${LABEL[service]}: ${what}${work.row ? `, row ${work.row}` : ''}.`
  return ''
}

export function clockTime(value: string, timezone?: string) {
  try { return new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit', timeZone: timezone }).format(new Date(value)) }
  catch { return value }
}

export function calendarLayout(card: WorkCard) {
  const { work, phase } = card
  const date = dateOf(work)
  const timezone = work.timezone || 'Asia/Kolkata'
  function minutes(value: string, end = false) {
    const dt = new Date(value)
    if (!Number.isFinite(dt.getTime())) return null
    try {
      const parts = new Intl.DateTimeFormat('en-CA', { timeZone: timezone, year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).formatToParts(dt)
      const p = Object.fromEntries(parts.map(v => [v.type, v.value]))
      const day = `${p.year}-${p.month}-${p.day}`
      if (day < date) return 0
      if (day > date) return 1440
      return Math.min(1440, Number(p.hour) * 60 + Number(p.minute) + (end ? Number(dt.getSeconds() > 0) : 0))
    } catch { return null }
  }
  const items: { id: string; label: string; start: number; end: number; tone: string; time: string; lane: number; lanes: number }[] = []
  function add(id: string, label: string, start: string | undefined, end: string | undefined, tone: string) {
    if (!start || !end) return
    const a = minutes(start), b = minutes(end, true)
    if (a === null || b === null || b <= a) return
    items.push({ id, label, start: a, end: b, tone, time: `${clockTime(start, timezone)} – ${clockTime(end, timezone)}`, lane: 0, lanes: 1 })
  }
  const allDay = (work.events || []).filter(e => e.start.date && !e.start.dateTime)
  for (const e of work.events || []) add(e.id, e.title, e.start.dateTime, e.end.dateTime, 'busy')
  for (const [i, s] of (work.slots || []).entries()) add(`free-${i}`, 'Available', s.start, s.end, 'free')
  if (work.operation === 'calendar_upsert_event') add('proposal', work.title || work.details.title || 'Meeting',
    work.start || work.details.start, work.end || work.details.end, phase === 'saved' ? 'saved' : phase === 'cancelled' ? 'cancelled' : 'proposed')
  // Put overlapping events in separate lanes so none is hidden beneath another event.
  const laneEnds: number[] = []
  const busy = items.filter(i => i.tone === 'busy').sort((a, b) => a.start - b.start)
  for (const item of busy) {
    let lane = laneEnds.findIndex(end => end <= item.start)
    if (lane < 0) lane = laneEnds.length
    laneEnds[lane] = item.end; item.lane = lane
  }
  for (const item of busy) item.lanes = laneEnds.length
  const from = items.length ? Math.max(0, Math.floor(Math.min(...items.map(i => i.start)) / 60) - 1) : 8
  const to = items.length ? Math.min(24, Math.ceil(Math.max(...items.map(i => i.end)) / 60) + 1) : 18
  return { date, timezone, items, allDay, from, to }
}
