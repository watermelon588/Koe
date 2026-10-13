import asyncio
import os

os.environ.setdefault("GEMINI_API_KEY", "test")

import pytest

from koe.tools import calendar


@pytest.fixture
def api(monkeypatch):
    calls = []
    events = []

    async def request(method, path, **kwargs):
        calls.append((method, path, kwargs))
        if method == "GET" and path.endswith("/events"):
            return {"items": events}
        if method == "GET":
            return {"id": "moving", "etag": '"v1"', "summary": "Old", "recurrence": [],
                    "start": {"dateTime": "2026-10-12T15:00:00+05:30"},
                    "end": {"dateTime": "2026-10-12T16:00:00+05:30"}}
        return {"id": "new", "htmlLink": "https://calendar.google.com/event"}

    monkeypatch.setattr(calendar, "request", request)
    return calls, events


def test_day_boundaries_and_free_slots_use_kolkata_and_ignore_cancelled_events(api):
    calls, events = api
    events.extend([
        {"start": {"dateTime": "2026-10-12T10:00:00+05:30"}, "end": {"dateTime": "2026-10-12T11:00:00+05:30"}},
        {"status": "cancelled", "start": {"date": "2026-10-12"}, "end": {"date": "2026-10-13"}},
    ])
    result = asyncio.run(calendar.calendar_find_free("2026-10-12", 60, "09:00-12:00"))
    assert [(s["start"], s["end"]) for s in result["slots"]] == [
        ("2026-10-12T09:00:00+05:30", "2026-10-12T10:00:00+05:30"),
        ("2026-10-12T11:00:00+05:30", "2026-10-12T12:00:00+05:30")]
    assert calls[0][2]["params"]["timeMin"] == "2026-10-12T00:00:00+05:30"


def test_all_day_event_blocks_entire_day(api):
    api[1].append({"start": {"date": "2026-10-12"}, "end": {"date": "2026-10-13"}})
    assert asyncio.run(calendar.calendar_find_free("2026-10-12", 30))["slots"] == []


@pytest.mark.parametrize("start,end", [
    ("2026-10-12T19:00:00", "2026-10-12T19:30:00"),
    ("2026-10-12T19:00:00+05:30", "2026-10-12T18:30:00+05:30"),
])
def test_invalid_or_offsetless_times_never_reach_google(api, start, end):
    result = asyncio.run(calendar.calendar_upsert_event("Call", start, end))
    assert result["error"]["code"] == "bad_args"
    assert not api[0]


def test_conflict_recheck_prevents_insert(api):
    api[1].append({"start": {"dateTime": "2026-10-12T19:15:00+05:30"},
                   "end": {"dateTime": "2026-10-12T20:00:00+05:30"}})
    result = asyncio.run(calendar.calendar_upsert_event(
        "Call", "2026-10-12T19:00:00+05:30", "2026-10-12T19:30:00+05:30"))
    assert result["error"]["code"] == "calendar_conflict"
    assert all(method == "GET" for method, _, _ in api[0])


def test_move_ignores_its_own_old_slot_and_uses_etag(api):
    api[1].append({"id": "moving", "start": {"dateTime": "2026-10-12T15:00:00+05:30"},
                   "end": {"dateTime": "2026-10-12T16:00:00+05:30"}})
    result = asyncio.run(calendar.calendar_upsert_event(
        "Moved", "2026-10-12T15:30:00+05:30", "2026-10-12T16:30:00+05:30", event_id="moving"))
    assert "error" not in result
    assert api[0][-1][0] == "PATCH"
    assert api[0][-1][2]["headers"] == {"If-Match": '"v1"'}


def test_create_uses_stable_id_and_only_valid_explicit_attendees(api):
    result = asyncio.run(calendar.calendar_upsert_event(
        "Call", "2026-10-12T19:00:00+05:30", "2026-10-12T19:30:00+05:30",
        attendees=["rahul@example.com"], request_id="01234567-89ab-cdef-0123-456789abcdef"))
    assert "error" not in result
    assert api[0][-1][2]["json"]["id"] == "koe0123456789abcdef0123456789abcdef"
    assert api[0][-1][2]["params"]["sendUpdates"] == "all"


