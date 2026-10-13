"""Calendar tools. ISO offsets, working hours, pagination and a last-moment conflict check.

REST reference: https://developers.google.com/workspace/calendar/api/v3/reference/events
Events PATCH supports If-Match: https://developers.google.com/workspace/calendar/api/guides/version-resources
"""
import asyncio
import re
from datetime import date as Date, datetime, time, timedelta
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx

from koe import google_auth
from koe.config import settings

API = "https://www.googleapis.com/calendar/v3"
_write_lock = asyncio.Lock()  # also protects two different proposals in this one-process app


def error(code: str, message: str, hint: str = "Clarify the request and try again.") -> dict:
    return {"error": {"code": code, "message": message, "hint": hint}}


class CalendarError(Exception):
    def __init__(self, code, message):
        self.result = error(code, message)


async def request(method: str, path: str, **kwargs) -> dict:
    try:
        creds = await asyncio.to_thread(google_auth.credentials)
        headers = {"Authorization": f"Bearer {creds.token}", **kwargs.pop("headers", {})}
        async with httpx.AsyncClient(timeout=20, trust_env=False) as client:
            r = await client.request(method, API + path, headers=headers, **kwargs)
        if r.is_error:
            code = {401: "google_reauthorize", 403: "calendar_permission", 409: "calendar_duplicate",
                    412: "calendar_changed"}.get(r.status_code, "calendar_unavailable")
            raise CalendarError(code, f"Google Calendar returned HTTP {r.status_code}. No write was retried.")
        return r.json()
    except google_auth.GoogleAuthError as exc:
        raise CalendarError("google_not_connected", str(exc)) from None
    except httpx.HTTPError:
        raise CalendarError("calendar_unreachable", "Google did not answer. Check Calendar before retrying a write.") from None


def _path() -> str:
    return "/calendars/" + quote(settings.google_calendar_id, safe="") + "/events"


