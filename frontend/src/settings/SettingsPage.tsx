import { useEffect, useRef, useState } from 'react'
import { MASCOTS, mascotProfile, type MascotId } from '../mascot/catalog'
import { MascotView, type LoadState, type MascotController } from '../mascot/MascotView'
import type { Shot } from '../mascot/mascot'
import './settings.css'

type Props = { selected: MascotId; onSelect: (id: MascotId) => boolean }

// Companion settings: a quiet list on the left, the model standing in a flat viewer on the right.
// Browsing previews a mascot; only "Use …" changes the one on Home.
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
            <button aria-pressed={shot === 'bust'} onClick={() => { setShot('bust'); setZoom(1) }}>Portrait</button>
            <button aria-pressed={shot === 'full'} onClick={() => { setShot('full'); setZoom(1) }}>Full body</button>
          </div>
          <button className="chip" disabled={!ready} onClick={() => controller.current?.gesture('wave')}>Say hi</button>
          <button className="chip" disabled={!ready} aria-pressed={spinning} onClick={() => setSpinning(!spinning)}>Rotate</button>
        </div>
        <p className="viewer-hint" aria-hidden="true">Drag to turn · Scroll to zoom</p>
      </section>
    </main>
  )
}
