"""Approved Sheets schema/row operations; destinations and payloads are Python-owned.
https://developers.google.com/workspace/sheets/api/guides/metadata
https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets/batchUpdate
"""
import asyncio
import hashlib
import json
import math
import re
from collections import Counter
from contextlib import asynccontextmanager
from datetime import date as iso_date

import httpx

from koe import google_auth
from koe.tools import sheets
from koe.tools.github import _error

MAX_ROWS = 5000
OPERATION_SECONDS = 45
MAX_API_BYTES = 4_000_000
MAX_RESULT_BYTES = 24_000
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
async def api_client(args):
    try:
        async with asyncio.timeout(OPERATION_SECONDS):
            if await asyncio.to_thread(destination) != {key: args[key] for key in ('spreadsheet_id', 'sheet_name')}:
                raise ValueError('The connected timesheet changed. Propose again.')
            creds = await asyncio.to_thread(google_auth.credentials, required_scopes=[google_auth.SHEETS_SCOPE])
            # Constructing an HTTP client loads TLS certificates; keep that I/O off the call's event loop.
            connection = await asyncio.to_thread(httpx.AsyncClient,
                base_url='https://sheets.googleapis.com/v4/spreadsheets/' + args['spreadsheet_id'],
                timeout=15, trust_env=False, headers={'Authorization': f'Bearer {creds.token}'})
            async with connection as api:
                yield api
    except google_auth.GoogleAuthError:
        raise ValueError('Google Sheets is not connected or must be reauthorized. No mutation was retried.') from None
    except TimeoutError:
        raise ValueError('The Sheets operation exceeded its time budget. Check the sheet before retrying; no mutation was retried.') from None


async def request(api, method, suffix='', **kwargs):
    # httpx base_url appends a slash; colon RPC suffixes must address the spreadsheet itself.
    url = str(api.base_url).rstrip('/') + suffix
    try:
        async with api.stream(method, url, **kwargs) as response:
            response.raise_for_status()
            if int(response.headers.get('content-length', '0')) > MAX_API_BYTES: raise ValueError('Response too large.')
            content = bytearray()
            async for chunk in response.aiter_bytes(chunk_size=65536):
                content.extend(chunk)
                if len(content) > MAX_API_BYTES: raise ValueError('Response too large.')
            data = json.loads(content)
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
    if key == 'numberValue' and type(value) in (int, float) and math.isfinite(value): return value
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
    return {**parsed, **args, 'column_count': width}


def prepare_write(name, *, columns=None, row_id=None, expected_version=None, changes=None):
    if name == 'sheets_update_row':
        if columns is not None or not isinstance(row_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', row_id):
            raise ValueError('Use the exact stable row_id from sheets_find_rows.')
        if not isinstance(expected_version, str) or not re.fullmatch(r'[a-f0-9]{64}', expected_version):
            raise ValueError('Read the row first and use its exact version.')
        if not isinstance(changes, dict) or not 1 <= len(changes) <= 20:
            raise ValueError('Specify 1–20 exact column names and new scalar values.')
        base = {'Date': 'date', 'Client': 'client', 'Hours': 'hours', 'Note': 'note'}
        extra = {key: value for key, value in changes.items() if key not in base}
        checked = sheets.prepare_hours(changes.get('Date', '2000-01-01'), changes.get('Client', 'validation'),
            changes.get('Hours', 1), changes.get('Note', ''), fields=extra)
        return {'row_id': row_id, 'expected_version': expected_version,
                'changes': {key: checked[base[key]] if key in base else checked['fields'][key] for key in changes}}
    if name != 'sheets_add_columns': raise ValueError('Unsupported Sheets write.')
    if any(value is not None for value in (row_id, expected_version, changes)):
        raise ValueError('Column creation does not include row edits.')
    if not isinstance(columns, list) or not 1 <= len(columns) <= 10 or any(
        not isinstance(c, str) or not 1 <= len(c) <= 100 or c != c.strip() or any(ord(ch) < 32 for ch in c)
        or c.casefold() in {h.casefold() for h in sheets.HEADERS} for c in columns):
        raise ValueError('Provide 1–10 nonempty new optional column names; required headers are reserved.')
    if len({c.casefold() for c in columns}) != len(columns): raise ValueError('Column names must be unique.')
    return {'columns': list(columns)}


async def prepare_proposal(name, args):
    args = {**args, **(await asyncio.to_thread(destination))}
    async with api_client(args) as api:
        state = await snapshot(api, args, include_rows=name == 'sheets_update_row')
    if name == 'sheets_update_row':
        index, cells = current_row(state, args['row_id'], args['expected_version'])
        check_changes(state, cells, args['changes'])
        before = {key: scalar(cells[state['headers'].index(key)]) for key in args['changes']}
        context_note = str(scalar(cells[3]))
        context_note = context_note[:400] + ('… [truncated context]' if len(context_note) > 400 else '')
        frozen = {**args, 'sheet_id': state['sheet_id'], 'expected_headers': state['headers']}
        summary = (f"Update Sheets row ID {args['row_id']} (currently row {index + 1}). "
            f"Current entry: {json.dumps({h: scalar(cells[i]) for i, h in enumerate(state['headers'][:3])}, ensure_ascii=False)}.\n"
            f"Context note: {context_note}\n"
            f"Before: {json.dumps(before, ensure_ascii=False)}\nAfter: {json.dumps(args['changes'], ensure_ascii=False)}\n"
            f"Destination: https://docs.google.com/spreadsheets/d/{args['spreadsheet_id']}/edit tab {args['sheet_name']}. "
            'Only these cells change; other values, formulas and tracking ID are retained. Stable row metadata may be attached.')
        if len(summary.encode()) > 16_000: raise ValueError('The complete edit preview is too large. Split it into smaller approvals.')
        return frozen, summary
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
        async with sheets.write_lock(spreadsheet_id, sheet_name), api_client(args) as api:
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


def row_cells(state, cells):
    width = len(state['headers'])
    return cells[:width] + [{} for _ in range(max(0, width - len(cells)))]


def row_identity(cells):
    value = cells[4].get('stringValue', '') if len(cells) > 4 else ''
    return value if re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value) else ''


