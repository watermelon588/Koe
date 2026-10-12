import { useEffect, useRef, useState, type CSSProperties, type FormEvent } from 'react'
import { moodOf, useCall, type Line } from './call/useCall'
import { MascotView, type MascotController } from './mascot/MascotView'
import { mascotProfile, savedMascot, saveMascot } from './mascot/catalog'
import { SettingsPage } from './settings/SettingsPage'
import { Dashboard } from './dashboard/Dashboard'
import { useDashboard } from './dashboard/useDashboard'

// Two layouts to choose between. Shoji: she stands on the right; on a call a panel slides in from the
// right and she steps left, full figure. Engawa: she stands on the left; on a call a sheet rises on
// the right. Same content, same call; different composition and motion.
const LAYOUTS = ['shoji', 'engawa'] as const
type Layout = (typeof LAYOUTS)[number]
type Theme = 'dark' | 'light'

// Where she stands (0 = left edge, 1 = right edge) at home and during a call, on wide screens.
const PLACE: Record<Layout, { home: number; call: number }> = {
  shoji: { home: 0.74, call: 0.3 },
  engawa: { home: 0.25, call: 0.24 },
}
const WIDE = '(min-width: 900px)'

const STATUS = { idle: 'Ready', connecting: 'Connecting', listening: 'Listening', thinking: 'Thinking', speaking: 'Speaking' }

function param<T extends string>(name: string, allowed: readonly T[]): T {
  const v = new URLSearchParams(location.search).get(name) as T
  return allowed.includes(v) ? v : allowed[0] // invalid layout parameters fall back to Shoji
}
function savedTheme(): Theme {
  try {
    return localStorage.getItem('koe-theme') === 'light' ? 'light' : 'dark'
  } catch {
    return 'dark' // storage can be blocked (private mode); dark is the default anyway
  }
}
function greeting() {
  const h = new Date().getHours()
  return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening'
}

export default function App() {
  const [model, setModel] = useState(savedMascot)
  const [page, setPage] = useState(() => location.hash === '#settings' ? 'settings' : 'home')
  const [layout, setLayout] = useState<Layout>(() => param('ui', LAYOUTS))
  const [theme, setTheme] = useState<Theme>(savedTheme)
  const [wide, setWide] = useState(() => matchMedia(WIDE).matches)
  const [accessToken, setAccessToken] = useState('')
  const mascot = useRef<MascotController | null>(null)
  const call = useCall(mascot)
  const inCall = call.state !== 'idle'
  const dashboard = useDashboard(() => { if (!inCall) mascot.current?.react('sad', 3) })
  const x = wide ? PLACE[layout][inCall ? 'call' : 'home'] : 0.5
  useEffect(() => {
    function navigate() {
      if (inCall) {
        history.replaceState(null, '', `${location.pathname}${location.search}#home`)
        return
      }
      setPage(location.hash === '#settings' ? 'settings' : 'home')
      scrollTo({ top: 0 })
    }
    addEventListener('hashchange', navigate)
    return () => removeEventListener('hashchange', navigate)
  }, [inCall])

  useEffect(() => { document.getElementById('main-content')?.focus({ preventScroll: true }) }, [page])

  useEffect(() => {
    const mq = matchMedia(WIDE)
    const on = () => setWide(mq.matches)
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [])

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem('koe-theme', theme)
    } catch {
      /* not saved; still works for this visit */
    }
  }, [theme])

  useEffect(() => {
    const url = new URL(location.href)
    url.searchParams.delete('model') // only Settings can change the saved profile preference
    url.searchParams.set('ui', layout)
    history.replaceState(null, '', `${url.pathname}${url.search}${url.hash}`)
  }, [layout])

  // MascotView owns framing; bring the full figure into view when a phone call starts.
  useEffect(() => {
    if (inCall && !wide) scrollTo({ top: 0 })
  }, [inCall, wide])

  return (
    <div className="app" data-page={page} data-layout={layout} data-model={model} data-call={inCall ? 'on' : 'off'} data-state={call.state}>
      {page === 'home' && <div className="stage" style={{ '--x': x } as CSSProperties}>
        <MascotView model={model} controller={mascot} shot={inCall ? 'full' : 'bust'} x={x} onReady={(m) => {
          m.listen(call.analyser.current)
          m.mood(moodOf(call.state))
        }} />
        {/* She stands behind this desk in the half-figure shot, so the screen edge never cuts her. */}
        <div className="desk" inert={inCall}>
          <div className="desk-who">
            <span className="dot" aria-hidden="true" />
            <span>{mascotProfile(model).name}</span>
            <span className="status">{call.error ? 'Couldn’t connect' : 'Ready'}</span>
          </div>
          <p className="desk-hint">Tap her hair, face or hands, or drag to turn her.</p>
          <button className="ghost" onClick={() => mascot.current?.gesture('wave')}>Say hi</button>
        </div>
      </div>}

      <header className="bar">
        <span className="brand">
          koe <span className="jp">声</span>
        </span>
        <div className="controls">
          <nav className="page-nav" aria-label="Main navigation">
            <a href="#home" aria-current={page === 'home' ? 'page' : undefined}>Home</a>
            <a href="#settings" aria-current={page === 'settings' ? 'page' : undefined} aria-disabled={inCall}
              title={inCall ? 'End your call to open Settings' : 'Profile and mascot preferences'}
              onClick={(e) => { if (inCall) e.preventDefault() }}>Settings</a>
          </nav>
          {page === 'home' && <>
          <Segmented label="Layout" value={layout} options={LAYOUTS} onChange={setLayout} />
          <button className="chip" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} aria-label="Switch theme">
            {theme === 'dark' ? 'Light' : 'Dark'}
          </button>
          </>}
        </div>
      </header>

      {page === 'settings' ? <SettingsPage selected={model} onSelect={(id) => {
        setModel(id)
        return saveMascot(id)
      }} /> : <>
      <main className="home" id="main-content" tabIndex={-1} inert={inCall}>
        <section className="hello">
          <p className="date">{new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long' })}</p>
          <h1>{greeting()}, Rohit.</h1>
          <p className="sub">Ask about your day, your pull requests or your calendar.</p>
          <div className="actions">
            <button className="primary" onClick={() => { dashboard.connect(accessToken); call.start(accessToken) }}>
              Call Koe
            </button>
            {call.error && <p className="error" role="alert">{call.error}</p>}
          </div>
          <label className="access-token">
            Koe access token
            <input type="password" value={accessToken} onChange={(e) => setAccessToken(e.target.value)}
              placeholder="Required when configured" autoComplete="off" />
          </label>
          <div className="dashboard-connect">
            <button className="ghost" disabled={!accessToken.trim()} onClick={() => dashboard.connect(accessToken)}>Connect dashboard</button>
            <p className="note" role="status">{dashboard.status}</p>
          </div>
        </section>

        <Dashboard data={dashboard.data} connected={dashboard.connected} refresh={dashboard.refresh} />
      </main>

      <CallPanel open={inCall} call={call} dashboard={dashboard} />
      </>}
    </div>
  )
}

