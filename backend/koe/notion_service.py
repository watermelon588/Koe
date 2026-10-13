"""Scoped Notion workspace operations. Never retry an uncertain mutation.

https://developers.notion.com/reference/query-a-data-source
https://developers.notion.com/reference/patch-page
"""
import asyncio
import math
import re
from contextlib import asynccontextmanager
from datetime import date as Date, datetime
from uuid import UUID
from urllib.parse import urlparse

import httpx

from koe.config import settings
from koe import identity

VERSION = '2026-03-11'
KINDS = ('Daily log', 'Task', 'Meeting', 'Note')
STATUSES = ('Open', 'In progress', 'Done')
WORKFLOW = {
    'Koe type': {'select': {'options': [{'name': k} for k in KINDS]}},
    'Koe status': {'select': {'options': [{'name': s} for s in STATUSES]}},
    'Koe action ID': {'rich_text': {}},
}
EDITABLE_FIELDS = {'rich_text', 'number', 'checkbox', 'date', 'url', 'email', 'select', 'multi_select', 'status'}
_locks: dict[asyncio.AbstractEventLoop, asyncio.Lock] = {}


class NotionError(Exception):
    def __init__(self, message, code='notion_failed', hint='Check Notion before retrying an uncertain write.'):
        super().__init__(message)
        self.code, self.hint = code, hint

    def result(self):
        return {'error': {'code': self.code, 'message': str(self), 'hint': self.hint}}


def uid(value):
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise NotionError('Use a valid Notion database, source or page ID.', 'notion_setup') from None


def configured_destination():
    return ('source:' + uid(settings.notion_data_source_id) if settings.notion_data_source_id
            else 'database:' + uid(settings.notion_database_id))


def lock():
    return _locks.setdefault(asyncio.get_running_loop(), asyncio.Lock())


@asynccontextmanager
async def client():
    if not identity.is_owner():
        raise NotionError('Notion is currently connected for the owner only.', 'notion_scope')
    if not settings.notion_token:
        raise NotionError('Connect Notion with NOTION_TOKEN and a database ID.', 'notion_setup')
    async with httpx.AsyncClient(timeout=15, trust_env=False, headers={
        'Authorization': f'Bearer {settings.notion_token}', 'Notion-Version': VERSION,
    }) as api:
        yield api


async def call(api, method, path, **kwargs):
    try:
        r = await api.request(method, 'https://api.notion.com/v1' + path, **kwargs)
        if r.status_code == 429:
            raise NotionError('Notion is rate limited. Wait briefly, then refresh; no write was retried.', 'notion_rate_limit')
        if r.status_code in (401, 403, 404):
            raise NotionError('Notion access was refused. Check the token, connection capabilities and database sharing.', 'notion_access')
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, dict):
            raise ValueError()
        return data
    except (httpx.HTTPError, ValueError):
        raise NotionError('Notion did not confirm the operation. No write was retried.') from None


async def source(api):
    if settings.notion_data_source_id:
        source_id = uid(settings.notion_data_source_id)
    else:
        database = await call(api, 'GET', '/databases/' + uid(settings.notion_database_id))
        sources = database.get('data_sources', [])
        if len(sources) != 1:
            raise NotionError('Set NOTION_DATA_SOURCE_ID explicitly: this database must resolve to one source.', 'notion_setup')
        source_id = uid(sources[0].get('id'))
    schema = await call(api, 'GET', '/data_sources/' + source_id)
    props = schema.get('properties', {})
    if not isinstance(props, dict) or any(not isinstance(v, dict) for v in props.values()):
        raise NotionError('Notion returned an invalid database schema.', 'notion_incomplete')
    titles = [k for k, v in props.items() if v.get('type') == 'title']
    if len(titles) != 1:
        raise NotionError('Notion needs exactly one title property.', 'notion_setup')
    return source_id, schema, titles[0]


def missing_properties(schema):
    props = schema.get('properties', {})
    expected = {'Date': 'date', 'Koe type': 'select', 'Koe status': 'select', 'Koe action ID': 'rich_text'}
    conflicts = [name for name, kind in expected.items() if name in props and props[name].get('type') != kind]
    if conflicts:
        raise NotionError('Incompatible property types: ' + ', '.join(conflicts) + '. Existing properties were not changed.', 'notion_setup')
    return [name for name in expected if name not in props]


