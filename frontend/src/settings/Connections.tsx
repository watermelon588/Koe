import { Fragment, useEffect, useState, type ComponentType, type ReactNode } from 'react'
import { CalendarIcon, GeminiIcon, GitHubIcon, NotionIcon, SheetsIcon, SpotifyIcon } from '../components/BrandIcon'
import { httpUrl } from '../backend'
import { savedToken } from '../chat/api'
import { SESSION } from '../session'

// Settings → Connections (ACCOUNTS_SPEC.md): link your own Google Calendar + Sheets, GitHub (Notion next).
// Connect is a full-page trip to the provider's consent screen and back (/auth/<provider>/connect, backend auth.py);
// tokens stay on the server, encrypted (connections.py). The page only ever sees provider + account email.
type Connection = { provider: 'google' | 'github' | 'notion' | 'gemini' | 'spotify'; connected: boolean; account: string }
const NAMES = { google: 'Google Calendar & Sheets', github: 'GitHub', notion: 'Notion', gemini: 'Your Gemini key', spotify: 'Spotify' }
const ICONS = { google: CalendarIcon, github: GitHubIcon, notion: NotionIcon, gemini: GeminiIcon, spotify: SpotifyIcon }
const NOTICES: Record<string, string> = {
  'connected=google': 'Google connected. Koe now uses your calendar and timesheet.',
  'connect=missing-scopes': 'Koe needs both Calendar and Sheets. Connect again and leave both boxes ticked.',
  'connected=github': 'GitHub connected. Choose which repositories Koe should watch.',
  'connect=github-failed': 'GitHub didn’t finish connecting. Try again.',
  'connect=cancelled': 'Connecting was cancelled.',
}
const CONNECT: Record<string, string> = { google: '/auth/google/connect?next=%2F%23settings', github: '/auth/github/connect?next=%2F%23settings' }

// One settings section: its title and a line of context on the left (above, on phones), its rows on the right.
export function SettingSection({ id, title, intro, children }: { id: string; title: string; intro: string; children: ReactNode }) {
  return (
    <section className="set-section" aria-labelledby={id}>
      <div className="set-intro"><h2 id={id}>{title}</h2><p>{intro}</p></div>
      <div className="set-group">{children}</div>
    </section>
  )
}

