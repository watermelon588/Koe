"""Approved hours only. RAW avoids formula interpretation of user-controlled text.
https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values/append
"""
import asyncio
import math
import re
from datetime import date as iso_date
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

import httpx

from koe import connections, google_auth, identity
from koe.config import settings
from koe.tools.github import _error

HEADERS = ['Date', 'Client', 'Hours', 'Note', 'Koe action ID']


def timesheet_id() -> str:
    """The caller's own timesheet (Settings → Connections); the owner may still use GOOGLE_SHEETS_ID from .env."""
    mine = connections.pref('google_sheets_id')
    return mine or (settings.google_sheets_id if identity.is_owner() else '')


def optional_fields(fields):
    if fields is None:
        return {}
    if not isinstance(fields, dict) or len(fields) > 20:
        raise ValueError('Use at most 20 optional named columns.')
    for key, value in fields.items():
        if not isinstance(key, str) or not 1 <= len(key) <= 100 or key.casefold() in {h.casefold() for h in HEADERS}:
            raise ValueError('Optional fields cannot replace required columns or the Koe action ID.')
        if type(value) not in (str, int, float, bool) or (isinstance(value, str) and len(value) > 1000):
            raise ValueError('Optional column values must be text (up to 1000 characters), numbers or booleans.')
        if type(value) in (int, float) and (abs(value) > 1e15 or not math.isfinite(value)):
            raise ValueError('Optional numbers must be finite and at most 1e15 in magnitude.')
    return dict(fields)


def prepare_hours(date: str, client: str, hours: float, note: str = '', fields: dict | None = None) -> dict:
    if not isinstance(date, str) or iso_date.fromisoformat(date).isoformat() != date:
        raise ValueError('Use a date in YYYY-MM-DD format.')
    if not isinstance(client, str) or not 1 <= len(client.strip()) <= 120:
        raise ValueError('Specify a client name of 1–120 characters.')
    if not isinstance(note, str) or len(note) > 1000:
        raise ValueError('Note must contain at most 1,000 characters.')
    try:
        value = Decimal(str(hours))
        if isinstance(hours, bool) or not value.is_finite() or not 0 < value <= 24 or value != value.quantize(Decimal('.01')):
            raise ValueError('Hours must be positive, at most 24, with at most two decimal places.')
    except InvalidOperation:
        raise ValueError('Hours must be a finite number.') from None
    sheet = timesheet_id()
    tab = settings.google_sheets_tab
    if not re.fullmatch(r'[A-Za-z0-9_-]+', sheet) or not tab.strip() or len(tab) > 100:
        raise ValueError('No timesheet yet: Settings → Connections → Create my timesheet.')
    return {'date': date, 'client': client.strip(), 'hours': float(value), 'note': note,
            'spreadsheet_id': sheet, 'sheet_name': tab, 'fields': optional_fields(fields)}


def validate_headers(data):
    if not isinstance(data, dict):
        raise ValueError('Sheets did not return a header object.')
    values = data.get('values')
    if not isinstance(values, list) or len(values) != 1 or not isinstance(values[0], list):
        raise ValueError('Sheets did not return a complete header row.')
    headers = values[0]
    if headers[:5] != HEADERS or len(headers) > 52 or any(not isinstance(h, str) or not h.strip() or len(h) > 100 for h in headers):
        raise ValueError('Timesheet first five columns must be: ' + ', '.join(HEADERS) + '; optional headers must be nonempty.')
    if len({h.casefold() for h in headers}) != len(headers):
        raise ValueError('Timesheet headers must be unique, including letter case.')
    return headers


