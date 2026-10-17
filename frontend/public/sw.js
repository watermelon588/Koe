// Koe's service worker: shows push notifications (Koe's replies, GitHub alerts) and opens the chat when
// one is tapped. Plain JS, served as-is from /sw.js. https://developer.mozilla.org/en-US/docs/Web/API/Push_API
self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()))

self.addEventListener('push', (event) => {
  let data = {}
  try {
    data = event.data ? event.data.json() : {}
  } catch {
    data = { body: event.data && event.data.text() }
  }
  event.waitUntil((async () => {
    const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
    windows.forEach((w) => w.postMessage({ type: 'koe-refresh' })) // an open chat loads the new message
    // Already reading the chat on screen: no notification needed, like WhatsApp.
    if (windows.some((w) => w.visibilityState === 'visible' && (new URL(w.url).pathname === '/app/chat' || w.url.includes('#chat')))) return
    await self.registration.showNotification(data.title || 'Koe', {
      body: data.body || '',
      icon: '/icons/icon-192.png',
      tag: data.tag || 'koe',
      renotify: true,
      data: { url: data.url || '/app/chat' },
    })
  })())
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const url = (event.notification.data && event.notification.data.url) || '/app/chat'
  event.waitUntil((async () => {
    const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
    const open = windows[0]
    if (open) {
      await open.focus()
      return open.navigate ? open.navigate(url) : undefined
    }
    return self.clients.openWindow(url)
  })())
})
