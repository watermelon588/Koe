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
