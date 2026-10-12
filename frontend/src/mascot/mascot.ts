import * as THREE from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { VRMLoaderPlugin, VRMUtils, type VRM, type VRMHumanBoneName } from '@pixiv/three-vrm'
import type { MToonMaterial } from '@pixiv/three-vrm'
import { parseVroidPose, type PoseBones } from './vroidpose'

// Renders a VRM avatar on `canvas`: breathing, blinking, small idle routines (looking around, fixing her
// hair, shifting her weight), eyes that follow the pointer, reactions to being touched, a mouth driven by
// the loudness of whatever audio passes through `listen(analyser)`, and moods driven by the call.
// All motion is code on the standard VRM bones, so it works for any VRoid model.
// API usage follows pixiv's examples: https://github.com/pixiv/three-vrm/tree/dev/packages/three-vrm/examples
const FPS = 30 // a mascot doesn't need 60 fps; half the frames = half the main-thread + GPU work
// Loudness → mouth opening. Tuning knob: at 8 Gemini's voice pinned the mouth fully open
// (measured p50 0.79 while speaking); 5 leaves room between quiet and loud syllables.
const MOUTH_GAIN = 5
// Tuning knobs that pull VRoid's hard cel look toward the soft references (SPEC §6, MASCOT_GUIDE §0).
// MToon parameters: https://vrm.dev/en/vrm1/mtoon/
const SOFTEN = {
  outline: 0.3, // × the model's outline width (0 = none)
  toony: 0.6, // max shadingToonyFactor: lower = smoother light→shadow gradient
  shadeToLit: 0.45, // pull the (often saturated pink) shade colour this far toward the lit colour
}
// Skirt physics: VRoid's defaults (stiffness ~0.45, dragForce 0.05, no gravity) let a skirt float and flare
// on every turn or hop. Stiffer, heavily damped and pulled down, it sways a little and stays modest.
// Tuning knobs; spring bone parameters: https://vrm.dev/en/vrm1/springbone/
const SKIRT = { stiffness: 2.5, drag: 0.5, gravity: 0.4 } // stiffness is a multiplier; drag and gravity are minimums
const SHOT_SECS = 0.9 // camera move between the half and full figure
const IDLE_EVERY: [number, number] = [6, 12] // seconds between idle routines (random in this range)
// Share of the canvas height hidden by the desk card in the half-figure shot: she's framed so her waist
// sits on the desk's top edge, so the screen never cuts her. Must match --desk-h in index.css.
export const DESK = 0.24

// Base moods last until changed; reactions play for a while, then ease back to the base.
export type Mood = 'idle' | 'listening' | 'thinking'
export type Reaction = 'happy' | 'sad' | 'surprised'
// 'bust' = half figure, hair down to the chest; 'full' = head to toe.
export type Shot = 'bust' | 'full'
export type Gesture = 'wave' | 'fixHair' | 'lookAround' | 'tilt' | 'shift' | 'chin' | 'stretch' | `pose:${string}`

// What each mood does: expression weights, head pose (radians), gaze offset from the camera (metres).
type Look = { face: Partial<Record<string, number>>; pitch: number; yaw: number; roll: number; gaze: [number, number] }
const LOOKS: Record<Mood | Reaction, Look> = {
  idle: { face: {}, pitch: 0, yaw: 0, roll: 0, gaze: [0, 0] },
  listening: { face: { relaxed: 0.15 }, pitch: 0.03, yaw: 0, roll: 0.06, gaze: [0, 0] },
  thinking: { face: {}, pitch: -0.1, yaw: 0.18, roll: -0.04, gaze: [0.6, 0.5] }, // glance up and away
  happy: { face: { happy: 0.7 }, pitch: -0.03, yaw: 0, roll: 0.08, gaze: [0, 0] },
  sad: { face: { sad: 0.6 }, pitch: 0.12, yaw: 0, roll: 0, gaze: [0, -0.3] },
  surprised: { face: { surprised: 0.6 }, pitch: -0.06, yaw: 0, roll: 0, gaze: [0, 0] },
}
const FACES = ['happy', 'sad', 'relaxed', 'surprised']

