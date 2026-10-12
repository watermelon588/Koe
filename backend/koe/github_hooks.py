"""GitHub webhook -> WhatsApp alerts (SPEC §4, ARCHITECTURE Flow C). Rules, no LLM: fast, free, testable.

Signature: https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries
Payloads:  https://docs.github.com/en/webhooks/webhook-events-and-payloads
"""
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from koe import app_channel, events, whatsapp
from koe.config import settings

log = logging.getLogger("koe.github_hooks")
router = APIRouter()

# ponytail: in-memory dedupe, forgotten on restart. Move to store.py's github_deliveries table when it lands.
_seen_deliveries: set[str] = set()


def login(user: dict | None) -> str:
    return (user or {}).get("login", "").lower()


def alert(event: str, p: dict, me: str) -> str | None:
    """Map one GitHub event to an alert line, or None if it isn't one of the 4 rules."""
    if not me:  # else a missing login ("") would match "me", e.g. a team review request
        return None
    me, action = me.lower(), p.get("action")
    repo = p.get("repository", {}).get("full_name", "?")

    # CI. Only workflow_run, not check_suite too: GitHub Actions fires both for the same failure,
    # which would double-alert. workflow_run.pull_requests has no author, so "my PR" = I triggered the run.
    # ponytail: actor == author is right for PRs I push to; fetch the PR if co-authored PRs matter.
    if event == "workflow_run" and action == "completed":
        run = p["workflow_run"]
        if run.get("conclusion") == "failure" and run.get("pull_requests") and login(run.get("actor")) == me:
            return f"🔴 CI failed on #{run['pull_requests'][0]['number']} ({repo}): {run.get('name', 'workflow')}"

    pr = p.get("pull_request") or {}
    n, title = pr.get("number"), pr.get("title", "")
    if event == "pull_request" and action == "review_requested" and login(p.get("requested_reviewer")) == me:
        return f"👀 {p['sender']['login']} requested your review on #{n} ({repo}): {title}"
    if event == "pull_request" and action == "closed" and pr.get("merged") and login(pr.get("user")) == me:
        return f"✅ #{n} merged ({repo}): {title}"
    if event == "pull_request_review" and action == "submitted" and login(pr.get("user")) == me:
        review = p.get("review") or {}
        if (review.get("state") or "").lower() == "changes_requested":
            return f"✏️ Changes requested on #{n} ({repo}) by {review['user']['login']}"
    return None


async def send_alert(text: str) -> None:
    await app_channel.alert(text)  # the Koe app on the phone (SPEC §14); WhatsApp below once Meta allows it
    numbers = whatsapp.allowed_numbers()
    if not numbers:
        return
    try:
        await whatsapp.send_text(numbers[0], text)
    except Exception as e:  # e.g. Meta's 131031 account lock; the webhook must still succeed
        log.error("alert send failed (%s): %s", e, text)


@router.post("/webhooks/github")
async def receive(request: Request, background: BackgroundTasks):
    body = await request.body()
    if not whatsapp.valid_signature(settings.github_webhook_secret, body, request.headers.get("x-hub-signature-256")):
        raise HTTPException(401, "bad signature")
    delivery = request.headers.get("x-github-delivery", "")
    if delivery in _seen_deliveries:  # GitHub redelivery (manual or retried): already handled
        return {"ok": True, "duplicate": True}
    _seen_deliveries.add(delivery)

    text = alert(request.headers.get("x-github-event", ""), await request.json(), settings.github_login)
    if text:
        events.publish("alert", summary=text, channel="github")
        background.add_task(send_alert, text)  # after the 200: GitHub gives up after 10 s
    return {"ok": True, "alert": text}