async def status():
    async with client() as api:
        source_id, schema, title = await source(api)
        missing = missing_properties(schema)
        return {'connected': True, 'workflow_ready': not missing, 'missing_properties': missing,
                'source_id': source_id, 'title_property': title,
                'database_url': 'https://www.notion.so/' + uid(settings.notion_database_id).replace('-', '') if settings.notion_database_id else '',
                'name': plain(schema.get('title', [])) or 'Notion workspace',
                'schema': {k: v.get('type') for k, v in schema.get('properties', {}).items()}}


async def setup():
    """Explicit owner configuration action: add missing fields, never convert existing ones."""
    async with lock(), client() as api:
        source_id, schema, _ = await source(api)
        missing = missing_properties(schema)
        additions = {name: {'date': {}} if name == 'Date' else WORKFLOW[name] for name in missing}
        if additions:
            await call(api, 'PATCH', '/data_sources/' + source_id, json={'properties': additions})
        return {'added': missing, 'message': 'Database ready. Existing properties and records retained.'}


def optional_fields(fields):
    if fields is None:
        return {}
    if not isinstance(fields, dict) or len(fields) > 20:
        raise ValueError('Use at most 20 optional Notion properties.')
    for key, value in fields.items():
        if not isinstance(key, str) or not 1 <= len(key) <= 100 or key.casefold() in {k.casefold() for k in ('Date', *WORKFLOW)}:
            raise ValueError('Optional fields cannot replace workflow properties or the Koe action ID.')
        if value is not None and type(value) not in (str, int, float, bool, list):
            raise ValueError('Use text, numbers, booleans, option-name lists or null for optional properties.')
        if isinstance(value, str) and len(value) > 2000:
            raise ValueError('Optional property text must be at most 2000 characters.')
        if type(value) in (int, float) and (not math.isfinite(value) or abs(value) > 1e15):
            raise ValueError('Optional property numbers must be finite and at most 1e15 in magnitude.')
        if isinstance(value, list) and (len(value) > 30 or any(not isinstance(v, str) or len(v) > 100 for v in value)):
            raise ValueError('Use at most 30 existing option names.')
    return dict(fields)


def field_contract(schema, fields):
    props, result = schema['properties'], {}
    protected_ids = {v.get('id') for k, v in props.items() if k in ('Date', *WORKFLOW) or v.get('type') == 'title'}
    for key in fields:
        prop = props.get(key, {})
        kind, prop_id = prop.get('type'), prop.get('id')
        if kind not in EDITABLE_FIELDS or not isinstance(prop_id, str) or not prop_id or prop_id in protected_ids:
            raise NotionError('An optional property is unknown, reserved or read-only. Read notion_schema.', 'notion_property')
        contract = {'id': prop_id, 'type': kind}
        if kind in ('select', 'multi_select', 'status'):
            options = prop.get(kind, {}).get('options', [])
            if not isinstance(options, list) or any(not isinstance(o, dict) or not isinstance(o.get('name'), str)
                or not isinstance(o.get('id'), str) for o in options):
                raise NotionError('Notion returned incomplete property options.', 'notion_incomplete')
            contract['options'] = {o['name']: o['id'] for o in options}
            if len(contract['options']) != len(options):
                raise NotionError('Notion option names are ambiguous.', 'notion_incomplete')
        result[key] = contract
    return result


