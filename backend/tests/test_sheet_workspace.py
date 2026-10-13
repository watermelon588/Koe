import asyncio
import copy
import json
from types import SimpleNamespace

import httpx
import pytest
import respx

from koe import agent, google_auth
from koe.config import settings
from koe.tools import sheets
from test_approvals import fake_store

ROOT = 'https://sheets.googleapis.com/v4/spreadsheets/synthetic-sheet'
ROW_ID = '11111111-1111-1111-1111-111111111111'


def cell(value):
    if isinstance(value, dict): return {'userEnteredValue': value}
    kind = 'boolValue' if type(value) is bool else 'numberValue' if type(value) in (int, float) else 'stringValue'
    return {'userEnteredValue': {kind: value}} if value != '' else {}


class Sheet:
    def __init__(self):
        self.rows = [sheets.HEADERS + ['Project'], ['2026-10-14', 'Client', 1, 'Original note', ROW_ID, 'Koe']]
        self.columns = 26
        self.row_count = 20
        self.writes = []
        self.metadata = []
        self.value_writes = []
        self.move_before_update = False

    def response(self, grid=False):
        tab = {'properties': {'sheetId': 7, 'title': 'Hours', 'gridProperties': {
            'rowCount': self.row_count, 'columnCount': self.columns}}}
        if grid:
            tab['data'] = [{'startRow': 0, 'startColumn': 0, 'rowData': [
                {'values': [cell(v) for v in row]} for row in self.rows]}]
        return {'spreadsheetId': 'synthetic-sheet', 'sheets': [tab]}

    def get(self, request):
        return httpx.Response(200, json=self.response(grid='includeGridData' in request.url.params))

    def batch(self, request):
        body = json.loads(request.content)
        self.writes.append(body)
        replies = []
        for item in body['requests']:
            reply = {}
            if 'insertDimension' in item:
                r = item['insertDimension']['range']
                index, count = r['startIndex'], r['endIndex'] - r['startIndex']
                for row in self.rows: row[index:index] = [''] * count
                self.columns += count
            elif 'updateCells' in item:
                update = item['updateCells']
                for offset, value in enumerate(update['rows'][0]['values']):
                    self.rows[0][update['start']['columnIndex'] + offset] = value['userEnteredValue']['stringValue']
            elif 'createDeveloperMetadata' in item:
                entry = copy.deepcopy(item['createDeveloperMetadata']['developerMetadata'])
                entry['metadataId'] = 42 + len(self.metadata)
                self.metadata.append(entry)
                reply = {'createDeveloperMetadata': {'developerMetadata': entry}}
            replies.append(reply)
        return httpx.Response(200, json={'replies': replies})

    def search(self, request):
        return httpx.Response(200, json={'matchedDeveloperMetadata': [{'developerMetadata': m} for m in self.metadata]})

    def by_filter(self, request):
        body = json.loads(request.content)
        selected = next(f['developerMetadataLookup']['metadataId'] for f in body['dataFilters'] if 'developerMetadataLookup' in f)
        meta = next(m for m in self.metadata if m['metadataId'] == selected)
        index = meta['location']['dimensionRange']['startIndex']
        result = self.response()
        result['sheets'][0]['data'] = [
            {'startRow': 0, 'rowData': [{'values': [cell(v) for v in self.rows[0]]}]},
            {'startRow': index, 'rowData': [{'values': [cell(v) for v in self.rows[index]]}]}]
        return httpx.Response(200, json=result)

    def update(self, request):
        body = json.loads(request.content)
        self.value_writes.append(body)
        if self.move_before_update:
            self.rows.insert(1, ['2026-10-14', 'Other', 2, 'Preserve', 'other-id', 'Other project'])
            for meta in self.metadata:
                meta['location']['dimensionRange']['startIndex'] += 1
                meta['location']['dimensionRange']['endIndex'] += 1
        selected = body['data'][0]['dataFilter']['developerMetadataLookup']['metadataId']
        meta = next(m for m in self.metadata if m['metadataId'] == selected)
        row = self.rows[meta['location']['dimensionRange']['startIndex']]
        for index, value in enumerate(body['data'][0]['values'][0]):
            if value is not None: row[index] = value
        return httpx.Response(200, json={'totalUpdatedRows': 1})


@pytest.fixture(autouse=True)
def account(monkeypatch):
    monkeypatch.setattr(settings, 'google_sheets_id', 'synthetic-sheet')
    monkeypatch.setattr(settings, 'google_sheets_tab', 'Hours')
    monkeypatch.setattr(google_auth, 'credentials', lambda **kwargs: SimpleNamespace(token='synthetic'))


