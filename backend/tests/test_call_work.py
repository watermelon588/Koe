"""Call display data must follow actual tools and never expose credentials."""
import asyncio
from types import SimpleNamespace

from koe import call_work, voice_call


def test_calendar_projection_bounds_results_and_omits_raw_credentials():
    data = call_work.project('calendar_list', {'date': '2026-10-13', 'token': 'private'}, {
        'date': '2026-10-13', 'timezone': 'Asia/Kolkata', 'token': 'private',
        'events': [{'id': str(i), 'title': 'Review', 'start': {'dateTime': '2026-10-13T10:00:00+05:30'},
                    'end': {'dateTime': '2026-10-13T11:00:00+05:30'}, 'secret': 'private'} for i in range(125)]})
    assert data['service'] == 'calendar' and len(data['events']) == 100
    assert data['total'] == 125 and data['truncated']
    assert 'private' not in str(data) and 'secret' not in str(data)
    assert call_work.project('github_my_prs', {}, {}) is None


def test_sheet_projection_uses_exact_normalized_proposal_and_authoritative_row():
    args = {'date': '2026-10-13', 'client': 'Client A', 'hours': 1.25, 'note': '=literal text',
            'spreadsheet_id': 'sheet-123', 'sheet_name': 'Hours', 'token': 'private'}
    data = call_work.project('sheets_log_hours', args, {'row': 8, 'range': 'Hours!A8:E8', 'status': 'executed'})
    assert data['details'] == {k: args[k] for k in ('date', 'client', 'hours', 'note', 'sheet_name')}
    assert data['row'] == 8 and data['range'] == 'Hours!A8:E8'
    assert data['url'] == 'https://docs.google.com/spreadsheets/d/sheet-123/edit'
    assert 'private' not in str(data)


def test_call_tool_events_include_results_and_correlate_to_original_tool(monkeypatch):
    sent = []
    async def send_json(data): sent.append(data)
    async def run_tool(*args, **kwargs): return {'date': '2026-10-13', 'slots': [], 'timezone': 'Asia/Kolkata'}
    async def send_tool_response(**kwargs): pass
    monkeypatch.setattr(voice_call.agent, 'run_tool', run_tool)
    asyncio.run(voice_call._run_tools(SimpleNamespace(send_json=send_json),
        SimpleNamespace(send_tool_response=send_tool_response),
        [SimpleNamespace(id='fc-1', name='calendar_find_free', args={'date': '2026-10-13', 'duration_min': 30})],
        voice_call.CallState()))
    assert [e['phase'] for e in sent] == ['start', 'end']
    assert all(e['operation_id'] == 'fc-1' for e in sent)
    assert sent[1]['work']['slots'] == []


def test_approval_progress_and_result_use_original_stored_row_even_on_failure(monkeypatch):
    state, sent = voice_call.CallState(), []
    state.context.pending = {'id': 'a', 'tool': 'sheets_log_hours', 'args_json': {
        'date': '2026-10-13', 'client': 'Original', 'hours': 2, 'note': 'Exact note',
        'spreadsheet_id': 'sheet-123', 'sheet_name': 'Hours'}}
    state.context.approval_ready = True
    async def send_json(data): sent.append(data)
    async def confirm(context, approve, action_id):
        context.pending = None
        return {'status': 'failed', 'error': {'message': 'Uncertain write', 'hint': 'Inspect the sheet.'}}
    monkeypatch.setattr(voice_call.agent, 'confirm', confirm)
    asyncio.run(voice_call._approval_result(SimpleNamespace(send_json=send_json), state, True, 'a'))
    assert [e['type'] for e in sent] == ['approval_progress', 'approval_result']
    assert sent[0]['work']['details']['client'] == 'Original'
    assert sent[1]['work']['error']['message'] == 'Uncertain write'
    assert sent[1]['work']['action_id'] == 'a'
