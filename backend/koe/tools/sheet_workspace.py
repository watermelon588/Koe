"""Approved Sheets schema/row operations; destinations and payloads are Python-owned.
https://developers.google.com/workspace/sheets/api/guides/metadata
https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets/batchUpdate
"""
import asyncio
import hashlib
import json
import re
from contextlib import asynccontextmanager

import httpx

from koe import google_auth
from koe.tools import sheets
from koe.tools.github import _error

MAX_ROWS = 5000
GRID_FIELDS = 'sheets(properties(sheetId,title,gridProperties),data(startRow,startColumn,rowData(values(userEnteredValue))))'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                                     separators=(',', ':')).encode()).hexdigest()


def letters(number):
    result = ''
    while number:
        number, rest = divmod(number - 1, 26)
        result = chr(65 + rest) + result
    return result


def destination():
    args = sheets.prepare_hours('2000-01-01', 'destination read', 1)
    return {key: args[key] for key in ('spreadsheet_id', 'sheet_name')}


@asynccontextmanager
async def client(args):
    if await asyncio.to_thread(destination) != {key: args[key] for key in ('spreadsheet_id', 'sheet_name')}:
        raise ValueError('The connected timesheet changed. Propose again.')
    creds = await asyncio.to_thread(google_auth.credentials, required_scopes=[google_auth.SHEETS_SCOPE])
    async with httpx.AsyncClient(base_url='https://sheets.googleapis.com/v4/spreadsheets/' + args['spreadsheet_id'],
                                 timeout=15, trust_env=False, headers={'Authorization': f'Bearer {creds.token}'}) as api:
        yield api


async def request(api, method, suffix='', **kwargs):
    # httpx base_url appends a slash; colon RPC suffixes must address the spreadsheet itself.
    url = str(api.base_url).rstrip('/') + suffix
    try:
        response = await api.request(method, url, **kwargs)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict): raise ValueError()
        return data
    except (httpx.HTTPError, ValueError):
        raise ValueError('Google Sheets did not confirm the operation. Check the sheet before retrying; no write was retried.') from None


def scalar(cell):
    if not cell: return ''
    if not isinstance(cell, dict) or len(cell) != 1:
        raise ValueError('Sheets returned an invalid typed cell.')
    key, value = next(iter(cell.items()))
    if key == 'formulaValue' and isinstance(value, str): return value
    if key == 'stringValue' and isinstance(value, str): return value
    if key == 'boolValue' and type(value) is bool: return value
    if key == 'numberValue' and type(value) in (int, float): return value
    raise ValueError('Sheets returned an unsupported typed cell.')


def parse_grid(data, sheet_id):
    tabs = [tab for tab in data.get('sheets', []) if tab.get('properties', {}).get('sheetId') == sheet_id]
    if len(tabs) != 1: raise ValueError('Sheets did not return the intended tab.')
    rows = {}
    for block in tabs[0].get('data', []):
        if block.get('startColumn', 0) != 0: raise ValueError('Unexpected partial row data.')
        for offset, row in enumerate(block.get('rowData', [])):
            index = block.get('startRow', 0) + offset
            if index > MAX_ROWS: raise ValueError('Sheet exceeds the safe row scan limit.')
            cells = [c.get('userEnteredValue', {}) for c in row.get('values', [])]
            for value in cells: scalar(value)
            if index in rows and rows[index] != cells: raise ValueError('Sheets returned conflicting row data.')
            rows[index] = cells
    header_cells = rows.pop(0, [])
    while header_cells and not header_cells[-1]: header_cells.pop()
    if any('formulaValue' in c for c in header_cells): raise ValueError('Header names must be literal text.')
    headers = sheets.validate_headers({'values': [[scalar(c) for c in header_cells]]})
    return {'sheet_id': sheet_id, 'headers': headers, 'rows': rows}


async def snapshot(api, args, *, include_rows=False):
    data = await request(api, 'GET', params={'fields': 'sheets.properties'})
    tabs = [t['properties'] for t in data.get('sheets', []) if t.get('properties', {}).get('title') == args['sheet_name']]
    if len(tabs) != 1: raise ValueError('The configured sheet tab is missing or ambiguous.')
    props = tabs[0]
    grid = props.get('gridProperties', {})
    count, width = grid.get('rowCount'), grid.get('columnCount')
    if type(count) is not int or type(width) is not int or count < 1 or not 5 <= width <= 500:
        raise ValueError('Unsupported sheet grid dimensions.')
    if include_rows and count > MAX_ROWS + 1:
        raise ValueError('This dedicated tab exceeds 5000 data rows; a complete identity scan is required for edits.')
    tab = "'" + args['sheet_name'].replace("'", "''") + "'"
    params = [('includeGridData', 'true'), ('fields', GRID_FIELDS), ('ranges', f'{tab}!A1:{letters(width)}1')]
    if include_rows and count > 1:
        params.append(('ranges', f'{tab}!A2:{letters(min(width, 52))}{count}'))
    parsed = parse_grid(await request(api, 'GET', params=params), props['sheetId'])
    return {**parsed, 'column_count': width}


