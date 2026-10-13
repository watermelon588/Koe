import asyncio
from datetime import datetime, timezone

import httpx
import pytest
import respx

from koe.config import settings
from koe.tools import github_work


@pytest.fixture(autouse=True)
def account(monkeypatch):
    monkeypatch.setattr(settings, 'github_token', 'synthetic')
    monkeypatch.setattr(settings, 'github_login', 'me')
    monkeypatch.setattr(settings, 'github_repos', 'me/app')


def commit(sha, when):
    return {'sha': sha, 'html_url': f'https://github.com/me/app/commit/{sha}',
            'commit': {'message': 'Synthetic change', 'committer': {'date': when}}}


@respx.mock
def test_yesterday_excludes_today_and_deduplicates_evidence():
    respx.get('https://api.github.com/search/issues').respond(200, json={'items': [], 'total_count': 0})
    rows = [commit('abc', '2026-10-12T00:00:00Z')] * 2 + [commit('new', '2026-10-12T18:30:00Z')]
    route = respx.get('https://api.github.com/repos/me/app/commits').respond(200, json=rows)
    result = asyncio.run(github_work.github_shipped('yesterday', now=datetime(2026, 10, 13, 1, tzinfo=timezone.utc)))
    assert result['since'] == '2026-10-11T18:30:00+00:00'
    assert result['until'] == '2026-10-12T18:30:00+00:00'
    assert [c['sha'] for c in result['commits']] == ['abc']
    assert route.calls[0].request.url.params['until'] < result['until']


@respx.mock
def test_explicit_exclusive_end_and_invalid_ranges_never_query():
    respx.get('https://api.github.com/search/issues').respond(200, json={'items': [], 'total_count': 0})
    respx.get('https://api.github.com/repos/me/app/commits').respond(200, json=[])
    now = datetime(2026, 10, 13, 1, tzinfo=timezone.utc)
    result = asyncio.run(github_work.github_shipped('2026-10-11', until='2026-10-12', now=now))
    assert result['until'] == '2026-10-11T18:30:00+00:00'
    before = len(respx.calls)
    for end in ['2026-10-10', '2026-10-20', 'bad']:
        result = asyncio.run(github_work.github_shipped('2026-10-11', until=end, now=now))
        assert result['error']['code'] == 'bad_args'
    assert len(respx.calls) == before


def test_activity_calculates_counts_and_bounds_line_details(monkeypatch):
    from koe.tools import github_stats
    async def shipped(**kwargs):
        return {'commits': [{'repo': 'me/app', 'sha': str(n)} for n in range(3)],
                'prs': [{'repo': 'me/app', 'number': 1}], 'repositories': ['me/app'], 'partial': False}
    async def request(method, path, **kwargs):
        return httpx.Response(200, json={'stats': {'additions': 5, 'deletions': 2}})
    monkeypatch.setattr(github_work, 'github_shipped', shipped)
    monkeypatch.setattr(github_work, 'request', request)
    monkeypatch.setattr(github_stats, 'MAX_LINE_COMMITS', 2)
    result = asyncio.run(github_stats.github_activity(include_lines=True))
    assert result['totals'] == {'commits': 3, 'merged_prs': 1}
    assert result['by_repository'][0]['commits'] == 3
    assert result['lines']['additions'] == 10 and result['lines']['net'] == 6
    assert result['lines']['commits_analyzed'] == 2 and result['lines']['partial']


def test_line_detail_permission_failure_is_unknown_not_zero(monkeypatch):
    from koe.tools import github_stats
    async def shipped(**kwargs):
        return {'commits': [{'repo': 'me/app', 'sha': 'abc'}], 'prs': [], 'repositories': ['me/app'], 'partial': False}
    async def request(*args, **kwargs): raise github_work.GitHubError('permission denied')
    monkeypatch.setattr(github_work, 'github_shipped', shipped)
    monkeypatch.setattr(github_work, 'request', request)
    result = asyncio.run(github_stats.github_activity(include_lines=True))
    assert result['lines']['additions'] is None and result['lines']['partial']
    assert result['lines']['commits_analyzed'] == 0


