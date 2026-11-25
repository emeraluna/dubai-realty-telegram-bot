import re

import httpx

t = httpx.get("https://trakheesi.dubailand.gov.ae/rev/static/js/main.0dad9b96.js", timeout=60).text
for needle in ("tR=xr.create", "nR=tR", "site_token_Key", "listing_validation", "tR.interceptors"):
    i = t.find(needle)
    while i >= 0:
        print("===", needle, "at", i, "===")
        print(t[max(0, i - 100) : i + 700])
        print()
        i = t.find(needle, i + 1)
        if needle != "site_token_Key":
            break