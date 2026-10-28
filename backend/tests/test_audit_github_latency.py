import asyncio
from datetime import datetime, timezone

import httpx

from koe import connections
from koe.tools import github_work


def test_history_reads_branches_concurrently_with_a_shared_bound(monkeypatch):
    async def scope():
        return {'repos':['qa/app'], 'partial':False, 'mode':'selected'}
    monkeypatch.setattr(connections, 'github_scope', scope)
    monkeypatch.setattr(connections, 'github_account', lambda: {'login':'qa','source':'personal','token':'synthetic'})
    monkeypatch.setattr(github_work, 'HISTORY_SECONDS', .14)
    active=maximum=0
    async def request(method,path,**kwargs):
        nonlocal active,maximum
        if path=='/search/issues':
            return httpx.Response(200,json={'items':[], 'total_count':0})
        if path.endswith('/branches'):
            return httpx.Response(200,json=[{'name':'main'},{'name':'feature'}])
        active+=1
        maximum=max(maximum,active)
        try:
            await asyncio.sleep(.06)
            return httpx.Response(200,json=[])
        finally:
            active-=1
    monkeypatch.setattr(github_work,'request',request)
    result=asyncio.run(github_work.github_shipped('yesterday',now=datetime(2026,10,26,6,tzinfo=timezone.utc)))
    assert 'error' not in result
    assert result['partial'] is False
    assert 2 <= maximum <= 4
    assert result['branch_coverage']['qa/app']['unavailable'] == []
