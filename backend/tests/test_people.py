"""Settings → People: only the owner invites/removes, and a removed person is signed out everywhere."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from koe import auth, people
from koe.config import settings
from tests.test_auth import ADMIN, SITE, sign_in

FRIEND = "friend@gmail.com"
SAME = {"origin": SITE}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "google_web_client_id", "client-id")
    monkeypatch.setattr(settings, "google_web_client_secret", "client-secret")
    monkeypatch.setattr(settings, "koe_admin_email", ADMIN)
    monkeypatch.setattr(settings, "koe_public_url", SITE)
    app = FastAPI()
    app.include_router(auth.router)
    app.include_router(people.router)
    return TestClient(app, follow_redirects=False)


def test_the_owner_invites_and_a_removed_friend_is_signed_out(client, monkeypatch):
    friend = TestClient(client.app, follow_redirects=False)
    assert sign_in(friend, monkeypatch, FRIEND, sub="friend-sub").headers["location"].endswith("not-invited")

    sign_in(client, monkeypatch, ADMIN)
    assert client.post("/api/people", json={"email": " Friend@Gmail.com "}, headers=SAME).json() == {"email": FRIEND}
    assert client.post("/api/people", json={"email": FRIEND}, headers=SAME).status_code == 201  # twice is harmless
    listed = client.get("/api/people").json()
    assert listed["owner"] == ADMIN and [(p["email"], p["joined"]) for p in listed["people"]] == [(FRIEND, False)]

    sign_in(friend, monkeypatch, FRIEND, sub="friend-sub")
    assert friend.get("/auth/status").json()["user"]["email"] == FRIEND
    assert client.get("/api/people").json()["people"][0]["joined"] is True

    assert client.delete(f"/api/people/{FRIEND}", headers=SAME).status_code == 204
    assert friend.get("/auth/status").json()["user"] is None  # signed out at once
    assert sign_in(friend, monkeypatch, FRIEND, sub="friend-sub").headers["location"].endswith("not-invited")
    assert client.get("/api/people").json()["people"] == []


def test_only_the_owner_from_koes_own_site_can_manage_people(client, monkeypatch):
    assert client.get("/api/people").status_code == 401
    sign_in(client, monkeypatch, ADMIN)
    assert client.post("/api/people", json={"email": FRIEND}, headers={"origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/people", json={"email": FRIEND}).status_code == 403  # no Origin at all
    assert client.delete(f"/api/people/{FRIEND}", headers={"origin": "https://evil.example"}).status_code == 403
    client.post("/api/people", json={"email": FRIEND}, headers=SAME)

    friend = TestClient(client.app, follow_redirects=False)
    sign_in(friend, monkeypatch, FRIEND, sub="friend-sub")
    assert friend.get("/api/people").status_code == 403
    assert friend.post("/api/people", json={"email": "x@gmail.com"}, headers=SAME).status_code == 403
    assert friend.delete(f"/api/people/{FRIEND}", headers=SAME).status_code == 403


@pytest.mark.parametrize("email", ["not-an-email", "a@b", "two@@x.com", "x" * 250 + "@gmail.com", ADMIN])
def test_bad_addresses_and_the_owner_are_refused(client, monkeypatch, email):
    sign_in(client, monkeypatch, ADMIN)
    assert client.post("/api/people", json={"email": email}, headers=SAME).status_code == 422
    assert client.delete(f"/api/people/{email}", headers=SAME).status_code in (404, 422)
