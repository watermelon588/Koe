"""Read-only live setup check. Does not create events or send messages."""
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from koe.config import settings
from koe.tools.calendar import calendar_list


async def main():
    failed = False
    if not settings.supabase_url or not settings.supabase_secret_key:
        print("MISSING Supabase: set SUPABASE_URL and SUPABASE_SECRET_KEY in backend/.env.")
        failed = True
    elif not settings.supabase_url.startswith("https://"):
        print("FAIL Supabase: SUPABASE_URL must use HTTPS.")
        failed = True
    else:
        key = settings.supabase_secret_key
        headers = {"apikey": key}
        if not key.startswith("sb_secret_"):
            headers["Authorization"] = f"Bearer {key}"
        try:
            async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
                for table in ("koe_activity", "koe_pending_actions", "koe_daily_notes", "koe_github_deliveries"):
                    r = await client.get(f"{settings.supabase_url.rstrip('/')}/rest/v1/{table}",
                                         params={"select": "*", "limit": 0}, headers=headers)
                    if r.is_error:
                        print(f"FAIL Supabase {table}: HTTP {r.status_code}. Check backend key and run migration 001.")
                        failed = True
                        break
                else:
                    print("PASS Supabase: all four tables are reachable (read only).")
        except httpx.HTTPError:
            print("FAIL Supabase: cannot connect. Check project status and network.")
            failed = True
    print("PASS browser access token configured." if settings.koe_access_token else
          "MISSING KOE_ACCESS_TOKEN: browser calls with Supabase will be refused; CLI remains available.")
    result = await calendar_list(datetime.now(ZoneInfo(settings.timezone)).date().isoformat())
    if "error" in result:
        print("FAIL Calendar:", result["error"]["message"])
        failed = True
    else:
        print(f"PASS Calendar: read today's events ({len(result['events'])}); nothing was booked.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
