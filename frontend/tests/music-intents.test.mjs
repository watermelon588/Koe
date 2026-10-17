import assert from 'node:assert/strict'
import { test } from 'node:test'
import { MusicIntents } from '../src/music/intents.ts'

const storage = () => { const data = new Map(); return { getItem: k => data.get(k) ?? null, setItem: (k, v) => data.set(k, v), removeItem: k => data.delete(k) } }
test('lost mutation response persists across reload and is inspected, never resent', async () => {
  const saved = storage(); let writes = 0
  const intents = new MusicIntents('generation', async (_path, method) => { if (method !== 'GET') { writes++; throw Error('network') } return { http: 202, body: { state: 'outcome_unknown' } } }, saved, () => 'intent-1')
  await assert.rejects(intents.write('/api/music/playback', 'POST', { operation: 'play' }))
  const reloaded = new MusicIntents('generation', async () => ({ http: 202, body: { state: 'outcome_unknown' } }), saved)
  assert.equal(reloaded.pending().length, 1)
  await reloaded.inspect()
  await assert.rejects(reloaded.write('/api/music/playback', 'POST', { operation: 'play' }), /unconfirmed/)
  assert.equal(writes, 1)
})
test('confirmed result and definitive rejection clear intent; uncertain response does not', async () => {
  const saved = storage()
  const good = new MusicIntents('g', async () => ({ http: 200, body: { state: 'confirmed', result: { accepted: true } } }), saved, () => 'id')
  await good.write('/api/music/playback', 'POST', {})
  assert.equal(good.pending().length, 0)
  const bad = new MusicIntents('g', async () => ({ http: 429, body: { error: { code: 'spotify_rate_limited', outcome: 'not_sent' } } }), saved, () => 'id2')
  await assert.rejects(bad.write('/api/music/playback', 'POST', {}))
  assert.equal(bad.pending().length, 0)
})
test('blocked browser storage fails before sending a write', async () => {
  let calls = 0
  const intents = new MusicIntents('g', async () => { calls++ }, { getItem: () => null, setItem: () => { throw Error('blocked') } })
  await assert.rejects(intents.write('/api/music/playback', 'POST', {}), /remember/)
  assert.equal(calls, 0)
})

test('inspection can clear an intent proven not sent without retrying the original write', async () => {
  const saved = storage(); let writes = 0
  const first = new MusicIntents('g',async () => {writes++; throw Error('lost')},saved,()=> 'not-sent')
  await assert.rejects(first.write('/api/music/playlist/items','POST',{}))
  const reloaded = new MusicIntents('g',async (_path,method) => {
    assert.equal(method,'GET')
    return {http:409,body:{error:{code:'spotify_request_not_sent',outcome:'not_sent'}}}
  },saved)
  await reloaded.inspect()
  assert.equal(reloaded.pending().length,0)
  assert.equal(writes,1)
})

test('an uncertain shuffle never replays and does not block independent play or playlist edits', async () => {
  const sent = []
  const intents = new MusicIntents('g', async (path, method, body) => {
    if (method === 'GET') return {http:202,body:{state:'outcome_unknown'}}
    sent.push(body)
    return body.operation === 'shuffle' ? {http:202,body:{state:'outcome_unknown'}} : {http:200,body:{state:'confirmed',result:{accepted:true}}}
  }, storage())
  await assert.rejects(intents.write('/api/music/playback','POST',{operation:'shuffle',state:true}))
  assert.equal(intents.pending().length,1)
  assert.equal(intents.blocking().length,0)
  await intents.write('/api/music/playback','POST',{operation:'play'})
  await intents.write('/api/music/playlist/items','POST',{uri:'example'})
  assert.equal(sent.filter(body => body.operation === 'shuffle').length,1)
  assert.equal(sent.length,3)
})

test('malformed persisted action data fails closed without crashing status rendering or writing', async () => {
  const saved = storage(); let writes = 0
  saved.setItem('koe-music-intents:g', JSON.stringify([{id:'old',path:'/api/music/playback'}]))
  const intents = new MusicIntents('g', async () => { writes++ }, saved)
  assert.deepEqual(intents.blocking(), [])
  await assert.rejects(intents.write('/api/music/playback','POST',{operation:'play'}), /remember/)
  assert.equal(writes,0)
})
