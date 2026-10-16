// The app's footer (Home, Dashboard, Notion, Settings): the way to the public pages. They live at real paths
// (/guide, /privacy, /terms; see main.tsx), so these are plain links that leave the hash-routed app.
export function AppFooter() {
  return (
    <footer className="app-foot">
      <span className="brand">koe <span className="jp" lang="ja">声</span></span>
      <nav aria-label="Help and legal">
        <a href="/guide">Guide</a>
        <a href="/app#install">Install the app</a>
        <a href="/privacy">Privacy</a>
        <a href="/terms">Terms</a>
      </nav>
    </footer>
  )
}
