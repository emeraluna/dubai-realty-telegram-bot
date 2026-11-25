import asyncio
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "t")
os.environ.setdefault("APIFY_TOKEN", "a")
os.environ.setdefault("SCRAPEFORGE_KEY", "s")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from config.settings import get_settings

get_settings.cache_clear()

from scrapers.madmoun_playwright import fetch_madmoun_integration_json

URL = (
    "https://trakheesi.dubailand.gov.ae/rev/madmoun/listing/validation"
    "?khevJujtDig=qnzrseuxs57ltl64cp5jt82t2ip0cbe2o54hxgcqfpngnsxme"
)


async def main() -> None:
    data = await fetch_madmoun_integration_json(URL)
    print(json.dumps(data, ensure_ascii=False)[:8000])
    result = data.get("result") or data
    if isinstance(result, dict):
        owner_keys = [k for k in result if "owner" in k.lower() or "holder" in k.lower()]
        print("owner-like keys", owner_keys)


asyncio.run(main())