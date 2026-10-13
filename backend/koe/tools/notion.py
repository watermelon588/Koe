"""Append-only own daily log; current data sources API, not deprecated database query.
https://developers.notion.com/reference/post-page
https://developers.notion.com/reference/query-a-data-source
https://developers.notion.com/reference/patch-block-children
"""
import asyncio
from datetime import date as iso_date
from uuid import UUID

import httpx

from koe.config import settings
from koe import notion_service
from koe.tools.github import _error

# One backend worker; serialize query/create/append to avoid concurrent duplicate daily pages.
_locks: dict[asyncio.AbstractEventLoop, asyncio.Lock] = {}


def uuid(value: str) -> str:
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise ValueError('Configure a valid Notion database/data source ID.') from None


def bullet(text: str) -> dict:
    return {'object': 'block', 'type': 'bulleted_list_item',
            'bulleted_list_item': {'rich_text': [{'type': 'text', 'text': {'content': text}}]}}


async def notion_log(date: str, entries: list[str]) -> dict:
    try:
        if not isinstance(date, str) or iso_date.fromisoformat(date).isoformat() != date:
            raise ValueError('Use YYYY-MM-DD for the daily log date.')
        if not isinstance(entries, list) or not 1 <= len(entries) <= 50 or any(
                not isinstance(e, str) or not 1 <= len(e.strip()) <= 2000 for e in entries):
            raise ValueError('Supply 1–50 nonempty entries of at most 2,000 characters each.')
        entries = list(dict.fromkeys(e.strip() for e in entries))
        if not settings.notion_token:
            raise ValueError('Notion is not connected; set NOTION_TOKEN and a data source ID.')
        loop = asyncio.get_running_loop()
        lock = _locks.setdefault(loop, asyncio.Lock())
        async with lock, httpx.AsyncClient(timeout=15, headers={
                'Authorization': f'Bearer {settings.notion_token}', 'Notion-Version': '2026-03-11'}) as api:
            async def call(method, path, **kw):
                r = await api.request(method, 'https://api.notion.com/v1' + path, **kw)
                r.raise_for_status()
                return r.json()
            if settings.notion_data_source_id:
                source_id = uuid(settings.notion_data_source_id)
            else:
                database = await call('GET', '/databases/' + uuid(settings.notion_database_id))
                sources = database.get('data_sources', [])
                if len(sources) != 1:
                    raise ValueError('Set NOTION_DATA_SOURCE_ID explicitly; the database must have one source.')
                source_id = uuid(sources[0]['id'])
            schema = await call('GET', '/data_sources/' + source_id)
            properties = schema.get('properties', {})
            titles = [name for name, prop in properties.items() if prop.get('type') == 'title']
            if len(titles) != 1 or properties.get('Date', {}).get('type') != 'date':
                raise ValueError('Notion data source needs one title property and a Date property of type date.')
            daily_title = {'property': titles[0], 'title': {'equals': f'Koe — {date}'}}
            day_filter = {'property': 'Date', 'date': {'equals': date}}
            # Notion permits only two compound-filter levels: distribute the date
            # into each OR branch, rather than nesting AND -> OR -> AND.
            daily_filter = ({'or': [
                {'and': [day_filter, {'property': 'Koe type', 'select': {'equals': 'Daily log'}}]},
                {'and': [day_filter, {'property': 'Koe type', 'select': {'is_empty': True}}, daily_title]},
            ]} if properties.get('Koe type', {}).get('type') == 'select' else {'and': [day_filter, daily_title]})
            found = await call('POST', f'/data_sources/{source_id}/query', json={
                'filter': daily_filter, 'page_size': 2})
            pages = found.get('results')
            if (not isinstance(pages, list) or type(found.get('has_more')) is not bool or len(pages) > 1
                    or found['has_more'] or found.get('request_status', {}).get('type', 'complete') != 'complete'):
                raise ValueError('The daily page query is ambiguous or incomplete; check duplicate dates in Notion.')
            if not pages:
                page = await call('POST', '/pages', json={'parent': {'type': 'data_source_id', 'data_source_id': source_id},
                    'properties': {titles[0]: {'title': [{'type': 'text', 'text': {'content': f'Koe — {date}'}}]},
                                   'Date': {'date': {'start': date}},
                                   **({'Koe type': {'select': {'name': 'Daily log'}}} if 'Koe type' in properties else {})},
                    'children': [bullet(e) for e in entries]})
                return {'page_id': page['id'], 'url': page['url'], 'added': len(entries), 'date': date}
            page = pages[0]
            page_id = uuid(page['id'])
            existing, cursor = set(), None
            for _ in range(20):
                params = {'page_size': 100, **({'start_cursor': cursor} if cursor else {})}
                blocks = await call('GET', f'/blocks/{page_id}/children', params=params)
                if not isinstance(blocks.get('results'), list) or type(blocks.get('has_more')) is not bool:
                    raise ValueError('Notion returned incomplete blocks; no entries were appended.')
                for block in blocks['results']:
                    if block.get('type') == 'bulleted_list_item':
                        text = ''.join(r.get('plain_text', r.get('text', {}).get('content', ''))
                                       for r in block['bulleted_list_item'].get('rich_text', []))
                        existing.add(text)
                if not blocks.get('has_more'):
                    break
                cursor = blocks.get('next_cursor')
                if not cursor:
                    raise ValueError('Notion returned incomplete blocks; no entries were appended.')
            else:
                raise ValueError('Daily log exceeds the read limit; no entries were appended.')
            fresh = [e for e in entries if e not in existing]
            if fresh:
                await call('PATCH', f'/blocks/{page_id}/children', json={'children': [bullet(e) for e in fresh]})
            return {'page_id': page_id, 'url': page['url'], 'date': date, 'added': len(fresh)}
    except (ValueError, TypeError) as exc:
        return _error('notion_setup', str(exc), 'Check the configured daily log before retrying.')
    except (httpx.HTTPError, KeyError):
        return _error('notion_failed', 'Notion did not confirm the daily log operation.',
                      'Check the daily page before retrying; no automatic write retry was made.')


async def notion_read(query: str = '', kind: str = '', cursor: str = '', page_id: str = '') -> dict:
    try:
        return await notion_service.read(query, kind, cursor, page_id)
    except notion_service.NotionError as exc:
        return exc.result()


async def notion_save(*, request_id: str, **args) -> dict:
    try:
        result = await notion_service.save(**args, request_id=request_id)
        result['record_status'] = result.pop('status', None)
        return result
    except notion_service.NotionError as exc:
        return exc.result()


async def notion_archive(*, request_id: str, **args) -> dict:
    try:
        result = await notion_service.archive(**args, request_id=request_id)
        result['record_status'] = result.pop('status', None)
        return result
    except notion_service.NotionError as exc:
        return exc.result()
