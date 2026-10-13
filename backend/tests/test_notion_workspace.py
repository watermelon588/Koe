"""Notion workflow contracts at the HTTP boundary; never use owner credentials."""
import asyncio
import json

import httpx
import pytest
import respx

from koe import notion_service as service
from koe.config import settings

SOURCE = '11111111-1111-1111-1111-111111111111'
PAGE = '22222222-2222-2222-2222-222222222222'
OTHER_SOURCE = '33333333-3333-3333-3333-333333333333'
ACTION = '44444444-4444-4444-4444-444444444444'
EDITED = '2026-10-13T10:00:00.000Z'
ROOT = 'https://api.notion.com/v1'


@pytest.fixture(autouse=True)
def account(monkeypatch):
    monkeypatch.setattr(settings, 'notion_token', 'fake-notion-token')
    monkeypatch.setattr(settings, 'notion_database_id', '')
    monkeypatch.setattr(settings, 'notion_data_source_id', SOURCE)


def schema(*, workflow=True):
    properties = {
        'Name': {'id': 'title', 'name': 'Name', 'type': 'title', 'title': {}},
        'Date': {'id': 'date', 'name': 'Date', 'type': 'date', 'date': {}},
    }
    if workflow:
        properties.update({
            'Koe type': {'id': 'type', 'name': 'Koe type', 'type': 'select', 'select': {
                'options': [{'id': kind, 'name': kind} for kind in ['Daily log', 'Note', 'Task', 'Meeting']]}},
            'Koe status': {'id': 'status', 'name': 'Koe status', 'type': 'select', 'select': {
                'options': [{'id': status, 'name': status} for status in ['Open', 'In progress', 'Done', 'Cancelled']]}},
            'Koe action ID': {'id': 'action', 'name': 'Koe action ID', 'type': 'rich_text', 'rich_text': {}},
        })
    return {'object': 'data_source', 'id': SOURCE,
            'parent': {'type': 'database_id', 'database_id': OTHER_SOURCE},
            'title': [{'type': 'text', 'plain_text': 'Koe workspace', 'text': {'content': 'Koe workspace'}}],
            'properties': properties}


def page(*, source=SOURCE, edited=EDITED, title='Review project', action=''):
    return {'object': 'page', 'id': PAGE,
            'parent': {'type': 'data_source_id', 'data_source_id': source},
            'url': 'https://www.notion.so/' + PAGE.replace('-', ''),
            'archived': False, 'in_trash': False, 'last_edited_time': edited,
            'properties': {
                'Name': {'id': 'title', 'type': 'title', 'title': [
                    {'type': 'text', 'plain_text': title, 'text': {'content': title}}]},
                'Date': {'id': 'date', 'type': 'date', 'date': {'start': '2026-10-13', 'end': None}},
                'Koe type': {'id': 'type', 'type': 'select', 'select': {'name': 'Task'}},
                'Koe status': {'id': 'status', 'type': 'select', 'select': {'name': 'Open'}},
                'Koe action ID': {'id': 'action', 'type': 'rich_text', 'rich_text': [
                    {'type': 'text', 'plain_text': action, 'text': {'content': action}}] if action else []},
            }}


def connect(*, workflow=True):
    return respx.get(f'{ROOT}/data_sources/{SOURCE}').respond(200, json=schema(workflow=workflow))


def no_writes():
    return not any(call.request.method in {'PATCH', 'DELETE'} or
                   (call.request.method == 'POST' and call.request.url.path == '/v1/pages')
                   for call in respx.calls)


@pytest.mark.parametrize('title,kind', [('Existing personal note', 'Note'), ('Koe — 2026-10-13', 'Daily log')])
def test_untyped_legacy_records_do_not_all_become_daily_logs(title, kind):
    record = page(title=title)
    record['properties']['Koe type']['select'] = None
    assert service.display(record, 'Name')['kind'] == kind


@respx.mock
def test_status_reports_connected_database_with_missing_workflow_fields():
    connect(workflow=False)
    result = asyncio.run(service.status())
    assert result['connected'] is True
    assert result['workflow_ready'] is False
    assert set(result['missing_properties']) == {'Koe type', 'Koe status', 'Koe action ID'}
    assert no_writes()


@respx.mock
def test_status_reports_ready_only_when_required_schema_exists():
    connect()
    result = asyncio.run(service.status())
    assert result['connected'] is True and result['workflow_ready'] is True
    assert not result['missing_properties']