// One row: icon, name, a one-line status, one action. `sub` rows belong to the row above (Timesheet → Google).
// Anything else (a form, the repository list) goes underneath as children.
export function SettingRow({ icon: RowIcon, title, status, on, sub, action, children }: {
  icon: ComponentType<{ size?: number }>; title: string; status: ReactNode; on?: boolean; sub?: boolean; action?: ReactNode; children?: ReactNode
}) {
  return (
    <div className="set-row" data-on={on || undefined} data-sub={sub || undefined}>
      <span className="set-icon" aria-hidden="true"><RowIcon size={sub ? 16 : 18} /></span>
      <div className="set-main">
        <div className="set-text"><span>{title}</span><small>{status}</small></div>
        {action && <div className="set-action">{action}</div>}
        {children && <div className="set-below">{children}</div>}
      </div>
    </div>
  )
}

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

  const gemini = list?.find((c) => c.provider === 'gemini')
  return <>
    <SettingSection id="set-connections" title="Connections" intro="Koe sees a service only after you connect it. You can disconnect at any time.">
      {notice && <p className="set-notice" role="status">{notice}</p>}
      {!signedIn ? <p className="set-empty">Sign in with Google to connect your own accounts.</p>
        : !ready ? <p className="set-empty">The server needs KOE_SECRET_KEY before it can store connections.</p>
        : list === null ? <p className="set-empty">Loading your connections…</p>
        : list.filter((c) => c.provider !== 'gemini' && NAMES[c.provider]).map(({ provider, connected, account }) => {
          if (provider === 'spotify') return <SettingRow key={provider} icon={SpotifyIcon} title="Spotify" on={connected}
            status={connected ? 'Connected. Music only: Koe never hears or sees it.' : 'Optional. For your playlist on the Music page.'}
            action={<a className="soft" href="/app/music">{connected ? 'Manage' : 'Set up'}</a>} />
          const canConnect = CONNECT[provider] && (provider !== 'github' || githubReady || connected)
          return <Fragment key={provider}>
            <SettingRow icon={ICONS[provider]} title={NAMES[provider]} on={connected}
              status={connected ? `Connected as ${account}` : CONNECT[provider] && (provider !== 'github' || githubReady) ? 'Not connected' : 'Coming soon'}
              action={canConnect && (connected
                ? <button className="ghost" disabled={busy === provider} onClick={() => void disconnect(provider)}>{busy === provider ? 'Disconnecting…' : 'Disconnect'}</button>
                : <a className="soft" href={httpUrl(CONNECT[provider])}>Connect</a>)} />
            {provider === 'google' && connected && <SettingRow sub icon={SheetsIcon} title="Timesheet"
              status={sheetError || (timesheet ? 'Koe logs your hours here (each row needs your OK).' : 'A Google Sheet for logging hours, made for you.')}
              action={timesheet
                ? <a className="soft" href={timesheet} target="_blank" rel="noopener">Open</a>
                : <button className="soft" disabled={busy === 'timesheet'} onClick={() => void createTimesheet()}>{busy === 'timesheet' ? 'Creating…' : 'Create my timesheet'}</button>} />}
            {provider === 'github' && connected && <SettingRow sub icon={GitHubIcon} title="Repositories" status="Which repositories Koe reads (up to 20)."
              action={!repos && <button className="soft" disabled={busy === 'repos'} onClick={() => void openRepos()}>{busy === 'repos' ? 'Loading…' : 'Choose'}</button>}>
              {repos && <fieldset className="repo-pick">
                <legend className="visually-hidden">Repositories Koe reads</legend>
                <div className="repo-list">{repos.all.map((name) => <label key={name}>
                  <input type="checkbox" checked={repos.chosen.includes(name)} disabled={!repos.chosen.includes(name) && repos.chosen.length >= 20}
                    onChange={(e) => setRepos({ ...repos, chosen: e.target.checked ? [...repos.chosen, name] : repos.chosen.filter((r) => r !== name) })} />
                  <span>{name}</span>
                </label>)}</div>
                <div className="pair"><button type="button" className="ghost" onClick={() => setRepos(null)}>Cancel</button>
                  <button type="button" className="soft" disabled={busy === 'repos'} onClick={() => void saveRepos()}>Save {repos.chosen.length}</button></div>
              </fieldset>}
            </SettingRow>}
          </Fragment>
        })}
    </SettingSection>

    {signedIn && ready && <SettingSection id="set-gemini" title="Your Gemini key" intro="Koe’s shared key has a daily limit for friends. Your own free key removes it.">
      <SettingRow icon={GeminiIcon} title="Gemini API key" on={gemini?.connected}
        status={keyError || (gemini?.connected ? `Using your own key (${gemini.account}), no daily limit.` : 'Optional. Using Koe’s shared key.')}
        action={gemini?.connected && <button className="ghost" disabled={busy === 'gemini'} onClick={() => void disconnect('gemini')}>Remove</button>}>
        {!gemini?.connected && <form className="token-row" onSubmit={(e) => { e.preventDefault(); void saveGeminiKey() }}>
          <input type="password" value={geminiKey} onChange={(e) => setGeminiKey(e.target.value)} placeholder="Paste a key from aistudio.google.com/apikey"
            aria-label="Your Gemini API key" autoComplete="off" />
          <button className="soft" disabled={!geminiKey.trim() || busy === 'gemini'}>{busy === 'gemini' ? 'Checking…' : 'Save'}</button>
        </form>}
      </SettingRow>
    </SettingSection>}
  </>
}
