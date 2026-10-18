import asyncio
import json
import os
from datetime import datetime, timezone

os.environ.setdefault("GEMINI_API_KEY", "test")

import httpx  # noqa: E402
import respx  # noqa: E402
import pytest
from koe.config import settings

from koe.tools import github  # noqa: E402

NOW = datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def account(monkeypatch):
    monkeypatch.setattr(settings, 'github_repos', 'me/app,other/repo')
    monkeypatch.setattr(settings, 'github_token', 'synthetic-token')


def pr_node(**over):
    node = {
        "number": 42, "title": "Add login", "url": "https://github.com/me/app/pull/42", "isDraft": False,
        "createdAt": "2026-10-10T12:00:00Z", "updatedAt": "2026-10-12T09:00:00Z",
        "additions": 120, "deletions": 30, "changedFiles": 4,
        "mergeable": "MERGEABLE", "reviewDecision": "APPROVED",
        "author": {"login": "rahul"}, "repository": {"nameWithOwner": "me/app"},
        "commits": {"nodes": [{"commit": {"statusCheckRollup": {"state": "FAILURE"}}}]},
    }
    return {**node, **over}


def graphql_returns(*nodes):
    body = {"data": {"search": {"issueCount": len(nodes), "nodes": list(nodes)}}}
    return respx.post(github.GRAPHQL).mock(return_value=httpx.Response(200, json=body))


@respx.mock
def test_review_queue_summarizes_prs_and_searches_my_review_requests():
    route = graphql_returns(pr_node(), {})  # {} = a search hit that isn't a PR

    result = asyncio.run(github.github_review_queue(now=NOW))

    assert result == {"count": 1, "prs": [{
        "repo": "me/app", "number": 42, "title": "Add login", "author": "rahul",
        "age": "2d", "size": "+120/-30 in 4 files", "url": "https://github.com/me/app/pull/42",
    }]}
    query = json.loads(route.calls[0].request.content)["variables"]["q"]
    assert "is:pr is:open review-requested:@me" in query


@respx.mock
def test_review_queue_can_narrow_to_one_repo():
    route = graphql_returns()
    asyncio.run(github.github_review_queue(repo="me/app", now=NOW))
    assert "repo:me/app" in json.loads(route.calls[0].request.content)["variables"]["q"]


def test_review_queue_rejects_a_repo_that_is_not_owner_slash_name():
    # The model fills `repo`; it must not be able to smuggle extra search qualifiers in.
    result = asyncio.run(github.github_review_queue(repo="me/app author:someone", now=NOW))
    assert result["error"]["code"] == "bad_args"


@respx.mock
def test_my_prs_reports_ci_reviews_and_conflicts_in_plain_words():
    graphql_returns(
        pr_node(),
        pr_node(number=7, mergeable="CONFLICTING", reviewDecision=None,
                commits={"nodes": [{"commit": {"statusCheckRollup": None}}]}),
        pr_node(number=8, mergeable="UNKNOWN", reviewDecision="CHANGES_REQUESTED", isDraft=True,
                commits={"nodes": [{"commit": {"statusCheckRollup": {"state": "PENDING"}}}]}),
    )

    prs = asyncio.run(github.github_my_prs(now=NOW))["prs"]

    assert [(p["number"], p["ci"], p["review"], p["conflicts"]) for p in prs] == [
        (42, "failing", "approved", "no"),
        (7, "no checks", "no review yet", "yes"),
        (8, "running", "changes requested", "unknown (GitHub is still checking)"),
    ]
    assert prs[2]["draft"] is True
    assert prs[0]["updated"] == "3h ago"


@respx.mock
def test_my_prs_state_maps_to_search_qualifier():
    route = graphql_returns()
    asyncio.run(github.github_my_prs(state="merged", now=NOW))
    assert "is:merged" in json.loads(route.calls[0].request.content)["variables"]["q"]


def test_my_prs_rejects_unknown_state():
    assert asyncio.run(github.github_my_prs(state="deleted", now=NOW))["error"]["code"] == "bad_args"


@respx.mock
def test_graphql_errors_become_tool_errors_not_exceptions():
    respx.post(github.GRAPHQL).mock(return_value=httpx.Response(200, json={"errors": [{"message": "Bad credentials"}]}))
    result = asyncio.run(github.github_my_prs(now=NOW))
    assert result["error"]["code"] == "github_error" and "Bad credentials" in result["error"]["message"]
