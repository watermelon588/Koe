import { useEffect, type ReactNode } from 'react'
import './pages.css'

// Public pages (/guide, /privacy, /terms): readable signed-out, no mascot, no backend calls. Real paths, not
// hash routes, so Google, Meta and Notion can link to the privacy policy and terms. Vercel serves index.html
// for these paths (frontend/vercel.json rewrites).
export const UPDATED = '15 October 2026'
export const CONTACT_URL = 'https://github.com/watermelon588/Koe/issues' // ponytail: a contact email once Koe has its own domain

export function Layout({ title, intro, children, updated = UPDATED }: { title: string; intro: ReactNode; children: ReactNode; updated?: string }) {
  useEffect(() => {
    document.title = `${title} · Koe`
    try {
      document.documentElement.dataset.theme = localStorage.getItem('koe-theme') === 'light' ? 'light' : 'dark'
    } catch { /* storage blocked: dark */ }
  }, [title])

  return (
    <div className="doc-page">
      <header className="doc-top">
        <a href="/" className="doc-brand"><img src="/icons/icon-192.png" alt="" width="28" height="28" />Koe <span lang="ja">声</span></a>
        <nav aria-label="Pages">
          <a href="/guide" aria-current={location.pathname === '/guide' ? 'page' : undefined}>Guide</a>
          <a href="/app/install">Install</a>
          <a href="/app">Open Koe</a>
        </nav>
      </header>
      <main id="main-content" tabIndex={-1}>
        <h1>{title}</h1>
        <p className="doc-intro">{intro}</p>
        {children}
      </main>
      <footer className="doc-foot">
        <nav aria-label="Legal">
          <a href="/guide">Guide</a>
          <a href="/privacy">Privacy</a>
          <a href="/terms">Terms</a>
          <a href={CONTACT_URL} rel="noopener">Contact</a>
        </nav>
        <small>Koe is a personal, invite-only project. Updated {updated}.</small>
      </footer>
    </div>
  )
}

// A section with an anchor, so the guide can link to "#notifications" and the table of contents works.
export function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`}><a href={`#${id}`}>{title}</a></h2>
      {children}
    </section>
  )
}
