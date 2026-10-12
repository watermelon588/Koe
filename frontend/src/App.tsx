import { useState } from 'react'
import { createPlayer } from './call/player'

export default function App() {
  const [status, setStatus] = useState('idle')

  function call() {
    const player = createPlayer() // created on click: browsers only allow audio after a user gesture
    const ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/call`)
    ws.binaryType = 'arraybuffer'
    ws.onopen = () => setStatus('connected')
    ws.onmessage = (e) => player.play(e.data)
    ws.onerror = () => setStatus('error: is the backend running on :8000?')
    ws.onclose = () => setStatus((s) => (s.startsWith('error') ? s : 'ended'))
  }

  return (
    <main>
      <h1>Koe 声</h1>
      <button onClick={call}>Call</button>
      <p>{status}</p>
    </main>
  )
}
