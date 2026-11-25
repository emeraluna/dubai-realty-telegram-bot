import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.chdir(ROOT)
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "t")
os.environ.setdefault("APIFY_TOKEN", "a")
os.environ.setdefault("SCRAPEFORGE_KEY", "s")

URL = sys.argv[1] if len(sys.argv) > 1 else ""


async def main() -> None:
    from config.settings import get_settings
    from scrapers.chain import ExtractorChain
    from scrapers.madmoun_validation import fetch_madmoun_validation
    from scrapers.trakheesi_integration import integration_to_listing_payload, post_madmoun_integration
    from services.input_parser import parse_lookup_input
    from services.owner_broker_guard import strip_broker_owner

    get_settings.cache_clear()
    req = parse_lookup_input(URL)
    payload = await ExtractorChain().extract(req)
    print("extract", json.dumps(payload.model_dump(), indent=2, ensure_ascii=False, default=str))
    vurl = (payload.raw_payload or {}).get("direct", {}).get("permit_validation_url")
    if not vurl:
        rera = (payload.raw_payload or {}).get("direct", {}).get("rera") or {}
        if isinstance(rera, dict):
            vurl = rera.get("permit_validation_url")
    if vurl:
        try:
            mad = await fetch_madmoun_validation(vurl)
            print("madmoun", json.dumps(madmoun_dump(mad), indent=2, ensure_ascii=False))
        except Exception as exc:
            print("madmoun_err", exc)
        guid = vurl.split("khevJujtDig=")[-1].split("&")[0]
        try:
            data = await post_madmoun_integration(guid, page_url=vurl)
            p = strip_broker_owner(integration_to_listing_payload(guid, data, url=vurl))
            (ROOT / "data" / f"madmoun_{req.external_id}.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print("integration", json.dumps(p.model_dump(), indent=2, ensure_ascii=False, default=str))
        except Exception as exc:
            print("integration_err", exc)


def madmoun_dump(p):
    return {k: v for k, v in p.model_dump().items() if k != "raw_payload" or v}


asyncio.run(main())