@respx.mock
def test_listing_passes_cursor_and_preserves_has_more():
    connect()
    listing = respx.post(f'{ROOT}/data_sources/{SOURCE}/query').respond(200, json={
        'object': 'list', 'results': [page()], 'has_more': True, 'next_cursor': 'next-page',
        'request_status': {'type': 'complete'}})
    result = asyncio.run(service.read(query='Review', kind='Task', cursor='previous-page'))
    assert result['has_more'] is True and result['next_cursor'] == 'next-page'
    assert len(result['pages']) == 1
    assert json.loads(listing.calls[0].request.content)['start_cursor'] == 'previous-page'
    assert no_writes()


@pytest.mark.parametrize('response', [
    {},
    {'results': [], 'has_more': True, 'next_cursor': None},
    {'results': [], 'has_more': False, 'request_status': {'type': 'incomplete'}},
])
@respx.mock
def test_malformed_or_incomplete_listing_never_looks_like_an_empty_success(response):
    connect()
    respx.post(f'{ROOT}/data_sources/{SOURCE}/query').respond(200, json=response)
    with pytest.raises(service.NotionError):
        asyncio.run(service.read())
    assert no_writes()


@respx.mock
def test_detail_reads_page_content_without_treating_it_as_instructions():
    connect()
    respx.get(f'{ROOT}/pages/{PAGE}').respond(200, json=page())
    respx.get(f'{ROOT}/blocks/{PAGE}/children').respond(200, json={
        'object': 'list', 'results': [{'object': 'block', 'id': ACTION, 'type': 'paragraph',
            'has_children': True, 'paragraph': {'rich_text': [{'type': 'text',
                'plain_text': 'Existing notes', 'text': {'content': 'Existing notes'}}]}}],
        'has_more': False, 'next_cursor': None})
    result = asyncio.run(service.read(page_id=PAGE))
    assert result['page']['id'] == PAGE
    assert result['blocks']
    assert no_writes()


@respx.mock
def test_detail_refuses_page_outside_configured_source_before_reading_blocks():
    connect()
    respx.get(f'{ROOT}/pages/{PAGE}').respond(200, json=page(source=OTHER_SOURCE))
    with pytest.raises(service.NotionError):
        asyncio.run(service.read(page_id=PAGE))
    assert no_writes()
    assert not any('/blocks/' in str(call.request.url) for call in respx.calls)


@pytest.mark.parametrize('date,end', [
    ('2026-10-13', ''),
    ('2026-10-13T15:00:00', '2026-10-13T16:00:00'),
    ('2026-10-13T15:00:00+05:30', '2026-10-13T14:00:00+05:30'),
])
def test_meeting_requires_explicit_offsets_and_a_later_end(date, end):
    with pytest.raises((ValueError, service.NotionError)):
        service.prepare_save('Review', date, kind='Meeting', end=end)


def test_meeting_preparation_preserves_explicit_start_end_without_booking_calendar():
    result = service.prepare_save('Review', '2026-10-13T15:00:00+05:30',
                                  kind='Meeting', end='2026-10-13T16:00:00+05:30')
    assert result['date'] == '2026-10-13T15:00:00+05:30'
    assert result['end'] == '2026-10-13T16:00:00+05:30'
    assert result['kind'] == 'Meeting'


@respx.mock
def test_create_task_has_typed_metadata_and_action_identity():
    connect()
    respx.post(f'{ROOT}/data_sources/{SOURCE}/query').respond(200, json={
        'results': [], 'has_more': False, 'next_cursor': None})
    create = respx.post(f'{ROOT}/pages').respond(200, json=page(action=ACTION))
    prepared = service.prepare_save('Review project', '2026-10-13', kind='Task', body='Check open questions')
    asyncio.run(service.save(**prepared, request_id=ACTION))
    payload = json.loads(create.calls[0].request.content)
    assert payload['parent']['data_source_id'] == SOURCE
    assert payload['properties']['Koe type']['select']['name'] == 'Task'
    assert payload['properties']['Koe status']['select']['name'] == 'Open'
    assert payload['properties']['Koe action ID']['rich_text'][0]['text']['content'] == ACTION
    assert payload['children']


@respx.mock
def test_replaying_action_identity_returns_existing_page_without_creating_duplicate():
    connect()
    respx.post(f'{ROOT}/data_sources/{SOURCE}/query').respond(200, json={
        'results': [page(action=ACTION)], 'has_more': False, 'next_cursor': None})
    prepared = service.prepare_save('Review project', '2026-10-13', kind='Task')
    result = asyncio.run(service.save(**prepared, request_id=ACTION))
    assert result
    assert no_writes()


