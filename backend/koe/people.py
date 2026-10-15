"""Settings → People (ACCOUNTS_SPEC.md, admin): the owner invites and removes the emails allowed to sign in.

  GET    /api/people          → the owner's email and every invite, with whether that person has signed in yet
  POST   /api/people          → {"email": "..."} invite (same-origin only)
  DELETE /api/people/{email}  → remove the invite and revoke every session of that account (same-origin only)

Only the owner may call these: a signed-in friend gets 403 even once friends can use the rest of Koe. Removing someone
signs them out on every device at once; their stored data stays until the owner deletes it (not built yet). A call
that is already open keeps running until it ends, because WebSocket tickets are checked only when a call starts.
"""
import re
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from koe import auth
from koe.config import settings
from koe.db import sql

router = APIRouter()
EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


class Invite(BaseModel):
    email: str


async def _owner(request: Request) -> None:
    if await auth.http_owner(request) != settings.koe_owner_id:
        raise HTTPException(403, "Only the owner can manage who uses Koe.")


def _email(raw: str) -> str:
    email = raw.strip().lower()
    if len(email) > 254 or not EMAIL.fullmatch(email):
        raise HTTPException(422, "That doesn't look like an email address.")
    if email == settings.koe_admin_email.lower():
        raise HTTPException(422, "That's the owner's own address; it always has access.")
    return email


@router.get("/api/people")
async def people(request: Request, response: Response):
    response.headers.update(auth.NO_STORE)
    await _owner(request)
    rows = await sql("select i.email, i.created, exists (select 1 from koe_users u where u.email = i.email) as joined "
                     "from koe_invites i order by i.created")
    return {"owner": settings.koe_admin_email.lower(),
            "people": [{"email": r["email"], "invited": r["created"], "joined": bool(r["joined"])} for r in rows]}


@router.post("/api/people", status_code=201)
async def invite(body: Invite, request: Request, response: Response):
    response.headers.update(auth.NO_STORE)
    auth.same_origin(request)
    await _owner(request)
    email = _email(body.email)
    await sql("insert into koe_invites (email, invited_by, created) values (%s, %s, %s) on conflict (email) do nothing",
              email, settings.koe_admin_email.lower(), datetime.now(timezone.utc).isoformat())
    return {"email": email}


@router.delete("/api/people/{email}", status_code=204)
async def remove(email: str, request: Request):
    auth.same_origin(request)
    await _owner(request)
    email = _email(email)
    await sql("delete from koe_invites where email = %s", email)
    await sql("update koe_sessions set revoked = %s where revoked is null and user_id in "
              "(select id from koe_users where email = %s)", datetime.now(timezone.utc).isoformat(), email)
    return Response(status_code=204, headers=auth.NO_STORE)
