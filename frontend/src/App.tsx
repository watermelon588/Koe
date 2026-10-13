import { useEffect, useRef, useState, type CSSProperties, type FormEvent } from 'react'
import { CalendarBlank, ChatCircle, ChatCircleDots, GearSix, HandWaving, House, Key, Microphone, MicrophoneSlash, Moon, PaperPlaneRight,
  Phone, PhoneDisconnect, Sun, IconContext, Notebook, SidebarSimple } from '@phosphor-icons/react'
import { LiveWorkspace } from './workspace/LiveWorkspace'
import { moodOf, useCall, type Line } from './call/useCall'
import { MascotView, type MascotController } from './mascot/MascotView'
import { mascotProfile, savedMascot, saveMascot } from './mascot/catalog'
import { SettingsPage } from './settings/SettingsPage'
import { ChatPage } from './chat/ChatPage'
import { InstallPage } from './install/InstallPage'
import { savedToken, saveToken } from './chat/api'
import { SESSION } from './session'
import { NotionPage } from './notion/NotionPage'
import { Dashboard } from './dashboard/Dashboard'
import { useDashboard } from './dashboard/useDashboard'

// Layout (Engawa, "veranda"): she stands on the left; your day sits on the right; a call raises a sheet
// over it while she shows her full figure.
type Theme = 'dark' | 'light'

// Where she stands (0 = left edge, 1 = right edge) at home and during a call, on wide screens.
const PLACE = { home: 0.25, call: 0.24 }
const WIDE = '(min-width: 900px)'

const STATUS = { idle: 'Ready', connecting: 'Connecting', listening: 'Listening', thinking: 'Thinking', speaking: 'Speaking' }

function savedTheme(): Theme {
  try {
    return localStorage.getItem('koe-theme') === 'light' ? 'light' : 'dark'
  } catch {
    return 'dark' // storage can be blocked (private mode); dark is the default anyway
  }
}
type Page = 'home' | 'chat' | 'settings' | 'install' | 'notion'
const pageOf = (hash: string): Page =>
  hash === '#settings' ? 'settings' : hash === '#chat' ? 'chat' : hash === '#install' ? 'install' : hash === '#notion' ? 'notion' : 'home'

function greeting() {
  const h = new Date().getHours()
  return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening'
}

export default function App() {
  const [model, setModel] = useState(savedMascot)
  const [page, setPage] = useState<Page>(() => pageOf(location.hash))
  const [theme, setTheme] = useState<Theme>(savedTheme)
  const [wide, setWide] = useState(() => matchMedia(WIDE).matches)
  const [accessToken, setAccessToken] = useState(savedToken)
  const mascot = useRef<MascotController | null>(null)
  const call = useCall(mascot)
  const inCall = call.state !== 'idle'
  const dashboard = useDashboard(() => { if (!inCall) mascot.current?.react('sad', 3) })
  const x = wide ? PLACE[inCall ? 'call' : 'home'] : 0.5
  useEffect(() => {
    function navigate() {
      setPage(pageOf(location.hash))
      scrollTo({ top: 0 })
    }
    addEventListener('hashchange', navigate)
    return () => removeEventListener('hashchange', navigate)
  }, [inCall])

  useEffect(() => {
    const sync = () => setAccessToken(savedToken())
    addEventListener('koe-auth-change', sync)
    return () => removeEventListener('koe-auth-change', sync)
  }, [])

  useEffect(() => { document.getElementById('main-content')?.focus({ preventScroll: true }) }, [page])
  // Signed in with Google: the day loads by itself, no token to type.
  useEffect(() => { if (accessToken === SESSION) dashboard.connect(SESSION) }, [accessToken]) // eslint-disable-line react-hooks/exhaustive-deps -- once per sign-in

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
    url.searchParams.delete('ui') // the old layout switch
    history.replaceState(null, '', `${url.pathname}${url.search}${url.hash}`)
  }, [])

  // MascotView owns framing; bring the full figure into view when a phone call starts.
  useEffect(() => {
    if (inCall && !wide) scrollTo({ top: 0 })
  }, [inCall, wide])

  return (
    <IconContext.Provider value={{ size: 18, weight: 'light' }}>
    <div className="app" data-page={page} data-model={model} data-call={inCall ? 'on' : 'off'} data-state={call.state}>
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
          <button className="ghost" onClick={() => mascot.current?.gesture('wave')}><HandWaving />Say hi</button>
        </div>
      </div>}

      <header className="bar">
        <span className="brand">
          koe <span className="jp">声</span>
        </span>
        <nav className="controls" aria-label="Main navigation">
          <a className="nav-link" href="#home" aria-label="Home" title="Home" aria-current={page === 'home' ? 'page' : undefined}>
            <House weight={page === 'home' ? 'fill' : 'light'} /><span>Home</span>
          </a>
          <a className="nav-link" href="#chat" aria-label="Chat" title="Chat" aria-current={page === 'chat' ? 'page' : undefined}>
            <ChatCircleDots weight={page === 'chat' ? 'fill' : 'light'} /><span>Chat</span>
          </a>
          <a className="nav-link" href="#notion" aria-label="Notion" title="Notion" aria-current={page === 'notion' ? 'page' : undefined}>
            <Notebook weight={page === 'notion' ? 'fill' : 'light'} /><span>Notion</span>
          </a>
          <a className="nav-link" href="#settings" aria-label="Settings" aria-current={page === 'settings' ? 'page' : undefined} title="Settings">
            <GearSix weight={page === 'settings' ? 'fill' : 'light'} /><span>Settings</span>
          </a>
          <span className="bar-divider" aria-hidden="true" />
          <button className="icon-btn" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'} title={theme === 'dark' ? 'Light theme' : 'Dark theme'}>
            {theme === 'dark' ? <Sun /> : <Moon />}
          </button>
        </nav>
      </header>

      {page === 'settings' ? <SettingsPage selected={model} onSelect={(id) => {
        setModel(id)
        return saveMascot(id)
      }} /> : page === 'chat' ? <ChatPage model={model} /> : page === 'notion' ? <NotionPage token={accessToken} onToken={value => {
        setAccessToken(value); saveToken(value)
      }} /> : page === 'install' ? <InstallPage model={model} /> : <>
      <main className="home" id="main-content" tabIndex={-1} inert={inCall}>
        <section className="hello">
          <p className="date">{new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long' })}</p>
          <h1>{greeting()}, Rohit.</h1>
          <p className="sub">Ask about your day, your pull requests or your calendar.</p>
          <div className="actions">
            <button className="primary" onClick={() => { dashboard.connect(accessToken); call.start(accessToken) }}>
              <Phone weight="regular" />Call Koe
            </button>
            {call.error && <p className="error" role="alert">{call.error}</p>}
          </div>
        </section>

        {/* One quiet row until the dashboard is live; it disappears once connected. */}
        {!dashboard.connected && accessToken !== SESSION && <form className="connect" onSubmit={(e) => { e.preventDefault(); saveToken(accessToken); dashboard.connect(accessToken) }}>
          <label className="connect-field">
            <Key aria-hidden="true" />
            <input type="password" value={accessToken} onChange={(e) => setAccessToken(e.target.value)}
              placeholder="Koe access token" aria-label="Koe access token" autoComplete="off" />
          </label>
          <button className="ghost" disabled={!accessToken.trim()}>Connect</button>
          <p className="note" role="status">{dashboard.status}</p>
        </form>}

        <Dashboard data={dashboard.data} connected={dashboard.connected} refresh={dashboard.refresh} />
      </main>

      </>}
      <CallPanel open={inCall && page === 'home'} call={call} dashboard={dashboard} />
      {inCall && page !== 'home' && <aside className="workspace-call" aria-label="Active Koe call">
        <span className="dot" aria-hidden="true" /><span>{call.approval ? 'Your call has a pending approval' : `Koe · ${STATUS[call.state]}`}</span>
        <a className="soft" href="#home">Return to call</a>
        <button className="ghost" aria-pressed={call.muted} onClick={call.toggleMute}>{call.muted ? 'Unmute' : 'Mute'}</button>
        <button className="end" onClick={call.stop}>End call</button>
      </aside>}
    </div>
    </IconContext.Provider>
  )
}