def test_free_slots_clamp_to_working_hours_and_reject_bad_duration(api):
    result = asyncio.run(calendar.calendar_find_free("2026-10-12", 30, "07:00-10:00"))
    assert result["slots"][0]["start"].endswith("09:00:00+05:30")
    assert "error" in asyncio.run(calendar.calendar_find_free("2026-10-12", 0))


def test_other_offset_is_converted_to_kolkata_before_booking(api):
    result = asyncio.run(calendar.calendar_upsert_event(
        "Call", "2026-10-12T13:30:00Z", "2026-10-12T14:00:00Z"))
    assert result["start"] == "2026-10-12T19:00:00+05:30"
    assert result["end"] == "2026-10-12T19:30:00+05:30"


def test_conflict_on_second_page_is_not_missed(monkeypatch):
    calls = []
    async def request(method, path, **kwargs):
        calls.append((method, kwargs))
        if "pageToken" not in kwargs["params"]:
            return {"items": [], "nextPageToken": "page2"}
        return {"items": [{"start": {"dateTime": "2026-10-12T19:00:00+05:30"},
                            "end": {"dateTime": "2026-10-12T20:00:00+05:30"}}]}
    monkeypatch.setattr(calendar, "request", request)
    result = asyncio.run(calendar.calendar_upsert_event(
        "Call", "2026-10-12T19:30:00+05:30", "2026-10-12T20:00:00+05:30"))
    assert result["error"]["code"] == "calendar_conflict"
    assert len(calls) == 2 and all(method == "GET" for method, _ in calls)


def test_event_details_and_reminders_are_validated_and_sent_exactly(api):
    from koe import agent
    args = {'title': 'Call', 'start': '2026-10-14T19:00:00+05:30', 'end': '2026-10-14T19:30:00+05:30',
            'description': 'Review release', 'location': 'Library',
            'reminders': [{'method': 'popup', 'minutes': 15}, {'method': 'email', 'minutes': 60}]}
    normalized, preview = agent.prepare_write('calendar_upsert_event', args)
    assert 'Review release' in preview and 'Library' in preview and '15' in preview and 'email' in preview
    result = asyncio.run(calendar.calendar_upsert_event(**normalized))
    assert 'error' not in result
    body = api[0][-1][2]['json']
    assert body['reminders'] == {'useDefault': False, 'overrides': args['reminders']}
    assert body['description'] == args['description'] and body['location'] == 'Library'


@pytest.mark.parametrize('reminders', [[{'method': 'sms', 'minutes': 10}], [{'method': 'popup', 'minutes': True}],
    [{'method': 'popup', 'minutes': -1}], [{'method': 'popup', 'minutes': 40321}],
    [{'method': 'popup', 'minutes': 10, 'unexpected': 'value'}], [{'method': 'popup', 'minutes': 10}] * 6])
def test_invalid_reminders_never_reach_google(api, reminders):
    result = asyncio.run(calendar.calendar_upsert_event('Call', '2026-10-14T19:00:00+05:30',
        '2026-10-14T19:30:00+05:30', reminders=reminders))
    assert result['error']['code'] == 'bad_args' and not api[0]


def test_omitted_details_preserved_and_explicit_clearing_supported(api):
    args = ('Call', '2026-10-14T19:00:00+05:30', '2026-10-14T19:30:00+05:30')
    asyncio.run(calendar.calendar_upsert_event(*args, event_id='moving'))
    body = api[0][-1][2]['json']
    assert all(k not in body for k in ('reminders', 'description', 'location'))
    asyncio.run(calendar.calendar_upsert_event(*args, description='', location='', reminders=[]))
    body = api[0][-1][2]['json']
    assert body['description'] == body['location'] == ''
    assert body['reminders'] == {'useDefault': False, 'overrides': []}
