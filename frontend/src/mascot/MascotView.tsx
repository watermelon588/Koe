import { useEffect, useLayoutEffect, useRef, useState, type RefObject } from 'react'
import { mascotProfile, type MascotId } from './catalog'
import type { createMascot, Shot } from './mascot'

export type MascotController = ReturnType<typeof createMascot>
export type LoadState = 'loading' | 'ready' | 'error'

type Props = {
  model: MascotId
  controller: RefObject<MascotController | null>
  shot?: Shot
  x?: number
  onStatus?: (status: LoadState) => void
  onReady?: (mascot: MascotController) => void
  inspection?: boolean
  zoom?: number
  spinning?: boolean
  motion?: boolean
}

// Both pages share loading, retry and disposal. Only the visible page owns a canvas.
export function MascotView({ model, controller, shot = 'bust', x = 0.5, onStatus, onReady, inspection = false, zoom = 1, spinning = false, motion = true }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const [status, setStatus] = useState<LoadState>('loading')
  const [attempt, setAttempt] = useState(0)
  const latest = useRef({ shot, x, onStatus, onReady, inspection, zoom, spinning, motion })
  useLayoutEffect(() => { latest.current = { shot, x, onStatus, onReady, inspection, zoom, spinning, motion } })

  useEffect(() => {
    let gone = false
    let instance: MascotController | null = null
    function update(next: LoadState) {
      if (gone) return
      setStatus(next)
      latest.current.onStatus?.(next)
    }
    update('loading')
    import('./mascot').then(({ createMascot }) => {
      if (gone) return
      instance = createMascot(canvas.current!, `/mascot/${model}.vrm`)
      instance.motion(latest.current.motion)
      instance.inspect(latest.current.inspection)
      instance.zoom(latest.current.zoom)
      instance.spin(latest.current.spinning)
      instance.shot(latest.current.shot, latest.current.x)
      controller.current = instance
      return instance.ready.then(() => {
        if (gone) return
        update('ready')
        latest.current.onReady?.(instance!)
      })
    }).catch(() => {
      if (gone) return
      instance?.dispose()
      controller.current = null
      update('error')
    })
    return () => {
      gone = true
      instance?.dispose()
      if (controller.current === instance) controller.current = null
    }
  }, [model, attempt, controller])

  useEffect(() => { controller.current?.shot(shot, x) }, [shot, x, controller])
  useEffect(() => { controller.current?.zoom(zoom) }, [zoom, controller])
  useEffect(() => { controller.current?.spin(spinning) }, [spinning, controller])
  useEffect(() => { controller.current?.motion(motion) }, [motion, controller])

  const name = mascotProfile(model).name
  return (
    <div className="mascot-view" data-load={status} data-motion={motion}>
      <canvas ref={canvas} tabIndex={0} aria-label={`${name}, interactive 3D mascot. Follows your cursor. Drag sideways or use left and right arrow keys to turn; Home resets rotation. Tap hair, face or hands for a reaction.`} />
      {status === 'loading' && <p className="mascot-loading" role="status">Loading {name}<span aria-hidden="true"> · · ·</span></p>}
      {status === 'error' && <div className="mascot-load-error" role="alert">
        <p>We couldn’t load {name}.</p>
        <p className="note">Check your connection or WebGL support and try again.</p>
        <button className="soft" onClick={() => setAttempt((n) => n + 1)}>Retry mascot</button>
      </div>}
    </div>
  )
}
