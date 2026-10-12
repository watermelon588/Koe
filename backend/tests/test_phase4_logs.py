import asyncio
import json
from types import SimpleNamespace
from urllib.parse import unquote

import httpx
import pytest
import respx

from koe.config import settings
from koe.tools import notion, sheets

SOURCE = '11111111-1111-1111-1111-111111111111'
PAGE = '22222222-2222-2222-2222-222222222222'


@pytest.fixture(autouse=True)
def account(monkeypatch):
    monkeypatch.setattr(settings, 'notion_token', 'fake')
    monkeypatch.setattr(settings, 'notion_data_source_id', SOURCE)
    monkeypatch.setattr(settings, 'google_sheets_id', 'test_sheet')
    monkeypatch.setattr(settings, 'google_sheets_tab', "Client's Hours")
    monkeypatch.setattr(sheets.google_auth, 'credentials', lambda **kw: SimpleNamespace(token='fake'))


def source():
    respx.get(f'https://api.notion.com/v1/data_sources/{SOURCE}').respond(200, json={
        'properties': {'Name': {'type': 'title'}, 'Date': {'type': 'date'}}})


@respx.mock
def test_notion_creates_daily_page_and_exact_entries_only():
    source()
    respx.post(f'https://api.notion.com/v1/data_sources/{SOURCE}/query').respond(200, json={'results': [], 'has_more': False})
    create = respx.post('https://api.notion.com/v1/pages').respond(200, json={'id': PAGE, 'url': 'https://notion.so/log'})
    result = asyncio.run(notion.notion_log('2026-10-13', ['Shipped #42', 'Shipped #42', 'Reviewed #4']))
    body = json.loads(create.calls[0].request.content)
    assert body['parent']['data_source_id'] == SOURCE
    assert body['properties']['Date']['date']['start'] == '2026-10-13'
    assert result['added'] == len(body['children']) == 2


@respx.mock
def test_notion_existing_entries_paginate_and_no_duplicate_write():
    source()
    respx.post(f'https://api.notion.com/v1/data_sources/{SOURCE}/query').respond(200, json={
        'results': [{'id': PAGE, 'url': 'https://notion.so/log'}], 'has_more': False})
    blocks = respx.get(f'https://api.notion.com/v1/blocks/{PAGE}/children').mock(side_effect=[
        httpx.Response(200, json={'results': [], 'has_more': True, 'next_cursor': 'next'}),
        httpx.Response(200, json={'results': [{'type': 'bulleted_list_item', 'bulleted_list_item': {
            'rich_text': [{'plain_text': 'Shipped #42'}]}}], 'has_more': False})])
    result = asyncio.run(notion.notion_log('2026-10-13', ['Shipped #42']))
    assert result['added'] == 0 and blocks.call_count == 2
    assert not any(c.request.method == 'PATCH' for c in respx.calls)


@respx.mock
def test_duplicate_daily_pages_fail_closed():
    source()
    respx.post(f'https://api.notion.com/v1/data_sources/{SOURCE}/query').respond(200, json={
        'results': [{'id': PAGE}, {'id': SOURCE}], 'has_more': False})
    result = asyncio.run(notion.notion_log('2026-10-13', ['Shipped #42']))
    assert 'error' in result
    assert not any(c.request.method == 'PATCH' for c in respx.calls)


@respx.mock
def test_sheets_append_raw_values_bound_to_approved_destination():
    prepared = sheets.prepare_hours('2026-10-13', '=formula', 1.25, '+literal')
    respx.get(url__regex=r'https://sheets.googleapis.com/.*/values/.*').respond(200, json={'values': [sheets.HEADERS]})
    append = respx.post(url__regex=r'https://sheets.googleapis.com/.*/values/.*:append').respond(200, json={
        'updates': {'updatedRange': "'Client''s Hours'!A2:E2"}})
    result = asyncio.run(sheets.sheets_log_hours(**prepared, request_id='action-1'))
    assert result['row'] == 2
    request = append.calls[0].request
    assert request.url.params['valueInputOption'] == 'RAW'
    assert "'Client''s Hours'!A:E" in unquote(request.url.path)
    assert json.loads(request.content)['values'] == [['2026-10-13', '=formula', 1.25, '+literal', 'action-1']]