@pytest.fixture
def sheet():
    with respx.mock:
        table = Sheet()
        respx.get(ROOT).mock(side_effect=table.get)
        respx.post(ROOT + ':batchUpdate').mock(side_effect=table.batch)
        respx.post(ROOT + '/developerMetadata:search').mock(side_effect=table.search)
        respx.post(ROOT + ':getByDataFilter').mock(side_effect=table.by_filter)
        respx.post(ROOT + '/values:batchUpdateByDataFilter').mock(side_effect=table.update)
        yield table


def test_add_columns_is_atomic_additive_and_literal(sheet):
    from koe.tools import sheet_workspace as workspace
    original = copy.deepcopy(sheet.rows[1])
    async def scenario():
        args, summary = await workspace.prepare_proposal('sheets_add_columns', workspace.prepare_write(
            'sheets_add_columns', columns=['Billable', '=Literal']))
        assert 'Billable' in summary and '=Literal' in summary and not sheet.writes
        return await workspace.sheets_add_columns(**args, request_id='action')
    result = asyncio.run(scenario())
    assert result['added_columns'] == ['Billable', '=Literal']
    assert sheet.rows[1][:6] == original and sheet.rows[1][6:] == ['', '']
    assert len(sheet.writes) == 1
    assert sheet.writes[0]['requests'][0]['insertDimension']['range']['dimension'] == 'COLUMNS'
    assert sheet.writes[0]['requests'][1]['updateCells']['fields'] == 'userEnteredValue'


@pytest.mark.parametrize('columns', [['Date'], ['Project'], ['New', 'new'], [], ['x'] * 11, [' bad ']])
def test_invalid_or_existing_column_names_never_write(sheet, columns):
    from koe.tools import sheet_workspace as workspace
    async def scenario():
        await workspace.prepare_proposal('sheets_add_columns', workspace.prepare_write('sheets_add_columns', columns=columns))
    with pytest.raises(ValueError): asyncio.run(scenario())
    assert not sheet.writes


def test_column_proposal_rejects_changed_headers_and_destination(sheet, monkeypatch):
    from koe.tools import sheet_workspace as workspace
    async def scenario():
        args, _ = await workspace.prepare_proposal('sheets_add_columns', workspace.prepare_write('sheets_add_columns', columns=['Billable']))
        sheet.rows[0][-1] = 'Changed'
        assert 'error' in await workspace.sheets_add_columns(**args, request_id='action')
        monkeypatch.setattr(settings, 'google_sheets_id', 'another-sheet')
        assert 'error' in await workspace.sheets_add_columns(**args, request_id='action')
    asyncio.run(scenario())
    assert not sheet.writes


def test_columns_require_separate_approval_and_execute_once(sheet, fake_store):
    async def scenario():
        ctx = agent.Conversation('cli')
        proposal = await agent.run_tool('sheets_add_columns', {'columns': ['Billable']}, context=ctx)
        assert 'pending_action' in proposal and not sheet.writes
        assert 'error' in await agent.confirm(ctx, True)
        ctx.approval_ready = True
        assert (await agent.confirm(ctx, True))['status'] == 'executed'
        assert 'error' in await agent.confirm(ctx, True)
    asyncio.run(scenario())
    assert len(sheet.writes) == 1


def test_row_discovery_returns_real_identity_values_and_version(sheet):
    from koe.tools import sheet_workspace as workspace
    result = asyncio.run(workspace.sheets_find_rows(client='Client', date='2026-10-14'))
    row = result['matches'][0]
    assert row['row_id'] == ROW_ID and row['fields']['Note'] == 'Original note'
    assert len(row['version']) == 64 and row['editable'] and not sheet.writes


def test_edit_follows_moving_metadata_and_preserves_unrequested_cells(sheet, fake_store):
    from koe.tools import sheet_workspace as workspace
    sheet.rows[0].append('Calculated')
    sheet.rows[1].append({'formulaValue': '=C2*2'})
    async def scenario():
        row = (await workspace.sheets_find_rows(row_id=ROW_ID))['matches'][0]
        ctx = agent.Conversation('cli')
        result = await agent.run_tool('sheets_update_row', {'row_id': ROW_ID, 'expected_version': row['version'],
            'changes': {'Hours': 1.5, 'Note': '=literal'}}, context=ctx)
        assert 'pending_action' in result and 'Original note' in result['pending_action']['summary'] and not sheet.value_writes
        assert 'error' in await agent.confirm(ctx, True)
        stored = fake_store[0][result['pending_action']['id']]
        stored['args_json'] = json.loads(json.dumps(stored['args_json']))
        sheet.move_before_update = True
        ctx.approval_ready = True
        assert (await agent.confirm(ctx, True))['status'] == 'executed'
        assert 'error' in await agent.confirm(ctx, True)
    asyncio.run(scenario())
    assert len(sheet.value_writes) == 1
    assert sheet.rows[1][3] == 'Preserve' and sheet.rows[2][2:5] == [1.5, '=literal', ROW_ID]
    assert sheet.rows[2][6] == {'formulaValue': '=C2*2'}
    sent = sheet.value_writes[0]
    assert sent['valueInputOption'] == 'RAW'
    assert sent['data'][0]['values'] == [[None, None, 1.5, '=literal']]


