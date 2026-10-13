import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { BellSimple, ChatCircleDots, CheckCircle, DeviceMobile, Key } from '@phosphor-icons/react'
import { mascotProfile, type MascotId } from '../mascot/catalog'
import { api, AuthError, savedToken, saveToken } from '../chat/api'
import { enablePush, pushState, useInstall, type PushState } from '../pwa'
import { SESSION } from '../session'
import './install.css'

// The phone setup portal (#install): scan the QR on the laptop, then on the phone install Koe, connect it with the
// Google sign-in (or the access token), turn on notifications and prove they arrive, then open the chat. Each step shows when it's done.
// The QR is a static file for https://koe-pi.vercel.app/#install. If the domain changes, regenerate it:
//   uv run --no-project --with segno python -c "import segno; segno.make('<url>/#install', error='m').save('install-qr.svg', border=4, dark='#111', light='#fff', xmldecl=False)"
// (then swap width/height for viewBox="0 0 37 37").
type Check = 'idle' | 'busy' | 'ok' | string // a string is the error to show

export function InstallPage({ model }: { model: MascotId }) {
  const profile = mascotProfile(model)
  const install = useInstall()
  const [token, setToken] = useState(savedToken)
  const [connected, setConnected] = useState<Check>('idle')
  const [push, setPush] = useState<PushState | 'busy'>('off')
  const [pushError, setPushError] = useState('')
  const [test, setTest] = useState<Check>('idle')

  async function connect(value = token) {
    if (!value.trim()) return
    saveToken(value)
    setConnected('busy')
    try {
      await api.messages(0) // also wakes the backend on Render's free plan (up to a minute)
      setConnected('ok')
    } catch (e) {
      setConnected(e instanceof AuthError ? 'That token was not accepted. Check KOE_ACCESS_TOKEN.' : 'Koe did not answer. Try again in a minute.')
    }
  }
  useEffect(() => {
    void pushState().then(setPush)
    if (savedToken()) void connect(savedToken()) // eslint-disable-line react-hooks/exhaustive-deps -- once, on open
  }, [])

  async function turnOnPush() {
    setPushError('')
    setPush('busy')
    try {
      await enablePush()
    } catch (e) {
      setPushError(e instanceof Error ? e.message : String(e))
    }
    setPush(await pushState())
  }
  async function sendTest() {
    setTest('busy')
    try {
      setTest((await api.pushTest()) ? 'ok' : 'Koe has no device to notify. Turn notifications off and on in Settings.')
    } catch (e) {
      setTest(e instanceof Error ? e.message : String(e))
    }
  }

  const installed = install.installed
  const ready = connected === 'ok'
  return (
    <main className="install-page" id="main-content" tabIndex={-1} data-mascot={model}>
      <header className="install-head">
        <img src={profile.portrait} alt="" width="72" height="72" />
        <h1>Koe on your phone</h1>
        <p>Chat by text or voice note, and get Koe’s replies and GitHub alerts as notifications. New here? Read the <a href="/guide">guide</a>.</p>
      </header>

      <figure className="install-qr">
        <img src="/install-qr.svg" alt="QR code that opens this page on your phone" width="184" height="184" />
        <figcaption>Scan with your phone’s camera, then follow the steps there.</figcaption>
      </figure>

      <ol className="steps">
        <Step n={1} done={installed} icon={<DeviceMobile />} title="Install the app">
          {installed ? <p>Installed. Open Koe from your home screen.</p>
            : install.canPrompt ? <button className="primary" onClick={() => void install.install()}>Install Koe</button>
            : install.ios ? <p>In Safari, tap <b>Share</b>, then <b>Add to Home Screen</b>, and open Koe from there.</p>
            : <p>Open this page on your phone in Chrome. If no button appears there, use the browser menu → <b>Install app</b> (or <b>Add to Home screen</b>).</p>}
        </Step>

        <Step n={2} done={ready} icon={<Key />} title="Connect to Koe">
          {token === SESSION ? null : <form className="token-row" onSubmit={(e: FormEvent) => { e.preventDefault(); void connect() }}>
            <input type="password" value={token} onChange={(e) => { setToken(e.target.value); setConnected('idle') }}
              placeholder="KOE_ACCESS_TOKEN" aria-label="Koe access token" autoComplete="off" />
            <button className="soft" disabled={!token.trim() || connected === 'busy'}>{connected === 'busy' ? 'Connecting…' : 'Connect'}</button>
          </form>}
          <p role="status">{connected === 'ok' ? (token === SESSION ? 'Signed in with Google.' : 'Connected. The token stays on this device.')
            : connected === 'busy' ? 'Waking Koe up. This can take up to a minute.'
            : connected === 'idle' ? 'The password from backend/.env.' : connected}</p>
        </Step>

        <Step n={3} done={push === 'on' && test === 'ok'} icon={<BellSimple />} title="Turn on notifications">
          {push === 'unsupported' ? <p>{install.ios ? 'Install Koe to the home screen first, then open this step from the app.' : 'This browser can’t show notifications.'}</p>
            : push === 'denied' ? <p>Blocked. Allow notifications for this site in the browser’s site settings.</p>
            : push === 'on' ? <div className="pair">
                <button className="soft" disabled={!ready || test === 'busy'} onClick={() => void sendTest()}>Send a test</button>
                <p role="status">{test === 'ok' ? 'Sent. It should pop up within a few seconds.' : test === 'busy' ? 'Sending…'
                  : test === 'idle' ? (ready ? 'Notifications are on.' : 'Connect first, then send a test.') : test}</p>
              </div>
            : <><button className="soft" disabled={!ready || push === 'busy'} onClick={() => void turnOnPush()}>Turn on</button>
                <p role="status">{pushError || (ready ? 'Your phone will ask for permission.' : 'Connect first.')}</p></>}
        </Step>

        <Step n={4} done={false} icon={<ChatCircleDots />} title="Say hi">
          <p>Send a text or hold the mic for a voice note. Koe answers a voice note with a voice note.</p>
          <a className="primary" href="#chat" aria-disabled={!ready || undefined}>Open chat</a>
        </Step>
      </ol>
    </main>
  )
}

function Step({ n, done, icon, title, children }: { n: number; done: boolean; icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <li className="step" data-done={done || undefined}>
      <span className="step-mark" aria-hidden="true">{done ? <CheckCircle weight="fill" /> : icon}</span>
      <div className="step-body">
        <h2>{title}<span className="visually-hidden">{done ? ' (done)' : ` (step ${n})`}</span></h2>
        {children}
      </div>
    </li>
  )
}