def row_version(state, cells):
    normalized = [{'numberValue': float(c['numberValue'])} if 'numberValue' in c else c for c in row_cells(state, cells)]
    return digest({'destination': [state['spreadsheet_id'], state['sheet_id']], 'headers': state['headers'], 'cells': normalized})


def current_row(state, row_id, version=None):
    matches = [(index, row_cells(state, cells)) for index, cells in state['rows'].items() if row_identity(cells) == row_id]
    if len(matches) != 1: raise ValueError('The row ID is missing or duplicated. No row edit is safe.')
    index, cells = matches[0]
    if version is not None and row_version(state, cells) != version:
        raise ValueError('The row or headers changed since it was read. Refresh and propose again.')
    return index, cells


def check_changes(state, cells, changes):
    if set(changes) - set(state['headers']): raise ValueError('A requested column does not exist.')
    if any('formulaValue' in cells[state['headers'].index(key)] for key in changes):
        raise ValueError('Existing formula cells cannot be edited through Koe.')
    if any(isinstance(scalar(cells[state['headers'].index(key)]), str) and len(scalar(cells[state['headers'].index(key)])) > 2000 for key in changes):
        raise ValueError('An existing target cell is too large for a complete approval preview. Edit it directly in Sheets.')
    if all(entered(value) == cells[state['headers'].index(key)] for key, value in changes.items()):
        raise ValueError('The requested values are already present. No edit is needed.')


def entered(value):
    if value == '' and isinstance(value, str): return {}
    key = 'boolValue' if type(value) is bool else 'numberValue' if type(value) in (int, float) else 'stringValue'
    return {key: value}


async def sheets_find_rows(query='', client='', date='', row_id=''):
    try:
        if any(not isinstance(value, str) or len(value) > 200 for value in (query, client, date, row_id)):
            raise ValueError('Use bounded text filters.')
        if date and iso_date.fromisoformat(date).isoformat() != date: raise ValueError('Use YYYY-MM-DD for the date filter.')
        args = await asyncio.to_thread(destination)
        async with api_client(args) as api:
            state = await snapshot(api, args, include_rows=True)
        counts = Counter(row_identity(cells) for cells in state['rows'].values())
        matches, match_count = [], 0
        for index, raw in sorted(state['rows'].items(), reverse=True):
            if not any(raw): continue
            cells = row_cells(state, raw)
            values = {header: scalar(cells[i]) for i, header in enumerate(state['headers']) if i != 4}
            identifier = row_identity(cells)
            if row_id and identifier != row_id or client and str(values['Client']).casefold() != client.casefold(): continue
            if date and values['Date'] != date: continue
            if query and not any(query.casefold() in str(value).casefold() for value in values.values()): continue
            match_count += 1
            if len(matches) >= 20: continue
            truncated = [key for key, value in values.items() if isinstance(value, str) and len(value) > 400]
            display_values = {key: (value[:400] + '… [truncated]' if key in truncated else value) for key, value in values.items()}
            item = {'row_id': identifier, 'row': index + 1, 'fields': display_values, 'truncated_fields': truncated,
                'version': row_version(state, cells),
                'editable': bool(identifier and counts[identifier] == 1),
                'formula_columns': [header for i, header in enumerate(state['headers']) if 'formulaValue' in cells[i]]}
            if len(json.dumps([*matches, item]).encode()) <= MAX_RESULT_BYTES - 1000: matches.append(item)
        return {'matches': matches, 'has_more': match_count > len(matches), 'match_count': match_count,
            'note': 'Row numbers are display hints. Use exact row_id/version; never guess. Long display text is labeled truncated, but versions use full data. Narrow filters when has_more is true.'}
    except (ValueError, google_auth.GoogleAuthError) as exc:
        return _error('sheets_rows', str(exc), 'No rows were changed. Read a smaller dedicated timesheet if bounds were exceeded.')