// Gestures: bone rotations (radians, VRM normalized bones, added on top of the rest pose) at full
// strength, given progress p (0..1) and time t. An envelope eases each one in and out.
// Axes (VRM 1.0 T-pose, facing the camera), tuned by eye on kami and miku: on her right arm, −z raises the
// upper arm and folds the forearm up, +y swings the upper arm forward, −y swings the forearm in toward her
// head. Her right arm is the one on screen left.
type Euler3 = [number, number, number]
// `bones` are offsets on top of the rest pose; `pose` is absolute (a VRoid pose: where each bone should end up).
type Move = { bones: Partial<Record<VRMHumanBoneName, Euler3>>; pose?: PoseBones; face?: Partial<Record<string, number>>; gaze?: [number, number] }
type GestureDef = { secs: number; move: (p: number, t: number) => Move }
const TAU = Math.PI * 2
const GESTURES: Record<string, GestureDef> = {
  wave: {
    secs: 2.4,
    move: (_p, t) => ({
      bones: { rightUpperArm: [0, 0.75, -1.05], rightLowerArm: [0, 0.35 + Math.sin(t * 9) * 0.3, -2.05], head: [0, 0, 0.06] },
      face: { happy: 0.55 },
    }),
  },
  fixHair: {
    secs: 3.2,
    move: (p, t) => ({
      bones: {
        rightUpperArm: [0, 0.9, -1.4],
        rightLowerArm: [0, -0.6 + Math.sin(t * 4) * 0.12 * Math.sin(Math.PI * p), -2.15], // brushing along the hair
        rightHand: [0, 0, -0.4],
        head: [0.04, -0.1, 0.12],
      },
      face: { relaxed: 0.45 },
      gaze: [-0.25, -0.15],
    }),
  },
  lookAround: {
    secs: 4.5,
    move: (p) => ({ bones: { head: [-0.04, 0.42 * Math.sin(TAU * p), 0] }, gaze: [0.9 * Math.sin(TAU * p), 0.15] }),
  },
  tilt: { secs: 2.6, move: () => ({ bones: { head: [0, 0, 0.17], neck: [0, 0, 0.05] }, face: { happy: 0.35 } }) },
  shift: {
    secs: 3.6,
    move: (p) => {
      const s = Math.sin(Math.PI * p)
      return { bones: { hips: [0, 0, 0.035 * s], spine: [0, 0, -0.045 * s], head: [0, 0, 0.03 * s] } }
    },
  },
  // Thinking: hand to her chin while a tool runs.
  chin: {
    secs: 5,
    move: (p, t) => ({
      bones: {
        rightUpperArm: [0, 1.1, -0.75],
        rightLowerArm: [0, -0.85, -2.2 + Math.sin(t * 2) * 0.04 * Math.sin(Math.PI * p)],
        rightHand: [0, 0, -0.45],
        head: [0.06, 0, 0.05],
      },
      gaze: [0.5, 0.4],
    }),
  },
  // A slow stretch, arms over her head, eyes closed.
  stretch: {
    secs: 4,
    move: () => ({
      bones: {
        rightUpperArm: [0, 0.2, -2.6], leftUpperArm: [0, -0.2, 2.6],
        rightLowerArm: [0, 0, -0.35], leftLowerArm: [0, 0, 0.35],
        spine: [-0.08, 0, 0], head: [-0.12, 0, 0],
      },
      face: { relaxed: 0.8 },
    }),
  },
}
// Poses saved from VRoid Studio: put .vroidpose files in src/mascot/poses/ and they join her idle routines,
// held for a few seconds each (bundled at build time). https://vite.dev/guide/features#glob-import
const POSE_FILES = import.meta.glob('./poses/*.vroidpose', { query: '?raw', import: 'default', eager: true }) as Record<string, string>
for (const [path, text] of Object.entries(POSE_FILES)) {
  let pose: PoseBones = {}
  try {
    pose = parseVroidPose(text)
  } catch {
    console.warn(`Skipping unreadable pose file ${path}`)
  }
  if (Object.keys(pose).length) GESTURES[`pose:${path.split('/').pop()!.replace(/\.vroidpose$/, '')}`] = { secs: 5, move: () => ({ bones: {}, pose }) }
}
const IDLE_ROUTINES = ['lookAround', 'fixHair', 'tilt', 'shift', 'stretch', ...Object.keys(GESTURES).filter((g) => g.startsWith('pose:'))] as Gesture[]
const QUIET_ROUTINES: Gesture[] = ['tilt', 'shift'] // during a call: nothing that turns away or raises a hand
const FINGERS = ['Index', 'Middle', 'Ring', 'Little'] as const
const smooth = (a: number, b: number, x: number) => {
  const k = Math.min(1, Math.max(0, (x - a) / (b - a)))
  return k * k * (3 - 2 * k)
}

