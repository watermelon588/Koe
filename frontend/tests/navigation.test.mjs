import assert from 'node:assert/strict'
import { test } from 'node:test'
import { pageOf, pagePath } from '../src/navigation.ts'

test('app paths and legacy bookmarks resolve to the same canonical route', () => {
  for (const page of ['home', 'music', 'chat', 'dashboard', 'settings', 'notion', 'install']) {
    assert.equal(pageOf('/app', '#' + page), page)
    assert.equal(pageOf(pagePath(page)), page)
    assert.equal(pagePath(page).includes('#'), false)
  }
  assert.equal(pageOf('/app/music/'), 'music')
  assert.equal(pageOf('/unrelated'), 'home')
})
