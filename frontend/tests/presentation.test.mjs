import assert from 'node:assert/strict'
import { test } from 'node:test'
import { providerLink, approvalMessageText } from '../src/approvals/presentation.ts'
import { activityText, activityLink, activityDay, clockTime } from '../src/dashboard/state.ts'

test('chat removes only its exact duplicate audit suffix when a preview is present', () => {
  const approval = { summary: 'Audit with {"raw":"JSON"}' }
  const prefix = 'Review this change.'
  const full = `${prefix}\nPending: ${approval.summary}. Confirm with yes or cancel with no.`
  assert.equal(approvalMessageText(full, approval), prefix)
  assert.equal(approvalMessageText(full), full)
  assert.equal(approvalMessageText('Other text mentioning Pending:', approval), 'Other text mentioning Pending:')
})

test('provider links reject foreign hosts, credentials, protocols and ports', () => {
  for (const url of ['javascript:alert(1)', 'http://github.com/me/app', 'https://github.com.evil.test/x',
    'https://user:password@github.com/x', 'https://github.com:444/x']) assert.equal(providerLink(url), '')
  assert.equal(providerLink('https://github.com/me/app/pull/42'), 'https://github.com/me/app/pull/42')
})

test('activity uses authoritative status and compact display; keeps errors visible', () => {
  const display = { title: 'Add column Billable', lines: ['Tab: Timesheet'], url: 'https://docs.google.com/spreadsheets/d/test/edit' }
  const item = { type: 'approval_result', result: { status: 'executed', display }, summary: 'Full long audit' }
  assert.equal(activityText(item), 'Executed · Add column Billable')
  assert.equal(activityLink(item), display.url)
  assert.match(activityText({ ...item, result: { status: 'failed', display, error: { message: 'Sheet changed' } } }), /Sheet changed/)
  assert.equal(activityText({ kind: 'approval', summary: 'rejected', display }), 'Cancelled · Add column Billable')
  assert.equal(activityText({ type: 'approval_pending', action: { display } }), 'Proposed · Add column Billable')
})

test('legacy activity hides long URLs from its line but supplies an Open link', () => {
  const item = { summary: 'Log 2 hours. Destination: https://docs.google.com/spreadsheets/d/test/edit tab Timesheet.' }
  assert.ok(!activityText(item).includes('https://'))
  assert.equal(activityLink(item), 'https://docs.google.com/spreadsheets/d/test/edit')
})

test('day headings follow the app timezone including midnight and year changes', () => {
  const now = new Date('2026-01-01T00:05:00+05:30')
  assert.equal(activityDay('2025-12-31T20:00:00Z', now), 'Today')
  assert.equal(activityDay('2025-12-31T18:00:00Z', now), 'Yesterday')
  assert.match(activityDay('2025-12-29T10:00:00Z', now), /29 Dec 2025/)
  assert.equal(clockTime('2026-10-16T05:46:00Z', 'Asia/Kolkata'), '11:16')
})
