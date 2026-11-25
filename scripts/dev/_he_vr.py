import re

import httpx

t = httpx.get("https://trakheesi.dubailand.gov.ae/rev/static/js/main.0dad9b96.js", timeout=60).text
idx = t.find("zr=e=>He.get(e)")
print("zr def", t[idx - 500 : idx + 200])
for m in re.finditer(r"Vr\(Ke\.token\.trakheesi_token", t):
    print("set", t[m.start() : m.start() + 300])
for m in re.finditer(r"trakheesi_token_Key", t):
    sn = t[m.start() : m.start() + 250]
    if "Vr" in sn or "He.set" in sn:
        print(sn)
        print("---")