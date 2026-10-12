import { useRef, useState } from 'react'
import { startMic } from './call/mic'
import { createPlayer } from './call/player'

export default function App() {
  const [status, setStatus] = useState('idle')
  const hangUp = useRef<(() => void) | null>(null)

  async function call() {
    // Slice 2 echo test: the backend sends our 16 kHz mic audio straight back, so play it at 16 kHz.
    const player = createPlayer(16000) // created on click: browsers only allow audio after a user gesture
    const ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/call`)
    ws.binaryType = 'arraybuffer'
    ws.onmessage = (e) => player.play(e.data)
    ws.onerror = () => setStatus('error: is the backend running on :8000?')
    ws.onclose = () => {
      hangUp.current?.() // server closed: release the mic too
      setStatus((s) => (s.startsWith('error') ? s : 'ended'))
    }
    ws.onopen = async () => {
      try {
        const stopMic = await startMic((pcm) => ws.readyState === WebSocket.OPEN && ws.send(pcm))
        hangUp.current = () => {
          stopMic()
          ws.close()
          player.ctx.close()
          hangUp.current = null
        }
        setStatus('connected: speak, you should hear yourself')
      } catch (err) {
        setStatus(`mic error: ${err}`)
        ws.close()
      }
    }
  }

  return (
    <main>
      <h1>Koe 声</h1>
      {status.startsWith('connected') ? (
        <button onClick={() => hangUp.current?.()}>Hang up</button>
      ) : (
        <button onClick={call}>Call</button>
      )}
      <p>{status}</p>
    </main>
  )
}
