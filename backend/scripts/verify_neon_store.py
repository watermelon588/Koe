"""Live Neon adapter check with isolated synthetic rows; never runs external tools.

Run from backend/: python -m scripts.verify_neon_store
Only rows belonging to a freshly generated verification owner are removed afterward.
"""
import asyncio
from uuid import uuid4

import psycopg

from koe import store
from koe.config import settings


async def main():
    original_owner = settings.koe_owner_id
    test_owner = f"koe-verify-{uuid4()}"
    session = str(uuid4())
    settings.koe_owner_id = test_owner
    failed = False
    try:
        await store.check_connection()
        proposal = await store.propose(session, "app", "storage_verification", {"check": True}, "Synthetic storage verification")
        assert proposal["channel"] == "app"
        assert (await store.propose(session, "app", "storage_verification", {"check": True}, "Same"))["id"] == proposal["id"]
        assert "error" in await store.propose(session, "app", "storage_verification", {"different": True}, "Different")
        assert await store.claim(proposal["id"], str(uuid4()), True) is None
        settings.koe_owner_id = f"koe-other-{uuid4()}"
        assert await store.claim(proposal["id"], session, True) is None
        assert await store.dashboard_read() == {"activity": [], "pending": []}
        settings.koe_owner_id = test_owner
        claims = await asyncio.gather(*(store.claim(proposal["id"], session, True) for _ in range(4)))
        assert sum(c is not None and c["status"] == "executing" for c in claims) == 1
        assert (await store.finish(proposal["id"], session, {"check": "complete"}))["status"] == "executed"
        assert await store.claim(proposal["id"], session, True) is None
        rejected = await store.propose(session, "cli", "storage_verification", {}, "Reject check")
        assert (await store.claim(rejected["id"], session, False))["status"] == "rejected"
        assert await store.claim(rejected["id"], session, True) is None
        expired = await store.propose(session, "cli", "storage_verification", {}, "Expiry check")
        def expire():
            with psycopg.connect(**store.connection_options()) as con:
                con.execute("UPDATE public.koe_pending_actions SET expires_ts=now()-interval '1 second' WHERE id=%s AND owner_id=%s",
                            (expired["id"], test_owner))
        await asyncio.to_thread(expire)
        assert (await store.claim(expired["id"], session, True))["status"] == "expired"
        rows = await store.dashboard_read()
        assert rows["activity"] and not rows["pending"]
        assert all("payload_json" not in row and "args_json" not in row for row in rows["activity"])
        print("PASS live Neon: adapter, JSON, idempotent proposals, owner/session isolation, four concurrent claims (one winner), replay, rejection, expiry and dashboard.")
    except (psycopg.Error, store.StoreError, AssertionError):
        print("FAIL live Neon verification. No external tool was executed; credentials were not printed.")
        failed = True
    finally:
        settings.koe_owner_id = original_owner
        try:
            # Exact unique namespace generated above; never delete the configured owner's rows.
            def cleanup():
                with psycopg.connect(**store.connection_options()) as con:
                    con.execute("DELETE FROM public.koe_activity WHERE owner_id=%s", (test_owner,))
                    con.execute("DELETE FROM public.koe_pending_actions WHERE owner_id=%s", (test_owner,))
            await asyncio.to_thread(cleanup)
            print("PASS verification rows removed; owner's records retained.")
        except (psycopg.Error, store.StoreError):
            print("FAIL cleanup: isolated synthetic verification rows may remain.")
            failed = True
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