async def row_anchor(api, state, row_id, index):
    data = await request(api, 'POST', '/developerMetadata:search', json={'dataFilters': [
        {'developerMetadataLookup': {'metadataKey': 'koe.row', 'metadataValue': row_id, 'visibility': 'DOCUMENT'}}]})
    matching = []
    for match in data.get('matchedDeveloperMetadata', []):
        meta = match.get('developerMetadata', {})
        location = meta.get('location', {}).get('dimensionRange', {})
        if location.get('sheetId') == state['sheet_id']:
            if meta.get('metadataKey') != 'koe.row' or meta.get('metadataValue') != row_id or location.get('dimension') != 'ROWS':
                raise ValueError('The existing row metadata is incompatible.')
            if type(location.get('startIndex')) is not int or location.get('endIndex') != location['startIndex'] + 1:
                raise ValueError('A row metadata anchor must identify exactly one row.')
            matching.append(meta)
    if len(matching) > 1: raise ValueError('The row has multiple metadata anchors. Inspect Sheets before editing.')
    if matching:
        identifier = matching[0].get('metadataId')
    else:
        meta = {'metadataKey': 'koe.row', 'metadataValue': row_id, 'visibility': 'DOCUMENT',
                'location': {'dimensionRange': {'sheetId': state['sheet_id'], 'dimension': 'ROWS', 'startIndex': index, 'endIndex': index + 1}}}
        data = await request(api, 'POST', ':batchUpdate', json={'requests': [{'createDeveloperMetadata': {'developerMetadata': meta}}]})
        identifier = data.get('replies', [{}])[0].get('createDeveloperMetadata', {}).get('developerMetadata', {}).get('metadataId')
    if type(identifier) is not int or identifier < 1: raise ValueError('Google did not confirm a unique row metadata ID.')
    return identifier


async def anchored_snapshot(api, args, sheet_id, metadata_id):
    data = await request(api, 'POST', ':getByDataFilter', params={'fields': GRID_FIELDS}, json={'includeGridData': True,
        'dataFilters': [{'gridRange': {'sheetId': sheet_id, 'startRowIndex': 0, 'endRowIndex': 1}},
                        {'developerMetadataLookup': {'metadataId': metadata_id}}]})
    return {**parse_grid(data, sheet_id), **args}


async def sheets_update_row(*, row_id, expected_version, changes, spreadsheet_id, sheet_name, sheet_id, expected_headers, request_id):
    args = {'spreadsheet_id': spreadsheet_id, 'sheet_name': sheet_name}
    try:
        checked = await asyncio.to_thread(prepare_write, 'sheets_update_row', row_id=row_id, expected_version=expected_version, changes=changes)
        changes = checked['changes']
        async with sheets.write_lock(spreadsheet_id, sheet_name), api_client(args) as api:
            state = await snapshot(api, args, include_rows=True)
            if state['sheet_id'] != sheet_id or state['headers'] != expected_headers:
                raise ValueError('The destination tab or headers changed. Propose again.')
            index, cells = current_row(state, row_id, expected_version)
            check_changes(state, cells, changes)
            metadata_id = await row_anchor(api, state, row_id, index)
            anchored = await anchored_snapshot(api, args, sheet_id, metadata_id)
            _, cells = current_row(anchored, row_id, expected_version)
            check_changes(anchored, cells, changes)
            last = max(expected_headers.index(key) for key in changes)
            values = [None] * (last + 1)
            for key, value in changes.items(): values[expected_headers.index(key)] = value
            # Null skips unrequested cells, preserving formulas; RAW makes '=text' a literal.
            # https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values
            result = await request(api, 'POST', '/values:batchUpdateByDataFilter', json={'valueInputOption': 'RAW', 'data': [
                {'dataFilter': {'developerMetadataLookup': {'metadataId': metadata_id}}, 'majorDimension': 'ROWS', 'values': [values]}]})
            if result.get('totalUpdatedRows') != 1: raise ValueError('Sheets did not confirm exactly one updated row.')
            verified = await anchored_snapshot(api, args, sheet_id, metadata_id)
            final_index, cells = current_row(verified, row_id)
            if verified['headers'] != expected_headers or any(entered(value) != cells[expected_headers.index(key)] for key, value in changes.items()):
                raise ValueError('The row readback differs. Inspect Sheets before proposing another edit.')
            return {'row_id': row_id, 'row': final_index + 1, 'changed_fields': changes, 'verified': True,
                    'title': 'Updated existing Sheets row', 'url': f'https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit'}
    except (ValueError, google_auth.GoogleAuthError) as exc:
        return _error('sheets_row_edit', str(exc), 'No mutation was retried. Check the row before proposing another edit.')
