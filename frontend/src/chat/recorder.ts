import { startMic } from '../call/mic'

// A voice note: the same 16 kHz mono PCM16 stream the call uses (AudioWorklet), wrapped in a 44-byte WAV
// header. Gemini accepts WAV, and every browser can make it, so no encoder or server conversion is needed.
// WAV format: http://soundfile.sapp.org/doc/WaveFormat/
export async function record() {
  const chunks: ArrayBuffer[] = []
  const stop = await startMic((pcm) => chunks.push(pcm))
  return {
    finish: (): Blob => {
      stop()
      return toWav(chunks)
    },
    cancel: () => stop(),
  }
}

export function toWav(chunks: ArrayBuffer[], rate = 16000): Blob {
  const bytes = chunks.reduce((n, c) => n + c.byteLength, 0)
  const h = new DataView(new ArrayBuffer(44))
  const text = (at: number, s: string) => [...s].forEach((c, i) => h.setUint8(at + i, c.charCodeAt(0)))
  text(0, 'RIFF')
  h.setUint32(4, 36 + bytes, true)
  text(8, 'WAVE')
  text(12, 'fmt ')
  h.setUint32(16, 16, true) // fmt chunk size
  h.setUint16(20, 1, true) // PCM
  h.setUint16(22, 1, true) // mono
  h.setUint32(24, rate, true)
  h.setUint32(28, rate * 2, true) // bytes per second
  h.setUint16(32, 2, true) // bytes per frame
  h.setUint16(34, 16, true) // bits per sample
  text(36, 'data')
  h.setUint32(40, bytes, true)
  return new Blob([h.buffer, ...chunks], { type: 'audio/wav' })
}
