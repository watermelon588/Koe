"""Bounded display projections of Calendar/Sheets/Notion work for the call and the app chat's live workspace
(SPEC §2 "Live workspace"). Never send raw tool args, tokens or credentials: only these whitelisted fields."""
import re
from urllib.parse import urlparse

from koe.config import settings
from koe.tools import sheets

TOOLS = {'docs_find': 'docs', 'docs_read': 'docs', 'docs_create': 'docs', 'docs_edit': 'docs', 'calendar_list': 'calendar', 'calendar_find_free': 'calendar',
         'calendar_upsert_event': 'calendar', 'calendar_get_event': 'calendar',
         'calendar_cancel_event': 'calendar', 'sheets_log_hours': 'sheets',
         'notion_save': 'notion', 'notion_archive': 'notion', 'notion_log': 'notion'}
HOSTS = {'docs': {'docs.google.com'}, 'calendar': {'calendar.google.com', 'www.google.com'}, 'sheets': {'docs.google.com'},
         'notion': {'notion.so', 'www.notion.so', 'app.notion.com'}, 'meet': {'meet.google.com'}}


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


def conference(data):
    if not isinstance(data, dict): return None
    status = data.get('status')
    if status not in ('none', 'pending', 'success', 'failure', 'unavailable'): return None
    return {'status': status, 'url': link(data.get('url'), 'meet') if status == 'success' else ''}


def calendar_row(row):
    entry = fields(row, ('id', 'title', 'etag', 'all_day', 'recurring_event_id', 'event_type', 'attendees_omitted'))
    for when in ('start', 'end', 'original_start'):
        if isinstance(row.get(when), dict):
            entry[when] = fields(row[when], ('date', 'dateTime', 'timeZone'))
        elif isinstance(row.get(when), str):
            entry[when] = row[when][:100]
    entry['url'] = link(row.get('url'), 'calendar')
    if isinstance(row.get('attendees'), list):
        entry['attendees'] = [v[:254] for v in row['attendees'][:50] if isinstance(v, str)]
    if isinstance(row.get('recurrence'), list):
        entry['recurrence'] = [v[:500] for v in row['recurrence'][:20] if isinstance(v, str)]
    if (meeting := conference(row.get('conference'))) is not None: entry['conference'] = meeting
    return entry


def project(name, args, result=None, action_id=None):
    service = TOOLS.get(name)
    if not service:
        return None
    args, result = args or {}, result or {}
    source = {**args, **args.get('approved_event', {})} if name == 'calendar_cancel_event' and isinstance(args.get('approved_event'), dict) else args
    details = fields(source, {'calendar': ('date', 'title', 'start', 'end', 'event_id', 'duration_min', 'between', 'scope', 'all_day',
                                           'create_meet', 'description', 'location'),
                              'sheets': ('date', 'client', 'hours', 'note', 'sheet_name'),
                              'docs': ('title', 'body', 'old_text', 'mode', 'document', 'tab_id', 'tab_title'),
                              'notion': ('date', 'title', 'kind', 'status', 'end', 'body', 'page_id')}[service])
    if isinstance(source.get('attendees'), list):
        details['attendees'] = [v[:254] for v in source['attendees'][:50] if isinstance(v, str)]
    if service == 'calendar':
        for when in ('start', 'end'):
            if isinstance(source.get(when), dict):
                part = source[when]
                value = part.get('dateTime') or part.get('date')
                if isinstance(value, str): details[when] = value[:100]
        if isinstance(args.get('recurrence'), dict): details['recurrence'] = fields(args['recurrence'], ('frequency', 'interval', 'count'))
        if isinstance(args.get('reminders'), list): details['reminders'] = [fields(r, ('method', 'minutes')) for r in args['reminders'][:5] if isinstance(r, dict)]
    data = {'service': service, 'operation': name, 'details': details, 'timezone': settings.timezone}
    if action_id:
        data['action_id'] = action_id
    if isinstance(result.get('error'), dict):
        data['error'] = fields(result['error'], ('code', 'message', 'hint'))
    data.update(fields(result, ('date', 'timezone', 'duration_min', 'title', 'start', 'end', 'row', 'range', 'status')))
    if service == 'docs':
        for key in ('body', 'old_text'):
            if isinstance(args.get(key), str): details[key] = args[key][:12000]
        data.update(fields(result, ('document_id', 'revision_id', 'message', 'truncated', 'scope', 'partial', 'has_suggestions', 'next_page_token')))
        data['url'] = link(result.get('url'), service)
        if isinstance(result.get('tabs'), list):
            data['tabs'] = [fields(t, ('tab_id', 'title', 'text', 'truncated')) for t in result['tabs'][:100]]
            for shown, raw in zip(data['tabs'], result['tabs']):
                shown['truncated'] = bool(shown.get('truncated')) or len(raw.get('text', '')) > 2000
        if isinstance(result.get('documents'), list):
            data['documents'] = [{**fields(d, ('document_id', 'title', 'modified')), 'url': link(d.get('url'), 'docs')} for d in result['documents'][:20]]
    elif service == 'notion':
        if isinstance(args.get('entries'), list):  # notion_log: the exact bullets appended to the daily page
            details['entries'] = [v[:2000] for v in args['entries'][:50] if isinstance(v, str)]
        data.update(fields(result, ('kind', 'record_status', 'added', 'message')))
        if isinstance(result.get('id') or result.get('page_id'), str):
            data['page_id'] = result.get('id') or result.get('page_id')
        if isinstance(result.get('date'), dict):  # a saved record's Date property {start, end}
            data['date'] = fields(result['date'], ('start', 'end')).get('start', '')
        data['url'] = link(result.get('url'), service)
    elif service == 'sheets':
        sheet = args.get('spreadsheet_id') or sheets.timesheet_id()  # the caller's own sheet, never the owner's for a friend
        details.setdefault('sheet_name', settings.google_sheets_tab)
        data['url'] = f'https://docs.google.com/spreadsheets/d/{sheet}/edit' if isinstance(sheet, str) and re.fullmatch(r'[A-Za-z0-9_-]+', sheet) else ''
    else:
        data['url'] = link(result.get('url'), service)
        data.update(fields(result, ('cancelled', 'scope', 'all_day', 'id', 'etag', 'recurrence', 'verified')))
        if (meeting := conference(result.get('conference'))) is not None: data['conference'] = meeting
        if isinstance(result.get('occurrences'), list):
            data['occurrences'] = [fields(p, ('start', 'end')) for p in result['occurrences'][:20] if isinstance(p, dict)]
        if name in ('calendar_get_event', 'calendar_cancel_event') and result.get('id'):
            data['event'] = calendar_row(result)
            part = result.get('start')
            if isinstance(part, dict):
                value = part.get('dateTime') or part.get('date')
                if isinstance(value, str): data['date'] = value[:10]
        for key in ('events', 'slots'):
            if not isinstance(result.get(key), list):
                continue
            rows = []
            for row in result[key][:100]:
                if not isinstance(row, dict):
                    continue
                entry = calendar_row(row) if key == 'events' else fields(row, ('start', 'end'))
                rows.append(entry)
            data[key], data['total'], data['truncated'] = rows, len(result[key]), len(result[key]) > 100
    return data
