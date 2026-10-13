import { wsCredential } from '../session'
import { useEffect, useReducer, useRef, useState } from 'react'
import { emptyState, reduceEvent } from './state'
import { wsUrl } from '../backend'

export function useDashboard(onAlert: () => void) {
  const [data, dispatch] = useReducer(reduceEvent, emptyState)
  const [status, setStatus] = useState('Enter your access token and connect to load your day.')
  const [connected, setConnected] = useState(false)
  const [token, setToken] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)
  const socket = useRef<WebSocket | null>(null)
  const alertHandler = useRef(onAlert)
  useEffect(() => { alertHandler.current = onAlert }, [onAlert])

  useEffect(() => {
    if (!token) return
    let gone = false
    let retries = 0
    let timer: ReturnType<typeof setTimeout>
    let ws: WebSocket
    function open() {
      if (gone) return
      setStatus('Connecting dashboard…')
      ws = new WebSocket(wsUrl('/ws/events'))
      socket.current = ws
      ws.onopen = () => wsCredential(token ?? '')
        .then((credential) => ws.send(JSON.stringify({ type: 'auth', token: credential })))
        .catch((e) => { setStatus(e instanceof Error ? e.message : String(e)); ws.close() })
      ws.onmessage = (message) => {
        try {
          const event = JSON.parse(message.data)
          if (!event || typeof event !== 'object') return
          dispatch(event)
          if (event.type === 'snapshot') {
            setConnected(true)
            setStatus('Live updates connected')
            retries = 0
          }
          if (event.type === 'alert') alertHandler.current()
          if (event.type === 'approval_result' && event.result?.status === 'executed') ws.send(JSON.stringify({ type: 'refresh' }))
        } catch { /* ignore malformed frames and unknown protocol additions */ }
      }
      ws.onclose = (event) => {
        if (gone) return
        setConnected(false)
        if (event.code === 1008) {
          setStatus(event.reason || 'Check your Koe access token.')
          return // editing the token and pressing Connect is required; no credential retry loop
        }
        setStatus('Dashboard disconnected. Showing last received data; reconnecting…')
        timer = setTimeout(open, Math.min(1000 * 2 ** retries++, 30000))
      }
      ws.onerror = () => setStatus('Couldn’t reach the dashboard. Check the backend on port 8000.')
    }
    open()
    return () => { gone = true; clearTimeout(timer); socket.current = null; ws?.close(); setConnected(false) }
  }, [token, attempt])

  return { data, status, connected,
    connect: (value: string) => { if (value.trim()) { setToken(value.trim()); setAttempt((n) => n + 1) } },
    refresh: () => { if (socket.current?.readyState === WebSocket.OPEN) socket.current.send(JSON.stringify({ type: 'refresh' })) } }
}
