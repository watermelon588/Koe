import { useEffect, useState } from 'react'
import { CalendarBlank, GithubLogo, NotePencil, Sparkle, Table } from '@phosphor-icons/react'
import { httpUrl } from '../backend'
import { savedToken } from '../chat/api'
import { SESSION } from '../session'

// Settings → Connections (ACCOUNTS_SPEC.md): link your own Google Calendar + Sheets (GitHub and Notion next).
// Connect is a full-page trip to Google's consent screen and back (/auth/google/connect, backend auth.py);
// tokens stay on the server, encrypted (connections.py). The page only ever sees provider + account email.
type Connection = { provider: 'google' | 'github' | 'notion' | 'gemini'; connected: boolean; account: string }
const NAMES = { google: 'Google Calendar & Sheets', github: 'GitHub', notion: 'Notion', gemini: 'Your Gemini key' }
const ICONS = { google: CalendarBlank, github: GithubLogo, notion: NotePencil, gemini: Sparkle }
const NOTICES: Record<string, string> = {
  'connected=google': 'Google connected. Koe now uses your calendar and timesheet.',
  'connect=missing-scopes': 'Koe needs both Calendar and Sheets. Connect again and leave both boxes ticked.',
}

export function ConnectionsSection() {
  const signedIn = savedToken() === SESSION
  const [list, setList] = useState<Connection[] | null>(null)
  const [ready, setReady] = useState(true)
  const [timesheet, setTimesheet] = useState('')
  const [sheetError, setSheetError] = useState('')
  const [geminiKey, setGeminiKey] = useState('')
  const [keyError, setKeyError] = useState('')
  const [busy, setBusy] = useState('')
  const [notice] = useState(() => NOTICES[location.search.slice(1)] ?? '')

  async function load() {
    const r = await fetch(httpUrl('/api/connections'))
    if (!r.ok) return setList([])
    const body = await r.json()
    setReady(body.ready)
    setTimesheet(body.timesheet ?? '')
    setList(body.connections)
  }
  useEffect(() => {
    if (location.search) history.replaceState(null, '', location.pathname + location.hash) // a notice shows once
    if (signedIn) void load()
  }, [signedIn])

  async function createTimesheet() {
    setBusy('timesheet')
    setSheetError('')
    try {
      const r = await fetch(httpUrl('/api/connections/google/timesheet'), { method: 'POST' })
      const body = await r.json().catch(() => ({}))
      if (r.ok) setTimesheet(body.timesheet)
      else setSheetError(body.detail ?? 'Google didn’t create the sheet. Try again.')
    } finally {
      setBusy('')
    }
  }

  async function saveGeminiKey() {
    setBusy('gemini')
    setKeyError('')
    try {
      const r = await fetch(httpUrl('/api/connections/gemini'), { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ key: geminiKey }) })
      if (r.ok) setGeminiKey('')
      else setKeyError((await r.json().catch(() => ({}))).detail ?? 'That key wasn’t accepted.')
    } finally {
      setBusy('')
      void load()
    }
  }

  async function disconnect(provider: string) {
    setBusy(provider)
    try {
      await fetch(httpUrl(`/api/connections/${provider}`), { method: 'DELETE' })
    } finally {
      setBusy('')
      void load() // show what the server now has, whatever happened
    }
  }

  return (
    <section className="device" aria-label="Connections">
      <h2>Connections</h2>
      {notice && <p className="device-note" role="status">{notice}</p>}
      {!signedIn ? <p className="device-note">Sign in with Google to connect your own accounts.</p>
        : !ready ? <p className="device-note">The server needs KOE_SECRET_KEY before it can store connections.</p>
        : (list ?? []).filter((c) => c.provider !== 'gemini').map(({ provider, connected, account }) => {
          const Icon = ICONS[provider]
          return (
            <div className="device-row" key={provider}>
              <span><span><Icon size={16} /> {NAMES[provider]}</span>
                <small>{connected ? `Connected as ${account}` : provider === 'google' ? 'Not connected' : 'Coming soon'}</small></span>
              {provider === 'google' && (connected
                ? <button className="ghost" disabled={busy === provider} onClick={() => void disconnect(provider)}>{busy === provider ? 'Disconnecting…' : 'Disconnect'}</button>
                : <a className="soft" href={httpUrl('/auth/google/connect?next=%2F%23settings')}>Connect</a>)}
            </div>
          )
        })}
      {signedIn && ready && list?.find((c) => c.provider === 'google')?.connected && <div className="device-row">
        <span><span><Table size={16} /> Timesheet</span>
          <small>{sheetError || (timesheet ? 'Koe logs your hours here (each row needs your OK).' : 'A Google Sheet for logging hours, made for you.')}</small></span>
        {timesheet
          ? <a className="soft" href={timesheet} target="_blank" rel="noopener">Open</a>
          : <button className="soft" disabled={busy === 'timesheet'} onClick={() => void createTimesheet()}>{busy === 'timesheet' ? 'Creating…' : 'Create my timesheet'}</button>}
      </div>}
      {signedIn && ready && (() => {
        const gemini = list?.find((c) => c.provider === 'gemini')
        return <>
          <div className="device-row">
            <span><span><Sparkle size={16} /> Your Gemini key</span>
              <small>{keyError || (gemini?.connected ? `Using your own key (${gemini.account}), no daily limit.` : 'Optional. Koe’s shared key has a daily limit for friends; your own free key removes it.')}</small></span>
            {gemini?.connected && <button className="ghost" disabled={busy === 'gemini'} onClick={() => void disconnect('gemini')}>Remove</button>}
          </div>
          {!gemini?.connected && <form className="token-row" onSubmit={(e) => { e.preventDefault(); void saveGeminiKey() }}>
            <input type="password" value={geminiKey} onChange={(e) => setGeminiKey(e.target.value)} placeholder="Paste a key from aistudio.google.com/apikey"
              aria-label="Your Gemini API key" autoComplete="off" />
            <button className="soft" disabled={!geminiKey.trim() || busy === 'gemini'}>{busy === 'gemini' ? 'Checking…' : 'Save'}</button>
          </form>}
        </>
      })()}
    </section>
  )
}
