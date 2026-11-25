import re

import httpx

t = httpx.get("https://trakheesi.dubailand.gov.ae/rev/static/js/main.0dad9b96.js", timeout=60).text
# Find zr(e) where e is passed string - look for pattern like `function(e){return` near CryptoJS
# Search for public_language_Key usage
for pat in [r"public_language_Key", r"language_Key\|\|", r"7!FAu&9P", r"jwt_token_Key"]:
    for m in re.finditer(pat, t):
        sn = t[m.start() - 120 : m.end() + 300]
        if "return" in sn and len(sn) < 500:
            print(sn)
            print("---")