def _iso(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Times must be ISO-8601 strings with an explicit offset.")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if "T" not in value or dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("Times must be ISO-8601 with an explicit offset, e.g. 2026-10-12T19:00:00+05:30.")
    return dt.astimezone(ZoneInfo(settings.timezone))


def prepare_event(title: str, start: str, end: str, attendees: list[str] | None = None,
                  event_id: str | None = None, description: str | None = None,
                  location: str | None = None, reminders: list[dict] | None = None,
                  all_day: bool = False, recurrence: dict | None = None) -> dict:
    if not isinstance(title, str) or not title.strip() or len(title) > 200:
        raise ValueError("Provide a title of 1 to 200 characters.")
    if type(all_day) is not bool:
        raise ValueError('all_day must be true or false.')
    if all_day:
        if any(not isinstance(v, str) or Date.fromisoformat(v).isoformat() != v for v in (start, end)):
            raise ValueError('All-day events need YYYY-MM-DD dates and an exclusive end date.')
        start_dt, end_dt = _day(start)[0], _day(end)[0]
    else:
        start_dt, end_dt = _iso(start), _iso(end)
    if end_dt <= start_dt:
        raise ValueError("The end must be after the start.")
    if attendees is not None and (not isinstance(attendees, list) or len(attendees) > 50 or any(
        not isinstance(email, str) or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) for email in attendees)):
        raise ValueError("Attendees must be explicit email addresses; don't guess an address from a name.")
    if event_id is not None and (not isinstance(event_id, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,1024}", event_id)):
        raise ValueError("Invalid event_id.")
    for label, value, limit in [('description', description, 6000), ('location', location, 500)]:
        if value is not None and (not isinstance(value, str) or len(value) > limit):
            raise ValueError(f'{label} must be text of at most {limit} characters.')
    # https://developers.google.com/workspace/calendar/api/v3/reference/events/insert
    if reminders is not None:
        if not isinstance(reminders, list) or len(reminders) > 5 or any(
            not isinstance(r, dict) or set(r) != {'method', 'minutes'} or r['method'] not in ('popup', 'email')
            or type(r['minutes']) is not int or not 0 <= r['minutes'] <= 40320 for r in reminders):
            raise ValueError('Use at most five popup/email reminders with integer minutes from 0 to 40320.')
    result = {"title": title.strip(), "start": start if all_day else start_dt.isoformat(),
            "end": end if all_day else end_dt.isoformat(),
            "attendees": attendees, "event_id": event_id, 'description': description,
            'location': location, 'reminders': reminders, 'all_day': all_day, 'recurrence': recurrence}
    event_plan(result)  # Validate and bound the entire plan before any API access.
    return result


def event_plan(args):
    """A deliberately small recurrence language; never accept arbitrary RRULEs from the model."""
    all_day, recurrence = args.get('all_day', False), args.get('recurrence')
    start = _day(args['start'])[0] if all_day else _iso(args['start'])
    end = _day(args['end'])[0] if all_day else _iso(args['end'])
    if end <= start or end - start > timedelta(days=31):
        raise ValueError('Each event must end after it starts and span at most31 days.')
    count, step, rrule = 1, 0, None
    if recurrence is not None:
        if args.get('event_id'):
            raise ValueError('Recurrence is supported for new series only; existing series cannot be rewritten.')
        if not isinstance(recurrence, dict) or set(recurrence) - {'frequency', 'interval', 'count'}:
            raise ValueError('Use frequency, interval and count only; raw recurrence rules are not accepted.')
        frequency, count, interval = recurrence.get('frequency'), recurrence.get('count'), recurrence.get('interval', 1)
        if frequency not in ('daily', 'weekly') or type(count) is not int or not 2 <= count <= 20 or type(interval) is not int or not 1 <= interval <= 4:
            raise ValueError('Use daily/weekly, count2–20 and interval1–4.')
        step = interval * (7 if frequency == 'weekly' else 1)
        if end - start > timedelta(days=step):
            raise ValueError('Recurring occurrences must not overlap one another.')
        rrule = f'RRULE:FREQ={frequency.upper()};INTERVAL={interval};COUNT={count}'
    occurrences = []
    for i in range(count):
        a, b = start + timedelta(days=step * i), end + timedelta(days=step * i)
        if b - start > timedelta(days=90):
            raise ValueError('The entire event plan must end within90 days of its first start.')
        if recurrence and not all_day and (a.utcoffset() != start.utcoffset() or b.utcoffset() != end.utcoffset()):
            raise ValueError('Recurring windows across a UTC-offset transition are not supported in this phase.')
        occurrences.append({'start': a.date().isoformat() if all_day else a.isoformat(),
                            'end': b.date().isoformat() if all_day else b.isoformat()})
    return {'occurrences': occurrences, 'rrule': rrule}


async def _events(start: datetime, end: datetime) -> list[dict]:
    events, token = [], None
    for _ in range(100):
        params = {"timeMin": start.isoformat(), "timeMax": end.isoformat(), "singleEvents": "true",
                  "orderBy": "startTime", "maxResults": 2500, "timeZone": settings.timezone}
        if token:
            params["pageToken"] = token
        data = await request("GET", _path(), params=params)
        events.extend(data.get("items", []))
        token = data.get("nextPageToken")
        if not token:
            return events
    raise CalendarError("calendar_too_large", "Too many events; narrow the time range.")


def _interval(event: dict) -> tuple[datetime, datetime] | None:
    if event.get("status") == "cancelled" or event.get("transparency") == "transparent":
        return None
    if any(a.get("self") and a.get("responseStatus") == "declined" for a in event.get("attendees", [])):
        return None
    tz = ZoneInfo(settings.timezone)
    def when(part):
        if "dateTime" in part:
            return _iso(part["dateTime"])
        return datetime.combine(Date.fromisoformat(part["date"]), time.min, tz)
    return when(event["start"]), when(event["end"])


def _day(value: str):
    d, tz = Date.fromisoformat(value), ZoneInfo(settings.timezone)
    start = datetime.combine(d, time.min, tz)
    return start, datetime.combine(d + timedelta(days=1), time.min, tz)


async def calendar_list(date: str) -> dict:
    try:
        start, end = _day(date)
        events = await _events(start, end)
        return {"date": date, "timezone": settings.timezone, "events": [
            {"id": e["id"], "title": e.get("summary", "Untitled"), "start": e["start"],
             "end": e["end"], "url": e.get("htmlLink"), 'description': e.get('description', ''),
             'location': e.get('location', ''), 'reminders': e.get('reminders', {})}
            for e in events if e.get("status") != "cancelled"]}
    except CalendarError as exc:
        return exc.result
    except (ValueError, TypeError):
        return error("bad_args", "Use an ISO date, e.g. 2026-10-12.")


async def calendar_find_free(date: str, duration_min: int, between: str | None = None) -> dict:
    try:
        if type(duration_min) is not int or not 1 <= duration_min <= 1440:
            raise ValueError("duration_min must be an integer from 1 to 1440.")
        day_start, day_end = _day(date)
        low, high = time.fromisoformat(settings.working_hours_start), time.fromisoformat(settings.working_hours_end)
        if low >= high:
            raise ValueError("Working hours must start before they end.")
        if between:
            a, b = between.split("-")
            a, b = time.fromisoformat(a), time.fromisoformat(b)
            if a >= b:
                raise ValueError("between must start before it ends.")
            low, high = max(low, a), min(high, b)
        cursor, limit = day_start.replace(hour=low.hour, minute=low.minute), day_start.replace(hour=high.hour, minute=high.minute)
        intervals = sorted(i for e in await _events(day_start, day_end) if (i := _interval(e)))
        gaps = []
        for a, b in intervals:
            if b <= cursor or a >= limit:
                continue
            if a > cursor:
                gaps.append((cursor, min(a, limit)))
            cursor = max(cursor, b)
        if cursor < limit:
            gaps.append((cursor, limit))
        return {"date": date, "timezone": settings.timezone, "duration_min": duration_min, "slots": [
            {"start": a.isoformat(), "end": b.isoformat()} for a, b in gaps
            if (b-a).total_seconds() >= duration_min * 60]}
    except CalendarError as exc:
        return exc.result
    except (ValueError, TypeError) as exc:
        return error("bad_args", str(exc))


async def calendar_upsert_event(title: str, start: str, end: str, attendees: list[str] | None = None,
                                event_id: str | None = None, description: str | None = None,
                                location: str | None = None, reminders: list[dict] | None = None,
                                all_day: bool = False, recurrence: dict | None = None, *,
                                request_id: str | None = None) -> dict:
    """Only agent.resolve may invoke a write after claiming its stored approval."""
    try:
        args = prepare_event(title, start, end, attendees, event_id, description, location, reminders, all_day, recurrence)
        plan = event_plan(args)
        intervals = [(_day(p['start'])[0], _day(p['end'])[0]) if all_day else (_iso(p['start']), _iso(p['end']))
                     for p in plan['occurrences']]
        async with _write_lock:
            old = await request("GET", _path() + "/" + quote(event_id, safe="")) if event_id else None
            if old and (old.get("recurrence") or old.get("recurringEventId")):
                return error("recurring_event", "Moving recurring events isn't supported in v1.")
            # Paginated event overlap check can exclude the event being moved, unlike freeBusy.
            for event in await _events(intervals[0][0], intervals[-1][1]):
                if event_id and event.get("id") == event_id:
                    continue
                interval = _interval(event)
                if interval and any(interval[0] < b and interval[1] > a for a, b in intervals):
                    return error("calendar_conflict", "That slot is now busy. Nothing was booked.", "Find another slot and approve again.")
            body = {"summary": args["title"], "start": {"dateTime": args["start"], "timeZone": settings.timezone},
                    "end": {"dateTime": args["end"], "timeZone": settings.timezone}}
            if all_day:
                body.update(start={'date': args['start']}, end={'date': args['end']})
            if plan['rrule']:
                body['recurrence'] = [plan['rrule']]
            if attendees is not None:
                body["attendees"] = [{"email": e} for e in attendees]
            for field in ('description', 'location'):
                if args[field] is not None:
                    body[field] = args[field]
            if reminders is not None:
                body['reminders'] = {'useDefault': False, 'overrides': args['reminders']}
            params = {"sendUpdates": "all"}
            if old:
                if not old.get("etag"):
                    return error("calendar_changed", "The event has no version; it wasn't moved.")
                result = await request("PATCH", _path() + "/" + quote(event_id, safe=""), json=body,
                                       headers={"If-Match": old["etag"]}, params=params)
            else:
                if request_id:
                    body["id"] = "koe" + request_id.replace("-", "")
                result = await request("POST", _path(), json=body, params=params)
            return {"id": result["id"], "url": result.get("htmlLink"), "title": args["title"],
                    "start": args["start"], "end": args["end"], 'all_day': all_day,
                    'occurrences': plan['occurrences'], 'recurrence': plan['rrule']}
    except CalendarError as exc:
        return exc.result
    except (ValueError, TypeError) as exc:
        return error("bad_args", str(exc))
