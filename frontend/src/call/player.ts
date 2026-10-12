// Plays a stream of raw PCM16 little-endian mono chunks without gaps.
// Each chunk becomes its own AudioBufferSourceNode (a node can only start() once),
// scheduled to begin exactly where the previous chunk ends.
// https://developer.mozilla.org/en-US/docs/Web/API/AudioBufferSourceNode/start
export function createPlayer(sampleRate = 24000) {
  // Context runs at the stream's own rate, so no resampling code is needed.
  // https://developer.mozilla.org/en-US/docs/Web/API/AudioContext/AudioContext
  const ctx = new AudioContext({ sampleRate })
  let nextStart = 0
  const queued = new Set<AudioBufferSourceNode>() // scheduled or playing
  // Every chunk passes through one analyser on its way to the speakers; the mascot reads
  // its loudness to move the mouth. https://developer.mozilla.org/en-US/docs/Web/API/AnalyserNode
  const analyser = ctx.createAnalyser()
  analyser.connect(ctx.destination)

  function play(chunk: ArrayBuffer) {
    const view = new DataView(chunk)
    const n = chunk.byteLength / 2
    const buffer = ctx.createBuffer(1, n, sampleRate)
    const out = buffer.getChannelData(0)
    for (let i = 0; i < n; i++) out[i] = view.getInt16(i * 2, true) / 32768 // true = little-endian

    const src = ctx.createBufferSource()
    src.buffer = buffer
    src.connect(analyser)
    nextStart = Math.max(nextStart, ctx.currentTime) // if we fell behind, start now
    src.start(nextStart)
    nextStart += buffer.duration
    queued.add(src)
    src.onended = () => queued.delete(src)
  }

  // Barge-in: the user started talking, so drop everything not yet heard.
  // https://developer.mozilla.org/en-US/docs/Web/API/AudioScheduledSourceNode/stop
  function flush() {
    queued.forEach((src) => src.stop())
    queued.clear()
    nextStart = 0
  }

  return { ctx, analyser, play, flush }
}
