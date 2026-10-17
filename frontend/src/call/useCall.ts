import { wsCredential } from '../session'
import { useEffect, useRef, useState } from 'react'
import { startMic } from './mic'
import { createPlayer } from './player'
import type { createMascot, Mood } from '../mascot/mascot'
import { wsUrl } from '../backend'
import { emptyWork, reduceWork } from '../workspace/workState'
import { acquire } from '../audio/coordinator'
import { music as musicRequest } from '../music/api'

// One live call over /ws/call: mic up, Koe's voice down, plus the chat transcript, typed messages,
// mute, and the mascot's moods. Wire format: SPEC §2 "/ws/call wire format".
type Mascot = ReturnType<typeof createMascot>
export type CallState = 'idle' | 'connecting' | 'listening' | 'thinking' | 'speaking'
// A chat line. `open` = still growing (transcripts arrive in pieces).
export type Line = { id: number; who: 'you' | 'koe' | 'tool'; text: string; open: boolean }
export type Approval = import('../dashboard/state').Approval

const TOOL_LABEL: Record<string, string> = {
  github_my_prs: 'Checking your pull requests',
  github_review_queue: 'Checking your review queue',
  github_pr_summary: 'Reading the pull request',
  github_shipped: 'Looking at what you shipped',
  calendar_list: 'Checking your calendar',
  calendar_find_free: 'Looking for a free slot',
  calendar_upsert_event: 'Preparing your Calendar change',
  sheets_log_hours: 'Preparing your Sheets row',
  notion_save: 'Preparing your Notion record',
  notion_archive: 'Preparing to move a Notion record to trash',
  notion_log: 'Writing your Notion daily log',
  notion_read: 'Reading your Notion records',
  notion_schema: 'Reading your Notion properties',
  notion_add_properties: 'Preparing new Notion properties',
  calendar_get_event: 'Reading the event',
  calendar_cancel_event: 'Preparing a cancellation',
  sheets_schema: 'Reading your timesheet columns',
  sheets_find_rows: 'Finding timesheet rows',
  sheets_add_columns: 'Preparing new timesheet columns',
  sheets_update_row: 'Preparing a timesheet edit',
  github_activity: 'Counting your GitHub activity',
  github_contributions: 'Reading your contribution graph',
  github_comment: 'Preparing your pull request comment',
}
export const moodOf = (s: CallState): Mood => (s === 'thinking' ? 'thinking' : s === 'idle' || s === 'connecting' ? 'idle' : 'listening')

let nextId = 1
function add(lines: Line[], who: Line['who'], text: string, open: boolean): Line[] {
  const last = lines.at(-1)
  if (last?.open && last.who === who) return [...lines.slice(0, -1), { ...last, text: last.text + text, open }]
  return [...lines.map((l) => (l.open ? { ...l, open: false } : l)), { id: nextId++, who, text, open }]
}
const closeAll = (lines: Line[]) => lines.map((l) => (l.open ? { ...l, open: false } : l))

