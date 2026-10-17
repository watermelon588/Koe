import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { BellRinging, GearSix, Microphone, PaperPlaneRight, Pause, Phone, Play, SidebarSimple, Trash } from '@phosphor-icons/react'
import { mascotProfile, type MascotId } from '../mascot/catalog'
import { api, AuthError, saveToken, type Message, type Reply } from './api'
import { record } from './recorder'
import { acquire, AudioBusy } from '../audio/coordinator'
import { resendPush } from '../pwa'
import { LiveWorkspace } from '../workspace/LiveWorkspace'
import { emptyWork, reduceWork, SERVICES, type WorkEvent } from '../workspace/workState'
import './chat.css'
import { ApprovalPreview } from '../approvals/ApprovalPreview'
import { approvalMessageText } from '../approvals/presentation'
import { clockTime } from '../dashboard/state'

// The Koe app's home on the phone (SPEC §14): a WhatsApp-style chat with Koe. Text or voice notes; Koe answers a
// voice note with a voice note; proposals come with Confirm / Cancel; GitHub alerts land here too.
const MAX_RECORD_SECONDS = 90

export function ChatPage({ model }: { model: MascotId }) {
  const profile = mascotProfile(model)
  const [messages, setMessages] = useState<Message[]>([])
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false) // waiting for Koe
  const [needToken, setNeedToken] = useState(false)
  const [error, setError] = useState('')
  const [recording, setRecording] = useState<{ finish: () => Blob; cancel: () => void; started: number } | null>(null)
  const [now, setNow] = useState(Date.now)
  const thread = useRef<HTMLOListElement>(null)
  const mounted = useRef(true)
  const activeRecording = useRef(recording)
  useEffect(() => { activeRecording.current = recording }, [recording])
  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false; activeRecording.current?.cancel() }
  }, [])
  const lastId = messages.filter((m) => !m.sending).at(-1)?.id ?? 0
  // The live workspace: what Koe read, proposed or wrote in Calendar/Sheets/Notion, beside the chat.
  const [work, setWork] = useState(emptyWork)
  const [panelOpen, setPanelOpen] = useState(false)
  const [deciding, setDeciding] = useState<string | null>(null)
  const toggle = useRef<HTMLButtonElement>(null)
  const panelHeading = useRef<HTMLHeadingElement>(null)
  const absorb = useCallback((events: WorkEvent[] = [], reveal = true) => {
    if (!events.length) return
    setWork((w) => events.reduce(reduceWork, w))
    const results = events.filter((e) => e.type === 'approval_result' && e.work?.action_id)
    if (results.length) setMessages((ms) => ms.map((m) => {
      const r = results.find((e) => e.work!.action_id === m.action_id)
      return r && !m.action_status ? { ...m, action_status: r.status ?? 'failed' } : m
    }))
    if (reveal) setPanelOpen(true) // opens without taking focus: you keep typing
  }, [])
  function openPanel(open: boolean) {
    setPanelOpen(open)
    requestAnimationFrame(() => (open ? panelHeading.current : toggle.current)?.focus())
  }

  const fail = useCallback((e: unknown) => {
    if (e instanceof AuthError) setNeedToken(true)
    else setError(e instanceof Error ? e.message : String(e))
  }, [])

  const load = useCallback(async (after: number) => {
    try {
      const { messages: fresh, workspace } = await api.messages(after)
      if (fresh.length) setMessages((ms) => [...ms.filter((m) => !fresh.some((f) => f.id === m.id)), ...fresh])
      absorb(workspace, false) // an open proposal after a reload: ready behind the panel button
      setNeedToken(false)
    } catch (e) {
      fail(e)
    }
  }, [fail, absorb])

  useEffect(() => { void load(0); resendPush().catch(() => {}) }, [load])
  // New messages while the app is open: the service worker pings us on push; also re-check on return to the app.
  useEffect(() => {
    const onPush = (e: MessageEvent) => { if (e.data?.type === 'koe-refresh') void load(lastId) }
    const onVisible = () => { if (document.visibilityState === 'visible') void load(lastId) }
    navigator.serviceWorker?.addEventListener('message', onPush)
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      navigator.serviceWorker?.removeEventListener('message', onPush)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [load, lastId])
  useEffect(() => { thread.current?.scrollTo({ top: thread.current.scrollHeight, behavior: 'smooth' }) }, [messages, busy])

  // Recording timer, with an automatic send at the size limit.
  const sendLatest = useRef<() => void>(() => {})
  useEffect(() => {
    if (!recording) return
    const timer = setInterval(() => {
      setNow(Date.now())
      if (Date.now() - recording.started >= MAX_RECORD_SECONDS * 1000) sendLatest.current()
    }, 250)
    return () => clearInterval(timer)
  }, [recording])
  const seconds = recording ? Math.floor((now - recording.started) / 1000) : 0

  async function deliver(local: Message, send: () => Promise<Reply>) {
    setError('')
    setMessages((ms) => [...ms, local])
    setBusy(true)
    try {
      const { messages: saved, workspace } = await send()
      setMessages((ms) => [...ms.filter((m) => m.id !== local.id), ...saved.filter((s) => !ms.some((m) => m.id === s.id))])
      absorb(workspace)
    } catch (e) {
      setMessages((ms) => ms.filter((m) => m.id !== local.id))
      fail(e)
    } finally {
      setBusy(false)
    }
  }
  const localMessage = (text: string, voice: string | null = null): Message =>
    ({ id: -Date.now(), ts: new Date().toISOString(), role: 'you', text, voice, action_id: null, action_status: null, sending: true })

  function submit(e: FormEvent) {
    e.preventDefault()
    const text = draft.trim()
    if (!text || busy) return
    setDraft('')
    void deliver(localMessage(text), () => api.send(text))
  }

  async function startRecording() {
    setError('')
    try {
      const session = await record()
      if (!mounted.current) { session.cancel(); return }
      const active = { ...session, started: Date.now() }
      activeRecording.current = active
      setRecording(active)
      setNow(Date.now())
    } catch (e) {
      setError(e instanceof AudioBusy ? e.message : `Microphone: ${e instanceof Error ? e.message : e}`)
    }
  }
  const sendRecording = useCallback(() => {
    if (!recording) return
    try {
      const wav = recording.finish()
      void deliver(localMessage('Voice note', 'local'), () => api.sendVoice(wav))
    } catch (error) { fail(error) }
    finally { setRecording(null); activeRecording.current = null }
  }, [recording]) // eslint-disable-line react-hooks/exhaustive-deps -- deliver is stable enough per render
  useEffect(() => { sendLatest.current = sendRecording }, [sendRecording])

  // One decision path for the bubble's and the panel's Confirm/Cancel: POST /api/app/approvals/{id} (SPEC §5).
  async function decide(actionId: string, approve: boolean) {
    if (deciding) return
    const card = SERVICES.map((s) => work[s]).find((c) => c?.work.action_id === actionId && c.phase === 'waiting')
    setDeciding(actionId)
    if (card && approve) setWork((w) => reduceWork(w, { type: 'approval_progress', work: card.work }))
    try {
      const r = await api.decide(actionId, approve)
      setMessages((ms) => [...ms.map((x) => (x.action_id === r.action.id ? { ...x, action_status: r.action.status } : x)), ...r.messages])
      absorb(r.workspace)
    } catch (e) {
      if (card) setWork((w) => reduceWork(w, { type: 'approval_pending', work: card.work })) // still undecided
      fail(e)
    } finally {
      setDeciding(null)
    }
  }
  const undecided = (actionId: string) => messages.some((m) => m.action_id === actionId && !m.action_status)
  const hasWork = SERVICES.some((s) => work[s])

  return (
    <>
    <main className="chat-page" id="main-content" tabIndex={-1} data-mascot={model} data-workspace={panelOpen ? 'open' : undefined}>
      <header className="chat-head">
        <img className="avatar" src={profile.portrait} alt="" width="40" height="40" />
        <div className="chat-who">
          <span>{profile.name}</span>
          <small aria-live="polite">{recording ? 'listening…' : busy ? 'typing…' : 'Koe, your assistant'}</small>
        </div>
        <button ref={toggle} className="icon-btn lw-toggle" aria-label={panelOpen ? 'Hide live workspace' : 'Show live workspace'} title="Live workspace"
          aria-expanded={panelOpen} aria-controls="live-workspace" data-has-work={hasWork || undefined} onClick={() => openPanel(!panelOpen)}><SidebarSimple /></button>
        <a className="icon-btn" href="/app" aria-label="Call Koe" title="Call"><Phone /></a>
        <a className="icon-btn" href="/app/settings" aria-label="Settings" title="Settings"><GearSix /></a>
      </header>

      <ol className="thread" ref={thread} aria-label="Conversation with Koe">
        {needToken && <li className="token-card"><TokenForm onSaved={() => { setNeedToken(false); void load(0) }} /></li>}
        {!needToken && !messages.length && (
          <li className="chat-empty">
            <img src={profile.portrait} alt="" width="96" height="96" />
            <p>Say hi to {profile.name}.</p>
            <small>Type, or tap the mic to send a voice note.</small>
          </li>
        )}
        {messages.map((m) => <Bubble key={m.id} m={m} busy={deciding === m.action_id} onDecide={(approve) => decide(m.action_id!, approve)} />)}
        {busy && <li className="msg koe typing" aria-label="Koe is typing"><i /><i /><i /></li>}
      </ol>

      {error && <p className="chat-error" role="alert">{error}</p>}
      <form className="chat-compose" onSubmit={submit}>
        {recording ? <>
          <button type="button" className="icon-btn" aria-label="Discard voice note" onClick={() => { recording.cancel(); setRecording(null) }}><Trash /></button>
          <div className="rec"><span className="rec-dot" aria-hidden="true" /><time>{Math.floor(seconds / 60)}:{String(seconds % 60).padStart(2, '0')}</time><span>Recording</span></div>
          <button type="button" className="icon-btn round" aria-label="Send voice note" onClick={sendRecording}><PaperPlaneRight weight="regular" /></button>
        </> : <>
          <input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Message" aria-label="Message" maxLength={2000} disabled={needToken} />
          {draft.trim()
            ? <button className="icon-btn round" type="submit" aria-label="Send" disabled={busy}><PaperPlaneRight weight="regular" /></button>
            : <button className="icon-btn round" type="button" aria-label="Record a voice note" disabled={busy || needToken} onClick={startRecording}><Microphone weight="regular" /></button>}
        </>}
      </form>
    </main>
    <LiveWorkspace work={work} open={panelOpen} onClose={() => openPanel(false)} headingRef={panelHeading}
      decision={(id) => (undecided(id) ? { deciding: deciding === id, decide: (approve) => void decide(id, approve) } : null)} />
    </>
  )
}

