import asyncio
import json
import os
import sys

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.chdir(ROOT)
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "t")
os.environ.setdefault("APIFY_TOKEN", "a")
os.environ.setdefault("SCRAPEFORGE_KEY", "s")

GUID = sys.argv[1] if len(sys.argv) > 1 else "ferfbzd0kp91lprotdcf1nt2ztlw32kwnqudffhaenqxfkzmy"
URL = (
    "https://trakheesi.dubailand.gov.ae/rev/madmoun/listing/validation"
    f"?khevJujtDig={GUID}"
)


async def main() -> None:
    from config.settings import get_settings
    from scrapers.dld_owner_api import fetch_dld_owner_by_key
    from scrapers.dld_private_owner import fetch_trakheesi_revamp_owner
    from scrapers.madmoun_validation import fetch_madmoun_validation
    from scrapers.trakheesi_integration import integration_to_listing_payload
    from services.owner_broker_guard import strip_broker_owner

    get_settings.cache_clear()
    for label, coro in [
        ("madmoun_validation", fetch_madmoun_validation(URL)),
        ("revamp_owner", fetch_trakheesi_revamp_owner(GUID)),
        ("dld_owner_ad", fetch_dld_owner_by_key("1026605")),
    ]:
        try:
            p = await coro
            if label == "revamp_owner":
                print(label, p.model_dump())
            elif hasattr(p, "model_dump"):
                p = strip_broker_owner(p) if label == "madmoun_validation" else p
                print(label, {k: getattr(p, k) for k in ("owner_name", "owner_phone", "permit_number", "building")})
            else:
                print(label, p)
        except Exception as exc:
            print(label, type(exc).__name__, exc)


asyncio.run(main())