def test_contribution_streak_uses_complete_calendar_and_yesterday_grace(monkeypatch):
    from koe.tools import github_stats
    async def request(*args, **kwargs):
        days = [{'date': f'2026-10-{day:02}', 'contributionCount': count}
                for day, count in [(9, 1), (10, 0), (11, 3), (12, 2), (13, 0)]]
        return httpx.Response(200, json={'data': {'viewer': {'contributionsCollection': {
            'contributionCalendar': {'weeks': [{'contributionDays': days}]}}}}})
    monkeypatch.setattr(github_work, 'request', request)
    result = asyncio.run(github_stats.github_contributions(days=5, now=datetime(2026, 10, 13, 1, tzinfo=timezone.utc)))
    assert result['current_streak'] == result['longest_streak_in_window'] == 2
    assert result['total_contributions'] == 6 and result['active_days'] == 3
    assert result['streak_ends_on'] == '2026-10-12'


def test_incomplete_calendar_never_becomes_a_fabricated_streak(monkeypatch):
    from koe.tools import github_stats
    async def request(*args, **kwargs):
        return httpx.Response(200, json={'data': {'viewer': {'contributionsCollection': {
            'contributionCalendar': {'weeks': []}}}}})
    monkeypatch.setattr(github_work, 'request', request)
    result = asyncio.run(github_stats.github_contributions(days=5))
    assert 'error' in result and 'current_streak' not in result


def test_slow_line_reads_return_bounded_partial_coverage(monkeypatch):
    from koe.tools import github_stats
    async def shipped(**kwargs):
        return {'commits': [{'repo': 'me/app', 'sha': 'a'}, {'repo': 'me/app', 'sha': 'b'}],
                'prs': [], 'repositories': ['me/app'], 'partial': False}
    async def request(method, path, **kwargs):
        if path.endswith('/b'): await asyncio.Event().wait()
        return httpx.Response(200, json={'stats': {'additions': 5, 'deletions': 2}})
    monkeypatch.setattr(github_work, 'github_shipped', shipped)
    monkeypatch.setattr(github_work, 'request', request)
    monkeypatch.setattr(github_stats, 'LINE_BUDGET_SECONDS', .01, raising=False)
    async def scenario():
        return await asyncio.wait_for(github_stats.github_activity(include_lines=True), timeout=.2)
    result = asyncio.run(scenario())
    assert result['lines']['partial'] and result['lines']['commits_analyzed'] == 1


@respx.mock
def test_history_read_has_a_total_deadline(monkeypatch):
    monkeypatch.setattr(github_work, 'HISTORY_SECONDS', .01, raising=False)
    async def stalled(*args, **kwargs): await asyncio.Event().wait()
    monkeypatch.setattr(github_work, 'request', stalled)
    async def scenario():
        return await asyncio.wait_for(github_work.github_shipped('today'), timeout=.2)
    result = asyncio.run(scenario())
    assert 'error' in result and 'commits' not in result


def test_one_day_window_does_not_guess_yesterdays_streak(monkeypatch):
    from koe.tools import github_stats
    async def request(*args, **kwargs):
        return httpx.Response(200, json={'data': {'viewer': {'contributionsCollection': {
            'contributionCalendar': {'weeks': [{'contributionDays': [{'date': '2026-10-13', 'contributionCount': 0}]}]}}}}})
    monkeypatch.setattr(github_work, 'request', request)
    result = asyncio.run(github_stats.github_contributions(days=1, now=datetime(2026, 10, 13, 1, tzinfo=timezone.utc)))
    assert result['current_streak'] is None
    assert 'days' not in result  # daily records are opt-in, avoiding a large model context on every streak read
