"""Durable write intents. A sent intent is never transmitted a second time."""
import hashlib
import json

from koe import auth, connections, spotify_service as sp

CAPACITY = 1000


def digest(body):
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


async def lookup(owner, generation, request_id):
    rows = await sp.sql("select * from koe_music_mutations where owner_id=%s and connection_id=%s and request_id=%s",
                        owner, generation, request_id)
    return rows[0] if rows else None


async def view(row, *, replay=False):
    if row["state"] == "prepared":
        raise sp.SpotifyError("spotify_invalid_request", 400, "This action has not been sent. Review its preview again.")
    result = await sp.io(connections.decrypt, row["result_enc"]) if row["result_enc"] else None
    if result and "_error" in result:
        if replay:
            raise sp.SpotifyError(**result["_error"])
        result = {"accepted": False}
    return {"request_id": row["request_id"],
            "state": "confirmed" if row["state"] == "confirmed" else "outcome_unknown", "result": result}


async def prepare(owner, body, operation, evidence):
    """Return (ticket, replay). Caller holds the owner's lock through send/finish."""
    generation, request_id = body["connection_id"], body["request_id"]
    await sp.connection(owner, generation)
    fingerprint = digest({"operation": operation, "body": body, "destination": evidence})
    row = await lookup(owner, generation, request_id)
    if row:
        if row["body_hash"] != fingerprint:
            raise sp.SpotifyError("spotify_request_conflict", message="That action ID belongs to a different music change.")
        if row["state"] != "prepared":
            return None, await view(row, replay=True)
    else:
        now = auth._now().isoformat()
        encrypted = await sp.io(connections.encrypt, {"destination": evidence, "intent": body, "operation": operation})
        rows = await sp.sql(
            "insert into koe_music_mutations "
            "(owner_id,connection_id,request_id,body_hash,operation,state,evidence_enc,created,updated) "
            "select %s,%s,%s,%s,%s,'prepared',%s,%s,%s where "
            "(select count(*) from koe_music_mutations where owner_id=%s and connection_id=%s)<%s "
            "on conflict (owner_id,connection_id,request_id) do nothing returning request_id",
            owner, generation, request_id, fingerprint, operation, encrypted, now, now, owner, generation, CAPACITY)
        if not rows:
            raise sp.SpotifyError("spotify_journal_full", message="Music action history is full; resolve it before continuing.")
    return {"owner": owner, "generation": generation, "request_id": request_id, "hash": fingerprint}, None


async def finish(ticket, state, result=None):
    encrypted = await sp.io(connections.encrypt, result) if result is not None else None
    await sp.sql("update koe_music_mutations set state=%s,result_enc=%s,updated=%s "
                 "where owner_id=%s and connection_id=%s and request_id=%s and body_hash=%s",
                 state, encrypted, auth._now().isoformat(), ticket["owner"], ticket["generation"], ticket["request_id"], ticket["hash"])


async def send(ticket, operation):
    rows = await sp.sql("update koe_music_mutations set state='sent',updated=%s where owner_id=%s "
                        "and connection_id=%s and request_id=%s and body_hash=%s and state='prepared' returning request_id",
                        auth._now().isoformat(), ticket["owner"], ticket["generation"], ticket["request_id"], ticket["hash"])
    if not rows:
        row = await lookup(ticket["owner"], ticket["generation"], ticket["request_id"])
        if not row:
            raise sp.SpotifyError("spotify_generation_stale")
        return await view(row, replay=True)
    sp.sent_intent.set(ticket["request_id"])
    try:
        result = await operation()
        await finish(ticket, "confirmed", result)
        return {"request_id": ticket["request_id"], "state": "confirmed", "result": result}
    except sp.SpotifyError as exc:
        if exc.code in ("spotify_rate_limited", "spotify_quota_exceeded", "spotify_forbidden", "spotify_premium_required",
                        "spotify_device_unavailable", "spotify_playlist_stale", "spotify_invalid_request", "spotify_reconnect_required"):
            await finish(ticket, "confirmed", {"_error": {"code": exc.code, "status": exc.status,
                                                         "message": exc.message, "retry_after": exc.retry_after}})
            if exc.code == "spotify_reconnect_required":
                await sp.invalidate(ticket["owner"], reconnect=True)
            raise
        await finish(ticket, "outcome_unknown")
        return {"request_id": ticket["request_id"], "state": "outcome_unknown", "result": None}
    # Cancellation, DB failure or process crash leaves durable 'sent'; all later
    # reads/replays project it as unknown. Never reset it to prepared.
