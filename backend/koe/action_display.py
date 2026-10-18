"""Display-only approvals. Raw summaries remain the authoritative audit; no execution args leave here."""
import re
from datetime import date, datetime, timedelta
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from koe.config import settings

HOSTS = {'calendar.google.com', 'www.google.com', 'docs.google.com', 'github.com',
         'notion.so', 'www.notion.so', 'app.notion.com'}


def text(value, limit=320):
    if value is None: return 'Empty'
    if isinstance(value, bool): return 'Yes' if value else 'No'
    if not isinstance(value, (str, int, float)): return 'See Details'
    value = ' '.join(str(value).split())
    return value if len(value) <= limit else value[:limit - 1] + '…'


def safe_link(value):
    if not isinstance(value, str) or len(value) > 2048 or any(c.isspace() for c in value): return ''
    try:
        url = urlparse(value)
        if url.scheme == 'https' and url.hostname in HOSTS and not url.username and not url.password and url.port in (None, 443):
            return value
    except ValueError:
        pass
    return ''


def day(value):
    try: return date.fromisoformat(value).strftime('%d %b %Y').lstrip('0')
    except (TypeError, ValueError): return text(value)


def when(args):
    start, end = args.get('start'), args.get('end')
    if isinstance(start, dict): start = start.get('dateTime') or start.get('date')
    if isinstance(end, dict): end = end.get('dateTime') or end.get('date')
    if not start: return 'Time: see Details'
    try:
        if args.get('all_day') or len(start) == 10:
            final = (date.fromisoformat(end) - timedelta(days=1)).isoformat()
            return f"{day(start)}{('–' + day(final)) if final != start else ''} · All day"
        tz = args.get('expected_timezone') or settings.timezone
        first, last = (datetime.fromisoformat(v.replace('Z', '+00:00')).astimezone(ZoneInfo(tz)) for v in (start, end))
        end_day = (last.strftime('%d %b %Y').lstrip('0') + ' · ') if first.date() != last.date() else ''
        return f"{day(first.date().isoformat())} · {first:%H:%M}–{end_day}{last:%H:%M} · {tz}"
    except (TypeError, ValueError, KeyError, AttributeError):
        return 'Time: see Details'


def describe(tool, args):
    args = args if isinstance(args, dict) else {}
    title, lines, url = 'Review proposed change', [], ''
    if tool in ('calendar_upsert_event', 'calendar_cancel_event'):
        source = args.get('approved_event') or args
        title = f"{'Cancel' if tool == 'calendar_cancel_event' else 'Move' if args.get('event_id') else 'Create'} {text(source.get('title', 'calendar event'), 140)}"
        lines = [when({**source, 'expected_timezone': args.get('expected_timezone')})]
        if tool == 'calendar_cancel_event':
            lines.append('Cancel ' + {'single': 'this event', 'instance': 'this occurrence', 'series': 'the whole series'}.get(args.get('scope'), 'scope in Details'))
        recurrence = args.get('recurrence')
        if isinstance(recurrence, dict):
            interval = recurrence.get('interval', 1)
            unit = 'week' if recurrence.get('frequency') == 'weekly' else 'day'
            lines.append(f"Every {unit if interval == 1 else str(interval) + ' ' + unit + 's'} · {recurrence.get('count')} times")
        guests = source.get('attendees')
        if isinstance(guests, list) and guests:
            lines.append('Guests: ' + ', '.join(text(v) for v in guests))
        else:
            lines.append('Existing guests kept' if args.get('event_id') and guests is None else 'No guests')
        if args.get('create_meet'): lines.append('Request a Google Meet · link available after Google confirms')
        else: lines.append('Guest notifications requested · Calendar: ' + text(args.get('expected_calendar', 'primary')))
        url = safe_link(source.get('url'))
    elif tool in ('docs_create', 'docs_edit'):
        title = ('Create ' if tool == 'docs_create' else 'Edit ') + text(args.get('title', 'Google Doc'), 140)
        lines = ['Google Docs' + (' · Tab: ' + text(args['tab_title']) if args.get('tab_title') else ''),
                 text(args.get('body', '(empty document)')), 'Exact text and destination in Details']
        identifier = args.get('document', '')
        if isinstance(identifier, str) and re.fullmatch(r'[A-Za-z0-9_-]+', identifier):
            url = f'https://docs.google.com/document/d/{identifier}/edit'
    elif tool.startswith('sheets_'):
        tab = text(args.get('sheet_name', settings.google_sheets_tab))
        if tool == 'sheets_add_columns':
            columns = args.get('columns') or []
            title = 'Add column ' + text(columns[0], 140) if len(columns) == 1 else f'Add {len(columns)} columns'
            lines = ['Columns: ' + ', '.join(text(v) for v in columns), 'Tab: ' + tab,
                     'Existing data retained · no row values filled']
        elif tool == 'sheets_update_row':
            title = 'Update timesheet row'
            lines = ['Tab: ' + tab, 'Changes: ' + ' · '.join(f'{text(k)}: {text(v)}' for k, v in (args.get('changes') or {}).items()),
                     'Only the reviewed cells change · see Details for before and after']
        else:
            title = f"Log {text(args.get('hours', ''))} hours · {text(args.get('client', ''), 120)}"
            lines = [day(args.get('date')) + ' · Tab: ' + tab]
            if args.get('note'): lines.append('Note: ' + text(args['note']))
            if args.get('fields'): lines.append('Optional values: see Details')
        sheet = args.get('spreadsheet_id', '')
        if isinstance(sheet, str) and re.fullmatch(r'[A-Za-z0-9_-]+', sheet):
            url = f'https://docs.google.com/spreadsheets/d/{sheet}/edit'
    elif tool == 'github_comment':
        repo, number = args.get('repo', ''), args.get('number', '')
        title = f'Comment on {text(repo, 100)} #{text(number)}'
        lines = [text(args.get('body', '')), 'Full comment in Details']
        if isinstance(repo, str) and re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo) and isinstance(number, int) and number > 0:
            url = f'https://github.com/{repo}/pull/{number}'
    elif tool.startswith('notion_'):
        if tool == 'notion_add_properties':
            title = 'Add Notion properties'
            lines = [f"{text(p.get('name'))} · {text(p.get('type')).replace('_', ' ')}" for p in args.get('properties', [])[:3]]
            lines.append('Existing properties retained · definitions and options in Details')
        else:
            title = f"{'Trash' if tool == 'notion_archive' else 'Update' if args.get('page_id') else 'Create'} {text(args.get('title', 'Notion record'), 140)}"
            if args.get('kind'): lines.append(text(args['kind']) + (' · ' + text(args['status']) if args.get('status') else ''))
            if args.get('date'): lines.append(day(args['date']) + ('–' + day(args['end']) if args.get('end') else ''))
            if args.get('body'): lines.append(text(args['body']))
            lines.append('Meeting record only · no Calendar booking' if args.get('kind') == 'Meeting' else 'Complete change in Details')
        identifier = args.get('page_id') or args.get('destination', '')
        if isinstance(identifier, str) and re.fullmatch(r'[0-9a-fA-F-]{32,36}', identifier): url = 'https://www.notion.so/' + identifier.replace('-', '')
    return {'title': text(title, 160), 'lines': [text(v) for v in lines[:4]], 'url': url}


def pending(action):
    if not action: return None
    return {**{k: action[k] for k in ('id', 'summary', 'expires_ts')},
            'display': describe(action.get('tool', ''), action.get('args_json'))}
