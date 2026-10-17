export const APP_PAGES = ['home', 'dashboard', 'chat', 'settings', 'install', 'notion', 'music'] as const
export type Page = typeof APP_PAGES[number]
export function pageOf(path: string, hash = ''): Page {
  return APP_PAGES.find(page => hash === `#${page}` || path.replace(/\/+$/, '') === `/app/${page}`) ?? 'home'
}
export const pagePath = (page: Page) => page === 'home' ? '/app' : `/app/${page}`

// Same-document navigation keeps the player and live call mounted. Old bookmarks still work.
export function installNavigation() {
  const migrate = () => {
    if (APP_PAGES.some(page => location.hash === `#${page}`))
      history.replaceState(null, '', pagePath(pageOf(location.pathname, location.hash)) + location.search)
  }
  const changed = () => { migrate(); dispatchEvent(new Event('koe-navigation')) }
  const click = (event: MouseEvent) => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
    const anchor = (event.target as Element).closest<HTMLAnchorElement>('a[href]')
    if (!anchor || anchor.target || anchor.hasAttribute('download')) return
    const url = new URL(anchor.href)
    if (url.origin !== location.origin || !APP_PAGES.some(page => url.pathname === pagePath(page))) return
    if (!location.pathname.startsWith('/app')) return
    event.preventDefault()
    history.pushState(null, '', url.pathname + url.search)
    changed()
  }
  changed()
  addEventListener('popstate', changed); addEventListener('hashchange', changed); document.addEventListener('click', click)
  return () => { removeEventListener('popstate', changed); removeEventListener('hashchange', changed); document.removeEventListener('click', click) }
}
