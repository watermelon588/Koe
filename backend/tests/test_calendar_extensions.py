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
        return {**kwargs['json'], 'id': kwargs['json']['id'], 'conferenceData': {'createRequest': {'status': {'statusCode': status}},
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


@pytest.fixture
def cancel_api(monkeypatch):
    event = {'id': 'event', 'etag': '"v1"', 'summary': 'Exact review', 'organizer': {'self': True},
        'start': {'dateTime': ARGS['start']}, 'end': {'dateTime': ARGS['end']},
        'attendees': [{'email': 'guest@example.com'}]}
    calls = []
    async def request(method, path, **kwargs):
        calls.append((method, path, kwargs))
        if method == 'GET' and path.endswith('/events'): return {'items': []}
        if method == 'GET': return dict(event)
        if method == 'DELETE': return {}
        return {'id': event['id']}
    monkeypatch.setattr(calendar, 'request', request)
    return event, calls


@pytest.mark.parametrize('scope', ['single', 'instance', 'series'])
def test_cancel_exact_scope_uses_frozen_etag_and_one_delete(fake_store, cancel_api, scope):
    import json
    from koe import agent
    event, calls = cancel_api
    if scope == 'instance': event.update(recurringEventId='parent', originalStartTime={'dateTime': ARGS['start']})
    if scope == 'series': event['recurrence'] = ['RRULE:FREQ=WEEKLY;COUNT=3']
    async def scenario():
        ctx = agent.Conversation('app')
        proposed = await agent.run_tool('calendar_cancel_event', {'event_id': 'event', 'expected_etag': '"v1"', 'scope': scope}, context=ctx)
        summary = proposed['pending_action']['summary']
        assert 'Exact review' in summary and 'guest@example.com' in summary and scope in summary
        assert all(c[0] == 'GET' for c in calls)
        action = fake_store[0][proposed['pending_action']['id']]
        action['args_json'] = json.loads(json.dumps(action['args_json']))
        ctx.approval_ready = True
        result = await agent.confirm(ctx, True)
        assert result['status'] == 'executed' and result['cancelled'] and result['scope'] == scope
        delete = calls[-1]
        assert delete[0] == 'DELETE' and delete[1].endswith('/event')
        assert delete[2] == {'headers': {'If-Match': '"v1"'}, 'params': {'sendUpdates': 'all'}}
        assert 'error' in await agent.confirm(ctx, True)
        assert sum(c[0] == 'DELETE' for c in calls) == 1
    asyncio.run(scenario())


@pytest.mark.parametrize('drift', ['etag', 'calendar', 'timezone'])
def test_cancel_rejects_drift_after_preview(fake_store, cancel_api, monkeypatch, drift):
    from koe import agent
    event, calls = cancel_api
    async def scenario():
        ctx = agent.Conversation('app')
        assert 'pending_action' in await agent.run_tool('calendar_cancel_event', {'event_id': 'event', 'expected_etag': '"v1"', 'scope': 'single'}, context=ctx)
        if drift == 'etag': event['etag'] = '"v2"'
        else: monkeypatch.setattr(settings, 'google_calendar_id' if drift == 'calendar' else 'timezone', 'changed')
        ctx.approval_ready = True
        result = await agent.confirm(ctx, True)
        assert result['status'] == 'failed' and not any(c[0] == 'DELETE' for c in calls)
    asyncio.run(scenario())


@pytest.mark.parametrize('invalid', ['wrong_scope', 'stale', 'cancelled', 'guest', 'omitted', 'type', 'internal'])
def test_unsafe_cancellations_never_get_a_proposal(fake_store, cancel_api, invalid):
    from koe import agent
    event, calls = cancel_api
    args = {'event_id': 'event', 'expected_etag': '"v1"', 'scope': 'single'}
    if invalid == 'wrong_scope': args['scope'] = 'series'
    if invalid == 'stale': args['expected_etag'] = '"old"'
    if invalid == 'cancelled': event['status'] = 'cancelled'
    if invalid == 'guest': event['organizer']['self'] = False
    if invalid == 'omitted': event['attendeesOmitted'] = True
    if invalid == 'type': event['eventType'] = 'birthday'
    if invalid == 'internal': args['expected_calendar'] = 'evil'
    async def scenario():
        assert (await agent.run_tool('calendar_cancel_event', args))['error']['code'] == 'approval_required'
        result = await agent.run_tool('calendar_cancel_event', args, context=agent.Conversation('app'))
        assert 'error' in result and not fake_store[0] and all(c[0] == 'GET' for c in calls)
    asyncio.run(scenario())


def test_cancellation_call_projection_and_dashboard_refresh_follow_executed_action(fake_store, cancel_api):
    from types import SimpleNamespace
    from koe import agent, events, voice_call
    sent = []
    async def send_json(data): sent.append(data)
    async def scenario():
        state = voice_call.CallState()
        await agent.run_tool('calendar_cancel_event', {'event_id': 'event', 'expected_etag': '"v1"', 'scope': 'single'}, context=state.context)
        state.context.approval_ready = True
        await voice_call._approval_result(SimpleNamespace(send_json=send_json), state, True)
        assert [e['type'] for e in sent] == ['approval_progress', 'approval_result']
        assert sent[-1]['work']['cancelled'] and sent[-1]['work']['details']['title'] == 'Exact review'
        assert events.hub_for().calendar_dirty
    asyncio.run(scenario())


def test_text_confirmation_does_not_claim_pending_meet_ready_or_cancelled_event_saved():
    from koe.text_agent import approval_text
    text = approval_text({'status': 'executed', 'title': 'Review', 'conference': {'status': 'pending', 'url': None}})
    assert 'pending' in text.lower() and 'saved' in text.lower()
    text = approval_text({'status': 'executed', 'title': 'Review', 'scope': 'series', 'cancelled': True})
    assert 'series' in text and 'cancel' in text.lower() and 'saved' not in text.lower()


def test_provider_dropping_recurrence_cannot_be_reported_as_verified(monkeypatch):
    calls = []
    async def request(method, path, **kwargs):
        calls.append(method)
        if method == 'GET': return {'items': []}
        return {'id': 'new', **{k: v for k, v in kwargs['json'].items() if k != 'recurrence'}}
    monkeypatch.setattr(calendar, 'request', request)
    result = asyncio.run(calendar.calendar_upsert_event(**ARGS, recurrence={'frequency': 'daily', 'count': 3}))
    assert result['error']['code'] == 'calendar_unverified' and calls.count('POST') == 1


def test_move_to_all_day_clears_old_timed_fields(api):
    result = asyncio.run(calendar.calendar_upsert_event('Review', '2026-10-15', '2026-10-16', all_day=True, event_id='moving'))
    assert 'error' not in result
    for key in ('start', 'end'):
        assert api[0][-1][2]['json'][key]['dateTime'] is None


@pytest.mark.parametrize('event', [{'start': {}, 'end': {}}, {'attendees': None},
    {'start': {'dateTime': ARGS['end']}, 'end': {'dateTime': ARGS['start']}}])
def test_malformed_conflict_evidence_fails_closed(monkeypatch, event):
    calls = []
    async def request(method, *args, **kwargs):
        calls.append(method)
        return {'items': [event]}
    monkeypatch.setattr(calendar, 'request', request)
    result = asyncio.run(calendar.calendar_upsert_event(**ARGS))
    assert result['error']['code'] == 'calendar_evidence' and calls == ['GET']


def test_timeout_after_insert_is_uncertain_and_never_replayed(fake_store, monkeypatch):
    from koe import agent
    writes = []
    async def request(method, *args, **kwargs):
        if method == 'GET': return {'items': []}
        writes.append(kwargs['json'])
        await asyncio.sleep(1)
    monkeypatch.setattr(calendar, 'request', request)
    monkeypatch.setattr(calendar, 'OPERATION_SECONDS', .02)
    monkeypatch.setitem(agent.TOOLS, 'calendar_upsert_event', agent.TOOLS['calendar_upsert_event']._replace(fn=calendar.calendar_upsert_event))
    async def scenario():
        ctx = agent.Conversation('app')
        await agent.run_tool('calendar_upsert_event', ARGS, context=ctx)
        ctx.approval_ready = True
        result = await agent.confirm(ctx, True)
        assert result['status'] == 'failed' and result['error']['code'] == 'calendar_timeout'
        assert 'error' in await agent.confirm(ctx, True)
        assert len(writes) == 1
    asyncio.run(scenario())


def test_oversized_scan_and_stream_never_allow_booking(monkeypatch):
    import httpx
    import respx
    from types import SimpleNamespace
    real_request = calendar.request
    async def request(*args, **kwargs): return {'items': [{}] * 1001}
    monkeypatch.setattr(calendar, 'request', request)
    assert asyncio.run(calendar.calendar_upsert_event(**ARGS))['error']['code'] == 'calendar_too_large'
    monkeypatch.setattr(calendar.google_auth, 'credentials', lambda: SimpleNamespace(token='fake'))
    monkeypatch.setattr(calendar, 'MAX_RESPONSE_BYTES', 100)
    with respx.mock as router:
        router.get(calendar.API + '/events').mock(return_value=httpx.Response(200, text='x' * 101))
        with pytest.raises(calendar.CalendarError) as exc:
            asyncio.run(real_request('GET', '/events'))
        assert exc.value.result['error']['code'] == 'calendar_too_large'


def test_series_scope_is_never_inferred_from_an_instance(fake_store, cancel_api):
    from koe import agent
    event, calls = cancel_api
    event['recurringEventId'] = 'parent'
    result = asyncio.run(agent.run_tool('calendar_cancel_event', {'event_id': 'event', 'expected_etag': '"v1"', 'scope': 'series'}, context=agent.Conversation('app')))
    assert result['error']['code'] == 'calendar_scope'
    assert len(calls) == 1 and calls[0][1].endswith('/event')


def test_individual_move_freezes_proposal_time_etag(fake_store, cancel_api, monkeypatch):
    from koe import agent
    event, calls = cancel_api
    monkeypatch.setitem(agent.TOOLS, 'calendar_upsert_event', agent.TOOLS['calendar_upsert_event']._replace(fn=calendar.calendar_upsert_event))
    async def scenario():
        ctx = agent.Conversation('app')
        proposal = await agent.run_tool('calendar_upsert_event', {**ARGS, 'event_id': 'event'}, context=ctx)
        assert 'Exact review' in proposal['pending_action']['summary']
        event['etag'] = '"v2"'
        ctx.approval_ready = True
        result = await agent.confirm(ctx, True)
        assert result['error']['code'] == 'calendar_changed'
        assert not any(c[0] in ('POST', 'PATCH') for c in calls)
    asyncio.run(scenario())


@pytest.mark.parametrize('code', ['calendar_unreachable', 'calendar_changed'])
def test_cancellation_uncertain_or_precondition_failure_never_replays(fake_store, cancel_api, monkeypatch, code):
    from koe import agent
    original = calendar.request
    deletes = []
    async def request(method, *args, **kwargs):
        if method == 'DELETE':
            deletes.append(True)
            raise calendar.CalendarError(code, 'Inspect Calendar before retrying.')
        return await original(method, *args, **kwargs)
    monkeypatch.setattr(calendar, 'request', request)
    async def scenario():
        ctx = agent.Conversation('app')
        await agent.run_tool('calendar_cancel_event', {'event_id': 'event', 'expected_etag': '"v1"', 'scope': 'single'}, context=ctx)
        ctx.approval_ready = True
        result = await agent.confirm(ctx, True)
        assert result['status'] == 'failed' and result['error']['code'] == code
        assert 'error' in await agent.confirm(ctx, True)
        assert len(deletes) == 1
    asyncio.run(scenario())


def test_calendar_projection_is_compatible_with_old_start_strings_and_excludes_internal_data():
    from koe import call_work
    work = call_work.project('calendar_cancel_event', {'event_id': 'event', 'scope': 'single',
        'expected_calendar': 'private', 'approved_event': {'title': 'Review', 'start': {'date': '2026-10-15'},
        'end': {'date': '2026-10-16'}, 'all_day': True, 'token': 'private'}},
        {'id': 'event', 'cancelled': True, 'start': {'date': '2026-10-15'}, 'end': {'date': '2026-10-16'}, 'all_day': True})
    assert work['details']['start'] == '2026-10-15' and work['date'] == '2026-10-15'
    assert work['event']['start'] == {'date': '2026-10-15'}
    assert 'private' not in str(work)


def test_sdk_accepts_all_calendar_tool_contracts():
    from google.genai import types
    from koe import agent
    declarations = [types.FunctionDeclaration.model_validate(d) for d in agent.declarations()]
    assert len(declarations) == 23
    assert all(d.model_dump_json() for d in declarations)