def field_payload(fields, contracts):
    result = {}
    for key, value in fields.items():
        contract = contracts[key]
        kind = contract['type']
        if kind == 'rich_text' and (value is None or isinstance(value, str)):
            encoded = rich(value or '')
        elif kind == 'number' and (value is None or type(value) in (int, float)):
            encoded = value
        elif kind == 'checkbox' and type(value) is bool:
            encoded = value
        elif kind in ('select', 'status') and (value is None or isinstance(value, str) and value in contract['options']):
            encoded = {'id': contract['options'][value]} if value is not None else None
        elif kind == 'multi_select' and isinstance(value, list) and all(v in contract['options'] for v in value):
            encoded = [{'id': contract['options'][v]} for v in dict.fromkeys(value)]
        elif kind == 'date' and (value is None or isinstance(value, str)):
            if value is not None:
                if 'T' in value:
                    if datetime.fromisoformat(value.replace('Z', '+00:00')).utcoffset() is None:
                        raise ValueError('Optional date timestamps require an explicit offset.')
                elif Date.fromisoformat(value).isoformat() != value:
                    raise ValueError('Optional dates require YYYY-MM-DD.')
            encoded = {'start': value} if value is not None else None
        elif kind == 'email' and (value is None or isinstance(value, str) and re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value)):
            encoded = value
        elif kind == 'url' and (value is None or isinstance(value, str) and urlparse(value).scheme in ('http', 'https')
                               and urlparse(value).hostname and not urlparse(value).username):
            encoded = value
        else:
            raise ValueError(f'Invalid value for Notion property {key}; use its exact type and existing options.')
        result[contract['id']] = {kind: encoded}
    return result


async def freeze_fields(args):
    async with client() as api:
        if args['destination'] != configured_destination():
            raise NotionError('Notion destination changed; propose again.', 'notion_destination')
        source_id, schema, _ = await source(api)
        contracts = field_contract(schema, args['fields'])
        field_payload(args['fields'], contracts)  # validate before a proposal is stored
        return {**args, 'expected_properties': contracts, 'expected_source': source_id}


async def schema_fields():
    async with client() as api:
        source_id, schema, _ = await source(api)
        editable, protected = [], []
        props = schema['properties']
        for name in list(props)[:100]:
            try:
                contract = field_contract(schema, {name: None})[name]
                editable.append({'name': name, 'type': contract['type'], 'options': list(contract.get('options', {}))})
            except NotionError:
                protected.append(name)
        return {'source_id': source_id, 'editable': editable, 'read_only_or_reserved': protected,
            'partial': len(props) > 100, 'note': 'Exact existing names/options only. Computed results and workflow fields cannot be overridden. No properties are created.'}


def plain(rich):
    return ''.join(r.get('plain_text', r.get('text', {}).get('content', '')) for r in rich if isinstance(r, dict))


def rich(text):
    return [{'type': 'text', 'text': {'content': text}}] if text else []


def display(page, title):
    p = page.get('properties', {})
    name = plain(p.get(title, {}).get('title', [])) or 'Untitled'
    day = p.get('Date', {}).get('date')
    legacy_log = bool(day and name == 'Koe — ' + day.get('start', '')[:10])
    return {'id': uid(page.get('id')), 'title': name,
            'date': day, 'kind': (p.get('Koe type', {}).get('select') or {}).get('name', 'Daily log' if legacy_log else 'Note'),
            'status': (p.get('Koe status', {}).get('select') or {}).get('name', 'Open'),
            'url': safe_url(page.get('url', '')), 'last_edited_time': page.get('last_edited_time', ''),
            'in_trash': bool(page.get('in_trash')), 'fields': {
                key: plain(value.get('rich_text', [])) if value.get('type') == 'rich_text' else value.get(value.get('type'))
                for key, value in p.items() if isinstance(value, dict) and key not in ('Date', *WORKFLOW)
                and value.get('type') in EDITABLE_FIELDS}}


def safe_url(value):
    from urllib.parse import urlparse
    try:
        url = urlparse(value)
        if url.scheme == 'https' and not url.username and not url.password and url.hostname and (url.hostname in ('notion.so', 'www.notion.so', 'notion.site', 'www.notion.site', 'notion.com', 'www.notion.com')
                or url.hostname.endswith('.notion.site')):
            return value
    except (TypeError, ValueError):
        pass
    return ''


def query_rows(data):
    if (not isinstance(data.get('results'), list) or any(not isinstance(row, dict) for row in data['results'])
            or type(data.get('has_more')) is not bool or not isinstance(data.get('request_status', {}), dict)
            or data.get('request_status', {}).get('type', 'complete') != 'complete'):
        raise NotionError('Notion returned an incomplete query. No changes were made.', 'notion_incomplete')
    if data['has_more'] and not isinstance(data.get('next_cursor'), str):
        raise NotionError('Notion returned an invalid pagination cursor.', 'notion_incomplete')
    return data['results']


