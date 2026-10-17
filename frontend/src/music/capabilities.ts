// Spotify documents iOS volume as physical-only, including iPad's desktop UA.
// https://developer.spotify.com/documentation/web-playback-sdk/reference#spotifyplayer-setvolume
export function softwareVolumeSupported(device: Pick<Navigator, 'userAgent' | 'maxTouchPoints'> = navigator): boolean {
  return !(/iPad|iPhone|iPod/.test(device.userAgent) || /Macintosh/.test(device.userAgent) && device.maxTouchPoints > 1)
}
