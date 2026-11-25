import re

import httpx

t = httpx.get("https://trakheesi.dubailand.gov.ae/rev/static/js/main.0dad9b96.js", timeout=60).text
for pat in [
    r"7!FAu&9",
    r"decrypt\(",
    r"AES\.decrypt",
    r"CBC",
    r"trakheesi_token_Key",
    r"ElDEQZ",
]:
    print("===", pat, "count", len(re.findall(pat, t)))
    for m in re.finditer(pat, t):
        print(t[max(0, m.start() - 80) : m.end() + 120])
        break