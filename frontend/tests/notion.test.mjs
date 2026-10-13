import assert from 'node:assert/strict'
import { test } from 'node:test'
import { notionLink, inputDate, localDate } from '../src/notion/state.ts'

test('Notion links allow HTTPS workspace URLs and reject executable, credential and lookalike URLs', () => {
  assert.equal(notionLink('https://www.notion.so/page'), 'https://www.notion.so/page')
  assert.equal(notionLink('https://my-work.notion.site/page'), 'https://my-work.notion.site/page')
  for (const url of ['javascript:alert(1)', 'http://notion.so/page', 'https://notion.so.attacker.test/', 'https://attacker.test/notion.so', 'https://secret@notion.so/page', 'bad']) {
    assert.equal(notionLink(url), undefined)
  }
})

test('record date inputs preserve date-only values and safely handle invalid meeting timestamps', () => {
  assert.equal(inputDate('2026-10-13', false), '2026-10-13')
  assert.equal(inputDate('invalid', true), '')
  assert.match(inputDate('2026-10-13T15:00:00+05:30', true), /^2026-10-13T\d{2}:\d{2}$/)
  assert.match(localDate(), /^\d{4}-\d{2}-\d{2}$/)
})
