import asyncio
import json
from datetime import datetime, timezone

import httpx
import pytest
import respx

from koe.config import settings
from koe.tools import github, github_work


def test_pr_analysis_uses_bounded_gemini_generation_without_tools(monkeypatch):
    from types import SimpleNamespace
    from google import genai
    from koe import gemini
    seen = []
    async def generate(**kwargs):
        seen.append(kwargs)
        return SimpleNamespace(text='{"summary":"Synthetic summary.","risk_notes":[]}'), 'backup-model'
    monkeypatch.setattr(gemini, 'generate', generate)
    def forbidden_client(*args, **kwargs):
        pytest.fail('PR analysis bypassed the shared provider; no real client may be created in this test.')
    monkeypatch.setattr(genai, 'Client', forbidden_client)
    result = asyncio.run(github_work._summarize('Synthetic PR evidence'))
    assert result['summary'] == 'Synthetic summary.'
    assert seen[0]['contents'] == 'Synthetic PR evidence'
    assert seen[0]['config']['response_schema'] is github_work.Summary
    assert 'tools' not in seen[0]['config']


@pytest.fixture(autouse=True)
def account(monkeypatch):
    monkeypatch.setattr(settings, 'github_token', 'fake')
    monkeypatch.setattr(settings, 'github_repos', 'me/app')
    monkeypatch.setattr(settings, 'github_login', 'me')
    with respx.mock(assert_all_called=False):
        respx.get('https://api.github.com/user').respond(200, json={'login': 'me'})
        respx.get('https://api.github.com/repos/me/app/branches').respond(200, json=[])
        yield


def pr(head='abc'):
    return {'title': 'Fix race', 'body': 'untrusted text', 'head': {'sha': head},
            'changed_files': 2, 'html_url': 'https://github.com/me/app/pull/42'}


@respx.mock
def test_summary_bounds_unicode_source_and_discloses_missing_patches(monkeypatch):
    respx.get('https://api.github.com/repos/me/app/pulls/42').respond(200, json=pr())
    respx.get('https://api.github.com/repos/me/app/pulls/42/files').respond(200, json=[
        {'filename': 'binary.png', 'status': 'added', 'additions': 0, 'deletions': 0},
        {'filename': '声.py', 'status': 'modified', 'patch': '+声\\"\n' * 20000}])
    sources = []
    async def summarize(source):
        sources.append(source)
        return {'summary': 'Fixes a race.', 'risk_notes': ['Concurrency needs review.']}
    monkeypatch.setattr(github_work, '_summarize', summarize)
    result = asyncio.run(github_work.github_pr_summary('me/app', 42))
    assert len(sources[0].encode('utf-8')) <= 30000
    assert 'not supplied' in sources[0]
    assert result['truncated'] and result['files_changed'] == 2
    assert result['risk_notes_are_inferences'] is True
    assert result['head_sha'] == 'abc'
    assert json.loads(sources[0])['truncated'] is True


@respx.mock
def test_summary_refuses_mixed_revisions(monkeypatch):
    respx.get('https://api.github.com/repos/me/app/pulls/42').mock(side_effect=[
        httpx.Response(200, json=pr()), httpx.Response(200, json=pr('new'))])
    respx.get('https://api.github.com/repos/me/app/pulls/42/files').respond(200, json=[])
    result = asyncio.run(github_work.github_pr_summary('me/app', 42))
    assert result['error']['code'] == 'revision_changed'


@respx.mock
def test_shipped_uses_local_midnight_and_reports_partial_search():
    search = respx.get('https://api.github.com/search/issues').respond(200, json={
        'items': [{'number': 42, 'title': 'Fix', 'html_url': 'https://github.com/me/app/pull/42',
                   'pull_request': {'merged_at': '2026-10-12T23:00:00Z'}}],
        'incomplete_results': True, 'total_count': 1})
    commits = respx.get('https://api.github.com/repos/me/app/commits').respond(200, json=[
        {'sha': 'abc', 'html_url': 'https://github.com/me/app/commit/abc',
         'commit': {'message': 'Fix\nMore', 'committer': {'date': '2026-10-12T23:00:00Z'}}}])
    result = asyncio.run(github_work.github_shipped('today', now=datetime(2026,10,13,1,tzinfo=timezone.utc)))
    assert result['since'] == '2026-10-12T18:30:00+00:00'
    assert result['partial'] and len(result['prs']) == len(result['commits']) == 1
    assert 'author:me' in search.calls[0].request.url.params['q']
    assert commits.calls[0].request.url.params['author'] == 'me'
    assert 'overlap' in result['scope']


@respx.mock
def test_comment_rechecks_allowlist_and_never_retries_timeout(monkeypatch):
    args = github_work.prepare_comment('me/app', 42, '  Looks good.\nPlease add a test.  ')
    assert args['body'] == 'Looks good.\nPlease add a test.'
    monkeypatch.setattr(settings, 'github_repos', 'me/other')
    assert 'error' in asyncio.run(github_work.github_comment(**args, request_id='action'))
    assert not respx.calls
    monkeypatch.setattr(settings, 'github_repos', 'me/app')
    respx.get('https://api.github.com/repos/me/app/pulls/42').respond(200, json=pr())
    post = respx.post('https://api.github.com/repos/me/app/issues/42/comments').mock(side_effect=httpx.ReadTimeout('uncertain'))
    result = asyncio.run(github_work.github_comment(**args, request_id='action'))
    assert 'error' in result and post.call_count == 1
    assert json.loads(post.calls[0].request.content)['body'] == args['body']


@pytest.mark.parametrize('repo,number', [('me/../app',42), ('me/app',True), ('me/app',0)])
def test_invalid_target_rejected(repo, number):
    with pytest.raises(ValueError):
        github_work.prepare_comment(repo, number, 'ok')


@respx.mock
def test_history_follows_fixed_endpoint_pages_not_link_hosts():
    search = respx.get('https://api.github.com/search/issues').mock(side_effect=[
        httpx.Response(200, json={'items': [], 'total_count': 101}),
        httpx.Response(200, json={'items': [], 'total_count': 101})])
    commits = respx.get('https://api.github.com/repos/me/app/commits').mock(side_effect=[
        httpx.Response(200, json=[], headers={'Link': '<https://evil.invalid/steal>; rel="next"'}),
        httpx.Response(200, json=[])])
    result = asyncio.run(github_work.github_shipped('this week', now=datetime(2026,10,13,1,tzinfo=timezone.utc)))
    assert 'error' not in result and not result['partial']
    assert result['since'] == '2026-10-11T18:30:00+00:00'
    assert search.call_count == commits.call_count == 2
    assert commits.calls[1].request.url.params['page'] == '2'


@respx.mock
def test_history_pagination_limit_disclosed():
    respx.get('https://api.github.com/search/issues').respond(200, json={'items': [], 'total_count': 2000})
    respx.get('https://api.github.com/repos/me/app/commits').respond(200, json=[])
    result = asyncio.run(github_work.github_shipped('today'))
    assert result['partial']


@respx.mock
def test_read_errors_do_not_include_response_secrets():
    respx.get('https://api.github.com/repos/me/app/pulls/42').respond(403, json={'message': 'private-token-secret'})
    result = asyncio.run(github_work.github_pr_summary('me/app', 42))
    assert result['error']['code'] == 'github_error'
    assert 'private-token-secret' not in str(result)
