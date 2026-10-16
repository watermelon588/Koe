// Original transparent PNGs supplied by the user. Vite fingerprints only referenced assets.
import kamiFront from '../../assets/mascot/5-kami.png'
import meiFront from '../../assets/mascot/26-Oct-16-01-01-21-44.png'
import kobashiFront from '../../assets/mascot/26-Oct-16-01-01-17-58.png'
import type { MascotId } from '../mascot/catalog'

export type HomepageMascotId = Exclude<MascotId, 'aoi'>

export const HOMEPAGE_ART: Record<HomepageMascotId, string> = {
  kami: kamiFront,
  miku: meiFront,
  kobashi: kobashiFront,
}
