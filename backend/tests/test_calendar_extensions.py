import asyncio

import pytest

from koe.tools import calendar
from koe.config import settings
from test_calendar import api
from test_approvals import fake_store

ARGS = {'title': 'Review', 'start': '2026-10-15T19:00:00+05:30', 'end': '2026-10-15T19:30:00+05:30'}


def test_bounded_daily_plan_has_exact_occurrences_and_rrule():
    args = calendar.prepare_event(**ARGS, recurrence={'frequency': 'daily', 'count': 3})
    plan = calendar.event_plan(args)
    assert plan['rrule'] == 'RRULE:FREQ=DAILY;INTERVAL=1;COUNT=3'
    assert [p['start'] for p in plan['occurrences']] == [f'2026-10-{d}T19:00:00+05:30' for d in (15, 16, 17)]


@pytest.mark.parametrize('recurrence', [
    {'frequency': 'monthly', 'count': 3}, {'frequency': 'daily', 'count': True},
    {'frequency': 'daily', 'count': 21}, {'frequency': 'weekly', 'count': 20},
    {'frequency': 'daily', 'count': 2, 'until': 'forever'}, {'frequency': 'daily'},
    {'frequency': 'daily', 'count': 2, 'interval': 0},
])
def test_invalid_or_excessive_recurrence_never_reaches_api(api, recurrence):
    result = asyncio.run(calendar.calendar_upsert_event(**ARGS, recurrence=recurrence))
    assert result['error']['code'] == 'bad_args' and not api[0]


def test_all_day_uses_date_and_exclusive_end(api):
    result = asyncio.run(calendar.calendar_upsert_event('Holiday', '2026-10-15', '2026-10-17', all_day=True))
    assert 'error' not in result
    body = api[0][-1][2]['json']
    assert body['start'] == {'date': '2026-10-15'} and body['end'] == {'date': '2026-10-17'}
    assert result['all_day'] is True


def test_later_recurrence_conflict_prevents_entire_insert(api):
    api[1].append({'start': {'dateTime': '2026-10-17T19:00:00+05:30'}, 'end': {'dateTime': '2026-10-17T20:00:00+05:30'}})
    result = asyncio.run(calendar.calendar_upsert_event(**ARGS, recurrence={'frequency': 'daily', 'count': 3}))
    assert result['error']['code'] == 'calendar_conflict' and all(c[0] == 'GET' for c in api[0])


def test_recurring_plan_crossing_dst_is_refused(monkeypatch):
    monkeypatch.setattr(settings, 'timezone', 'America/New_York')
    with pytest.raises(ValueError, match='offset transition'):
        calendar.prepare_event('Review', '2026-10-31T19:00:00-04:00', '2026-10-31T19:30:00-04:00',
                               recurrence={'frequency': 'daily', 'count': 3})


def test_recurring_creation_runs_actual_adapter_only_after_approval(fake_store, api, monkeypatch):
    import json
    from koe import agent
    monkeypatch.setitem(agent.TOOLS, 'calendar_upsert_event', agent.TOOLS['calendar_upsert_event']._replace(fn=calendar.calendar_upsert_event))
    async def scenario():
        ctx = agent.Conversation('app')
        proposed = await agent.run_tool('calendar_upsert_event', {**ARGS, 'recurrence': {'frequency': 'weekly', 'count': 3}}, context=ctx)
        assert not api[0]
        assert '2026-10-29T19:00:00+05:30' in proposed['pending_action']['summary']
        action = fake_store[0][proposed['pending_action']['id']]
        action['args_json'] = json.loads(json.dumps(action['args_json']))
        ctx.approval_ready = True
        result = await agent.confirm(ctx, True)
        assert result['status'] == 'executed' and len(result['occurrences']) == 3
        assert api[0][-1][2]['json']['recurrence'] == ['RRULE:FREQ=WEEKLY;INTERVAL=1;COUNT=3']
        assert 'error' in await agent.confirm(ctx, True)
        assert sum(c[0] == 'POST' for c in api[0]) == 1
    asyncio.run(scenario())


@pytest.mark.parametrize('status', ['pending', 'success', 'failure'])
def test_meet_requests_unique_conference_and_returns_provider_state(monkeypatch, status):
    calls = []
    async def request(method, path, **kwargs):
        calls.append((method, path, kwargs))
        if method == 'GET': return {'items': []}
        return {'id': 'new', 'conferenceData': {'createRequest': {'status': {'statusCode': status}},
            'entryPoints': [{'entryPointType': 'video', 'uri': 'https://meet.google.com/abc-defg-hij'}] if status == 'success' else []}}
    monkeypatch.setattr(calendar, 'request', request)
    result = asyncio.run(calendar.calendar_upsert_event(**ARGS, create_meet=True, request_id='a1b2-c3d4'))
    assert result['conference']['status'] == status
    assert bool(result['conference']['url']) == (status == 'success')
    body, params = calls[-1][2]['json'], calls[-1][2]['params']
    assert body['conferenceData']['createRequest'] == {'requestId': 'a1b2-c3d4', 'conferenceSolutionKey': {'type': 'hangoutsMeet'}}
    assert params['conferenceDataVersion'] == 1


def test_meet_missing_approval_id_or_nonboolean_never_reaches_api(api):
    for kwargs in ({'create_meet': True}, {'create_meet': 'yes', 'request_id': 'abc'}):
        result = asyncio.run(calendar.calendar_upsert_event(**ARGS, **kwargs))
        assert result['error']['code'] == 'bad_args'
    assert not api[0]


def test_event_read_returns_version_instance_and_safe_conference(monkeypatch):
    async def request(*args, **kwargs):
        return {'id': 'instance', 'etag': '"v1"', 'summary': 'Review', 'recurringEventId': 'series',
            'originalStartTime': {'date': '2026-10-15'}, 'start': {'date': '2026-10-15'}, 'end': {'date': '2026-10-16'},
            'attendees': [{'email': 'me@example.com'}],
            'conferenceData': {'createRequest': {'status': {'statusCode': 'success'}},
                               'entryPoints': [{'entryPointType': 'video', 'uri': 'https://meet.google.com.evil.test/x'}]}}
    monkeypatch.setattr(calendar, 'request', request)
    result = asyncio.run(calendar.calendar_get_event('instance'))
    assert result['etag'] == '"v1"' and result['recurring_event_id'] == 'series'
    assert result['all_day'] and result['conference']['url'] is None
    assert result['original_start'] == {'date': '2026-10-15'}


def test_calendar_request_accepts_delete_no_content(monkeypatch):
    from types import SimpleNamespace
    import httpx
    import respx
    monkeypatch.setattr(calendar.google_auth, 'credentials', lambda: SimpleNamespace(token='fake'))
    with respx.mock as router:
        router.delete(calendar.API + '/calendars/primary/events/old').mock(return_value=httpx.Response(204))
        assert asyncio.run(calendar.request('DELETE', '/calendars/primary/events/old')) == {}


def test_incomplete_or_repeating_calendar_pages_are_not_treated_as_free(monkeypatch):
    async def request(*args, **kwargs): return {'items': [], 'nextPageToken': 'same'}
    monkeypatch.setattr(calendar, 'request', request)
    result = asyncio.run(calendar.calendar_upsert_event(**ARGS))
    assert result['error']['code'] == 'calendar_too_large'
