import re

import httpx

t = httpx.get("https://trakheesi.dubailand.gov.ae/rev/static/js/main.0dad9b96.js", timeout=60).text
patterns = [
    r"CardHolder[A-Za-z]*",
    r"TransactionNumber",
    r"mv-portal[^\"']{0,80}",
    r"public/permit[^\"']{0,60}",
    r"owner[A-Za-z]*:\"[^\"]+\"",
    r"listing_guid[^\"']{0,100}",
]
for pat in patterns:
    found = set()
    for m in re.finditer(pat, t, re.I):
        sn = t[m.start() : m.start() + 120]
        if sn not in found and len(found) < 8:
            found.add(sn)
            print(sn)
    print("---")