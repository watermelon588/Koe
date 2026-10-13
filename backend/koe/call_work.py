"""Bounded display projections of Calendar/Sheets/Notion work for the call and the app chat's live workspace
(SPEC §2 "Live workspace"). Never send raw tool args, tokens or credentials: only these whitelisted fields."""
import re
from urllib.parse import urlparse

from koe.config import settings

TOOLS = {'calendar_list': 'calendar', 'calendar_find_free': 'calendar',
         'calendar_upsert_event': 'calendar', 'sheets_log_hours': 'sheets',
         'notion_save': 'notion', 'notion_archive': 'notion', 'notion_log': 'notion'}
HOSTS = {'calendar': {'calendar.google.com', 'www.google.com'}, 'sheets': {'docs.google.com'},
         'notion': {'notion.so', 'www.notion.so', 'app.notion.com'}}


def fields(data, names):
    return {name: value[:2000] if isinstance(value, str) else value
            for name in names if isinstance((value := data.get(name)), (str, int, float))}


def link(value, service):
    try:
        url = urlparse(value)
        if url.scheme == 'https' and url.hostname in HOSTS[service] and not url.username and not url.password:
            return value
    except (TypeError, ValueError):
        pass
    return ''


def project(name, args, result=None, action_id=None):
    service = TOOLS.get(name)
    if not service:
        return None
    args, result = args or {}, result or {}
    details = fields(args, {'calendar': ('date', 'title', 'start', 'end', 'event_id', 'duration_min', 'between'),
                            'sheets': ('date', 'client', 'hours', 'note', 'sheet_name'),
                            'notion': ('date', 'title', 'kind', 'status', 'end', 'body', 'page_id')}[service])
    if isinstance(args.get('attendees'), list):
        details['attendees'] = [v[:254] for v in args['attendees'][:50] if isinstance(v, str)]
    data = {'service': service, 'operation': name, 'details': details, 'timezone': settings.timezone}
    if action_id:
        data['action_id'] = action_id
    if isinstance(result.get('error'), dict):
        data['error'] = fields(result['error'], ('code', 'message', 'hint'))
    data.update(fields(result, ('date', 'timezone', 'duration_min', 'title', 'start', 'end', 'row', 'range', 'status')))
    if service == 'notion':
        if isinstance(args.get('entries'), list):  # notion_log: the exact bullets appended to the daily page
            details['entries'] = [v[:2000] for v in args['entries'][:50] if isinstance(v, str)]
        data.update(fields(result, ('kind', 'record_status', 'added', 'message')))
        if isinstance(result.get('id') or result.get('page_id'), str):
            data['page_id'] = result.get('id') or result.get('page_id')
        if isinstance(result.get('date'), dict):  # a saved record's Date property {start, end}
            data['date'] = fields(result['date'], ('start', 'end')).get('start', '')
        data['url'] = link(result.get('url'), service)
    elif service == 'sheets':
        sheet = args.get('spreadsheet_id', settings.google_sheets_id)
        details.setdefault('sheet_name', settings.google_sheets_tab)
        data['url'] = f'https://docs.google.com/spreadsheets/d/{sheet}/edit' if isinstance(sheet, str) and re.fullmatch(r'[A-Za-z0-9_-]+', sheet) else ''
    else:
        data['url'] = link(result.get('url'), service)
        for key in ('events', 'slots'):
            if not isinstance(result.get(key), list):
                continue
            rows = []
            for row in result[key][:100]:
                if not isinstance(row, dict):
                    continue
                entry = fields(row, ('id', 'title', 'start', 'end'))
                for when in ('start', 'end'):
                    if isinstance(row.get(when), dict):
                        entry[when] = fields(row[when], ('date', 'dateTime', 'timeZone'))
                if key == 'events':
                    entry['url'] = link(row.get('url'), service)
                rows.append(entry)
            data[key], data['total'], data['truncated'] = rows, len(result[key]), len(result[key]) > 100
    return data
