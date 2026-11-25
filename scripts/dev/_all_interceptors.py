import re

import httpx

t = httpx.get("https://trakheesi.dubailand.gov.ae/rev/static/js/main.0dad9b96.js", timeout=60).text
for m in re.finditer(r"interceptors\.request\.use\(\(e=>\{const t=zr", t):
    print(t[m.start() : m.start() + 400])
    print()