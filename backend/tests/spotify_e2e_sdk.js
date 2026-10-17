// Browser-test double only. This script is never shipped or imported by the app.
(() => {
  const get = () => fetch('/__e2e/state').then(r => r.json())
  class Player {
    constructor(options) { this.options = options; this.listeners = {}; this.id = crypto.randomUUID() }
    addListener(name, fn) { this.listeners[name] = fn; return true }
    removeListener(name) { delete this.listeners[name]; return true }
    async action(operation, value) {
      await fetch('/__e2e/sdk', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({operation,device_id:this.id,value}) })
      this.listeners.player_state_changed?.(await this.getCurrentState())
    }
    async connect() {
      await new Promise(resolve => this.options.getOAuthToken(resolve))
      await this.action('connect'); await this.action('volume', this.options.volume); this.listeners.ready?.({device_id:this.id})
      this.timer = setInterval(async () => this.listeners.player_state_changed?.(await this.getCurrentState()), 200)
      return true
    }
    disconnect() { clearInterval(this.timer); void this.action('disconnect') }
    async activateElement() {}
    async getCurrentState() {
      const state = await get()
      if (state.device_id !== this.id || !state.track) return null
      // Real SDK observations lag accepted Web API writes. Exercise that lag
      // throughout the browser pipeline, rather than making every write instant.
      const key = `${state.playing}:${state.track.uri}`
      if (this.observedKey !== key) { this.observedKey = key; this.observedAt = performance.now() }
      if (state.playing && performance.now() - this.observedAt < 450) return null
      return {paused:!state.playing,position:state.position,duration:state.track.duration_ms,disallows:{},track_window:{current_track:state.track}}
    }
    pause() { return this.action('pause') }
    resume() { return this.action('resume') }
    seek(value) { return this.action('seek',value) }
    previousTrack() { return this.action('previous') }
    nextTrack() { return this.action('next') }
    setVolume(value) { return this.action('volume',value) }
  }
  window.Spotify = {Player}; window.onSpotifyWebPlaybackSDKReady?.()
})()
