import { useEffect, useState, type ReactNode } from 'react'
import { httpUrl } from './backend'
import { savedToken, saveToken } from './chat/api'
import { SESSION, signIn } from './session'
import './signin.css'
import { GoogleIcon } from './components/BrandIcon'

// The Continue with Google screen and the gate in front of the app; helpers live in session.ts.
type Status = { google: boolean; user: { email: string; name: string; is_admin: boolean } | null }

export function SignInGate({ children }: { children: ReactNode }) {
  const [state, setState] = useState<'checking' | 'in' | 'out' | 'off'>('checking')
  useEffect(() => {
    fetch(httpUrl('/auth/status'))
      .then((r) => r.json() as Promise<Status>)
      .then((s) => {
        if (s.user) {
          if (savedToken() !== SESSION) saveToken(SESSION)
          setState('in')
        } else if (s.google) {
          if (savedToken() === SESSION) saveToken('') // the session ended
          setState('out')
        } else setState('off') // sign-in isn't set up on this server: the access-token flow
      })
      .catch(() => setState('off'))
  }, [])

  if (state === 'checking') return <p className="signin-wait" role="status">Waking Koe up…</p>
  if (state === 'out') return <SignIn />
  return children
}

const NOTICE: Record<string, string> = {
  'not-invited': 'That Google account isn’t invited to Koe. Ask the owner for an invite, or try another account.',
  cancelled: 'Sign-in was cancelled.',
}

function SignIn() {
  const notice = NOTICE[new URLSearchParams(location.search).get('signin') ?? '']
  return (
    <main className="signin" id="main-content">
      <img src="/icons/icon-192.png" alt="" width="96" height="96" />
      <h1>Koe <span lang="ja">声</span></h1>
      <p>Your voice assistant for GitHub, your calendar and your notes. Invite only.</p>
      {notice && <p className="signin-notice" role="alert">{notice}</p>}
      <button className="primary" onClick={signIn}>
        <GoogleIcon size={18} />
        Continue with Google
      </button>
      <nav aria-label="About Koe"><a href="/guide">Guide</a><a href="/privacy">Privacy</a><a href="/terms">Terms</a></nav>
    </main>
  )
}