function Segmented<T extends string>(p: { label: string; value: T; options: readonly T[]; onChange: (v: T) => void }) {
  return (
    <div className="seg" role="group" aria-label={p.label}>
      {p.options.map((o) => (
        <button key={o} aria-pressed={o === p.value} onClick={() => p.onChange(o)}>
          {o[0].toUpperCase() + o.slice(1)}
        </button>
      ))}
    </div>
  )
}

function CallPanel({ open, call, dashboard }: { open: boolean; call: ReturnType<typeof useCall>; dashboard: ReturnType<typeof useDashboard> }) {
  const [tab, setTab] = useState<'chat' | 'day'>('chat')
  const [clock, setClock] = useState(Date.now)
  useEffect(() => { if (!open) return; const timer = setInterval(() => setClock(Date.now()), 1000); return () => clearInterval(timer) }, [open])
  const expired = !!call.approval && new Date(call.approval.expires_ts).getTime() <= clock
  const [draft, setDraft] = useState('')
  const list = useRef<HTMLOListElement>(null)
  useEffect(() => {
    list.current?.scrollTo({ top: list.current.scrollHeight }) // follow the conversation
  }, [call.lines])

  function submit(e: FormEvent) {
    e.preventDefault()
    if (call.send(draft)) setDraft('')
  }

  return (
    <aside className="panel" aria-label="Call with Koe" inert={!open}>
      <div className="panel-head">
        <div className="who">
          <span className="dot" aria-hidden="true" />
          <span>Koe</span>
          <span className="status" aria-live="polite">{STATUS[call.state]}</span>
        </div>
        {call.latency !== null && <span className="latency" title="You stopped speaking → Koe’s first audio">{(call.latency / 1000).toFixed(2)} s</span>}
      </div>

      <div className="call-tabs"><Segmented label="Call view" value={tab} options={['chat', 'day'] as const} onChange={setTab} /></div>
      {tab === 'day' ? <div className="panel-day"><Dashboard data={dashboard.data} connected={dashboard.connected}
        currentApproval={call.approval} decide={call.decide} refresh={dashboard.refresh} /></div> : <ol className="transcript" ref={list} aria-live="polite">
        {call.lines.length === 0 && <li className="empty">Say hi, or type below.</li>}
        {call.lines.map((l: Line) => (
          <li key={l.id} className={l.who}>
            {l.who !== 'tool' && <small>{l.who === 'you' ? 'You' : 'Koe'}</small>}
            <p>{l.text}</p>
          </li>
        ))}
      </ol>}

      <form className="composer" onSubmit={submit}>
        {call.approval && (
          <div className="approval-card" role="status">
            <p>{call.approval.summary}</p>
            <small>{expired ? 'Expired. Ask Koe to propose it again.' : `Expires ${new Date(call.approval.expires_ts).toLocaleTimeString()}. Say yes/no or choose below.`}</small>
            <div className="pair">
              <button className="ghost" type="button" disabled={expired} onClick={() => call.decide(false)}>Cancel</button>
              <button className="soft" type="button" disabled={expired} onClick={() => call.decide(true)}>Confirm</button>
            </div>
          </div>
        )}
        <input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Type a message" aria-label="Message" maxLength={2000} />
        <button className="soft" type="submit" disabled={!draft.trim() || call.state === 'connecting'}>
          Send
        </button>
      </form>
      <div className="panel-foot">
        <button className="ghost" aria-pressed={call.muted} onClick={call.toggleMute}>
          {call.muted ? 'Unmute' : 'Mute'}
        </button>
        <button className="end" onClick={call.stop}>
          End call
        </button>
      </div>
    </aside>
  )
}
