import { Fragment, useEffect, useState, type ComponentType, type ReactNode } from 'react'
import { CalendarIcon, DocsIcon, GeminiIcon, GitHubIcon, NotionIcon, SheetsIcon, SpotifyIcon } from '../components/BrandIcon'
import { httpUrl } from '../backend'
import { savedToken } from '../chat/api'
import { SESSION } from '../session'

// Settings → Connections (ACCOUNTS_SPEC.md): link your own Google Calendar + Sheets, GitHub (Notion next).
// Connect is a full-page trip to the provider's consent screen and back (/auth/<provider>/connect, backend auth.py);
// tokens stay on the server, encrypted (connections.py). The page only ever sees provider + account email.
type Connection = { provider: 'google' | 'github' | 'notion' | 'gemini' | 'spotify'; connected: boolean; account: string; reconnect_required?: boolean }
const NAMES = { google: 'Google Calendar & Sheets', github: 'GitHub', notion: 'Notion', gemini: 'Your Gemini key', spotify: 'Spotify' }
const ICONS = { google: CalendarIcon, github: GitHubIcon, notion: NotionIcon, gemini: GeminiIcon, spotify: SpotifyIcon }
const NOTICES: Record<string, string> = {
  'connected=google': 'Google connected. Your enabled services are shown below.',
  'connected=docs': 'Google Docs permissions saved. You can create and edit documents with Koe.',
  'connect=missing-scopes': 'A requested Google permission was not granted. Enable the service again and review its permission boxes.',
  'connected=github': 'GitHub connected. Choose which repositories Koe should watch.',
  'connect=github-failed': 'GitHub didn’t finish connecting. Try again.',
  'connect=cancelled': 'Connecting was cancelled.',
}
const CONNECT: Record<string, string> = { google: '/auth/google/connect?next=%2Fapp%2Fsettings', github: '/auth/github/connect?next=%2Fapp%2Fsettings' }

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
  const [docsReady, setDocsReady] = useState(false)
  const [docsSupported, setDocsSupported] = useState(false)
  const [sources, setSources] = useState<Record<string, string>>({})
  const [tokenReady, setTokenReady] = useState(false)
  const [scopeReady, setScopeReady] = useState(false)
  const [repoMode, setRepoMode] = useState<'selected' | 'all'>('selected')
  const [githubToken, setGithubToken] = useState('')
  const [showGitHubToken, setShowGitHubToken] = useState(false)
  const [githubError, setGithubError] = useState('')
  const [loadError, setLoadError] = useState('')
  const [githubReady, setGithubReady] = useState(false)
  const [repos, setRepos] = useState<{ all: string[]; chosen: string[]; next: number | null } | null>(null)
  const [repoError, setRepoError] = useState('')
  const [timesheet, setTimesheet] = useState('')
  const [sheetError, setSheetError] = useState('')
  const [geminiKey, setGeminiKey] = useState('')
  const [keyError, setKeyError] = useState('')
  const [busy, setBusy] = useState('')
  const [googleHealth, setGoogleHealth] = useState<{ ready: boolean; reconnect_required: boolean; message?: string } | null>(null)
  const [notice] = useState(() => NOTICES[location.search.slice(1)] ?? '')

  async function load() {
    try {
    const r = await fetch(httpUrl('/api/connections'), { cache: 'no-store' })
    if (!r.ok) throw Error('Could not load your connections. Retry below.')
    const body = await r.json()
    setLoadError('')
    setReady(body.ready)
    setSources(body.sources ?? {})
    setTokenReady(Boolean(body.github_token_ready))
    setScopeReady(Boolean(body.features?.github_scope))
    setRepoMode(body.github_repo_mode === 'all' ? 'all' : 'selected')
    setGithubReady(Boolean(body.github_ready))
    setDocsSupported(typeof body.docs_ready === 'boolean')
    setDocsReady(Boolean(body.docs_ready))
    setTimesheet(body.timesheet ?? '')
    setList(body.connections)
    } catch { setLoadError('Could not load your connections. Retry below.') }
  }
  useEffect(() => {
    if (location.search) history.replaceState(null, '', location.pathname + location.hash) // a notice shows once
    let active = true
    if (signedIn) void Promise.resolve().then(() => { if (active) void load() })
    return () => { active = false }
  }, [signedIn])

  async function checkGoogle() {
    setBusy('google-check')
    try {
      const response = await fetch(httpUrl('/api/connections/google/health'), { cache: 'no-store' })
      if (!response.ok) throw Error('Google could not be checked. Try the check again shortly.')
      const health = await response.json()
      setGoogleHealth({ ...health, message: health.message ?? (health.ready ? 'Google Calendar and Sheets are ready.' : 'Connect Google to use Calendar and Sheets.') })
      if (health.reconnect_required) setDocsReady(false)
      else if (health.ready) await load()
    } catch (error) {
      setGoogleHealth({ ready: false, reconnect_required: false, message: error instanceof Error ? error.message : 'Google could not be checked.' })
    } finally { setBusy('') }
  }

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

  async function openRepos(page = 1) {
    setBusy('repos')
    setRepoError('')
    try {
      const r = await fetch(httpUrl(`/api/connections/github/repos?page=${page}`))
      if (!r.ok) throw Error('Could not load repositories. Check your GitHub connection and retry.')
      const body = await r.json()
      if (page === 1) setRepoMode(body.mode === 'all' ? 'all' : 'selected')
      setRepos(old => ({ all: [...new Set([...(page > 1 ? old?.all ?? [] : []), ...body.repos, ...body.selected])] as string[], chosen: page > 1 ? old?.chosen ?? body.selected : body.selected, next: body.next_page ?? null }))
    } catch (error) { setRepoError(error instanceof Error ? error.message : 'Could not load repositories.')
    } finally {
      setBusy('')
    }
  }

  async function saveRepos() {
    if (!repos) return
    setBusy('repos')
    try {
      const r = await fetch(httpUrl('/api/connections/github/repos'), { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ repos: repos.chosen, mode: repoMode }) })
      if (!r.ok) throw Error('Could not save repositories. Choose up to 20 and try again.')
      setRepos(null); setRepoError('')
    } catch (error) { setRepoError(error instanceof Error ? error.message : 'Could not save repositories.')
    } finally {
      setBusy('')
    }
  }

  async function connectGitHubToken() {
    setBusy('github-token'); setGithubError('')
    try {
      const r = await fetch(httpUrl('/api/connections/github/token'), { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token: githubToken.trim() }) })
      if (!r.ok) throw Error((await r.json().catch(() => ({}))).detail ?? 'GitHub could not verify that token.')
      setGithubToken(''); setShowGitHubToken(false); setRepos(null)
      await load()
      await openRepos()
    } catch (error) { setGithubError(error instanceof Error ? error.message : 'Could not connect GitHub.') }
    finally { setBusy('') }
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
      {loadError && <p role="alert">{loadError} <button className="ghost" onClick={() => void load()}>Retry connections</button></p>}
      {!signedIn ? <p className="set-empty">Sign in with Google to connect your own accounts.</p>
        : !ready ? <p className="set-empty">The server needs KOE_SECRET_KEY before it can store connections.</p>
        : list === null ? <p className="set-empty">Loading your connections…</p>
        : list.filter((c) => c.provider !== 'gemini' && NAMES[c.provider]).map(({ provider, connected, account, reconnect_required }) => {
          if (provider === 'spotify') return <SettingRow key={provider} icon={SpotifyIcon} title="Spotify" on={connected}
            status={connected ? 'Connected. Music only: Koe never hears or sees it.' : 'Optional. For your playlist on the Music page.'}
            action={<a className="soft" href="/app/music">{connected ? 'Manage' : 'Set up'}</a>} />
          if (provider === 'notion') return <SettingRow key={provider} icon={NotionIcon} title="Notion" on={connected}
            status={connected ? 'Owner workspace connected. Tasks, notes and daily logs are available.' : 'The owner workspace needs a Notion integration and database connection.'}
            action={<a className="soft" href="/app/notion">Open workspace</a>} />
          const canConnect = CONNECT[provider] && (provider !== 'github' || githubReady || connected)
          return <Fragment key={provider}>
            <SettingRow icon={ICONS[provider]} title={NAMES[provider]} on={connected && !(provider === 'google' && (reconnect_required || googleHealth?.reconnect_required))}
              status={provider === 'google' && (googleHealth?.message || reconnect_required) ? googleHealth?.message ?? 'Google access expired or was revoked. Reconnect to restore Calendar and Sheets.' : connected ? (sources[provider] === 'server' ? 'Owner connection available. Choose repositories below or connect your own account.' : `Connected as ${account}`) : provider === 'github' && !githubReady ? 'Connect your GitHub account with a personal access token.' : 'Not connected'}
              action={<>{canConnect && (connected
                ? <button className="ghost" disabled={busy === provider} onClick={() => void disconnect(provider)}>{busy === provider ? 'Disconnecting…' : 'Disconnect'}</button>
                : <a className="soft" href={httpUrl(CONNECT[provider])}>Connect</a>)}
                {provider === 'google' && connected && <><button className="ghost" disabled={busy === 'google-check'} onClick={() => void checkGoogle()}>{busy === 'google-check' ? 'Checking…' : 'Check connection'}</button><a className="soft" href={httpUrl(CONNECT.google)}>Reconnect</a></>}
                {provider === 'github' && tokenReady && <button className="soft" onClick={() => setShowGitHubToken(!showGitHubToken)}>{connected ? 'Change account' : 'Use a token'}</button>}</>}>
              {provider === 'github' && !githubReady && !tokenReady && <p role="status">The deployed backend does not offer account setup here yet. Update the backend to enable GitHub connections.</p>}
              {provider === 'github' && githubError && <p role="alert">{githubError}</p>}
              {provider === 'github' && showGitHubToken && <form className="github-token-form" onSubmit={e => { e.preventDefault(); void connectGitHubToken() }}>
                <p>Create a fine-grained GitHub token for selected repositories or all repositories. Give Contents and Pull requests read access; allow Pull requests write only if you want approved comments. Koe stores the token encrypted on the server.</p>
                <p><a href="https://github.com/settings/personal-access-tokens/new" target="_blank" rel="noopener">Create a GitHub token</a></p>
                <label>GitHub personal access token<input type="password" autoComplete="off" value={githubToken} onChange={e => setGithubToken(e.target.value)} /></label>
                <div className="pair"><button className="ghost" type="button" onClick={() => { setShowGitHubToken(false); setGithubToken('') }}>Cancel</button><button className="soft" disabled={!githubToken.trim() || busy === 'github-token'}>{busy === 'github-token' ? 'Connecting…' : 'Connect account'}</button></div>
              </form>}
            </SettingRow>
            {provider === 'google' && <SettingRow sub icon={DocsIcon} title="Google Docs" on={connected && docsReady}
              status={!docsSupported ? 'This backend version does not support Docs yet. Update the backend; reconnecting Google cannot enable it.' : connected && docsReady ? 'Ready. Ask Koe to create a Doc, or paste a Doc link in chat. Edits need your confirmation.' : 'Create and edit documents with Koe. Enable additional Google permissions.'}
              action={!docsSupported ? <button className="ghost" onClick={() => void load()}>Refresh status</button> : connected && docsReady ? <a className="soft" href="/app/chat">Open chat</a>
                : <a className="soft" href={httpUrl('/auth/google/connect?docs=true&next=%2Fapp%2Fsettings')}>Enable Docs</a>} />}
            {provider === 'google' && connected && <SettingRow sub icon={SheetsIcon} title="Timesheet"
              status={sheetError || (timesheet ? 'Koe logs your hours here (each row needs your OK).' : 'A Google Sheet for logging hours, made for you.')}
              action={timesheet
                ? <a className="soft" href={timesheet} target="_blank" rel="noopener">Open</a>
                : <button className="soft" disabled={busy === 'timesheet'} onClick={() => void createTimesheet()}>{busy === 'timesheet' ? 'Creating…' : 'Create my timesheet'}</button>} />}
            {provider === 'github' && connected && <SettingRow sub icon={GitHubIcon} title="Repositories" status={repoMode === 'all' ? 'All repositories accessible to your connection.' : 'Choose which repositories Koe may use.'}
              action={!repos && <button className="soft" disabled={busy === 'repos'} onClick={() => void openRepos()}>{busy === 'repos' ? 'Loading…' : 'Choose'}</button>}>
              {repoError && <p role="status">{repoError}</p>}
              {repos && <fieldset className="repo-pick">
                <legend className="visually-hidden">Repositories Koe reads</legend>
                {scopeReady && <><label><input type="radio" name="github-scope" checked={repoMode === 'selected'} onChange={() => setRepoMode('selected')} /> Selected repositories</label>
                  <label><input type="radio" name="github-scope" checked={repoMode === 'all'} onChange={() => setRepoMode('all')} /> All accessible repositories</label>
                  <p>Your GitHub token or OAuth grant sets the maximum access. Koe follows the choice you save here. Large activity reads report any coverage limits.</p></>}
                {repoMode === 'selected' && <div className="repo-list">{repos.all.map((name) => <label key={name}>
                  <input type="checkbox" checked={repos.chosen.includes(name)} disabled={!repos.chosen.includes(name) && repos.chosen.length >= 20}
                    onChange={(e) => setRepos({ ...repos, chosen: e.target.checked ? [...repos.chosen, name] : repos.chosen.filter((r) => r !== name) })} />
                  <span>{name}</span>
                </label>)}</div>}
                {repos.next && <button type="button" className="ghost" disabled={busy === 'repos'} onClick={() => void openRepos(repos.next!)}>Load more repositories</button>}
                <div className="pair"><button type="button" className="ghost" onClick={() => setRepos(null)}>Cancel</button>
                  <button type="button" className="soft" disabled={busy === 'repos'} onClick={() => void saveRepos()}>Save {repoMode === 'all' ? 'all repositories' : repos.chosen.length}</button></div>
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
