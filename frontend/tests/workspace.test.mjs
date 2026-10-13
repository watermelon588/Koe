import assert from 'node:assert/strict'
import { test } from 'node:test'
import { emptyWork, reduceWork, serviceLink, calendarLayout, liveUrl, announce } from '../src/workspace/workState.ts'

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
  assert.equal(serviceLink('https://docs.google.com/spreadsheets/d/a/edit','sheets'),'https://docs.google.com/spreadsheets/d/a/edit')
  for (const link of ['javascript:alert(1)','https://docs.google.com.evil.test/a','https://secret@docs.google.com/a','http://calendar.google.com/'])
    assert.equal(serviceLink(link,'sheets'),'')
})
test('timeline respects provider timezone, all-day events and overnight bounds', () => {
  const layout = calendarLayout({phase:'ready',work:{service:'calendar',operation:'calendar_list',date:'2026-10-13',timezone:'Asia/Kolkata',details:{},events:[
    {id:'day',title:'Holiday',start:{date:'2026-10-13'},end:{date:'2026-10-14'}},
    {id:'night',title:'Late',start:{dateTime:'2026-10-13T18:00:00Z'},end:{dateTime:'2026-10-13T19:00:00Z'}}]}})
  assert.equal(layout.allDay.length,1)
  assert.equal(layout.items[0].start,23*60+30)
  assert.equal(layout.items[0].end,1440)
})
test('Notion: a proposal waits, only an executed result is saved, the own daily log saves without approval', () => {
  const record = {service:'notion',operation:'notion_save',action_id:'n1',details:{title:'Plan Q4',kind:'Task',date:'2026-10-13'}}
  let s = reduceWork(emptyWork, {type:'approval_pending',work:record})
  assert.equal(s.active,'notion'); assert.equal(s.notion.phase,'waiting')
  assert.equal(reduceWork(s,{type:'approval_result',status:'rejected',work:record}).notion.phase,'cancelled')
  s = reduceWork(s,{type:'approval_result',status:'executed',work:{...record,url:'https://app.notion.com/p/x',page_id:'p'}})
  assert.equal(s.notion.phase,'saved')
  assert.equal(announce('notion', s.notion), 'Saved in Notion: Plan Q4.')
  const log = {service:'notion',operation:'notion_log',details:{date:'2026-10-13',entries:['Shipped #4']},added:1}
  s = reduceWork(s,{type:'tool',phase:'start',operation_id:'o',work:log})
  assert.equal(reduceWork(s,{type:'tool',phase:'end',operation_id:'o',work:log}).notion.phase,'saved')
  assert.equal(reduceWork(s,{type:'tool',phase:'end',operation_id:'o',work:{...log,error:{message:'Notion is not connected'}}}).notion.phase,'error')
})
test('live view frames only verified Google URL forms and never Notion', () => {
  const sheet = {service:'sheets',operation:'sheets_log_hours',details:{},url:'https://docs.google.com/spreadsheets/d/abc_1-2/edit'}
  assert.equal(liveUrl('sheets',sheet,{timesheet:'',google:''}),'https://docs.google.com/spreadsheets/d/abc_1-2/edit?rm=minimal')
  assert.equal(liveUrl('sheets',undefined,{timesheet:'https://docs.google.com/spreadsheets/d/T/edit',google:''}),'https://docs.google.com/spreadsheets/d/T/edit?rm=minimal')
  assert.equal(liveUrl('sheets',{...sheet,url:'https://evil.test/spreadsheets/d/x/edit'},{timesheet:'',google:''}),'')
  assert.equal(liveUrl('calendar',undefined,{timesheet:'',google:'me@example.com'}),
    'https://calendar.google.com/calendar/embed?src=me%40example.com&ctz=Asia%2FKolkata&mode=WEEK')
  assert.ok(liveUrl('calendar',undefined,{timesheet:'',google:'me@x.com&src=other'}).includes('src=me%40x.com%26src%3Dother&'))
  assert.equal(liveUrl('calendar',undefined,{timesheet:'',google:'not an address'}),'')
  assert.equal(liveUrl('notion',{service:'notion',operation:'notion_save',details:{},url:'https://app.notion.com/p/x'},{timesheet:'',google:'me@x.com'}),'')
})
test('screen readers hear pending, saved (with the row) and failures', () => {
  const row = {service:'sheets',operation:'sheets_log_hours',action_id:'r',details:{client:'A',hours:2,date:'2026-10-13'}}
  assert.match(announce('sheets',{phase:'waiting',work:row}),/^Proposed in Google Sheets: 2 hours for A on 2026-10-13\. Not saved yet/)
  assert.equal(announce('sheets',{phase:'saved',work:{...row,row:8}}),'Saved in Google Sheets: 2 hours for A on 2026-10-13, row 8.')
  assert.equal(announce('sheets',{phase:'error',work:{...row,error:{message:'Sheets did not confirm the entry.'}}}),
    'Google Sheets needs attention: Sheets did not confirm the entry.')
})

