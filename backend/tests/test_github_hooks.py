import hashlib
import hmac
import json
import os

os.environ.setdefault("GEMINI_API_KEY", "test")

import httpx  # noqa: E402
import pytest  # noqa: E402
import respx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from koe import github_hooks, whatsapp  # noqa: E402
from koe.config import settings  # noqa: E402
from koe.main import app  # noqa: E402

ME = "rohit"
REPO = {"full_name": "me/app"}


def test_signature_matches_githubs_published_test_vector():
    sig = "sha256=757107ea0eb2509fc211221cce984b8a37570b6d7586c22c46f4379c8b043e17"
    assert whatsapp.valid_signature("It's a Secret to Everybody", b"Hello, World!", sig)
    assert not whatsapp.valid_signature("wrong secret", b"Hello, World!", sig)
    assert not whatsapp.valid_signature("", b"Hello, World!", sig)  # no secret configured: fail closed
    assert not whatsapp.valid_signature("It's a Secret to Everybody", b"Hello, World!", None)


def pr(author=ME, **over):
    return {"number": 42, "title": "Add login", "user": {"login": author}, "merged": False, **over}


def run(conclusion="failure", actor=ME, prs=({"number": 42},)):
    return {"action": "completed", "repository": REPO, "workflow_run": {
        "name": "CI", "conclusion": conclusion, "actor": {"login": actor}, "pull_requests": list(prs)}}


@pytest.mark.parametrize("event,payload,expected", [
    ("workflow_run", run(), "🔴 CI failed on #42 (me/app): CI"),
    ("workflow_run", run(actor="Rohit"), "🔴 CI failed on #42 (me/app): CI"),  # logins are case-insensitive
    ("workflow_run", run(conclusion="success"), None),
    ("workflow_run", run(actor="rahul"), None),  # someone else's PR
    ("workflow_run", run(prs=()), None),  # push to a branch, no PR
    ("pull_request", {"action": "review_requested", "repository": REPO, "pull_request": pr("rahul"),
                      "requested_reviewer": {"login": ME}, "sender": {"login": "rahul"}},
     "👀 rahul requested your review on #42 (me/app): Add login"),
    ("pull_request", {"action": "review_requested", "repository": REPO, "pull_request": pr("rahul"),
                      "requested_team": {"slug": "core"}, "sender": {"login": "rahul"}}, None),
    ("pull_request", {"action": "closed", "repository": REPO, "pull_request": pr(merged=True)},
     "✅ #42 merged (me/app): Add login"),
    ("pull_request", {"action": "closed", "repository": REPO, "pull_request": pr()}, None),  # closed unmerged
    ("pull_request_review", {"action": "submitted", "repository": REPO, "pull_request": pr(),
                             "review": {"state": "changes_requested", "user": {"login": "rahul"}}},
     "✏️ Changes requested on #42 (me/app) by rahul"),
    ("pull_request_review", {"action": "submitted", "repository": REPO, "pull_request": pr(),
                             "review": {"state": "approved", "user": {"login": "rahul"}}}, None),
    ("push", {"repository": REPO}, None),
])
def test_alert_rules(event, payload, expected):
    assert github_hooks.alert(event, payload, ME) == expected


def test_no_login_configured_means_no_alerts():
    team_request = {"action": "review_requested", "repository": REPO, "pull_request": pr("rahul"),
                    "requested_team": {"slug": "core"}, "sender": {"login": "rahul"}}
    assert github_hooks.alert("pull_request", team_request, "") is None


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "github_webhook_secret", "s3cret")
    monkeypatch.setattr(settings, "github_login", ME)
    monkeypatch.setattr(settings, "allowed_whatsapp_numbers", "919876543210")
    monkeypatch.setattr(settings, "whatsapp_phone_number_id", "123")
    monkeypatch.setattr(github_hooks, "_seen_deliveries", set())
    return TestClient(app)


def post(client, event, payload, delivery="d-1", secret="s3cret"):
    body = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return client.post("/webhooks/github", content=body, headers={
        "X-GitHub-Event": event, "X-GitHub-Delivery": delivery, "X-Hub-Signature-256": sig,
        "Content-Type": "application/json"})


@respx.mock
def test_failed_ci_sends_one_whatsapp_alert_and_ignores_redelivery(client):
    send = respx.post(f"{whatsapp.GRAPH}/123/messages").mock(
        return_value=httpx.Response(200, json={"messages": [{"id": "wamid.1"}]}))

    first = post(client, "workflow_run", run())
    again = post(client, "workflow_run", run())  # same X-GitHub-Delivery

    assert first.status_code == 200 and first.json()["alert"].startswith("🔴")
    assert again.json() == {"ok": True, "duplicate": True}
    assert send.call_count == 1
    sent = json.loads(send.calls[0].request.content)
    assert sent["to"] == "919876543210" and sent["text"]["body"].startswith("🔴 CI failed on #42")


@respx.mock
def test_bad_signature_is_rejected_and_sends_nothing(client):
    send = respx.post(f"{whatsapp.GRAPH}/123/messages")
    assert post(client, "workflow_run", run(), secret="forged").status_code == 401
    assert send.call_count == 0


@respx.mock
def test_whatsapp_failure_still_acks_github(client):
    respx.post(f"{whatsapp.GRAPH}/123/messages").mock(return_value=httpx.Response(400, json={}))
    assert post(client, "workflow_run", run()).status_code == 200


def test_ping_is_acknowledged(client):
    r = post(client, "ping", {"zen": "Keep it logically awesome.", "hook_id": 1})
    assert r.json() == {"ok": True, "alert": None}
