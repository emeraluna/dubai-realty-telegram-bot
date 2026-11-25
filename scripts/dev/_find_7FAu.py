import re

import httpx

t = httpx.get("https://trakheesi.dubailand.gov.ae/rev/static/js/main.0dad9b96.js", timeout=60).text
for m in re.finditer(r"7!FAu&9", t):
    print(t[m.start() - 150 : m.end() + 400])
    print("---")