function Bubble({ m, busy, onDecide }: { m: Message; busy: boolean; onDecide: (approve: boolean) => void }) {
  const time = clockTime(m.ts)
  const text = approvalMessageText(m.text, m.approval)
  if (m.role === 'alert') {
    return <li className="msg alert"><BellRinging /><p>{m.text}</p><time>{time}</time></li>
  }
  const decided = { executed: 'Done', rejected: 'Cancelled', failed: 'Failed' }[m.action_status ?? ''] ?? 'No longer available'
  return (
    <li className={`msg ${m.role}`} data-sending={m.sending || undefined}>
      {m.voice && m.voice !== 'local' && <VoiceNote name={m.voice} />}
      {text && <p className={m.voice ? 'transcript' : undefined}>{text}</p>}
      {m.action_id && m.approval && <ApprovalPreview action={m.approval} />}
      {m.action_id && (m.action_status
        ? <p className="decided">{decided}</p>
        : <div className="pair">
            <button className="ghost" disabled={busy} onClick={() => onDecide(false)}>Cancel</button>
            <button className="soft" disabled={busy} onClick={() => onDecide(true)}>{busy ? 'Checking…' : 'Confirm'}</button>
          </div>)}
      <time>{m.sending ? 'sending…' : time}</time>
    </li>
  )
}

