// Only runtime-ready models belong here; source VRoid projects stay in assets/.
export const MASCOTS = [
  { id: 'kami', name: 'Kami', portrait: '/mascot/portraits/kami.jpg' },
  { id: 'miku', name: 'Miku', portrait: '/mascot/portraits/miku.jpg' },
  { id: 'aoi', name: 'Aoi', portrait: '/mascot/portraits/aoi.jpg' },
  { id: 'kobashi', name: 'Kobashi', portrait: '/mascot/portraits/kobashi.jpg' },
] as const

export type MascotId = (typeof MASCOTS)[number]['id']
export const mascotProfile = (id: MascotId) => MASCOTS.find((m) => m.id === id)!

export function savedMascot(): MascotId {
  try {
    const saved = localStorage.getItem('koe-mascot')
    return MASCOTS.find((m) => m.id === saved)?.id ?? 'kami'
  } catch {
    return 'kami'
  }
}

export function saveMascot(id: MascotId): boolean {
  try {
    localStorage.setItem('koe-mascot', id)
    return true
  } catch {
    return false
  }
}
