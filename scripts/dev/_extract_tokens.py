import re

import httpx

t = httpx.get("https://trakheesi.dubailand.gov.ae/rev/static/js/main.0dad9b96.js", timeout=60).text
keys = [
    "trakheesi_token_Key",
    "trakheesi_api_integration_consumer_id",
    "listing_guid_validation_authorization_key",
    "trakheesi_integration_api_consumer_id",
]
for k in keys:
    m = re.search(rf"{re.escape(k)}:\"([^\"]+)\"", t)
    print(k, "=", m.group(1) if m else "MISSING")

# zr function - often base64 decode
m = re.search(r",zr=function\((\w+)\)\{return([^}]+\})", t)
if m:
    print("zr", m.group(0)[:300])
else:
    for m in re.finditer(r"function zr\(", t):
        print("zr at", m.start(), t[m.start() : m.start() + 200])