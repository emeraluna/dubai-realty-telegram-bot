import re

import httpx

t = httpx.get("https://trakheesi.dubailand.gov.ae/rev/static/js/main.0dad9b96.js", timeout=60).text
for m in re.finditer(r".{0,60}decrypt\(.{0,120}", t):
    s = m.group(0)
    if "Key" in s or "token" in s.lower() or "7!" in s:
        print(s[:200])
        print("---")