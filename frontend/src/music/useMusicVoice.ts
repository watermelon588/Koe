import { useCallback, useEffect, useRef, useState } from 'react'
import { wsUrl } from '../backend'
import { music as request } from './api'
import { musicVoiceBoundary, type VoiceCommand, type VoiceGrant, type VoiceResult } from './voice'

type Permission = { available: boolean; enabled: boolean; grant: VoiceGrant | null }
export function useMusicVoice(active: boolean, connectionId: string, playlistId: string,
  apply: (command: VoiceCommand) => Promise<VoiceResult>, suggest: (query: string, state: string) => void) {
  const [permission, setPermission] = useState<Permission>({ available: false, enabled: false, grant: null })
  const [connected, setConnected] = useState(false)
  const [notice, setNotice] = useState('')
  const ready = useRef('')
  const reconnect = useRef(() => {})
  const executor = useRef({ apply, suggest })
  useEffect(() => { executor.current = { apply, suggest } }, [apply, suggest])
  const load = useCallback(async () => {
    if (!connectionId || !playlistId) return
    const reply = await request('/api/music/voice-permission')
    if (reply.http !== 200) throw Error('Sign in again to enable playlist voice controls.')
    setPermission(reply.body as Permission)
  }, [connectionId, playlistId])
  useEffect(() => {
    if (!connectionId || !playlistId) return
    const controller = new AbortController()
    void request('/api/music/voice-permission', 'GET', undefined, controller.signal).then(reply => {
      if (!controller.signal.aborted && reply.http === 200) setPermission(reply.body as Permission)
    }).catch(() => {})
    return () => controller.abort()
  }, [connectionId, playlistId])
  const enabled = permission.enabled && permission.grant?.connection_id === connectionId && permission.grant?.playlist_id === playlistId
  async function allow(value: boolean) {
    try {
      const reply = await request('/api/music/voice-permission', 'PUT', { connection_id: connectionId, playlist_id: playlistId, enabled: value })
      if (reply.http !== 200) throw Error('Could not change playlist permission. Sign in and retry.')
      await load(); setNotice(''); return true
    } catch (error) { setNotice(error instanceof Error ? error.message : 'Voice controls unavailable.'); return false }
  }
  useEffect(() => {
    if (!active || !enabled) return
    let stopped = false, socket: WebSocket | undefined, timer: ReturnType<typeof setTimeout> | undefined
    let retries = 0, opening = false
    let closeBoundary = () => {}
    const grant = { connection_id: connectionId, playlist_id: playlistId }
    const key = `${connectionId}:${playlistId}`
    function retry() {
      if (stopped) return
      if (retries >= 5) { setNotice('Voice connection is unavailable. Call again to retry.'); return }
      timer = setTimeout(() => void connect(), Math.min(8000, 500 * 2 ** retries++))
    }
    async function connect() {
      if (stopped || opening || socket?.readyState === WebSocket.OPEN || socket?.readyState === WebSocket.CONNECTING) return
      opening = true
      try {
        const current = await request('/api/music/voice-permission')
        const value = current.body as Permission
        if (stopped) return
        if (current.http !== 200 || !value.enabled || value.grant?.connection_id !== connectionId || value.grant?.playlist_id !== playlistId) {
          setPermission(current.http === 200 ? value : { available: false, enabled: false, grant: null }); return
        }
        const ticket = await request('/api/music/voice-ticket', 'POST', {})
        const credential = (ticket.body as { ticket?: string })?.ticket
        if (stopped) return
        if (ticket.http !== 200 || !credential) throw Error('Could not establish playlist voice controls.')
        const boundary = musicVoiceBoundary(grant, async () => {
          const reply = await request('/api/music/voice-permission')
          const valid = reply.body as Permission
          return !stopped && reply.http === 200 && valid.enabled && valid.grant?.connection_id === connectionId && valid.grant?.playlist_id === playlistId
        }, command => executor.current.apply(command))
        closeBoundary = boundary.close
        let tail = Promise.resolve()
        socket = new WebSocket(wsUrl('/ws/music-control'))
        const currentSocket = socket
        socket.onopen = () => currentSocket.send(JSON.stringify({ ticket: credential }))
        socket.onmessage = event => {
          let message
          try { message = JSON.parse(event.data) } catch { return }
          if (message.type === 'ready') { ready.current = key; retries = 0; setConnected(true); setNotice(''); return }
          if (message.type === 'suggestion' && message.connection_id === connectionId && message.playlist_id === playlistId && typeof message.query === 'string' && message.query.length <= 401) {
            executor.current.suggest(message.query, message.state); return
          }
          if (message.type !== 'command' && message.type !== 'release') return
          tail = tail.then(async () => {
            const state = await boundary.receive(message as VoiceCommand)
            if (stopped || currentSocket.readyState !== WebSocket.OPEN) return
            currentSocket.send(JSON.stringify({ type: 'result', id: message.id, state }))
            setNotice(state === 'queued' ? 'Koe will finish her reply, then play your music.' : state === 'deferred' ? 'Volume saved for playback.' : state === 'failed' || state === 'outcome_unknown' ? 'Playback was not confirmed. Inspect the player before trying again.' : '')
          }).catch(() => setNotice('Music control was not confirmed.'))
        }
        socket.onclose = event => {
          boundary.close(); ready.current = ''; setConnected(false)
          if (stopped) return
          setNotice(event.reason || 'Reconnecting voice controls. Unconfirmed commands will not be repeated.')
          retry()
        }
        socket.onerror = () => { if (!stopped) setNotice('Reconnecting playlist voice controls…') }
      } catch (error) { if (!stopped) { setNotice(error instanceof Error ? error.message : 'Voice controls unavailable.'); retry() } }
      finally { opening = false }
    }
    const wake = () => { if (!stopped && (!socket || socket.readyState === WebSocket.CLOSED)) { retries = 0; clearTimeout(timer); void connect() } }
    reconnect.current = wake
    const ping = setInterval(() => { if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: 'ping' })) }, 15000)
    addEventListener('online', wake); document.addEventListener('visibilitychange', wake)
    void connect()
    return () => { stopped = true; ready.current = ''; if (reconnect.current === wake) reconnect.current = () => {}; closeBoundary(); clearTimeout(timer); clearInterval(ping); socket?.close(); removeEventListener('online', wake); document.removeEventListener('visibilitychange', wake) }
  }, [active, enabled, connectionId, playlistId])
  async function waitReady() {
    const key = `${connectionId}:${playlistId}`
    if (ready.current !== key) reconnect.current()
    for (let attempt = 0; attempt < 100; attempt++) {
      if (ready.current === key) return
      await new Promise(resolve => setTimeout(resolve, 100))
    }
    throw Error('Playlist voice controls are reconnecting. Try Call again shortly.')
  }
  return { available: permission.available && !!connectionId && !!playlistId, enabled, connected: active && enabled && connected, notice, allow, waitReady, refresh: load }
}