def prepare_write(name, *, columns=None):
    if name != 'sheets_add_columns': raise ValueError('Unsupported Sheets write.')
    if not isinstance(columns, list) or not 1 <= len(columns) <= 10 or any(
        not isinstance(c, str) or not 1 <= len(c) <= 100 or c != c.strip() or any(ord(ch) < 32 for ch in c)
        or c.casefold() in {h.casefold() for h in sheets.HEADERS} for c in columns):
        raise ValueError('Provide 1–10 nonempty new optional column names; required headers are reserved.')
    if len({c.casefold() for c in columns}) != len(columns): raise ValueError('Column names must be unique.')
    return {'columns': list(columns)}


async def prepare_proposal(name, args):
    args = {**args, **(await asyncio.to_thread(destination))}
    async with client(args) as api:
        state = await snapshot(api, args)
    if any(c.casefold() in {h.casefold() for h in state['headers']} for c in args['columns']):
        raise ValueError('A requested column already exists. Read sheets_schema and use its exact name.')
    if len(state['headers']) + len(args['columns']) > 52 or state['column_count'] + 2 * len(args['columns']) > 500:
        raise ValueError('The requested columns exceed this timesheet’s safe bounds.')
    frozen = {**args, 'sheet_id': state['sheet_id'], 'expected_headers': state['headers'], 'expected_columns': state['column_count']}
    summary = (f"Add optional Sheets columns {json.dumps(args['columns'], ensure_ascii=False)} after "
               f"{state['headers'][-1]!r}. Destination: https://docs.google.com/spreadsheets/d/{args['spreadsheet_id']}/edit "
               f"tab {args['sheet_name']}. Existing columns and data are retained; no row values are filled.")
    return frozen, summary


async def sheets_add_columns(*, columns, spreadsheet_id, sheet_name, sheet_id, expected_headers, expected_columns, request_id):
    args = {'spreadsheet_id': spreadsheet_id, 'sheet_name': sheet_name}
    try:
        prepare_write('sheets_add_columns', columns=columns)
        async with sheets.write_lock(spreadsheet_id, sheet_name), client(args) as api:
            state = await snapshot(api, args)
            if (state['sheet_id'], state['headers'], state['column_count']) != (sheet_id, expected_headers, expected_columns):
                raise ValueError('The sheet tab or headers changed. Refresh and propose again.')
            if {c.casefold() for c in columns} & {h.casefold() for h in state['headers']}:
                raise ValueError('A new column already exists; nothing was inserted.')
            start, count = len(expected_headers), len(columns)
            if start + count > 52 or expected_columns + 2 * count > 500: raise ValueError('Column bounds exceeded.')
            requests = []
            if start + count > expected_columns:
                requests.append({'appendDimension': {'sheetId': sheet_id, 'dimension': 'COLUMNS', 'length': start + count - expected_columns}})
            requests += [{'insertDimension': {'range': {'sheetId': sheet_id, 'dimension': 'COLUMNS',
                'startIndex': start, 'endIndex': start + count}, 'inheritFromBefore': True}},
                {'updateCells': {'start': {'sheetId': sheet_id, 'rowIndex': 0, 'columnIndex': start},
                    'rows': [{'values': [{'userEnteredValue': {'stringValue': c}} for c in columns]}], 'fields': 'userEnteredValue'}}]
            await request(api, 'POST', ':batchUpdate', json={'requests': requests})
            verified = await snapshot(api, args)
            if verified['sheet_id'] != sheet_id or verified['headers'] != expected_headers + columns:
                raise ValueError('The header readback differs. Inspect Sheets before proposing another change.')
            return {'added_columns': columns, 'verified': True, 'title': 'Added optional Sheets columns',
                    'url': f'https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit'}
    except (ValueError, google_auth.GoogleAuthError) as exc:
        return _error('sheets_schema_change', str(exc), 'No mutation was retried. Refresh the sheet before proposing again.')