async def read_headers(spreadsheet_id, sheet_name):
    try:
        creds = await asyncio.to_thread(google_auth.credentials, required_scopes=[google_auth.SHEETS_SCOPE])
        tab = "'" + sheet_name.replace("'", "''") + "'"
        url = f'https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/' + quote(tab + '!A1:AZ1', safe='')
        async with httpx.AsyncClient(timeout=15) as api:
            r = await api.get(url, headers={'Authorization': f'Bearer {creds.token}'})
            r.raise_for_status()
            return validate_headers(r.json())
    except (httpx.HTTPError, google_auth.GoogleAuthError):
        raise ValueError('Timesheet headers could not be read. Nothing was appended.') from None


async def freeze_fields(args):
    headers = await read_headers(args['spreadsheet_id'], args['sheet_name'])
    if set(args['fields']) - set(headers[5:]):
        raise ValueError('An optional field is not an existing column. Read sheets_schema; add columns separately in Sheets.')
    return {**args, 'expected_headers': headers}


async def sheets_schema():
    try:
        # Reuse destination validation without creating a proposal or writing a row.
        args = prepare_hours('2000-01-01', 'schema read', 1)
        headers = await read_headers(args['spreadsheet_id'], args['sheet_name'])
        return {'spreadsheet_id': args['spreadsheet_id'], 'sheet_name': args['sheet_name'],
                'required_headers': HEADERS, 'optional_headers': headers[5:],
                'note': 'Existing optional columns only, scalar values written as RAW. Headers define names, not data types. No columns are created.'}
    except (ValueError, TypeError):
        return _error('sheets_schema', 'The configured timesheet headers could not be validated.', 'Check the connected sheet and its unique headers.')


async def sheets_log_hours(date: str, client: str, hours: float, note: str = '', *,
                           spreadsheet_id: str, sheet_name: str, request_id: str,
                           fields: dict | None = None, expected_headers: list | None = None) -> dict:
    try:
        args = prepare_hours(date, client, hours, note, fields)
        if (spreadsheet_id, sheet_name) != (args['spreadsheet_id'], args['sheet_name']):
            raise ValueError('The timesheet destination changed; propose the entry again.')
        creds = await asyncio.to_thread(google_auth.credentials, required_scopes=[google_auth.SHEETS_SCOPE])
        root = f'https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/'
        tab = "'" + sheet_name.replace("'", "''") + "'"
        async with httpx.AsyncClient(timeout=15) as api:
            headers = {'Authorization': f'Bearer {creds.token}'}
            r = await api.get(root + quote(tab + '!A1:AZ1', safe=''), headers=headers)
            r.raise_for_status()
            columns = validate_headers(r.json())
            if args['fields'] and (expected_headers != columns or set(args['fields']) - set(columns[5:])):
                raise ValueError('The optional column schema changed or was not approved. Propose the row again.')
            last = max([4, *(columns.index(k) for k in args['fields'])])
            number = last + 1
            letters = ''
            while number:
                number, rest = divmod(number - 1, 26)
                letters = chr(65 + rest) + letters
            row = [date, args['client'], args['hours'], note, request_id] + [args['fields'].get(k, '') for k in columns[5:last + 1]]
            r = await api.post(root + quote(tab + '!A:' + letters, safe='') + ':append', headers=headers,
                params={'valueInputOption': 'RAW', 'insertDataOption': 'INSERT_ROWS'},
                json={'majorDimension': 'ROWS', 'values': [row]})
            r.raise_for_status()
            updated = r.json().get('updates', {}).get('updatedRange', '')
            match = re.search(r'!A(\d+):' + letters + r'(\d+)$', updated)
            if not match or match[1] != match[2]:
                raise ValueError('Sheets did not confirm the appended row.')
            return {'row': int(match[1]), 'url': f'https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit',
                    'title': f"{args['hours']:g} hours for {args['client']} on {date}", 'range': updated}
    except (ValueError, google_auth.GoogleAuthError) as exc:
        return _error('sheets_failed', str(exc), 'Check the sheet before proposing again if a write was attempted.')
    except httpx.HTTPError:
        return _error('sheets_unreachable', 'Sheets did not confirm the entry.',
                      'Check the sheet for the action ID before proposing again; no retry was made.')
