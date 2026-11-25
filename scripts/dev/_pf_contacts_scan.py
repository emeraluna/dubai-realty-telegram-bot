import asyncio
import json
import os
import re
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "t")
os.environ.setdefault("APIFY_TOKEN", "a")
os.environ.setdefault("SCRAPEFORGE_KEY", "s")

URL = sys.argv[1]


async def main() -> None:
    from scrapers.browser_headers import browser_headers
    from scrapers.embed_json import extract_embedded_nodes
    import httpx

    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        r = await client.get(URL, headers=browser_headers(referer=URL))
        html = r.text
    nodes = extract_embedded_nodes(html)
    phones = set()
    names = set()
    for node in nodes:
        for k, v in node.items():
            if isinstance(v, str) and re.search(r"971\d{8,9}|\+971", v):
                phones.add(f"{k}={v}")
            if isinstance(v, str) and re.search(r"(owner|landlord|seller)", k, re.I) and len(v) > 2:
                names.add(f"{k}={v}")
    contactish = [
        node
        for node in nodes
        if any(
            key in node
            for key in (
                "contact",
                "contact_options",
                "agent",
                "broker",
                "owner",
                "landlord",
                "phone",
                "mobile",
                "whatsapp",
            )
        )
    ]
    print("phones", sorted(phones)[:30])
    print("ownerish_keys", sorted(names)[:20])
    print("contact_nodes", json.dumps(contactish[:8], indent=2, default=str)[:4000])


asyncio.run(main())