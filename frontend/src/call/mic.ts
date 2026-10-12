import workletUrl from './mic-worklet.js?url' // https://vite.dev/guide/assets#explicit-url-imports

// Captures the mic as 16 kHz mono PCM16 LE chunks (Gemini Live's input format) and hands
// each chunk to onChunk. The AudioContext runs at 16 kHz, so the browser resamples the mic.
export async function startMic(onChunk: (pcm: ArrayBuffer) => void) {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
  })
  const ctx = new AudioContext({ sampleRate: 16000 })
  await ctx.audioWorklet.addModule(workletUrl)
  const node = new AudioWorkletNode(ctx, 'mic')
  node.port.onmessage = (e) => onChunk(e.data)
  ctx.createMediaStreamSource(stream).connect(node)

  return function stop() {
    stream.getTracks().forEach((t) => t.stop()) // turns off the browser's mic indicator
    ctx.close()
  }
}
