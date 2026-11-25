import asyncio
import json
import os
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "t")
GUID = sys.argv[1]
URL = f"https://trakheesi.dubailand.gov.ae/rev/madmoun/listing/validation?khevJujtDig={GUID}"


async def main() -> None:
    from scrapers.madmoun_validation import _fetch_by_listing_guid
    from scrapers.trakheesi_integration import integration_to_listing_payload
    from services.owner_broker_guard import broker_contact_from_payload, strip_broker_owner

    data = await _fetch_by_listing_guid(GUID, validation_url=URL)
    print(json.dumps(data, indent=2, ensure_ascii=False)[:4000])
    p = strip_broker_owner(integration_to_listing_payload(GUID, data, url=URL))
    print("owner", p.owner_name, p.owner_phone)
    print("broker", broker_contact_from_payload(p.raw_payload))


asyncio.run(main())