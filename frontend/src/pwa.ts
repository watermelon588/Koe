import { useEffect, useState } from 'react'
import { api } from './chat/api'

// Install Koe on the phone like an app, and receive push notifications (SPEC §14). No app store.
// Install prompt: https://developer.mozilla.org/en-US/docs/Web/API/BeforeInstallPromptEvent
// Push: https://developer.mozilla.org/en-US/docs/Web/API/PushManager/subscribe
type InstallPrompt = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }> }
let deferred: InstallPrompt | null = null
const listeners = new Set<() => void>()
const changed = () => listeners.forEach((f) => f())
addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault() // keep it for our own Install button instead of the browser's mini-bar
  deferred = e as InstallPrompt
  changed()
})
addEventListener('appinstalled', () => {
  deferred = null
  changed()
})

export const isInstalled = () =>
  matchMedia('(display-mode: standalone)').matches || (navigator as Navigator & { standalone?: boolean }).standalone === true
export const isIOS = () => /iphone|ipad|ipod/i.test(navigator.userAgent)

export function useInstall() {
  const [, rerender] = useState(0)
  useEffect(() => {
    const f = () => rerender((n) => n + 1)
    listeners.add(f)
    return () => void listeners.delete(f)
  }, [])
  return {
    canPrompt: deferred !== null,
    installed: isInstalled(),
    ios: isIOS(),
    async install() {
      if (!deferred) return
      await deferred.prompt()
      await deferred.userChoice
      deferred = null
      changed()
    },
  }
}

export function registerServiceWorker() {
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => {}) // no SW = no push; the app still works
}

export type PushState = 'unsupported' | 'denied' | 'on' | 'off'
export async function pushState(): Promise<PushState> {
  if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) return 'unsupported'
  if (Notification.permission === 'denied') return 'denied'
  const reg = await navigator.serviceWorker.ready
  return (await reg.pushManager.getSubscription()) ? 'on' : 'off'
}

export async function enablePush(): Promise<void> {
  if ((await Notification.requestPermission()) !== 'granted') throw new Error('Notifications are blocked. Allow them for this site in the browser settings.')
  const reg = await navigator.serviceWorker.ready
  const key = await api.pushKey()
  const sub = (await reg.pushManager.getSubscription()) ??
    (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: fromBase64Url(key) }))
  await api.subscribe(sub.toJSON())
}

export async function disablePush(): Promise<void> {
  const reg = await navigator.serviceWorker.ready
  await (await reg.pushManager.getSubscription())?.unsubscribe()
}

function fromBase64Url(value: string): Uint8Array<ArrayBuffer> {
  const b64 = (value + '='.repeat((4 - (value.length % 4)) % 4)).replace(/-/g, '+').replace(/_/g, '/')
  return Uint8Array.from(atob(b64), (c) => c.charCodeAt(0))
}
