// Runs on the audio thread. Turns mic Float32 samples (-1..1) into PCM16 little-endian
// chunks of 40 ms and posts them to the main thread.
// Plain JS on purpose: loaded with `?url`, which Vite copies as-is (not transpiled).
// https://developer.mozilla.org/en-US/docs/Web/API/AudioWorkletProcessor/process
const CHUNK = 640 // 40 ms at 16 kHz (the AudioContext's rate)

class MicProcessor extends AudioWorkletProcessor {
  constructor() {
    super()
    this.view = new DataView(new ArrayBuffer(CHUNK * 2))
    this.n = 0
  }

  process(inputs) {
    const samples = inputs[0][0] // first input, first (mono) channel; length is usually 128
    if (!samples) return true // mic not connected yet
    for (let i = 0; i < samples.length; i++) {
      const s = Math.max(-1, Math.min(1, samples[i]))
      this.view.setInt16(this.n * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true) // true = little-endian
      if (++this.n === CHUNK) {
        this.port.postMessage(this.view.buffer, [this.view.buffer]) // transfer, no copy
        this.view = new DataView(new ArrayBuffer(CHUNK * 2))
        this.n = 0
      }
    }
    return true // keep running while the call is open
  }
}

registerProcessor('mic', MicProcessor)
