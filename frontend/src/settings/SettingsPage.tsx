import { useEffect, useRef, useState } from 'react'
import { ArrowsClockwise, BellSimple, DeviceMobile, HandWaving, Key, Person, UserCircle, UserFocus } from '@phosphor-icons/react'
import { savedToken, saveToken } from '../chat/api'
import { SESSION, signOut } from '../session'
import { ConnectionsSection, SettingRow, SettingSection } from './Connections'
import { PeopleSection } from './People'
import { disablePush, enablePush, pushState, useInstall, type PushState } from '../pwa'
import { MASCOTS, mascotProfile, type MascotId } from '../mascot/catalog'
import { MascotView, type LoadState, type MascotController } from '../mascot/MascotView'
import type { Shot } from '../mascot/mascot'
import './settings.css'

type Props = { selected: MascotId; onSelect: (id: MascotId) => boolean }

// Settings: the companion studio on top (a quiet list on the left, the model standing in a flat viewer on the
// right; browsing previews a mascot, only "Use …" changes the one on Home), then calm sections below it:
// Account, Connections, Your Gemini key, People (owner only), This device.
export function SettingsPage({ selected, onSelect }: Props) {
  const [preview, setPreview] = useState(selected)
  const [shot, setShot] = useState<Shot>('bust')
  const [zoom, setZoom] = useState(1)
  const [spinning, setSpinning] = useState(false)
  const [status, setStatus] = useState<LoadState>('loading')
  const [notice, setNotice] = useState('')
  const controller = useRef<MascotController | null>(null)
  const viewer = useRef<HTMLElement>(null)
  const profile = mascotProfile(preview)
  const applied = preview === selected
  const ready = status === 'ready'

  // Scroll to zoom. A native listener, because React's wheel handlers are passive and can't stop the page scrolling.
  useEffect(() => {
    const el = viewer.current
    if (!el) return
    function onWheel(e: WheelEvent) {
      e.preventDefault()
      setZoom((z) => Math.min(2.5, Math.max(1, z - e.deltaY * 0.0015)))
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [])

  function inspect(id: MascotId) {
    if (id === preview) return
    setStatus('loading')
    setPreview(id)
    setZoom(1)
    setSpinning(false)
    setNotice('')
  }
  function apply() {
    setNotice(onSelect(preview) ? '' : 'Using her for this visit. Your browser couldn’t save the choice.')
  }

  return (
    <main className="settings-page" id="main-content" tabIndex={-1} data-mascot={preview}>
      <div className="settings-studio">
      <aside className="settings-side">
        <h1>Companion</h1>
        <p className="sub">Who stands beside you on Home.</p>
        <ul className="mascot-list" aria-label="Companions">
          {MASCOTS.map((m) => (
            <li key={m.id}>
              <button aria-pressed={preview === m.id} onClick={() => inspect(m.id)}>
                <img src={m.portrait} alt="" width="44" height="44" />
                <span>{m.name}</span>
                {selected === m.id && <small>Current</small>}
              </button>
            </li>
          ))}
        </ul>
        <button className="primary" disabled={applied || !ready} onClick={apply}>
          {applied ? 'Current companion' : `Use ${profile.name}`}
        </button>
        <p className="note" role="status">{notice}</p>
      </aside>

      <section className="viewer" ref={viewer} aria-label={`${profile.name} preview`}>
        <MascotView model={preview} controller={controller} shot={shot} onStatus={setStatus} inspection zoom={zoom} spinning={spinning} />
        <div className="viewer-bar">
          <div className="seg" role="group" aria-label="Framing">
            <button aria-pressed={shot === 'bust'} onClick={() => { setShot('bust'); setZoom(1) }}><UserFocus size={15} />Portrait</button>
            <button aria-pressed={shot === 'full'} onClick={() => { setShot('full'); setZoom(1) }}><Person size={15} />Full body</button>
          </div>
          <button className="chip" disabled={!ready} onClick={() => controller.current?.gesture('wave')}><HandWaving size={15} />Say hi</button>
          <button className="chip" disabled={!ready} aria-pressed={spinning} onClick={() => setSpinning(!spinning)}><ArrowsClockwise size={15} />Rotate</button>
        </div>
        <p className="viewer-hint" aria-hidden="true">Drag to turn · Scroll to zoom</p>
      </section>
      </div>

      <div className="settings-sections">
        <AccountSection />
        <ConnectionsSection />
        <PeopleSection />
        <DeviceSection />
      </div>
    </main>
  )
}

// Account: signed in with Google (sign out), or the development access token kept on this device.
function AccountSection() {
  const [token, setToken] = useState(savedToken)
  const [tokenSaved, setTokenSaved] = useState(false)
  return (
    <SettingSection id="set-account" title="Account" intro="How this device signs in to Koe.">
      {token === SESSION
        ? <SettingRow icon={UserCircle} title="Google account" status="Signed in with Google." on
          action={<button className="ghost" onClick={() => void signOut()}>Sign out</button>} />
        : <SettingRow icon={Key} title="Access token" status={tokenSaved ? 'Saved on this device.' : 'KOE_ACCESS_TOKEN from backend/.env.'} on={tokenSaved}>
          <form className="token-row" onSubmit={(e) => { e.preventDefault(); setTokenSaved(saveToken(token)) }}>
            <input type="password" value={token} onChange={(e) => { setToken(e.target.value); setTokenSaved(false) }} aria-label="Koe access token" autoComplete="off" />
            <button className="soft" disabled={!token.trim()}>Save</button>
          </form>
        </SettingRow>}
    </SettingSection>
  )
}

// This device: install Koe like an app and turn on notifications (SPEC §14).
function DeviceSection() {
  const install = useInstall()
  const [push, setPush] = useState<PushState | 'busy'>('off')
  const [pushError, setPushError] = useState('')
  useEffect(() => { void pushState().then(setPush) }, [])

  async function togglePush() {
    setPushError('')
    const was = push
    setPush('busy')
    try {
      if (was === 'on') await disablePush()
      else await enablePush()
    } catch (e) {
      setPushError(e instanceof Error ? e.message : String(e))
    }
    setPush(await pushState())
  }

  return (
    <SettingSection id="set-device" title="This device" intro="Install Koe like an app and get its replies as notifications.">
      <SettingRow icon={DeviceMobile} title="Koe app" on={install.installed}
        status={install.installed ? 'Installed on this device.' : install.canPrompt ? 'Add Koe to your home screen, like an app.'
          : install.ios ? 'On iPhone: Share, then Add to Home Screen.' : 'Scan a QR code to set Koe up on your phone.'}
        action={!install.installed && (install.canPrompt
          ? <button className="soft" onClick={() => void install.install()}>Install app</button>
          : <a className="ghost" href="#install">Phone setup</a>)} />
      <SettingRow icon={BellSimple} title="Notifications" on={push === 'on'}
        status={push === 'unsupported' ? (install.ios ? 'Install Koe to your home screen first.' : 'Not supported in this browser.')
          : push === 'denied' ? 'Blocked. Allow notifications for this site in the browser settings.'
          : pushError || 'Koe’s replies and GitHub alerts, like WhatsApp messages.'}
        action={(push === 'on' || push === 'off' || push === 'busy') &&
          <button className={push === 'on' ? 'ghost' : 'soft'} disabled={push === 'busy'} onClick={() => void togglePush()}>{push === 'on' ? 'Turn off' : 'Turn on'}</button>} />
    </SettingSection>
  )
}
