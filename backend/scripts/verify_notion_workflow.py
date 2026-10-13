"""Live owner-authorized acceptance: uniquely labeled synthetic records, trashed afterward.

No Calendar events, invitations, messages or unrelated Notion pages are modified.
Run from backend/: python -m scripts.verify_notion_workflow
"""
import asyncio
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import psycopg
import logging
from fastapi.testclient import TestClient

from koe import notion_service, store
from koe.config import settings
from koe.main import app
from koe.tools.notion import notion_log


def main():
    logging.getLogger('httpx').setLevel(logging.WARNING)
    original_owner = settings.koe_owner_id
    test_owner = f'koe-notion-verify-{uuid4()}'
    settings.koe_owner_id = test_owner
    headers = {'Authorization': f'Bearer {settings.koe_access_token}'}
    created = []
    failed = False
    title = f'Koe workflow verification {uuid4().hex[:8]}'
    day = datetime.now(ZoneInfo(settings.timezone)).date().isoformat()

    def result(response):
        assert response.status_code == 200, 'HTTP acceptance failed'
        value = response.json()
        assert 'error' not in value, 'Provider acceptance failed'
        return value

    try:
        with TestClient(app) as api:
            assert api.get('/api/notion/status').status_code == 401
            status = result(api.get('/api/notion/status', headers=headers))
            if not status['workflow_ready']:
                result(api.post('/api/notion/setup', headers=headers, json={'confirm': True}))
                assert result(api.get('/api/notion/status', headers=headers))['workflow_ready']
            print('PASS Notion connection and additive workflow schema.')
            proposal = result(api.post('/api/notion/proposals', headers=headers, json={
                'tool': 'notion_save', 'args': {'title': title, 'kind': 'Task', 'date': day, 'body': 'Synthetic end-to-end check. No actual work scheduled.'}}))
            pending = proposal['pending_action']
            assert not result(api.get('/api/notion/records', headers=headers, params={'query': title}))['pages']
            print('PASS preview creates no Notion record before approval.')
            saved = result(api.post('/api/notion/approvals/' + pending['id'], headers=headers, json={'approve': True}))['result']
            if saved.get('id'):
                created.append(saved['id'])
            assert saved.get('status') == 'executed' and 'error' not in saved
            page_id = saved['id']
            replay = result(api.post('/api/notion/approvals/' + pending['id'], headers=headers, json={'approve': True}))['result']
            assert 'error' in replay
            detail = result(api.get('/api/notion/records/' + page_id, headers=headers))
            assert detail['page']['title'] == title and detail['blocks']
            print('PASS approved create, replay rejection and real record preview.')
            proposal = result(api.post('/api/notion/proposals', headers=headers, json={'tool': 'notion_save', 'args': {
                'title': title, 'kind': 'Task', 'date': day, 'status': 'Done', 'body': 'Verification completed.',
                'page_id': page_id, 'expected_edited': detail['page']['last_edited_time']}}))
            updated = result(api.post('/api/notion/approvals/' + proposal['pending_action']['id'], headers=headers, json={'approve': True}))['result']
            assert updated.get('status') == 'executed' and 'error' not in updated
            detail = result(api.get('/api/notion/records/' + page_id, headers=headers))
            assert detail['page']['status'] == 'Done' and len(detail['blocks']) >= 2
            print('PASS approved task update and append-only notes.')
            proposal = result(api.post('/api/notion/proposals', headers=headers, json={'tool': 'notion_archive', 'args': {
                'page_id': page_id, 'title': title, 'expected_edited': detail['page']['last_edited_time']}}))
            archived = result(api.post('/api/notion/approvals/' + proposal['pending_action']['id'], headers=headers, json={'approve': True}))['result']
            assert archived.get('status') == 'executed' and archived['in_trash']
            created.remove(page_id)
            print('PASS approved reversible trash; synthetic task removed from active records.')
            # Meeting records document a date range; they never invoke Calendar booking tools.
            for kind in ('Meeting', 'Note'):
                date = day + 'T15:00:00+05:30' if kind == 'Meeting' else day
                args = {'title': title + ' ' + kind, 'date': date, 'kind': kind, 'body': 'Synthetic record; no calendar booking or invitation.'}
                if kind == 'Meeting':
                    args['end'] = day + 'T15:30:00+05:30'
                proposal = result(api.post('/api/notion/proposals', headers=headers, json={'tool': 'notion_save', 'args': args}))
                saved = result(api.post('/api/notion/approvals/' + proposal['pending_action']['id'], headers=headers, json={'approve': True}))['result']
                if saved.get('id'):
                    created.append(saved['id'])
                assert saved.get('status') == 'executed' and 'error' not in saved
                detail = result(api.get('/api/notion/records/' + saved['id'], headers=headers))
                assert detail['page']['kind'] == kind
                if kind == 'Meeting':
                    assert detail['page']['date']['end']
            print('PASS approved meeting date-range and note records; no Calendar tools invoked.')
            # A far-future, uniquely labeled daily entry tests the log path without changing today's real log.
            log_day = '2099-12-31'
            marker = title + ' daily-log check'
            existing = result(api.get('/api/notion/records', headers=headers, params={'query': 'Koe — ' + log_day}))['pages']
            assert not any(p['title'] == 'Koe — ' + log_day for p in existing), 'Dedicated test date already contains a log; do not modify it'
            first = asyncio.run(notion_log(log_day, [marker]))
            assert 'error' not in first
            created.append(first['page_id'])
            second = asyncio.run(notion_log(log_day, [marker]))
            assert 'error' not in second and second['added'] == 0 and first['added'] == 1
            print('PASS real daily-log creation and exact-entry deduplication.')
    except Exception as exc:
        print('FAIL live Notion acceptance:', type(exc).__name__, '(provider details and credentials hidden).')
        failed = True
    finally:
        async def cleanup_notion():
            async with notion_service.client() as api:
                for page_id in created:
                    await notion_service.call(api, 'PATCH', '/pages/' + page_id, json={'in_trash': True})
        try:
            asyncio.run(cleanup_notion())
            print('PASS temporary verification pages moved to trash.')
        except Exception:
            print('ATTENTION: a labeled verification page may remain; inspect Notion before rerunning.')
            failed = True
        settings.koe_owner_id = original_owner
        try:
            with psycopg.connect(**store.connection_options()) as con:
                con.execute('DELETE FROM public.koe_activity WHERE owner_id=%s', (test_owner,))
                con.execute('DELETE FROM public.koe_pending_actions WHERE owner_id=%s', (test_owner,))
            print('PASS isolated verification approval/audit rows removed; owner records retained.')
        except Exception:
            print('ATTENTION: isolated verification audit rows may remain.')
            failed = True
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
