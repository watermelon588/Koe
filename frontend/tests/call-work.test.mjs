import assert from 'node:assert/strict'
import { test } from 'node:test'
import { emptyWork, reduceWork, googleLink, calendarLayout } from '../src/call/workState.ts'

const booking = { service: 'calendar', operation: 'calendar_upsert_event', action_id: 'a', timezone: 'Asia/Kolkata',
  details: { title: 'Review', start: '2026-10-13T19:00:00+05:30', end: '2026-10-13T19:30:00+05:30' } }
test('proposal stays pending through progress and only execution marks a slot saved', () => {
  let s = reduceWork(emptyWork, {type:'approval_pending', work:booking})
  assert.equal(s.calendar.phase, 'waiting')
  s = reduceWork(s, {type:'approval_progress', work:booking})
  assert.equal(s.calendar.phase, 'saving')
  s = reduceWork(s, {type:'approval_result', work:booking, status:'executed'})
  assert.equal(s.calendar.phase, 'saved')
  const layout = calendarLayout(s.calendar)
  assert.equal(layout.items[0].start, 19 * 60)
  assert.equal(layout.items[0].end, 19 * 60 + 30)
})
test('read failure replaces old results, unknown tools do not open panels, late results cannot overwrite', () => {
  let s = reduceWork(emptyWork, {type:'tool', phase:'start', operation_id:'new', work:{...booking, operation:'calendar_list'}})
  assert.equal(reduceWork(s, {type:'tool',phase:'end',operation_id:'old',work:booking}), s)
  assert.equal(reduceWork(s, {type:'transcript'}), s)
  s = reduceWork(s, {type:'tool',phase:'end',operation_id:'new',work:{...booking,error:{message:'Connect Google'}}})
  assert.equal(s.calendar.phase,'error')
  assert.equal(s.calendar.work.events,undefined)
})
test('switching to Sheets retains Calendar and errors/cancellation never mark a row saved', () => {
  let s = reduceWork(emptyWork, {type:'approval_pending',work:booking})
  const row = {service:'sheets',operation:'sheets_log_hours',action_id:'b',details:{client:'A',hours:2,note:'Full note'}}
  s = reduceWork(s, {type:'approval_pending',work:row})
  assert.equal(s.active,'sheets'); assert.ok(s.calendar)
  s = reduceWork(s, {type:'approval_result',status:'failed',work:{...row,error:{message:'Check the sheet'}}})
  assert.equal(s.sheets.phase,'error')
  s = reduceWork(s, {type:'approval_result',status:'rejected',work:row})
  assert.equal(s.sheets.phase,'cancelled')
})
test('a confirmed move clears stale free windows and removes the old event occurrence', () => {
  let s = reduceWork(emptyWork, {type:'tool',phase:'end',operation_id:'r',work:{...booking, operation:'calendar_list',date:'2026-10-13',
    events:[{id:'move-me',title:'Old time',start:{dateTime:booking.details.start},end:{dateTime:booking.details.end}}],
    slots:[{start:booking.details.start,end:booking.details.end}]}})
  const work={...booking,details:{...booking.details,event_id:'move-me'}}
  s=reduceWork(s,{type:'approval_result',status:'executed',work})
  assert.deepEqual(s.calendar.work.slots,[])
  assert.deepEqual(s.calendar.work.events,[])
})
test('Google links reject executable, credential and lookalike URLs', () => {
  assert.equal(googleLink('https://docs.google.com/spreadsheets/d/a/edit','sheets'),'https://docs.google.com/spreadsheets/d/a/edit')
  for (const link of ['javascript:alert(1)','https://docs.google.com.evil.test/a','https://secret@docs.google.com/a','http://calendar.google.com/'])
    assert.equal(googleLink(link,'sheets'),'')
})
test('timeline respects provider timezone, all-day events and overnight bounds', () => {
  const layout = calendarLayout({phase:'ready',work:{service:'calendar',operation:'calendar_list',date:'2026-10-13',timezone:'Asia/Kolkata',details:{},events:[
    {id:'day',title:'Holiday',start:{date:'2026-10-13'},end:{date:'2026-10-14'}},
    {id:'night',title:'Late',start:{dateTime:'2026-10-13T18:00:00Z'},end:{dateTime:'2026-10-13T19:00:00Z'}}]}})
  assert.equal(layout.allDay.length,1)
  assert.equal(layout.items[0].start,23*60+30)
  assert.equal(layout.items[0].end,1440)
})
