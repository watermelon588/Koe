import assert from 'node:assert/strict'
import { test } from 'node:test'
import { softwareVolumeSupported } from '../src/music/capabilities.ts'

test('iPhone and desktop-mode iPad use physical volume; Android and desktop retain software controls', () => {
  for (const userAgent of ['iPhone Safari', 'iPad Safari', 'Mozilla/5.0 (Macintosh; Intel Mac OS X)'])
    assert.equal(softwareVolumeSupported({ userAgent, maxTouchPoints: 5 }), false)
  for (const userAgent of ['Android Chrome', 'Windows Chrome', 'Macintosh Safari'])
    assert.equal(softwareVolumeSupported({ userAgent, maxTouchPoints: 0 }), true)
})
