import re

import httpx

t = httpx.get("https://trakheesi.dubailand.gov.ae/rev/static/js/main.0dad9b96.js", timeout=60).text
for pat in [
    r"language_Key",
    r"public_language_Key",
    r"\.decrypt\([^)]+token",
    r"CryptoJS",
    r"Utf8\.parse",
]:
    print("===", pat)
    for m in re.finditer(pat, t):
        sn = t[m.start() - 100 : m.end() + 200]
        if "token" in sn.lower() or "Key" in sn:
            print(sn[:350])
            break