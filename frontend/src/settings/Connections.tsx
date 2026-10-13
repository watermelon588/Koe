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
  'connected=github': 'GitHub connected. Choose which repositories Koe should watch.',
  'connect=github-failed': 'GitHub didn’t finish connecting. Try again.',
  'connect=cancelled': 'Connecting was cancelled.',
}
const CONNECT: Record<string, string> = { google: '/auth/google/connect?next=%2F%23settings', github: '/auth/github/connect?next=%2F%23settings' }

export function ConnectionsSection() {
  const signedIn = savedToken() === SESSION
  const [list, setList] = useState<Connection[] | null>(null)
  const [ready, setReady] = useState(true)
  const [githubReady, setGithubReady] = useState(false)
  const [repos, setRepos] = useState<{ all: string[]; chosen: string[] } | null>(null)
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
    setGithubReady(Boolean(body.github_ready))
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

  async function openRepos() {
    setBusy('repos')
    try {
      const r = await fetch(httpUrl('/api/connections/github/repos'))
      if (r.ok) { const body = await r.json(); setRepos({ all: body.repos, chosen: body.selected }) }
    } finally {
      setBusy('')
    }
  }

  async function saveRepos() {
    if (!repos) return
    setBusy('repos')
    try {
      const r = await fetch(httpUrl('/api/connections/github/repos'), { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ repos: repos.chosen }) })
      if (r.ok) setRepos(null)
    } finally {
      setBusy('')
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
                <small>{connected ? `Connected as ${account}` : CONNECT[provider] && (provider !== 'github' || githubReady) ? 'Not connected' : 'Coming soon'}</small></span>
              {CONNECT[provider] && (provider !== 'github' || githubReady || connected) && (connected
                ? <button className="ghost" disabled={busy === provider} onClick={() => void disconnect(provider)}>{busy === provider ? 'Disconnecting…' : 'Disconnect'}</button>
                : <a className="soft" href={httpUrl(CONNECT[provider])}>Connect</a>)}
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
      {signedIn && ready && list?.find((c) => c.provider === 'github')?.connected && <div className="device-row">
        <span><span><GithubLogo size={16} /> Repositories</span><small>Which repositories Koe reads (up to 20).</small></span>
        {!repos && <button className="soft" disabled={busy === 'repos'} onClick={() => void openRepos()}>{busy === 'repos' ? 'Loading…' : 'Choose'}</button>}
      </div>}
      {repos && <fieldset className="repo-pick">
        <legend className="visually-hidden">Repositories Koe reads</legend>
        {repos.all.map((name) => <label key={name}>
          <input type="checkbox" checked={repos.chosen.includes(name)} disabled={!repos.chosen.includes(name) && repos.chosen.length >= 20}
            onChange={(e) => setRepos({ ...repos, chosen: e.target.checked ? [...repos.chosen, name] : repos.chosen.filter((r) => r !== name) })} />
          {name}
        </label>)}
        <div className="pair"><button type="button" className="ghost" onClick={() => setRepos(null)}>Cancel</button>
          <button type="button" className="soft" disabled={busy === 'repos'} onClick={() => void saveRepos()}>Save {repos.chosen.length}</button></div>
      </fieldset>}
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