export function createMascot(canvas: HTMLCanvasElement, url = '/mascot/kami.vrm') {
  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true })
  // 1.5 caps the pixel count on large hi-dpi screens; the canvas can cover the whole window.
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5))
  const camera = new THREE.PerspectiveCamera(20, 1, 0.1, 20)
  const scene = new THREE.Scene()
  const light = new THREE.DirectionalLight(0xffffff, Math.PI)
  light.position.set(1, 1, 1).normalize()
  scene.add(light, new THREE.HemisphereLight(0xffffff, 0xd9c7c0, 0.6)) // soft fill lifts the shadows
  const gaze = new THREE.Object3D() // what the eyes look at: the camera, nudged per mood / pointer
  scene.add(gaze)

  let vrm: VRM | undefined
  let hipsY = 0 // rest height of the hips; the happy hop bounces on top of it
  const frames: Partial<Record<Shot, { centre: number; span: number }>> = {}
  let disposed = false
  let inspecting = false
  let zoom = 1
  let spinning = false
  const loader = new GLTFLoader()
  loader.register((parser) => new VRMLoaderPlugin(parser))
  const ready = loader.loadAsync(url).then((gltf) => {
    if (disposed) return VRMUtils.deepDispose(gltf.scene) // unmounted while downloading
    vrm = gltf.userData.vrm as VRM
    VRMUtils.removeUnnecessaryVertices(gltf.scene) // the three "performance" calls from the examples
    VRMUtils.combineSkeletons(gltf.scene)
    VRMUtils.combineMorphs(vrm)
    VRMUtils.rotateVRM0(vrm) // VRM 0.x models face the other way; no-op for VRM 1.0
    vrm.scene.traverse((o) => {
      o.frustumCulled = false
      const mats = (o as THREE.Mesh).material
      for (const m of Array.isArray(mats) ? mats : mats ? [mats] : []) soften(m as MToonMaterial)
    })
    if (vrm.lookAt) vrm.lookAt.target = gaze
    for (const j of vrm.springBoneManager?.joints ?? []) {
      if (!/skirt/i.test(j.bone.name)) continue // VRoid names them J_Sec_*Skirt*
      j.settings.stiffness *= SKIRT.stiffness
      j.settings.dragForce = Math.max(j.settings.dragForce, SKIRT.drag)
      j.settings.gravityPower = Math.max(j.settings.gravityPower, SKIRT.gravity)
      j.settings.gravityDir.set(0, -1, 0)
    }
    // Relaxed hands: a slight curl in every finger (z folds a finger toward the palm; mirrored per side).
    for (const side of ['left', 'right'] as const) {
      const dir = side === 'left' ? -1 : 1
      for (const f of FINGERS)
        (['Proximal', 'Intermediate', 'Distal'] as const).forEach((j, i) => {
          const bone = vrm!.humanoid.getNormalizedBoneNode(`${side}${f}${j}` as VRMHumanBoneName)
          if (bone) still.set(`${side}${f}${j}` as VRMHumanBoneName, [0, 0, dir * [0.25, 0.35, 0.25][i]])
        })
    }
    hipsY = vrm.humanoid.getNormalizedBoneNode('hips')!.position.y
    scene.add(vrm.scene)
    measure(vrm)
    Object.assign(to, frames[target.shot], { x: target.x }) // first frame: no camera move, just be there
    from = { ...to }
    Object.assign(now, to)
    shotK = 1
  })

  function soften(m: MToonMaterial) {
    if (!m.isMToonMaterial) return
    m.outlineWidthFactor *= SOFTEN.outline
    m.shadingToonyFactor = Math.min(m.shadingToonyFactor, SOFTEN.toony)
    m.shadeColorFactor.lerp(m.color, SOFTEN.shadeToLit)
  }

  // Both shots are measured from the skeleton, so tall, short and chibi models all fit.
  // The VRM head bone sits at the base of the skull; the hair ends ~0.2 × its height above it.
  function measure(v: VRM) {
    v.scene.updateMatrixWorld(true)
    const y = (b: VRMHumanBoneName) => v.humanoid.getRawBoneNode(b)!.getWorldPosition(new THREE.Vector3()).y
    const head = y('head'), spine = y('spine')
    if (inspecting) {
      const bounds = new THREE.Box3().setFromObject(v.scene)
      const height = bounds.max.y - bounds.min.y
      const bottom = spine + (head - spine) * 0.2
      frames.bust = { centre: (bottom + bounds.max.y) / 2, span: (bounds.max.y - bottom) * 1.25 }
      frames.full = { centre: (bounds.min.y + bounds.max.y) / 2, span: height * 1.18 }
      return
    }
    const top = head * 1.2
    // Half figure: hair down to the waist (the spine bone), with the waist on the desk's top edge.
    const viewTop = top + (top - spine) * 0.12 // a little room above her hair
    const bustSpan = (viewTop - spine) / (1 - DESK)
    frames.bust = { centre: viewTop - bustSpan / 2, span: bustSpan }
    frames.full = { centre: top / 2, span: top * 1.14 } // feet to hair, 7% margin top and bottom
  }

  // Camera: `to` is where we're heading, `from` where the last move started; x = her position on
  // screen (0 = left edge, 1 = right edge), done with a view offset so she's still seen head-on.
  // https://threejs.org/docs/#api/en/cameras/PerspectiveCamera.setViewOffset
  const target = { shot: 'bust' as Shot, x: 0.5 }
  let from = { centre: 1.2, span: 0.8, x: 0.5 }
  const to = { centre: 1.2, span: 0.8, x: 0.5 }
  const now = { ...to }
  let shotK = 1 // progress of the current move, 0..1
  function setShot(s: Shot, x: number) {
    target.shot = s
    target.x = x
    if (!vrm) return
    from = { ...now }
    Object.assign(to, frames[s], { x })
    shotK = 0
  }

  // Interaction: her eyes (and a little of her head) follow the pointer anywhere on the page; a tap on
  // her hair makes her fix it, on her face surprises her, on a hand makes her wave, on her body pleases
  // her; a sideways drag turns her and she springs back. Raycasting only runs on a tap, never per frame.
  // https://threejs.org/docs/#api/en/core/Raycaster
  const pointer = new THREE.Vector2(-9, -9) // canvas coordinates, -1..1 (can go past the edges)
  let lastMove = -10
  let attention = 0 // 1 = watching the pointer; fades out 3 s after it stops
  let turn = 0 // body yaw from dragging, radians
  let drag: { id: number; x: number; startX: number; startY: number } | null = null
  const ray = new THREE.Raycaster()
  function toCanvas(e: PointerEvent) {
    const r = canvas.getBoundingClientRect()
    return new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1)
  }
  function onMove(e: PointerEvent) {
    const p = toCanvas(e)
    pointer.set(THREE.MathUtils.clamp(p.x, -3, 3), THREE.MathUtils.clamp(p.y, -2, 2))
    lastMove = t
    if (drag && e.pointerId === drag.id) {
      const yaw = turn + (e.clientX - drag.x) * 0.012
      turn = inspecting ? yaw : THREE.MathUtils.clamp(yaw, -0.9, 0.9)
      drag.x = e.clientX
    }
  }
  function onDown(e: PointerEvent) {
    if (drag || e.button !== 0) return
    drag = { id: e.pointerId, x: e.clientX, startX: e.clientX, startY: e.clientY }
    if (inspecting) canvas.setPointerCapture(e.pointerId)
  }
  function onCancel() {
    drag = null // vertical touch scrolling can cancel a pointer before pointerup fires
  }
  function onUp(e: PointerEvent) {
    if (!drag || e.pointerId !== drag.id) return
    const tap = Math.hypot(e.clientX - drag.startX, e.clientY - drag.startY) < 6
    drag = null
    if (canvas.hasPointerCapture(e.pointerId)) canvas.releasePointerCapture(e.pointerId)
    if (tap && vrm) touched(toCanvas(e))
  }
  function touched(at: THREE.Vector2) {
    ray.setFromCamera(at, camera)
    const hit = ray.intersectObject(vrm!.scene, true)[0]
    if (!hit) return
    const mats = (hit.object as THREE.Mesh).material
    const name = (Array.isArray(mats) ? mats[hit.face?.materialIndex ?? 0] : mats).name.toUpperCase()
    const at3 = (b: VRMHumanBoneName) => vrm!.humanoid.getRawBoneNode(b)!.getWorldPosition(new THREE.Vector3())
    const nearHand = ['leftHand', 'rightHand'].some((b) => at3(b as VRMHumanBoneName).distanceTo(hit.point) < 0.1)
    if (nearHand) return play('wave')
    if (name.includes('HAIR')) {
      react('happy', 1.2)
      return play('fixHair')
    }
    const neck = vrm!.humanoid.getRawBoneNode('neck') ?? vrm!.humanoid.getRawBoneNode('head')!
    if (hit.point.y > neck.getWorldPosition(new THREE.Vector3()).y) {
      reaction = { r: 'surprised', until: t + 0.8 }
      after = { r: 'happy', secs: 1.8 } // startled, then a smile
      return
    }
    react('happy', 2)
    play('tilt')
  }
  canvas.style.touchAction = 'pan-y' // vertical swipes still scroll the page; horizontal ones turn her
  function onKey(e: KeyboardEvent) {
    if (!inspecting) return
    if (e.key === 'ArrowLeft') turn -= 0.2
    else if (e.key === 'ArrowRight') turn += 0.2
    else if (e.key === 'Home') turn = 0
    else return
    e.preventDefault()
  }
  canvas.addEventListener('keydown', onKey)
  addEventListener('pointermove', onMove)
  canvas.addEventListener('pointerdown', onDown)
  addEventListener('pointerup', onUp)
  addEventListener('pointercancel', onCancel)

  let analyser: AnalyserNode | null = null
  const samples = new Float32Array(2048) // AnalyserNode's default fftSize
  let mouth = 0
  let t = 0
  let blinkT = 1 // seconds since the last blink started
  let blinkEvery = 3
  let base: Mood = 'idle'
  let reaction: { r: Reaction; until: number } | null = null
  let after: { r: Reaction; secs: number } | null = null // a reaction that follows the current one
  let gesture: { g: Gesture; start: number } | null = null
  let nextIdle = 4
  const face: Record<string, number> = { happy: 0, sad: 0, relaxed: 0, surprised: 0 }
  const pose = { pitch: 0, yaw: 0, roll: 0, gx: 0, gy: 0 }
  const rest = new Map<VRMHumanBoneName, Euler3>() // per-frame base pose before gestures
  const blended = new Map<VRMHumanBoneName, Euler3>() // gesture offsets, eased so they never snap
  const still = new Map<VRMHumanBoneName, Euler3>() // rest rotations set once at load (relaxed fingers)
  const ZERO: Euler3 = [0, 0, 0]
  let last = 0
  let raf = requestAnimationFrame(frame) // rAF pauses by itself when the tab is hidden

  function react(r: Reaction, secs = 2.5) {
    reaction = { r, until: t + secs }
    after = null
  }
  function play(g: Gesture) {
    if (!GESTURES[g]) return
    gesture = { g, start: t }
    nextIdle = t + GESTURES[g].secs + IDLE_EVERY[0]
  }

  function frame(ms: number) {
    raf = requestAnimationFrame(frame)
    if (ms - last < 1000 / FPS - 2) return
    const dt = Math.min((ms - last) / 1000, 0.1) // clamp: a long pause shouldn't make a huge jump
    last = ms
    t += dt

    const w = canvas.clientWidth, h = canvas.clientHeight
    if (!w || !h) return // hidden or collapsed: nothing to draw
    if (canvas.width !== Math.round(w * renderer.getPixelRatio()) || canvas.height !== Math.round(h * renderer.getPixelRatio())) {
      renderer.setSize(w, h, false)
      camera.aspect = w / h
    }

    // Camera: ease along the current shot move (ease-in-out: it's movement on screen).
    shotK = Math.min(1, shotK + dt / SHOT_SECS)
    const k = shotK < 0.5 ? 4 * shotK ** 3 : 1 - (-2 * shotK + 2) ** 3 / 2
    for (const key of ['centre', 'span', 'x'] as const) now[key] = from[key] + (to[key] - from[key]) * k
    const dist = now.span / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2))) / zoom
    // Keep the measured framing centered. Dragging only changes body rotation.
    camera.position.set(0, now.centre, dist)
    camera.lookAt(0, now.centre, 0)
    camera.setViewOffset(w, h, (0.5 - now.x) * w, 0, w, h) // negative offset = window moves left = she appears right
    camera.updateProjectionMatrix()

    if (vrm) {
      if (reaction && t > reaction.until) {
        reaction = after ? { r: after.r, until: t + after.secs } : null
        after = null
      }
      const look = LOOKS[reaction?.r ?? base]
      const ease = Math.min(1, dt * 4) // ~0.25 s to settle into a new mood
      const em = vrm.expressionManager!

      // Mouth: RMS ("loudness") of the last 2048 samples, opened fast and closed a bit slower.
      let target = 0
      if (analyser) {
        analyser.getFloatTimeDomainData(samples)
        let sum = 0
        for (const s of samples) sum += s * s
        target = Math.min(1, Math.sqrt(sum / samples.length) * MOUTH_GAIN)
      }
      mouth += (target - mouth) * Math.min(1, dt * (target > mouth ? 30 : 15))
      em.setValue('aa', mouth)

      // Idle routines: every 6–12 s she does something small. During a call, only quiet ones,
      // and never while she's talking or reacting.
      if (!gesture && !reaction && t > nextIdle && mouth < 0.05) {
        const pool = base === 'idle' ? IDLE_ROUTINES : QUIET_ROUTINES
        play(pool[Math.floor(Math.random() * pool.length)])
        nextIdle = t + GESTURES[gesture!.g].secs + IDLE_EVERY[0] + Math.random() * (IDLE_EVERY[1] - IDLE_EVERY[0])
      }
      let move: Move = { bones: {} }
      let strength = 0
      if (gesture) {
        const g = GESTURES[gesture.g]
        const p = (t - gesture.start) / g.secs
        if (p >= 1) gesture = null
        else {
          move = g.move(p, t)
          strength = smooth(0, 0.18, p) * (1 - smooth(0.8, 1, p))
        }
      }

      // Mood (+ gesture) expressions blend toward their targets instead of snapping.
      for (const f of FACES) {
        const want = Math.max(look.face[f] ?? 0, (move.face?.[f] ?? 0) * strength)
        face[f] += (want - face[f]) * ease
        em.setValue(f, face[f])
      }

      // Blink: a quick 0.15 s close-open every 2–6 s. Skipped while smiling: VRoid's happy face
      // already squints, and blink adds on top (its overrideBlink is "none").
      blinkT += dt
      if (blinkT > blinkEvery) {
        blinkT = 0
        blinkEvery = 2 + Math.random() * 4
      }
      const blink = blinkT < 0.15 ? Math.sin((blinkT / 0.15) * Math.PI) : 0
      em.setValue('blink', blink * (1 - face.happy))

      // Where the pointer is, relative to her (she may sit left or right of the canvas centre).
      attention += ((t - lastMove < 3 ? 1 : 0) - attention) * Math.min(1, dt * 3)
      const rel = { x: pointer.x - (2 * now.x - 1), y: pointer.y }

      // Rest pose: arms down with a slight forward bend and a little sway; breathing; mood head pose;
      // small nods while listening; head turned a little toward the pointer. spine + head are required
      // VRM bones (chest/neck are optional): https://vrm.dev/en/vrm1/humanoid/
      pose.pitch += (look.pitch - pose.pitch) * ease
      pose.yaw += (look.yaw - pose.yaw) * ease
      pose.roll += (look.roll - pose.roll) * ease
      const nod = base === 'listening' && !reaction ? Math.max(0, Math.sin(t * 2.2)) ** 6 * 0.06 : 0
      const sway = Math.sin(t * 1.1) * 0.025
      rest.set('leftUpperArm', [0, -0.1, -1.25 + sway])
      rest.set('rightUpperArm', [0, 0.1, 1.25 + sway])
      rest.set('leftLowerArm', [0, -0.25, 0])
      rest.set('rightLowerArm', [0, 0.25, 0])
      rest.set('rightHand', [0, 0, 0])
      rest.set('spine', [Math.sin(t * 1.6) * 0.015, 0, 0]) // breathing
      rest.set('neck', [0, 0, 0])
      rest.set('hips', [0, 0, 0])
      rest.set('head', [
        pose.pitch + nod - Math.min(1, Math.max(-1, rel.y)) * 0.12 * attention,
        pose.yaw + Math.min(1, Math.max(-1, rel.x)) * 0.25 * attention,
        pose.roll + Math.sin(t * 0.7) * 0.04,
      ])
      // Every bone the rest pose, a gesture or a pose touches: offset = (target − rest) × strength, eased so
      // it never snaps, and eased back to zero when the gesture lets go.
      const names = new Set([...rest.keys(), ...still.keys(), ...blended.keys(), ...Object.keys(move.bones), ...Object.keys(move.pose ?? {})] as VRMHumanBoneName[])
      for (const name of names) {
        const r = rest.get(name) ?? still.get(name) ?? ZERO
        const abs = move.pose?.[name]
        const want = move.bones[name] ?? (abs ? [abs[0] - r[0], abs[1] - r[1], abs[2] - r[2]] : ZERO)
        const b = blended.get(name) ?? [0, 0, 0]
        for (let i = 0; i < 3; i++) b[i] += (want[i] * strength - b[i]) * Math.min(1, dt * 10)
        blended.set(name, b)
        vrm.humanoid.getNormalizedBoneNode(name)?.rotation.set(r[0] + b[0], r[1] + b[1], r[2] + b[2])
      }
      if (!drag && !inspecting) turn += (0 - turn) * Math.min(1, dt * 3)
      if (!drag && inspecting && spinning) turn += dt * 0.35
      vrm.scene.rotation.y = turn
      // Happy hop: a small bounce for the first second of the reaction.
      const hop = reaction?.r === 'happy' && reaction.until - t > 1.5 ? Math.abs(Math.sin(t * 9)) * 0.012 : 0
      vrm.humanoid.getNormalizedBoneNode('hips')!.position.y = hipsY + hop

      // Eyes: at the camera, offset by the mood (thinking glances up and away) or the gesture, or at
      // the pointer: the point in the viewer's plane that lines up with the cursor on screen.
      const half = now.span / 2
      const mx = look.gaze[0] + (move.gaze?.[0] ?? 0) * strength
      const my = look.gaze[1] + (move.gaze?.[1] ?? 0) * strength
      pose.gx += (mx + (rel.x * half * camera.aspect - mx) * attention - pose.gx) * ease
      pose.gy += (my + (rel.y * half - my) * attention - pose.gy) * ease
      gaze.position.set(camera.position.x + pose.gx, camera.position.y + pose.gy, camera.position.z)
      vrm.update(dt)
    }
    renderer.render(scene, camera)
  }

  return {
    // The UI waits for the actual VRM to load before enabling preview actions.
    ready,
    inspect(enabled: boolean) {
      inspecting = enabled
      canvas.style.touchAction = enabled ? 'none' : 'pan-y'
      if (vrm) { measure(vrm); setShot(target.shot, target.x) }
    },
    zoom(value: number) { zoom = THREE.MathUtils.clamp(value, 1, 2.5) },
    spin(enabled: boolean) { spinning = enabled },
    // Pass the player's analyser when a call starts, null when it ends.
    listen(a: AnalyserNode | null) {
      analyser = a
    },
    mood(m: Mood) {
      base = m
      if (m === 'thinking' && gesture?.g !== 'chin') play('chin')
    },
    react,
    // A one-off gesture (e.g. a wave when a call connects).
    gesture: play,
    // Frame her as a half or full figure, at horizontal position x (0..1) on the canvas. Animated.
    shot: setShot,
    dispose() {
      disposed = true
      cancelAnimationFrame(raf)
      removeEventListener('pointermove', onMove)
      canvas.removeEventListener('pointerdown', onDown)
      canvas.removeEventListener('keydown', onKey)
      removeEventListener('pointerup', onUp)
      removeEventListener('pointercancel', onCancel)
      if (vrm) VRMUtils.deepDispose(vrm.scene)
      renderer.dispose()
    },
  }
}