async def scoped_page(api, page_id, source_id):
    page = await call(api, 'GET', '/pages/' + uid(page_id))
    parent = page.get('parent', {})
    if parent.get('type') != 'data_source_id' or uid(parent.get('data_source_id')) != source_id:
        raise NotionError('This page is outside the configured Notion workspace.', 'notion_scope')
    if page.get('in_trash') or page.get('is_archived'):
        raise NotionError('This record is archived or in the trash.', 'notion_archived')
    return page


async def blocks(api, page_id):
    rows, cursor, truncated = [], None, False
    for _ in range(5):
        data = await call(api, 'GET', f'/blocks/{uid(page_id)}/children', params={'page_size': 100, **({'start_cursor': cursor} if cursor else {})})
        for block in query_rows(data):
            kind = block.get('type', '')
            content = block.get(kind, {})
            rows.append({'id': block.get('id', ''), 'type': kind, 'text': plain(content.get('rich_text', []))[:4000],
                         'checked': content.get('checked'), 'has_children': bool(block.get('has_children'))})
        truncated = data['has_more']
        if not truncated:
            break
        cursor = data['next_cursor']
    return rows, truncated


async def read(query='', kind='', cursor='', page_id=''):
    if not isinstance(query, str) or len(query) > 200 or kind not in ('', *KINDS) or not isinstance(cursor, str) or len(cursor) > 500:
        raise NotionError('Use a shorter search and a valid record type.', 'notion_arguments')
    async with client() as api:
        source_id, schema, title = await source(api)
        if page_id:
            page = await scoped_page(api, page_id, source_id)
            content, truncated = await blocks(api, page_id)
            return {'page': display(page, title), 'blocks': content, 'truncated': truncated,
                    'preview_note': 'Nested and non-text blocks are shown as labels; open Notion for the full page.'}
        filters = []
        if query:
            filters.append({'property': title, 'title': {'contains': query}})
        if kind:
            if schema.get('properties', {}).get('Koe type', {}).get('type') != 'select':
                raise NotionError('Prepare the workspace before filtering by record type.', 'notion_setup')
            filters.append({'property': 'Koe type', 'select': {'equals': kind}})
        body = {'page_size': 25, 'sorts': [{'timestamp': 'last_edited_time', 'direction': 'descending'}]}
        if filters:
            body['filter'] = {'and': filters} if len(filters) > 1 else filters[0]
        if cursor:
            body['start_cursor'] = cursor
        data = await call(api, 'POST', f'/data_sources/{source_id}/query', json=body)
        rows = query_rows(data)
        return {'pages': [display(p, title) for p in rows if p.get('object', 'page') == 'page'],
                'next_cursor': data.get('next_cursor'), 'has_more': data['has_more']}


def prepare_save(title, date, kind='Note', status='Open', body='', end='', page_id='', expected_edited='', fields=None):
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 200 or kind not in ('Task', 'Meeting', 'Note') or status not in STATUSES:
        raise ValueError('Use a title of 1–200 characters, type Task/Meeting/Note and a valid status.')
    if not isinstance(body, str) or len(body) > 6000:
        raise ValueError('Keep notes within 6,000 characters.')
    try:
        if kind == 'Meeting':
            start, finish = datetime.fromisoformat(date), datetime.fromisoformat(end)
            if start.utcoffset() is None or finish.utcoffset() is None or finish <= start:
                raise ValueError()
        else:
            if Date.fromisoformat(date).isoformat() != date or end:
                raise ValueError()
    except (ValueError, TypeError):
        raise ValueError('Use YYYY-MM-DD for tasks/notes; meeting records need start/end timestamps with offsets and end after start.') from None
    if page_id and (not isinstance(expected_edited, str) or not expected_edited):
        raise ValueError('Read the record first and provide its last_edited_time before editing.')
    return {'title': title.strip(), 'date': date, 'kind': kind, 'status': status, 'body': body.strip(), 'end': end,
            'page_id': uid(page_id) if page_id else '', 'expected_edited': expected_edited, 'destination': configured_destination(),
            'fields': optional_fields(fields)}