// Calendar extensions (docs/CALENDAR_EXTENSIONS.md)
import { meetLink, recurrenceText, reminderText } from '../src/workspace/workState.ts'
test('Join Meet appears only for a ready conference with a real meet.google.com link', () => {
  assert.equal(meetLink({status:'success', url:'https://meet.google.com/abc-defg-hij'}), 'https://meet.google.com/abc-defg-hij')
  assert.equal(meetLink({status:'pending', url:'https://meet.google.com/abc-defg-hij'}), '')
  assert.equal(meetLink({status:'success', url:'https://evil.example/meet'}), '')
  assert.equal(meetLink({status:'success', url:''}), '')
  assert.equal(meetLink(undefined), '')
})
test('recurrence and reminders read as plain English; omitted reminders say nothing', () => {
  assert.equal(recurrenceText({frequency:'weekly', interval:2, count:5}), 'Repeats every 2 weeks, 5 times')
  assert.equal(recurrenceText({frequency:'daily', count:3}), 'Repeats daily, 3 times')
  assert.equal(recurrenceText(undefined), '')
  assert.equal(reminderText(undefined), '')
  assert.equal(reminderText([]), 'Reminders off')
  assert.equal(reminderText([{method:'popup', minutes:10}, {method:'email', minutes:60}]), 'Reminders: pop-up 10 min before, email 60 min before')
})
test('an all-day proposal goes in the all-day strip, never on the timed grid', () => {
  const allDay = { ...booking, details: { title: 'Offsite', start: '2026-10-15', end: '2026-10-16', all_day: true } }
  const s = reduceWork(emptyWork, {type:'approval_pending', work:allDay})
  const layout = calendarLayout(s.calendar)
  assert.equal(layout.proposedAllDay, true)
  assert.equal(layout.items.some(i => i.id === 'proposal'), false)
})
test('a confirmed cancellation removes the event from the day view', () => {
  const day = { service:'calendar', operation:'calendar_list', timezone:'Asia/Kolkata', date:'2026-10-13', details:{date:'2026-10-13'},
    events:[{id:'e1', title:'Sync', start:{dateTime:'2026-10-13T10:00:00+05:30'}, end:{dateTime:'2026-10-13T10:30:00+05:30'}}] }
  let s = reduceWork(emptyWork, {type:'tool', phase:'end', work:day})
  const cancel = { service:'calendar', operation:'calendar_cancel_event', action_id:'c', timezone:'Asia/Kolkata', date:'2026-10-13',
    details:{event_id:'e1', title:'Sync', start:'2026-10-13T10:00:00+05:30', end:'2026-10-13T10:30:00+05:30', scope:'single', date:'2026-10-13'} }
  s = reduceWork(s, {type:'approval_pending', work:cancel})
  s = reduceWork(s, {type:'approval_result', status:'executed', work:{...cancel, cancelled:true}})
  assert.equal(s.calendar.phase, 'saved')
  assert.deepEqual(s.calendar.work.events, [])
})