export function useCall(mascot: { current: Mascot | null }) {
  const [state, setStateRaw] = useState<CallState>('idle')
  const [lines, setLines] = useState<Line[]>([])
  const [error, setError] = useState('')
  const [latency, setLatency] = useState<number | null>(null)
  const [muted, setMuted] = useState(false)
  const [approval, setApproval] = useState<Approval | null>(null)
  const [workspace, setWorkspace] = useState(emptyWork)
  const [deciding, setDeciding] = useState(false)
  const stateRef = useRef<CallState>('idle')
  const mutedRef = useRef(false)
  const analyser = useRef<AnalyserNode | null>(null) // Koe's voice, for the mascot's mouth
  const live = useRef<{ ws: WebSocket; stop: () => void } | null>(null)
  const starting = useRef(0) // id of a start still waiting for audio (music pausing); 0 = none

  function setState(s: CallState) {
    stateRef.current = s
    setStateRaw(s)
    mascot.current?.mood(moodOf(s))
  }

  async function start(accessToken = '', prepare?: () => Promise<void>) {
    if (live.current || starting.current) return
    const id = Date.now()
    starting.current = id
    setError('')
    setLines([])
    setLatency(null)
    setApproval(null)
    setDeciding(false)
    setWorkspace(old => ({ ...emptyWork, revision: old.revision + 1 }))
    // Created on the click: browsers only allow audio after a user gesture. It stays silent until the socket opens.
    const player = createPlayer()
    setState('connecting')
    let release: () => void
    try {
      await prepare?.()
      if (starting.current !== id) { await player.ctx.close(); return }
      release = await acquire('call', () => { starting.current = 0; live.current?.stop(); setError('Music resumed unexpectedly. Koe stopped audio for safety.') })
    } catch (err) {
      player.ctx.close()
      if (starting.current === id) { starting.current = 0; setState('idle') }
      setError(err instanceof Error ? err.message : String(err))
      return
    }
    if (starting.current !== id) { release(); player.ctx.close(); return } // ended while the music was pausing
    starting.current = 0
    analyser.current = player.analyser
    mascot.current?.listen(player.analyser)
    const ws = new WebSocket(wsUrl('/ws/call'))
    ws.binaryType = 'arraybuffer'
    let stopMic = () => {}
    let failed = ''
    let tools = 0 // tools running right now
    let decisionRunning = false
    let musicHandoff: string | null = null
    let completedTurn = 0
    let loudAt = 0
    const buf = new Float32Array(2048)
    // Speaking = Koe's audio is loud right now (held 0.4 s so pauses between words don't flicker).
    const tick = setInterval(() => {
      if (stateRef.current === 'connecting') return
      player.analyser.getFloatTimeDomainData(buf)
      let sum = 0
      for (const s of buf) sum += s * s
      if (Math.sqrt(sum / buf.length) > 0.01) loudAt = performance.now()
      const next = performance.now() - loudAt < 400 ? 'speaking' : tools > 0 || decisionRunning ? 'thinking' : 'listening'
      if (next !== stateRef.current) setState(next)
    }, 100)
    const stop = () => {
      if (live.current?.ws !== ws) return Promise.resolve()
      live.current = null
      clearInterval(tick)
      stopMic()
      ws.close()
      const silent = player.ctx.close().finally(release) // only a specific requested handoff may start music later
      analyser.current = null
      mascot.current?.listen(null)
      setLines(closeAll)
      setState('idle')
      setApproval(null)
      setDeciding(false)
      return silent
    }
    live.current = { ws, stop }

    // Binary frames = Koe's voice; text frames = control events.
    ws.onmessage = (e) => {
      if (live.current?.ws !== ws) return // a late frame after hang-up must not play
      if (typeof e.data !== 'string') return player.play(e.data)
      const msg = JSON.parse(e.data)
      setWorkspace(old => reduceWork(old, msg))
      if (msg.type === 'interrupted') {
        completedTurn++
        musicHandoff = null // barge-in cancels queued playback; never resume on a later unrelated turn
        player.flush()
        setLines(closeAll)
      }
      if (msg.type === 'latency') setLatency(msg.ms)
      if (msg.type === 'transcript') setLines((ls) => add(ls, msg.role === 'user' ? 'you' : 'koe', msg.text, true))
      if (msg.type === 'music_handoff' && /^[a-f0-9]{64}$/.test(msg.id)) musicHandoff = msg.id
      if (msg.type === 'turn_complete') {
        setLines(closeAll)
        const handoff = musicHandoff, turn = ++completedTurn
        if (handoff) void player.drained().then(async () => {
          if (live.current?.ws !== ws || turn !== completedTurn || musicHandoff !== handoff) return
          musicHandoff = null
          await stop() // microphone, voice output and cross-tab audio ownership are released first
          const reply = await musicRequest('/api/music/voice-release', 'POST', { id: handoff })
          if (reply.http !== 200 || (reply.body as { state?: string })?.state !== 'applied') setError('Music playback was not confirmed. Check the music window before retrying.')
        }).catch(() => setError('Music handoff was not confirmed. Check the music window.'))
      }
      if (msg.type === 'approval_pending') setApproval({ id: msg.id, summary: msg.summary, display: msg.display, expires_ts: msg.expires_ts })
      if (msg.type === 'approval_result') {
        decisionRunning = false
        setDeciding(false)
        setApproval(msg.pending_action ?? null)
        const text = msg.error ? `${msg.error.message} ${msg.error.hint ?? ''}`
          : msg.status === 'executed' ? `Saved: ${msg.title ?? 'Approved action'}` : 'Cancelled. Nothing was changed.'
        setLines((ls) => add(ls, 'tool', text, false))
        mascot.current?.react(msg.status === 'executed' ? 'happy' : msg.error ? 'sad' : 'happy')
      }
      if (msg.type === 'approval_progress') { decisionRunning = true; setDeciding(true) }
      if (msg.type === 'tool' && msg.phase === 'start') {
        tools++
        setLines((ls) => add(ls, 'tool', TOOL_LABEL[msg.name] ?? `Using ${msg.name}`, false))
      }
      if (msg.type === 'tool' && msg.phase === 'end') {
        tools = Math.max(0, tools - 1)
        mascot.current?.react(msg.ok ? 'happy' : 'sad')
      }
    }
    ws.onerror = () => (failed = 'Couldn’t reach Koe. Is the backend running on port 8000?')
    ws.onclose = (e) => {
      stop()
      if (e.reason || failed) {
        setError(e.reason || failed)
        mascot.current?.react('sad', 4)
      }
    }
    ws.onopen = async () => {
      try {
        // The private app token is sent in a frame, never in the URL or a bundled environment variable.
        ws.send(JSON.stringify({ type: 'auth', token: await wsCredential(accessToken) })) // signed in: a one-time ticket
        stopMic = await startMic((pcm) => ws.readyState === WebSocket.OPEN && !mutedRef.current && ws.send(pcm))
        if (live.current?.ws !== ws) return stopMic() // hung up while the mic prompt was open
        setState('listening')
        mascot.current?.gesture('wave')
      } catch (err) {
        failed = `Microphone: ${err instanceof Error ? err.message : err}`
        ws.close()
      }
    }
  }

  // A typed message: same conversation, Koe answers out loud (and in the transcript).
  function send(text: string) {
    const ws = live.current?.ws
    if (!ws || ws.readyState !== WebSocket.OPEN || !text.trim()) return false
    ws.send(JSON.stringify({ type: 'text', text }))
    setLines((ls) => add(ls, 'you', text.trim(), false))
    return true
  }

  function toggleMute() {
    mutedRef.current = !mutedRef.current
    setMuted(mutedRef.current)
  }

  function decide(approve: boolean) {
    const ws = live.current?.ws
    if (!approval || deciding || !ws || ws.readyState !== WebSocket.OPEN) return
    setDeciding(true)
    ws.send(JSON.stringify({ type: 'approval', action_id: approval.id, approve }))
  }

  function stop() {
    if (live.current) return live.current.stop()
    if (starting.current) { starting.current = 0; setState('idle') } // still waiting for the music to pause
  }
  useEffect(() => stop, []) // eslint-disable-line react-hooks/exhaustive-deps -- leaving the page ends the call

  return { state, lines, error, latency, muted, approval, deciding, workspace, analyser, start, stop, send, toggleMute, decide }
}
