import { lazy, Suspense, useEffect, useState } from 'react'
import { Guide } from './pages/Guide'
import { Privacy } from './pages/Privacy'
import { Terms } from './pages/Terms'
import { SignInGate } from './signin'
import { APP_PAGES, installNavigation } from './navigation'

const App = lazy(() => import('./App'))
const Homepage = lazy(() => import('./homepage/Homepage').then(module => ({ default: module.Homepage })))
const PUBLIC = { '/guide': Guide, '/privacy': Privacy, '/terms': Terms } as Record<string, () => React.JSX.Element>
const APP_HASHES = new Set(APP_PAGES.map(page => `#${page}`))

// Root stays public; both /app and earlier /#settings-style bookmarks retain the sign-in gate.
export function Root() {
  const [hash, setHash] = useState(location.hash)
  useEffect(() => {
    const sync = () => setHash(location.pathname + location.hash)
    addEventListener('koe-navigation', sync)
    const dispose = installNavigation()
    return () => { dispose(); removeEventListener('koe-navigation', sync) }
  }, [])
  const path = location.pathname.replace(/\/+$/, '')
  const Page = PUBLIC[path]
  if (Page) return <Page />
  const app = path === '/app' || path.startsWith('/app/') || APP_HASHES.has(hash) || matchMedia('(display-mode: standalone)').matches
  return <Suspense fallback={<p className="signin-wait" role="status">Opening Koe…</p>}>
    {app ? <SignInGate><App /></SignInGate> : <Homepage />}
  </Suspense>
}