def test_stale_or_duplicate_rows_never_write(sheet):
    from koe.tools import sheet_workspace as workspace
    async def scenario():
        row = (await workspace.sheets_find_rows(row_id=ROW_ID))['matches'][0]
        sheet.rows[1][3] = 'Changed elsewhere'
        with pytest.raises(ValueError):
            await workspace.prepare_proposal('sheets_update_row', workspace.prepare_write('sheets_update_row',
                row_id=ROW_ID, expected_version=row['version'], changes={'Note': 'New'}))
        sheet.rows.append(copy.deepcopy(sheet.rows[1]))
        rows = await workspace.sheets_find_rows(row_id=ROW_ID)
        assert all(not r['editable'] for r in rows['matches'])
    asyncio.run(scenario())
    assert not sheet.writes and not sheet.value_writes


@pytest.mark.parametrize('changes', [{'Koe action ID': 'spoof'}, {'Hours': True}, {'Unknown': 'x'}, {'Project': {'nested': 'x'}}])
def test_invalid_row_fields_cannot_be_proposed(sheet, changes):
    from koe.tools import sheet_workspace as workspace
    async def scenario():
        row = (await workspace.sheets_find_rows(row_id=ROW_ID))['matches'][0]
        await workspace.prepare_proposal('sheets_update_row', workspace.prepare_write('sheets_update_row',
            row_id=ROW_ID, expected_version=row['version'], changes=changes))
    with pytest.raises(ValueError): asyncio.run(scenario())
    assert not sheet.writes


def test_formula_target_and_changed_row_after_approval_are_rejected(sheet):
    from koe.tools import sheet_workspace as workspace
    async def scenario():
        sheet.rows[1][5] = {'formulaValue': '=1+1'}
        row = (await workspace.sheets_find_rows(row_id=ROW_ID))['matches'][0]
        with pytest.raises(ValueError):
            await workspace.prepare_proposal('sheets_update_row', workspace.prepare_write('sheets_update_row',
                row_id=ROW_ID, expected_version=row['version'], changes={'Project': 'New'}))
        args, _ = await workspace.prepare_proposal('sheets_update_row', workspace.prepare_write('sheets_update_row',
            row_id=ROW_ID, expected_version=row['version'], changes={'Note': 'New'}))
        sheet.rows[1][2] = 2
        assert 'error' in await workspace.sheets_update_row(**args, request_id='action')
    asyncio.run(scenario())
    assert not sheet.writes and not sheet.value_writes


def test_discovery_refuses_incomplete_scan_and_reports_match_limit(sheet):
    from koe.tools import sheet_workspace as workspace
    sheet.rows += [['2026-10-14', 'Client', 1, 'Note', f'id-{i}', 'Koe'] for i in range(25)]
    sheet.row_count = 50
    result = asyncio.run(workspace.sheets_find_rows(client='Client'))
    assert len(result['matches']) == 20 and result['has_more'] and result['match_count'] == 26
    sheet.row_count = 6000
    assert 'error' in asyncio.run(workspace.sheets_find_rows())


def test_review_disconnected_oauth_returns_safe_proposal_error(sheet, monkeypatch):
    def unavailable(**kwargs): raise google_auth.GoogleAuthError('private OAuth diagnostics')
    monkeypatch.setattr(google_auth, 'credentials', unavailable)
    result = asyncio.run(agent.run_tool('sheets_add_columns', {'columns': ['Billable']}, context=agent.Conversation('cli')))
    assert 'error' in result and 'private OAuth' not in str(result) and not sheet.writes


def test_review_read_budget_is_total_and_does_not_hang(sheet, monkeypatch):
    from koe.tools import sheet_workspace as workspace
    monkeypatch.setattr(workspace, 'OPERATION_SECONDS', .01, raising=False)
    async def stalled(*args, **kwargs): await asyncio.Event().wait()
    monkeypatch.setattr(workspace, 'request', stalled)
    async def scenario(): return await asyncio.wait_for(workspace.sheets_find_rows(), timeout=.2)
    assert 'error' in asyncio.run(scenario()) and not sheet.writes


def test_review_malformed_grid_is_an_error_not_missing_rows(sheet):
    from koe.tools import sheet_workspace as workspace
    sheet.rows[1][5] = {'numberValue': None}
    result = asyncio.run(workspace.sheets_find_rows())
    assert 'error' in result and 'matches' not in result and not sheet.writes


