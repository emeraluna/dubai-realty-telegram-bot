import asyncio
import os
import sys

sys.path.insert(0, "src")
os.chdir(r"e:\my\New folder\1")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "t")
os.environ.setdefault("APIFY_TOKEN", "a")
os.environ.setdefault("SCRAPEFORGE_KEY", "s")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from config.settings import get_settings

get_settings.cache_clear()

from scrapers.trakheesi_runtime import load_trakheesi_public_config
from scrapers.madmoun_validation import _fetch_by_listing_guid

GUID = "qnzrseuxs57ltl64cp5jt82t2ip0cbe2o54hxgcqfpngnsxme"


async def main() -> None:
    config = await load_trakheesi_public_config()
    print("config ok", config.validate_guid_path[:20])
    import json

    data = await _fetch_by_listing_guid(GUID)
    print(json.dumps(data, ensure_ascii=False)[:3000])


asyncio.run(main())