"""Read-only live Spotify/DB preflight. Never prints credentials or provider bodies."""
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import psycopg

from koe import connections, spotify_service as sp, store
from koe.config import settings


def main(destination=None):
    result = {"checked_at_utc": datetime.now(timezone.utc).isoformat(),
              "mode": "live-read-only-preflight", "checks": {}}
    checks = result["checks"]
    checks["configuration"] = {"valid": sp.configured(), "enabled_in_env": settings.spotify_enabled,
        "client_id_present": bool(settings.spotify_client_id), "client_secret_present": bool(settings.spotify_client_secret),
        "client_id_expected_format": bool(re.fullmatch(r"[a-fA-F0-9]{32}", settings.spotify_client_id)),
        "redirect_uri": settings.spotify_redirect_uri, "local_origin": settings.koe_local_url,
        "callback_matches_origin": settings.spotify_redirect_uri == settings.koe_local_url.rstrip("/") + "/auth/spotify/callback",
        "encryption_key_length_ok": connections.configured(), "google_sign_in_configured": bool(settings.google_web_client_id and settings.google_web_client_secret)}
    started = time.monotonic()
    try:
        with httpx.Client(timeout=12, trust_env=False, follow_redirects=False) as client:
            response = client.post(sp.TOKEN_URL, auth=(settings.spotify_client_id, settings.spotify_client_secret),
                                   data={"grant_type": "client_credentials"})
            body = response.json()
            code = body.get("error")
            checks["spotify_client_credentials"] = {"http_status": response.status_code,
                "accepted": response.status_code == 200 and isinstance(body.get("access_token"), str),
                "provider_error": code if code in ("invalid_client", "invalid_grant", "unauthorized_client", "unsupported_grant_type") else None,
                "elapsed_ms": round((time.monotonic() - started) * 1000)}
    except Exception as error:
        checks["spotify_client_credentials"] = {"accepted": False, "exception_type": type(error).__name__}
    started = time.monotonic()
    try:
        options = store.connection_options()
        options.update(connect_timeout=8)
        with psycopg.connect(**options) as con:
            # Neon PgBouncer rejects libpq startup `options`; establish a read-only transaction instead.
            con.read_only = True
            con.execute("set local statement_timeout='8000ms'")
            con.execute("set local lock_timeout='2000ms'")
            required = ("koe_users", "koe_sessions", "koe_connections", "koe_prefs", "koe_usage", "koe_spotify_flows", "koe_music_mutations")
            present = {table: con.execute("select to_regclass(%s) is not null", ("public." + table,)).fetchone()[0] for table in required}
            constraint = con.execute("select pg_get_constraintdef(oid) from pg_constraint where conrelid='public.koe_connections'::regclass and conname='koe_connections_provider_check'").fetchone()
            security = con.execute("select relname,relrowsecurity from pg_class where oid in (to_regclass('public.koe_spotify_flows'),to_regclass('public.koe_music_mutations'))").fetchall()
            connected = con.execute("select token_enc,scopes from public.koe_connections where owner_id=%s and provider='spotify'", (settings.koe_owner_id,)).fetchone()
            connection_state = {"connected": bool(connected)}
            if connected:
                try:
                    token = connections.decrypt(connected[0])
                    connection_state.update(decryptable=True, refresh_token_present=bool(token.get("refresh_token")),
                        generation_present=bool(token.get("connection_id")), required_scopes_present=set(sp.SCOPES) <= set(connected[1].split()))
                except Exception as error:
                    connection_state.update(decryptable=False, exception_type=type(error).__name__)
            checks["database"] = {"reachable": True, "transaction_read_only": con.execute("show transaction_read_only").fetchone()[0],
                "required_tables": present, "spotify_allowed_by_constraint": bool(constraint and "spotify" in constraint[0]),
                "rls": dict(security), "owner_spotify_connection": connection_state,
                "elapsed_ms": round((time.monotonic() - started) * 1000)}
    except Exception as error:
        checks["database"] = {"reachable": False, "exception_type": type(error).__name__}
    destination = Path(destination) if destination is not None else Path(__file__).resolve().parents[1] / "data" / "spotify-live-checks" / "preflight.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    main()
