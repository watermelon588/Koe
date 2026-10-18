"""GitHub read tools (SPEC §3: #1 github_review_queue, #2 github_my_prs).

One GraphQL search per tool returns everything the user asks about (CI, reviews, conflicts,
size) in a single request; REST would need ~3 calls per PR.
GraphQL API: https://docs.github.com/en/graphql
Search qualifiers: https://docs.github.com/en/search-github/searching-on-github/searching-issues-and-pull-requests
Tools return plain dicts; failures come back as {"error": {...}} so the model can recover.
"""
import asyncio
import re
from datetime import datetime, timezone

import httpx

from koe import connections

GRAPHQL = "https://api.github.com/graphql"
_QUERY = """query($q: String!) { search(query: $q, type: ISSUE, first: 20) { nodes { ... on PullRequest {
  number title url isDraft createdAt updatedAt additions deletions changedFiles mergeable reviewDecision
  author { login } repository { nameWithOwner }
  commits(last: 1) { nodes { commit { statusCheckRollup { state } } } } } } } }"""

_REPO = re.compile(r"^[\w.-]+/[\w.-]+$")
_STATES = {"open": "is:open", "closed": "is:closed is:unmerged", "merged": "is:merged", "all": ""}
_CI = {"SUCCESS": "passing", "FAILURE": "failing", "ERROR": "failing", "PENDING": "running", "EXPECTED": "running"}
_REVIEW = {"APPROVED": "approved", "CHANGES_REQUESTED": "changes requested", "REVIEW_REQUIRED": "review required"}
_CONFLICTS = {"MERGEABLE": "no", "CONFLICTING": "yes"}  # UNKNOWN until GitHub computes it in the background


def _error(code: str, message: str, hint: str) -> dict:
    return {"error": {"code": code, "message": message, "hint": hint}}


_clients: dict[asyncio.AbstractEventLoop, httpx.AsyncClient] = {}


def _client() -> httpx.AsyncClient:
    # One reused client (per event loop) keeps the TLS connection to GitHub open between calls.
    # A fresh client per call cost ~2-3 s here: DNS + TCP + TLS handshakes at ~400 ms RTT from India.
    # ponytail: never closed; fine for one long-running server process.
    loop = asyncio.get_running_loop()
    if loop not in _clients:
        _clients[loop] = httpx.AsyncClient(timeout=15, limits=httpx.Limits(keepalive_expiry=120))
    return _clients[loop]


async def _search(q: str) -> list[dict]:
    account = await asyncio.to_thread(connections.github_account)
    if not account['token']:
        raise GitHubError('Connect GitHub in Settings → Connections first.')
    r = await _client().post(GRAPHQL, json={"query": _QUERY, "variables": {"q": q}},
                             headers={"Authorization": f"Bearer {account['token']}"})
    r.raise_for_status()
    data = r.json()
    if data.get("errors"):
        raise GitHubError(data["errors"][0].get("message", "GraphQL error"))
    return [n for n in data["data"]["search"]["nodes"] if n]  # non-PR hits come back as {}


class GitHubError(Exception):
    pass


def _ago(iso: str, now: datetime) -> str:
    secs = (now - datetime.fromisoformat(iso.replace("Z", "+00:00"))).total_seconds()
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60)):
        if secs >= size:
            return f"{int(secs // size)}{unit}"
    return "just now"


def _basics(n: dict, now: datetime) -> dict:
    return {
        "repo": n["repository"]["nameWithOwner"], "number": n["number"], "title": n["title"],
        "author": (n.get("author") or {}).get("login", "ghost"), "age": _ago(n["createdAt"], now),
        "size": f"+{n['additions']}/-{n['deletions']} in {n['changedFiles']} files", "url": n["url"],
    }


async def _run(q: str, shape, now: datetime | None) -> dict:
    now = now or datetime.now(timezone.utc)
    try:
        prs = [shape(n, now) for n in await _search(q)]
    except (GitHubError, connections.ConnectionError_) as e:
        return _error("github_error", str(e), "Check GitHub in Settings → Connections. Missing access is not an empty result.")
    except httpx.HTTPError as e:
        return _error("github_unreachable", str(e), "GitHub didn't answer; try again in a moment.")
    return {"count": len(prs), "prs": prs}


async def scope_query(repo=None):
    if repo:
        if not await asyncio.to_thread(connections.github_repo_allowed, repo):
            raise GitHubError('Choose this repository in Settings → Connections first.')
        return f' repo:{repo}'
    if await asyncio.to_thread(connections.github_repo_mode) == 'all':
        return ''
    repos = await asyncio.to_thread(connections.github_repos)
    if not repos:
        raise GitHubError('No repositories selected. Choose repositories or all accessible repositories in Settings.')
    return ''.join(f' repo:{r}' for r in repos)


async def github_review_queue(repo: str | None = None, now: datetime | None = None) -> dict:
    """PRs where my review is requested (directly or via a team), oldest first."""
    if repo and not _REPO.match(repo):
        return _error("bad_args", f"repo must look like owner/name, got {repo!r}", "Omit repo to search everywhere.")
    try:
        q = "is:pr is:open review-requested:@me archived:false sort:created-asc" + await scope_query(repo)
    except GitHubError as exc:
        return _error('github_scope', str(exc), 'Repository selection controls what Koe reads.')
    return await _run(q, _basics, now)


async def github_my_prs(state: str = "open", now: datetime | None = None) -> dict:
    """My PRs with CI status, review state and merge conflicts, most recently updated first."""
    if state not in _STATES:
        return _error("bad_args", f"state must be one of {sorted(_STATES)}", "Use 'open' unless the user asked otherwise.")

    def shape(n: dict, now: datetime) -> dict:
        commits = n["commits"]["nodes"]
        rollup = commits[0]["commit"]["statusCheckRollup"] if commits else None
        return {
            **_basics(n, now),
            "draft": n["isDraft"],
            "updated": f"{_ago(n['updatedAt'], now)} ago",
            "ci": _CI.get(rollup["state"], rollup["state"].lower()) if rollup else "no checks",
            "review": _REVIEW.get(n["reviewDecision"], "no review yet"),
            "conflicts": _CONFLICTS.get(n["mergeable"], "unknown (GitHub is still checking)"),
        }

    try:
        q = f"is:pr author:@me archived:false sort:updated-desc {_STATES[state]}".strip() + await scope_query()
    except GitHubError as exc:
        return _error('github_scope', str(exc), 'Repository selection controls what Koe reads.')
    return await _run(q, shape, now)