@respx.mock
def test_sheets_configuration_change_and_wrong_header_prevent_append(monkeypatch):
    args = sheets.prepare_hours('2026-10-13', 'Client', 1, '')
    monkeypatch.setattr(settings, 'google_sheets_id', 'different')
    assert 'error' in asyncio.run(sheets.sheets_log_hours(**args, request_id='action'))
    assert not respx.calls
    monkeypatch.setattr(settings, 'google_sheets_id', 'test_sheet')
    respx.get(url__regex=r'https://sheets.googleapis.com/.*/values/.*').respond(200, json={'values': [['Wrong']]})
    assert 'error' in asyncio.run(sheets.sheets_log_hours(**args, request_id='action'))
    assert not any(c.request.method == 'POST' for c in respx.calls)


@pytest.mark.parametrize('hours', [True, 0, -1, 25, float('nan'), float('inf'), 1.234])
def test_hours_validation(hours):
    with pytest.raises(ValueError):
        sheets.prepare_hours('2026-10-13', 'Client', hours, '')


@respx.mock
def test_timesheet_timeout_is_not_retried():
    respx.get(url__regex=r'https://sheets.googleapis.com/.*/values/.*').respond(200, json={'values': [sheets.HEADERS]})
    write = respx.post(url__regex=r'https://sheets.googleapis.com/.*/values/.*:append').mock(side_effect=httpx.ReadTimeout('uncertain'))
    args = sheets.prepare_hours('2026-10-13', 'Client', 1, '')
    result = asyncio.run(sheets.sheets_log_hours(**args, request_id='action'))
    assert 'error' in result and write.call_count == 1


@respx.mock
def test_notion_ambiguous_read_shape_does_not_create_page():
    source()
    respx.post(f'https://api.notion.com/v1/data_sources/{SOURCE}/query').respond(200, json={})
    result = asyncio.run(notion.notion_log('2026-10-13', ['Shipped #42']))
    assert 'error' in result
    assert not any(c.request.url.path == '/v1/pages' for c in respx.calls)


@respx.mock
def test_notion_appends_only_new_bullets_and_does_not_retry_timeout():
    source()
    respx.post(f'https://api.notion.com/v1/data_sources/{SOURCE}/query').respond(200, json={
        'results': [{'id': PAGE, 'url': 'https://notion.so/log'}], 'has_more': False})
    respx.get(f'https://api.notion.com/v1/blocks/{PAGE}/children').respond(200, json={
        'results': [{'type': 'bulleted_list_item', 'bulleted_list_item': {'rich_text': [{'plain_text': 'Shipped #42'}]}}], 'has_more': False})
    write = respx.patch(f'https://api.notion.com/v1/blocks/{PAGE}/children').mock(side_effect=httpx.ReadTimeout('uncertain'))
    result = asyncio.run(notion.notion_log('2026-10-13', ['Shipped #42', 'Reviewed #4']))
    assert 'error' in result and write.call_count == 1
    children = json.loads(write.calls[0].request.content)['children']
    assert len(children) == 1
    assert children[0]['bulleted_list_item']['rich_text'][0]['text']['content'] == 'Reviewed #4'


@respx.mock
def test_notion_concurrent_identical_entries_create_only_one_page():
    source()
    saved = []
    def query(request):
        return httpx.Response(200, json={'results': saved, 'has_more': False})
    def create(request):
        saved.append({'id': PAGE, 'url': 'https://notion.so/log'})
        return httpx.Response(200, json=saved[0])
    respx.post(f'https://api.notion.com/v1/data_sources/{SOURCE}/query').mock(side_effect=query)
    writes = respx.post('https://api.notion.com/v1/pages').mock(side_effect=create)
    respx.get(f'https://api.notion.com/v1/blocks/{PAGE}/children').respond(200, json={
        'results': [{'type': 'bulleted_list_item', 'bulleted_list_item': {'rich_text': [{'plain_text': 'Shipped #42'}]}}], 'has_more': False})
    async def scenario():
        return await asyncio.gather(*(notion.notion_log('2026-10-13', ['Shipped #42']) for _ in range(2)))
    results = asyncio.run(scenario())
    assert writes.call_count == 1 and sorted(r['added'] for r in results) == [0, 1]
