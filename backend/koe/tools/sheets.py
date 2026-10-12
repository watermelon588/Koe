"""Approved hours only. RAW avoids formula interpretation of user-controlled text.
https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values/append
"""
import asyncio
import re
from datetime import date as iso_date
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

import httpx

from koe import google_auth
from koe.config import settings
from koe.tools.github import _error

HEADERS = ['Date', 'Client', 'Hours', 'Note', 'Koe action ID']


def prepare_hours(date: str, client: str, hours: float, note: str = '') -> dict:
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
    sheet = settings.google_sheets_id
    tab = settings.google_sheets_tab
    if not re.fullmatch(r'[A-Za-z0-9_-]+', sheet) or not tab.strip() or len(tab) > 100:
        raise ValueError('Set GOOGLE_SHEETS_ID and GOOGLE_SHEETS_TAB.')
    return {'date': date, 'client': client.strip(), 'hours': float(value), 'note': note,
            'spreadsheet_id': sheet, 'sheet_name': tab}


async def sheets_log_hours(date: str, client: str, hours: float, note: str = '', *,
                           spreadsheet_id: str, sheet_name: str, request_id: str) -> dict:
    try:
        args = prepare_hours(date, client, hours, note)
        if (spreadsheet_id, sheet_name) != (args['spreadsheet_id'], args['sheet_name']):
            raise ValueError('The timesheet destination changed; propose the entry again.')
        creds = await asyncio.to_thread(google_auth.credentials, required_scopes=[google_auth.SHEETS_SCOPE])
        root = f'https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/'
        tab = "'" + sheet_name.replace("'", "''") + "'"
        async with httpx.AsyncClient(timeout=15) as api:
            headers = {'Authorization': f'Bearer {creds.token}'}
            r = await api.get(root + quote(tab + '!A1:E1', safe=''), headers=headers)
            r.raise_for_status()
            if r.json().get('values') != [HEADERS]:
                raise ValueError('Timesheet A1:E1 must be: ' + ', '.join(HEADERS))
            r = await api.post(root + quote(tab + '!A:E', safe='') + ':append', headers=headers,
                params={'valueInputOption': 'RAW', 'insertDataOption': 'INSERT_ROWS'},
                json={'majorDimension': 'ROWS', 'values': [[date, args['client'], args['hours'], note, request_id]]})
            r.raise_for_status()
            updated = r.json().get('updates', {}).get('updatedRange', '')
            match = re.search(r'!A(\d+):E\d+$', updated)
            if not match:
                raise ValueError('Sheets did not confirm the appended row.')
            return {'row': int(match[1]), 'url': f'https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit',
                    'title': f"{args['hours']:g} hours for {args['client']} on {date}", 'range': updated}
    except (ValueError, google_auth.GoogleAuthError) as exc:
        return _error('sheets_failed', str(exc), 'Check the sheet before proposing again if a write was attempted.')
    except httpx.HTTPError:
        return _error('sheets_unreachable', 'Sheets did not confirm the entry.',
                      'Check the sheet for the action ID before proposing again; no retry was made.')