def test_review_wrong_row_anchor_never_changes_values(sheet):
    from koe.tools import sheet_workspace as workspace
    sheet.rows.append(['2026-10-14', 'Other', 2, 'Preserve', 'other-id', 'Other'])
    sheet.metadata.append({'metadataId': 42, 'metadataKey': 'koe.row', 'metadataValue': ROW_ID, 'visibility': 'DOCUMENT',
        'location': {'dimensionRange': {'sheetId': 7, 'dimension': 'ROWS', 'startIndex': 2, 'endIndex': 3}}})
    async def scenario():
        row = (await workspace.sheets_find_rows(row_id=ROW_ID))['matches'][0]
        args, _ = await workspace.prepare_proposal('sheets_update_row', workspace.prepare_write('sheets_update_row',
            row_id=ROW_ID, expected_version=row['version'], changes={'Note': 'New'}))
        return await workspace.sheets_update_row(**args, request_id='action')
    assert 'error' in asyncio.run(scenario()) and not sheet.value_writes
    assert sheet.rows[2][3] == 'Preserve'


def test_review_value_timeout_is_never_replayed(sheet):
    from koe.tools import sheet_workspace as workspace
    def uncertain(request):
        sheet.update(request)  # model the write taking effect before its response is lost
        raise httpx.ReadTimeout('private timeout body')
    respx.post(ROOT + '/values:batchUpdateByDataFilter').mock(side_effect=uncertain)
    async def scenario():
        row = (await workspace.sheets_find_rows(row_id=ROW_ID))['matches'][0]
        args, _ = await workspace.prepare_proposal('sheets_update_row', workspace.prepare_write('sheets_update_row',
            row_id=ROW_ID, expected_version=row['version'], changes={'Note': 'New'}))
        result = await workspace.sheets_update_row(**args, request_id='action')
        assert 'error' in result and 'private timeout' not in str(result)
    asyncio.run(scenario())
    assert len(sheet.value_writes) == 1 and sheet.rows[1][3] == 'New'


def test_review_column_timeout_is_never_replayed(sheet):
    from koe.tools import sheet_workspace as workspace
    def uncertain(request):
        sheet.batch(request)
        raise httpx.ReadTimeout('private timeout body')
    respx.post(ROOT + ':batchUpdate').mock(side_effect=uncertain)
    async def scenario():
        args, _ = await workspace.prepare_proposal('sheets_add_columns', workspace.prepare_write('sheets_add_columns', columns=['Billable']))
        result = await workspace.sheets_add_columns(**args, request_id='action')
        assert 'error' in result and 'private timeout' not in str(result)
    asyncio.run(scenario())
    assert len(sheet.writes) == 1 and sheet.rows[0][-1] == 'Billable'


def test_review_readback_mismatch_never_claims_verified(sheet):
    from koe.tools import sheet_workspace as workspace
    def changed(request):
        result = sheet.update(request)
        sheet.rows[1][3] = 'Concurrent change'
        return result
    respx.post(ROOT + '/values:batchUpdateByDataFilter').mock(side_effect=changed)
    async def scenario():
        row = (await workspace.sheets_find_rows(row_id=ROW_ID))['matches'][0]
        args, _ = await workspace.prepare_proposal('sheets_update_row', workspace.prepare_write('sheets_update_row',
            row_id=ROW_ID, expected_version=row['version'], changes={'Note': 'New'}))
        return await workspace.sheets_update_row(**args, request_id='action')
    result = asyncio.run(scenario())
    assert 'error' in result and 'verified' not in result and len(sheet.value_writes) == 1


def test_review_model_cannot_supply_internal_snapshots_or_destination(sheet):
    result = asyncio.run(agent.run_tool('sheets_add_columns', {'columns': ['Billable'], 'spreadsheet_id': 'other'},
                                       context=agent.Conversation('cli')))
    assert result['error']['code'] == 'bad_args' and not sheet.writes


def test_review_discovery_bounds_model_context_and_labels_truncated_text(sheet):
    from koe.tools import sheet_workspace as workspace
    sheet.rows[1][3] = 'long note ' * 500
    sheet.rows += [['2026-10-14', 'Client', 1, 'x' * 4000, f'row-{n}', 'Koe'] for n in range(30)]
    sheet.row_count = 50
    result = asyncio.run(workspace.sheets_find_rows())
    assert len(json.dumps(result).encode()) <= workspace.MAX_RESULT_BYTES
    assert result['matches'][0]['truncated_fields'] == ['Note'] and result['has_more']


def test_review_large_api_payload_fails_before_using_incomplete_evidence(sheet):
    from koe.tools import sheet_workspace as workspace
    sheet.rows += [['2026-10-14', 'Client', 1, 'x' * 45000, f'row-{n}', 'Koe'] for n in range(100)]
    sheet.row_count = 200
    result = asyncio.run(workspace.sheets_find_rows())
    assert 'error' in result and 'matches' not in result