export function CallPanel({ open, call, dashboard }: { open: boolean; call: ReturnType<typeof useCall>; dashboard: ReturnType<typeof useDashboard> }) {
  type View = 'chat' | 'day' | 'work'
  const [chosen, setChosen] = useState<{ view: View; revision: number }>({ view: 'chat', revision: -1 })
  // Koe touching Calendar/Sheets/Notion opens the live workspace tab; picking a tab wins until the next change.
  const tab = chosen.revision === call.workspace.revision ? chosen.view : call.workspace.active ? 'work' : 'chat'
  const setTab = (view: View) => setChosen({ view, revision: call.workspace.revision })
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

      <div className="call-tabs">
        <div className="seg" role="group" aria-label="Call view">
          <button aria-pressed={tab === 'chat'} onClick={() => setTab('chat')}><ChatCircle size={15} />Chat</button>
          <button aria-pressed={tab === 'day'} onClick={() => setTab('day')}><CalendarBlank size={15} />Day</button>
          <button aria-pressed={tab === 'work'} onClick={() => setTab('work')}><SidebarSimple size={15} />Workspace</button>
        </div>
      </div>
      {tab === 'work' ? <LiveWorkspace inline work={call.workspace}
        decision={(id) => (call.approval?.id === id ? { deciding: call.deciding, decide: call.decide } : null)} /> : tab === 'day' ? <div className="panel-day"><Dashboard data={dashboard.data} connected={dashboard.connected}
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
            <div className="approval-copy">
            <p>{call.approval.summary}</p>
            <small>{expired ? 'Expired. Ask Koe to propose it again.' : `Expires ${new Date(call.approval.expires_ts).toLocaleTimeString()}. Say yes/no or choose below.`}</small>
            </div>
            <div className="pair">
              <button className="ghost" type="button" disabled={expired || call.deciding} onClick={() => call.decide(false)}>Cancel</button>
              <button className="soft" type="button" disabled={expired || call.deciding} onClick={() => call.decide(true)}>{call.deciding ? 'Checking…' : 'Confirm'}</button>
            </div>
          </div>
        )}
        <input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Type a message" aria-label="Message" maxLength={2000} />
        <button className="icon-btn send" type="submit" aria-label="Send" title="Send" disabled={!draft.trim() || call.state === 'connecting'}>
          <PaperPlaneRight weight="regular" />
        </button>
      </form>
      <div className="panel-foot">
        <button className="ghost" aria-pressed={call.muted} onClick={call.toggleMute}>
          {call.muted ? <MicrophoneSlash /> : <Microphone />}{call.muted ? 'Unmute' : 'Mute'}
        </button>
        <button className="end" onClick={call.stop}>
          <PhoneDisconnect weight="regular" />End call
        </button>
      </div>
    </aside>
  )
}
