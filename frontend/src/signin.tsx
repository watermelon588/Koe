import { useEffect, useState, type ReactNode } from 'react'
import { httpUrl } from './backend'
import { savedToken, saveToken } from './chat/api'
import { SESSION, signIn } from './session'
import './signin.css'

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
        <svg viewBox="0 0 48 48" width="18" height="18" aria-hidden="true">
          <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.6 5.4 2.7 13.3l7.9 6.1C12.5 13.6 17.8 9.5 24 9.5z" />
          <path fill="#4285F4" d="M46.1 24.6c0-1.6-.1-3.1-.4-4.6H24v9h12.4c-.5 2.9-2.2 5.3-4.6 6.9l7.4 5.7c4.3-4 6.9-9.9 6.9-17z" />
          <path fill="#FBBC05" d="M10.6 28.6c-.5-1.4-.8-3-.8-4.6s.3-3.2.8-4.6l-7.9-6.1C1 16.6 0 20.2 0 24s1 7.4 2.7 10.7l7.9-6.1z" />
          <path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.8-5.8l-7.4-5.7c-2.1 1.4-4.8 2.3-8.4 2.3-6.2 0-11.5-4.1-13.4-9.9l-7.9 6.1C6.6 42.6 14.6 48 24 48z" />
        </svg>
        Continue with Google
      </button>
      <nav aria-label="About Koe"><a href="/guide">Guide</a><a href="/privacy">Privacy</a><a href="/terms">Terms</a></nav>
    </main>
  )
}