def prepare_archive(page_id, expected_edited, title):
    if not expected_edited or not isinstance(title, str) or not title.strip():
        raise ValueError('Read the record first; title and last_edited_time are required.')
    return {'page_id': uid(page_id), 'expected_edited': expected_edited, 'title': title, 'destination': configured_destination()}


def paragraphs(text):
    # Keep within Notion's 2,000-character rich-text item limit.
    return [{'object': 'block', 'type': 'paragraph', 'paragraph': {'rich_text': rich(text[i:i + 1800])}}
            for i in range(0, len(text), 1800)]


async def save(*, title, date, kind, status, body, end, page_id, expected_edited, destination, request_id,
               fields=None, expected_properties=None, expected_source=None):
    prepared = prepare_save(title, date, kind, status, body, end, page_id, expected_edited, fields)
    if destination != prepared['destination']:
        raise NotionError('The Notion destination changed. Propose this action again.', 'notion_destination')
    async with lock(), client() as api:
        source_id, schema, title_key = await source(api)
        if missing_properties(schema):
            raise NotionError('Prepare the Notion workspace first; required workflow properties are missing.', 'notion_setup')
        extra_props = {}
        if prepared['fields']:
            contracts = field_contract(schema, prepared['fields'])
            if expected_properties != contracts or expected_source != source_id:
                raise NotionError('Optional property schema changed or was not approved. Propose again.', 'notion_stale')
            try:
                extra_props = field_payload(prepared['fields'], contracts)
            except ValueError:
                raise NotionError('Optional property values no longer match the schema.', 'notion_property') from None
        props = {title_key: {'title': rich(title)}, 'Date': {'date': {'start': date, **({'end': end} if end else {})}},
                 'Koe type': {'select': {'name': kind}}, 'Koe status': {'select': {'name': status}},
                 'Koe action ID': {'rich_text': rich(request_id)}}
        props.update(extra_props)
        if page_id:
            page = await scoped_page(api, page_id, source_id)
            if page.get('last_edited_time') != expected_edited:
                raise NotionError('The record changed since the preview. Refresh it and propose again.', 'notion_stale')
            await call(api, 'PATCH', '/pages/' + page_id, json={'properties': props})
            if body:
                await call(api, 'PATCH', f'/blocks/{page_id}/children', json={'children': paragraphs('Update\n' + body)})
            page = await call(api, 'GET', '/pages/' + page_id)
        else:
            data = await call(api, 'POST', f'/data_sources/{source_id}/query', json={
                'filter': {'property': 'Koe action ID', 'rich_text': {'equals': request_id}}, 'page_size': 2})
            existing = query_rows(data)
            if len(existing) > 1 or data['has_more']:
                raise NotionError('Multiple records match this action. Inspect Notion before retrying.', 'notion_ambiguous')
            if existing:
                page = existing[0]
            else:
                page = await call(api, 'POST', '/pages', json={'parent': {'type': 'data_source_id', 'data_source_id': source_id},
                                  'properties': props, 'children': paragraphs(body)})
        return {**display(page, title_key), 'source_id': source_id,
                'message': 'Meeting notes saved; no Calendar slot was booked.' if kind == 'Meeting' else 'Record saved.'}


async def archive(*, page_id, expected_edited, title, destination, request_id):
    if destination != configured_destination():
        raise NotionError('The Notion destination changed. Propose again.', 'notion_destination')
    async with lock(), client() as api:
        source_id, _, title_key = await source(api)
        page = await scoped_page(api, page_id, source_id)
        if page.get('last_edited_time') != expected_edited or display(page, title_key)['title'] != title:
            raise NotionError('The record changed since the preview. Refresh and propose again.', 'notion_stale')
        # Notion trash is reversible; never erase page content or hard-delete.
        page = await call(api, 'PATCH', '/pages/' + uid(page_id), json={'in_trash': True})
        return {**display(page, title_key), 'message': 'Moved to Notion trash. You can restore it in Notion.'}