@respx.mock
def test_missing_required_schema_prevents_creating_generic_note_that_loses_task_metadata():
    connect(workflow=False)
    prepared = service.prepare_save('Review project', '2026-10-13', kind='Task')
    with pytest.raises(service.NotionError):
        asyncio.run(service.save(**prepared, request_id=ACTION))
    assert no_writes()


@respx.mock
def test_changed_configured_destination_invalidates_saved_proposal(monkeypatch):
    prepared = service.prepare_save('Review project', '2026-10-13', kind='Task')
    monkeypatch.setattr(settings, 'notion_data_source_id', OTHER_SOURCE)
    with pytest.raises((ValueError, service.NotionError)):
        asyncio.run(service.save(**prepared, request_id=ACTION))
    assert no_writes()


@respx.mock
def test_uncertain_create_timeout_is_never_retried():
    connect()
    respx.post(f'{ROOT}/data_sources/{SOURCE}/query').respond(200, json={
        'results': [], 'has_more': False, 'next_cursor': None})
    create = respx.post(f'{ROOT}/pages').mock(side_effect=httpx.ReadTimeout('uncertain'))
    prepared = service.prepare_save('Review project', '2026-10-13', kind='Task')
    with pytest.raises(service.NotionError):
        asyncio.run(service.save(**prepared, request_id=ACTION))
    assert create.call_count == 1


@respx.mock
def test_stale_page_edit_is_rejected_before_any_patch():
    connect()
    respx.get(f'{ROOT}/pages/{PAGE}').respond(200, json=page(edited='2026-10-13T10:01:00.000Z'))
    prepared = service.prepare_save('Review project', '2026-10-13', kind='Task',
                                    page_id=PAGE, expected_edited=EDITED)
    with pytest.raises(service.NotionError):
        asyncio.run(service.save(**prepared, request_id=ACTION))
    assert no_writes()


@respx.mock
def test_update_preserves_existing_content_and_appends_requested_notes():
    connect()
    respx.get(f'{ROOT}/pages/{PAGE}').respond(200, json=page())
    update = respx.patch(f'{ROOT}/pages/{PAGE}').respond(200, json=page(edited='2026-10-13T10:01:00.000Z'))
    append = respx.patch(f'{ROOT}/blocks/{PAGE}/children').respond(200, json={
        'object': 'list', 'results': [], 'has_more': False, 'next_cursor': None})
    prepared = service.prepare_save('Review project', '2026-10-13', kind='Task',
                                    body='Additional notes', page_id=PAGE, expected_edited=EDITED)
    asyncio.run(service.save(**prepared, request_id=ACTION))
    assert 'erase_content' not in json.loads(update.calls[0].request.content)
    assert append.call_count == 1
    assert json.loads(append.calls[0].request.content)['children']
    assert not any(call.request.method == 'DELETE' for call in respx.calls)


@respx.mock
def test_archive_is_reversible_trash_and_scoped_to_existing_page():
    connect()
    respx.get(f'{ROOT}/pages/{PAGE}').respond(200, json=page())
    update = respx.patch(f'{ROOT}/pages/{PAGE}').respond(200, json={**page(), 'in_trash': True})
    prepared = service.prepare_archive(PAGE, EDITED, 'Review project')
    asyncio.run(service.archive(**prepared, request_id=ACTION))
    assert json.loads(update.calls[0].request.content)['in_trash'] is True
    assert not any(call.request.method == 'DELETE' for call in respx.calls)


@respx.mock
def test_archive_refuses_an_outside_page_even_when_integration_has_permission():
    connect()
    respx.get(f'{ROOT}/pages/{PAGE}').respond(200, json=page(source=OTHER_SOURCE))
    prepared = service.prepare_archive(PAGE, EDITED, 'Review project')
    with pytest.raises(service.NotionError):
        asyncio.run(service.archive(**prepared, request_id=ACTION))
    assert no_writes()


@pytest.mark.parametrize('current', [
    page(edited='2026-10-13T10:01:00.000Z'),
    page(title='A different record'),
])
@respx.mock
def test_archive_refuses_page_changed_after_preview(current):
    connect()
    respx.get(f'{ROOT}/pages/{PAGE}').respond(200, json=current)
    prepared = service.prepare_archive(PAGE, EDITED, 'Review project')
    with pytest.raises(service.NotionError):
        asyncio.run(service.archive(**prepared, request_id=ACTION))
    assert no_writes()


def test_agent_notion_wrappers_expose_read_save_and_archive():
    from koe.tools import notion
    assert callable(notion.notion_read)
    assert callable(notion.notion_save)
    assert callable(notion.notion_archive)
