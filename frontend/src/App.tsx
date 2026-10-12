import { useRef, useState } from 'react'
import { startMic } from './call/mic'
import { createPlayer } from './call/player'

export default function App() {
  const [status, setStatus] = useState('idle')
  const hangUp = useRef<(() => void) | null>(null)

  async function call() {
    const player = createPlayer() // 24 kHz, Gemini's output rate. Created on click: browsers only allow audio after a user gesture
    const ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/call`)
    ws.binaryType = 'arraybuffer'
    // Binary frames = Koe's audio; text frames = control events (JSON).
    ws.onmessage = (e) => {
      if (typeof e.data !== 'string') return player.play(e.data)
      if (JSON.parse(e.data).type === 'interrupted') player.flush()
    }
    ws.onerror = () => setStatus('error: is the backend running on :8000?')
    ws.onclose = (e) => {
      hangUp.current?.() // server closed: release the mic too
      setStatus((s) => (e.reason ? `error: ${e.reason}` : s.startsWith('error') ? s : 'ended'))
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
        setStatus('connected: say hi to Koe')
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
