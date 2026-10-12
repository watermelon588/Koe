import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { BellRinging, GearSix, Microphone, PaperPlaneRight, Pause, Phone, Play, Trash } from '@phosphor-icons/react'
import { mascotProfile, type MascotId } from '../mascot/catalog'
import { api, AuthError, saveToken, type Message } from './api'
import { record } from './recorder'
import './chat.css'

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
  const lastId = messages.filter((m) => !m.sending).at(-1)?.id ?? 0

  const fail = useCallback((e: unknown) => {
    if (e instanceof AuthError) setNeedToken(true)
    else setError(e instanceof Error ? e.message : String(e))
  }, [])

  const load = useCallback(async (after: number) => {
    try {
      const fresh = await api.messages(after)
      if (fresh.length) setMessages((ms) => [...ms.filter((m) => !fresh.some((f) => f.id === m.id)), ...fresh])
      setNeedToken(false)
    } catch (e) {
      fail(e)
    }
  }, [fail])

  useEffect(() => { void load(0) }, [load])
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

  async function deliver(local: Message, send: () => Promise<Message[]>) {
    setError('')
    setMessages((ms) => [...ms, local])
    setBusy(true)
    try {
      const saved = await send()
      setMessages((ms) => [...ms.filter((m) => m.id !== local.id), ...saved.filter((s) => !ms.some((m) => m.id === s.id))])
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
      setRecording({ ...(await record()), started: Date.now() })
      setNow(Date.now())
    } catch (e) {
      setError(`Microphone: ${e instanceof Error ? e.message : e}`)
    }
  }
  const sendRecording = useCallback(() => {
    if (!recording) return
    const wav = recording.finish()
    setRecording(null)
    void deliver(localMessage('Voice note', 'local'), () => api.sendVoice(wav))
  }, [recording]) // eslint-disable-line react-hooks/exhaustive-deps -- deliver is stable enough per render
  useEffect(() => { sendLatest.current = sendRecording }, [sendRecording])

  async function decide(m: Message, approve: boolean) {
    try {
      const r = await api.decide(m.action_id!, approve)
      setMessages((ms) => [...ms.map((x) => (x.action_id === r.action.id ? { ...x, action_status: r.action.status } : x)), ...r.messages])
    } catch (e) {
      fail(e)
    }
  }

  return (
    <main className="chat-page" id="main-content" tabIndex={-1} data-mascot={model}>
      <header className="chat-head">
        <img className="avatar" src={profile.portrait} alt="" width="40" height="40" />
        <div className="chat-who">
          <span>{profile.name}</span>
          <small aria-live="polite">{recording ? 'listening…' : busy ? 'typing…' : 'Koe, your assistant'}</small>
        </div>
        <a className="icon-btn" href="#home" aria-label="Call Koe" title="Call"><Phone /></a>
        <a className="icon-btn" href="#settings" aria-label="Settings" title="Settings"><GearSix /></a>
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
        {messages.map((m) => <Bubble key={m.id} m={m} onDecide={(approve) => decide(m, approve)} />)}
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
  )
}

function Bubble({ m, onDecide }: { m: Message; onDecide: (approve: boolean) => void }) {
  const time = new Date(m.ts).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
  if (m.role === 'alert') {
    return <li className="msg alert"><BellRinging /><p>{m.text}</p><time>{time}</time></li>
  }
  const decided = { executed: 'Done', rejected: 'Cancelled', failed: 'Failed' }[m.action_status ?? ''] ?? 'No longer available'
  return (
    <li className={`msg ${m.role}`} data-sending={m.sending || undefined}>
      {m.voice && m.voice !== 'local' && <VoiceNote name={m.voice} />}
      {m.text && <p className={m.voice ? 'transcript' : undefined}>{m.text}</p>}
      {m.action_id && (m.action_status
        ? <p className="decided">{decided}</p>
        : <div className="pair">
            <button className="ghost" onClick={() => onDecide(false)}>Cancel</button>
            <button className="soft" onClick={() => onDecide(true)}>Confirm</button>
          </div>)}
      <time>{m.sending ? 'sending…' : time}</time>
    </li>
  )
}

function VoiceNote({ name }: { name: string }) {
  const audio = useRef<HTMLAudioElement | null>(null)
  const [playing, setPlaying] = useState(false)
  const [progress, setProgress] = useState(0)
  const [length, setLength] = useState<number | null>(null)

  async function toggle() {
    if (!audio.current) {
      const a = new Audio(await api.voice(name))
      a.ontimeupdate = () => setProgress(a.duration ? a.currentTime / a.duration : 0)
      a.onloadedmetadata = () => setLength(a.duration)
      a.onended = () => { setPlaying(false); setProgress(0) }
      audio.current = a
    }
    if (playing) audio.current.pause()
    else void audio.current.play()
    setPlaying(!playing)
  }
  useEffect(() => () => audio.current?.pause(), [])

  return (
    <div className="voice">
      <button type="button" className="icon-btn round small" aria-label={playing ? 'Pause voice note' : 'Play voice note'} onClick={toggle}>
        {playing ? <Pause weight="fill" /> : <Play weight="fill" />}
      </button>
      <span className="voice-track"><span style={{ transform: `scaleX(${progress})` }} /></span>
      <time>{length ? `${Math.floor(length / 60)}:${String(Math.round(length % 60)).padStart(2, '0')}` : 'Voice'}</time>
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
