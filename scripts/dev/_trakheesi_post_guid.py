import asyncio
import json
import os
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "t")

GUID = sys.argv[1] if len(sys.argv) > 1 else "ferfbzd0kp91lprotdcf1nt2ztlw32kwnqudffhaenqxfkzmy"


async def main() -> None:
    import httpx
    from scrapers.trakheesi_runtime import load_trakheesi_public_config

    config = await load_trakheesi_public_config()
    revamp = f"{config.revamp_api_base.rstrip('/')}/{config.validate_guid_path.lstrip('/')}"
    integration = f"{config.integration_api_base.rstrip('/')}/{config.integration_post_path.lstrip('/')}"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "consumer-id": config.integration_consumer_id,
        "authorizationKey": config.listing_guid_auth_key,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0 Safari/537.36",
        "Origin": "https://trakheesi.dubailand.gov.ae",
        "Referer": "https://trakheesi.dubailand.gov.ae/",
    }
    posts = [
        (revamp, {"ListingGUID": GUID, "authorizationKey": config.listing_guid_auth_key}),
        (integration, {"ListingGUID": GUID, "CaptchaToken": ""}),
    ]
    async with httpx.AsyncClient(timeout=90, follow_redirects=True) as client:
        for url, body in posts:
            r = await client.post(url, json=body, headers=headers)
            text = r.text[:5000]
            print("POST", r.status_code, url)
            try:
                data = r.json()
            except json.JSONDecodeError:
                print(text[:800])
                continue
            print(json.dumps(data, indent=2, ensure_ascii=False)[:3000])
            path = __import__("pathlib").Path(__file__).resolve().parents[1] / "data" / f"madmoun_176491831.json"
            if r.status_code == 200 and isinstance(data, dict):
                path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                print("saved", path)


asyncio.run(main())