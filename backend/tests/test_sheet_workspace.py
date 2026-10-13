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
        for item in body['requests']:
            if 'insertDimension' in item:
                r = item['insertDimension']['range']
                index, count = r['startIndex'], r['endIndex'] - r['startIndex']
                for row in self.rows: row[index:index] = [''] * count
                self.columns += count
            elif 'updateCells' in item:
                update = item['updateCells']
                for offset, value in enumerate(update['rows'][0]['values']):
                    self.rows[0][update['start']['columnIndex'] + offset] = value['userEnteredValue']['stringValue']
        return httpx.Response(200, json={'replies': [{} for _ in body['requests']]})


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
