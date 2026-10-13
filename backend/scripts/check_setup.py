"""Read-only live setup check. Does not create events or send messages."""
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from koe import store
from koe.config import settings
from koe.tools.calendar import calendar_list


async def main():
    failed = False
    try:
        await store.check_connection()
        print("PASS Neon: all four tables are reachable (read only).")
    except store.StoreError as exc:
        print("FAIL Neon:", str(exc))
        failed = True
    if settings.koe_access_token:
        print("PASS development browser access token configured.")
    else:
        print("MISSING KOE_ACCESS_TOKEN: browser access is refused when storage enables writes.")
        failed = True
    result = await calendar_list(datetime.now(ZoneInfo(settings.timezone)).date().isoformat())
    if "error" in result:
        print("FAIL Calendar:", result["error"]["message"])
        failed = True
    else:
        print(f"PASS Calendar: read today's events ({len(result['events'])}); nothing was booked.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
