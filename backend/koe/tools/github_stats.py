"""Deterministic GitHub metrics. No LLM calls or writes.

https://docs.github.com/en/rest/commits/commits#get-a-commit
https://docs.github.com/en/graphql/reference/users#contributionscollection
"""
import asyncio
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from koe.config import settings
from koe.tools import github_work as work
from koe.tools.github import _error

MAX_LINE_COMMITS = 50


def nonnegative(value):
    if type(value) is not int or value < 0:
        raise ValueError('Invalid GitHub count.')
    return value


async def github_activity(since='today', until='', include_lines=False):
    if type(include_lines) is not bool:
        return _error('bad_args', 'include_lines must be true or false.', 'Use the documented arguments.')
    history = await work.github_shipped(since=since, until=until)
    if 'error' in history:
        return history
    counts = [{'repo': repo, 'commits': sum(c['repo'] == repo for c in history['commits']),
               'merged_prs': sum(p['repo'] == repo for p in history['prs'])} for repo in history['repositories']]
    result = {**history, 'totals': {'commits': len(history['commits']), 'merged_prs': len(history['prs'])},
              'by_repository': counts, 'totals_are_complete': not history['partial']}
    if not include_lines:
        return result
    gate = asyncio.Semaphore(4)
    async def detail(commit):
        async with gate:
            try:
                stats = (await work.request('GET', f"/repos/{commit['repo']}/commits/{commit['sha']}" )).json()['stats']
                return nonnegative(stats['additions']), nonnegative(stats['deletions'])
            except (work.GitHubError, ValueError, TypeError, KeyError):
                return None  # An unavailable detail is unknown, never a zero-line change.
    details = await asyncio.gather(*(detail(c) for c in history['commits'][:MAX_LINE_COMMITS]))
    known = [d for d in details if d is not None]
    complete = not history['partial'] and len(known) == len(history['commits'])
    additions = sum(d[0] for d in known) if known or not history['commits'] else None
    deletions = sum(d[1] for d in known) if known or not history['commits'] else None
    result['lines'] = {'additions': additions, 'deletions': deletions,
        'net': additions - deletions if additions is not None else None,
        'commits_analyzed': len(known), 'commits_in_history': len(history['commits']), 'partial': not complete,
        'note': 'Changed lines in analyzed commits only; not repository source LOC or unique code authored. Merge diffs may overlap.'}
    return result


async def github_contributions(days=365, now=None):
    if type(days) is not int or not 1 <= days <= 365:
        return _error('bad_args', 'days must be an integer from 1 to 365.', 'Choose a bounded contribution window.')
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(ZoneInfo(settings.timezone)).date()
    first = today - timedelta(days=days - 1)
    start = datetime.combine(first, time.min, ZoneInfo(settings.timezone))
    query = '''query($from:DateTime!,$to:DateTime!){viewer{contributionsCollection(from:$from,to:$to){
        contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}'''
    try:
        data = (await work.request('POST', '/graphql', json={'query': query,
            'variables': {'from': start.isoformat(), 'to': now.isoformat()}})).json()
        if data.get('errors'):
            raise ValueError('Incomplete GraphQL result.')
        weeks = data['data']['viewer']['contributionsCollection']['contributionCalendar']['weeks']
        values = {}
        for week in weeks:
            for day in week['contributionDays']:
                day_date = date.fromisoformat(day['date'])
                if first <= day_date <= today:
                    if day_date in values:
                        raise ValueError('Duplicate contribution day.')
                    values[day_date] = nonnegative(day['contributionCount'])
        expected = [first + timedelta(days=i) for i in range(days)]
        if set(values) != set(expected):
            raise ValueError('Incomplete contribution calendar.')
        longest = run = 0
        for day in expected:
            run = run + 1 if values[day] else 0
            longest = max(longest, run)
        anchor = today if values[today] else today - timedelta(days=1)
        cursor, current = anchor, 0
        while cursor in values and values[cursor] > 0:
            current += 1
            cursor -= timedelta(days=1)
        return {'window_start': first.isoformat(), 'window_end': today.isoformat(),
            'total_contributions': sum(values.values()), 'active_days': sum(v > 0 for v in values.values()),
            'current_streak': current, 'streak_ends_on': anchor.isoformat() if current else None,
            'current_streak_may_extend_before_window': bool(current and cursor < first),
            'longest_streak_in_window': longest, 'days': [{'date': d.isoformat(), 'count': values[d]} for d in expected],
            'note': 'GitHub contribution calendar dates and visible contributions, not a commit-only streak. Longest streak covers this window only; an unfinished today does not break yesterday’s streak.'}
    except (work.GitHubError, ValueError, TypeError, KeyError, AttributeError):
        return _error('github_contributions', 'GitHub did not return a complete accessible contribution calendar.',
                      'Check permissions and retry the read; no streak was guessed.')
