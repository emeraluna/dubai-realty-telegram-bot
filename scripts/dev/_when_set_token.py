import re

import httpx

t = httpx.get("https://trakheesi.dubailand.gov.ae/rev/static/js/main.0dad9b96.js", timeout=60).text
for m in re.finditer(r"Vr\([^)]*token", t, re.I):
    sn = t[m.start() : m.start() + 200]
    if "trakheesi" in sn.lower() or "ElDE" in sn or "jwt" in sn:
        print(sn)
        print("---")
# search He.set with trakheesi
for m in re.finditer(r"He\.set\([^)]+\)", t):
    sn = m.group(0)
    if "token" in sn.lower() or "ElDE" in sn:
        print(sn)