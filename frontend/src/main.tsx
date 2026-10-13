import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { registerServiceWorker } from './pwa'
import { Guide } from './pages/Guide'
import { Privacy } from './pages/Privacy'
import { Terms } from './pages/Terms'

// Public pages live at real paths (/guide, /privacy, /terms); everything else is the app (hash-routed inside).
const PUBLIC = { '/guide': Guide, '/privacy': Privacy, '/terms': Terms } as Record<string, () => React.JSX.Element>
const Page = PUBLIC[location.pathname.replace(/\/+$/, '')] ?? App

registerServiceWorker() // install + push notifications (SPEC §14)

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Page />
  </StrictMode>,
)
