import assert from 'node:assert/strict'
import { test } from 'node:test'
import { activityText, emptyState, latencyStats, latestResult, reduceEvent } from '../src/dashboard/state.ts'

test('snapshot restores state; unknown events do not reset it', () => {
  const state = reduceEvent(emptyState, { type: 'snapshot', panels: { calendar: { result: { events: [] } } },
    pending: [{ id: 'a' }], activity: [{ id: 'old' }], latencies: [{ id: 'turn', ms: 600 }], storage: 'Connected' })
  assert.equal(state.pending[0].id, 'a')
  assert.equal(state.panels.calendar.result.events.length, 0)
  assert.equal(reduceEvent(state, { type: 'future-event' }), state)
})

test('approval failures retain the proposal until the server clears it', () => {
  const action = { id: 'a', summary: 'Book', expires_ts: '2099-01-01T00:00:00Z' }
  let state = reduceEvent(emptyState, { type: 'approval_pending', id: 'proposal-event', action, channel: 'cli', session_id: 'original' })
  state = reduceEvent(state, { type: 'approval_pending', id: 'proposal-event', action, channel: 'cli', session_id: 'original' })
  assert.equal(state.pending.length, 1)
  assert.equal(state.activity.length, 1)
  assert.equal(state.pending[0].channel, 'cli')
  state = reduceEvent(state, { type: 'approval_result', id: 'retry', action_id: 'a', clear: false, result: { error: { message: 'Wait' } } })
  assert.equal(state.pending.length, 1)
  state = reduceEvent(state, { type: 'approval_result', id: 'completed', action_id: 'a', clear: true, result: { status: 'executed' } })
  assert.equal(state.pending.length, 0)
  assert.match(activityText(state.activity[0]), /executed/)
})

test('panel errors replace old results and activity/latency stay bounded', () => {
  let state = reduceEvent(emptyState, { type: 'panel', name: 'calendar', result: { events: [{ id: 'old' }] } })
  state = reduceEvent(state, { type: 'panel', name: 'calendar', result: { error: { message: 'Connect Google' } } })
  assert.equal(state.panels.calendar.result.events, undefined)
  for (let i = 0; i < 150; i++) {
    state = reduceEvent(state, { type: 'tool', id: `tool-${i}`, name: 'github_my_prs', phase: 'end', ok: true, ms: 40 })
    state = reduceEvent(state, { type: 'latency', id: `turn-${i}`, ms: i })
  }
  assert.equal(state.activity.length, 100)
  assert.equal(state.latencies.length, 100)
  assert.equal(state.latencies[0].ms, 50)
})

test('percentiles use measured values only with explicit nearest-rank p95', () => {
  assert.equal(latencyStats([]), null)
  assert.deepEqual(latencyStats([{ ms: 1000 }]), { count: 1, p50: 1000, p95: 1000 })
  assert.deepEqual(latencyStats([{ ms: 400 }, { ms: 100 }, { ms: 300 }, { ms: 200 }, { ms: NaN }, { ms: -1 }]),
    { count: 4, p50: 250, p95: 400 })
  assert.deepEqual(latencyStats(Array.from({ length: 20 }, (_, i) => ({ ms: (i + 1) * 100 }))),
    { count: 20, p50: 1050, p95: 1900 })
})

test('GitHub stats come only from the latest successful tool result', () => {
  const ok = { id: '2', ts: 't2', type: 'tool', phase: 'end', name: 'github_activity', ok: true, result: { totals: { commits: 3, merged_prs: null } } }
  const failed = { id: '1', ts: 't1', type: 'tool', phase: 'end', name: 'github_activity', ok: false, result: { error: { message: 'x' } } }
  assert.equal(latestResult({ ...emptyState, activity: [failed] }, 'github_activity'), null)
  const found = latestResult({ ...emptyState, activity: [failed, ok] }, 'github_activity')
  assert.equal(found.result.totals.commits, 3)
  assert.equal(found.result.totals.merged_prs, null) // unknown stays unknown, never zero
})
