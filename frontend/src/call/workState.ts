export type Service = 'calendar' | 'sheets'
export type Phase = 'working' | 'preparing' | 'ready' | 'waiting' | 'saving' | 'saved' | 'cancelled' | 'error'
type When = { dateTime?: string; date?: string }
export type Work = {
  service: Service; operation: string; action_id?: string; timezone?: string; date?: string
  details: { date?: string; title?: string; start?: string; end?: string; attendees?: string[]; event_id?: string;
    duration_min?: number; client?: string; hours?: number; note?: string; sheet_name?: string }
  events?: { id: string; title: string; start: When; end: When; url?: string }[]
  slots?: { start: string; end: string }[]; total?: number; truncated?: boolean
  row?: number; range?: string; url?: string; title?: string; start?: string; end?: string
  error?: { message: string; hint?: string }
}
export type WorkCard = { work: Work; phase: Phase; operationId?: string }
export type WorkState = { active: Service | null; revision: number; calendar?: WorkCard; sheets?: WorkCard }
export const emptyWork: WorkState = { active: null, revision: 0 }
type WorkEvent = { type: string; phase?: string; status?: string; operation_id?: string; work?: Work }
const dateOf = (w: Work) => w.date || w.details.date || w.details.start?.slice(0, 10) || ''

export function reduceWork(state: WorkState, event: WorkEvent): WorkState {
  const w = event.work
  if (!w || !['calendar', 'sheets'].includes(w.service) || !['tool', 'approval_pending', 'approval_progress', 'approval_result'].includes(event.type)) return state
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
      : event.phase === 'start' ? 'working' : reading ? 'ready' : 'preparing'
  if (phase === 'saved' && w.service === 'calendar') {
    work.slots = [] // Availability was read before the write; never show it as still current.
    work.events = work.events?.filter(e => e.id !== work.details.event_id)
  }
  return { ...state, active: w.service, revision: state.revision + 1,
    [w.service]: { work, phase, operationId: event.operation_id ?? old?.operationId } }
}

export function googleLink(value: string | undefined, service: Service): string {
  try {
    const url = new URL(value || '')
    const hosts = service === 'calendar' ? ['calendar.google.com', 'www.google.com'] : ['docs.google.com']
    return url.protocol === 'https:' && !url.username && !url.password && hosts.includes(url.hostname) ? url.href : ''
  } catch { return '' }
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
