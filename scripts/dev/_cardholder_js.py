import re

import httpx

t = httpx.get("https://trakheesi.dubailand.gov.ae/rev/static/js/main.0dad9b96.js", timeout=60).text
for pat in ["CardHolder", "cardHolder", "OwnerName", "ownerName", "TitleDeed"]:
    print(pat, len(re.findall(pat, t)))
    m = re.search(pat, t)
    if m:
        print(t[m.start() - 50 : m.end() + 150])