// One voice note plays at a time, like WhatsApp: starting one pauses the other. The audio coordinator does that,
// and also pauses in-app music first (or refuses during a call or recording).
function VoiceNote({ name }: { name: string }) {
  const audio = useRef<HTMLAudioElement | null>(null)
  const release = useRef<() => void>(() => {})
  const [state, setState] = useState<'idle' | 'loading' | 'playing'>('idle')
  const [progress, setProgress] = useState(0)
  const [length, setLength] = useState<number | null>(null)
  const [blocked, setBlocked] = useState('')

  async function toggle() {
    if (state === 'loading') return // a second tap while downloading used to start a second copy: an echo
    if (state === 'playing') return audio.current?.pause()
    setBlocked('')
    if (!audio.current) {
      setState('loading')
      try {
        const a = new Audio(await api.voice(name))
        a.ontimeupdate = () => setProgress(a.duration ? a.currentTime / a.duration : 0)
        a.onloadedmetadata = () => setLength(a.duration)
        a.onplay = () => setState('playing')
        a.onpause = () => { setState('idle'); release.current() }
        a.onended = () => { setState('idle'); setProgress(0); release.current() }
        audio.current = a
      } catch {
        return setState('idle')
      }
    }
    const a = audio.current
    try {
      release.current = await acquire('reply', () => a.pause())
    } catch (e) {
      setState('idle')
      return setBlocked(e instanceof Error ? e.message : String(e))
    }
    a.play().catch(() => { setState('idle'); release.current() })
  }
  useEffect(() => () => audio.current?.pause(), [])

  return (
    <div className="voice">
      <button type="button" className="icon-btn round small" aria-label={state === 'playing' ? 'Pause voice note' : 'Play voice note'}
        aria-busy={state === 'loading'} disabled={state === 'loading'} onClick={() => void toggle()}>
        {state === 'playing' ? <Pause weight="fill" /> : <Play weight="fill" />}
      </button>
      <span className="voice-track"><span style={{ transform: `scaleX(${progress})` }} /></span>
      <time>{state === 'loading' ? 'Loading…' : length ? `${Math.floor(length / 60)}:${String(Math.round(length % 60)).padStart(2, '0')}` : 'Voice'}</time>
      {blocked && <small className="voice-blocked" role="status">{blocked}</small>}
    </div>
  )
}

function TokenForm({ onSaved }: { onSaved: () => void }) {
  const [value, setValue] = useState('')
  return (
    <form onSubmit={(e) => { e.preventDefault(); if (value.trim()) { saveToken(value); onSaved() } }}>
      <p>Enter your Koe access token to start. It stays on this device.</p>
      <div className="token-row">
        <input type="password" value={value} onChange={(e) => setValue(e.target.value)} placeholder="KOE_ACCESS_TOKEN" aria-label="Koe access token" autoComplete="off" />
        <button className="soft" disabled={!value.trim()}>Save</button>
      </div>
    </form>
  )
}
