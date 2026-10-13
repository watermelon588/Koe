import { useEffect, useState } from 'react'
import { CalendarBlank, GithubLogo, NotePencil } from '@phosphor-icons/react'
import { httpUrl } from '../backend'
import { savedToken } from '../chat/api'
import { SESSION } from '../session'

// Settings → Connections (ACCOUNTS_SPEC.md): link your own Google Calendar + Sheets (GitHub and Notion next).
// Connect is a full-page trip to Google's consent screen and back (/auth/google/connect, backend auth.py);
// tokens stay on the server, encrypted (connections.py). The page only ever sees provider + account email.
type Connection = { provider: 'google' | 'github' | 'notion'; connected: boolean; account: string }
const NAMES = { google: 'Google Calendar & Sheets', github: 'GitHub', notion: 'Notion' }
const ICONS = { google: CalendarBlank, github: GithubLogo, notion: NotePencil }
const NOTICES: Record<string, string> = {
  'connected=google': 'Google connected. Koe now uses your calendar and timesheet.',
  'connect=missing-scopes': 'Koe needs both Calendar and Sheets. Connect again and leave both boxes ticked.',
}

export function ConnectionsSection() {
  const signedIn = savedToken() === SESSION
  const [list, setList] = useState<Connection[] | null>(null)
  const [ready, setReady] = useState(true)
  const [busy, setBusy] = useState('')
  const [notice] = useState(() => NOTICES[location.search.slice(1)] ?? '')

  async function load() {
    const r = await fetch(httpUrl('/api/connections'))
    if (!r.ok) return setList([])
    const body = await r.json()
    setReady(body.ready)
    setList(body.connections)
  }
  useEffect(() => {
    if (location.search) history.replaceState(null, '', location.pathname + location.hash) // a notice shows once
    if (signedIn) void load()
  }, [signedIn])

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
        : (list ?? []).map(({ provider, connected, account }) => {
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
    </section>
  )
}
