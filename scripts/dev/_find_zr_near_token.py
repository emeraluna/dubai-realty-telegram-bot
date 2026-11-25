import re

import httpx

t = httpx.get("https://trakheesi.dubailand.gov.ae/rev/static/js/main.0dad9b96.js", timeout=60).text
idx = t.find('const t=zr(Ke.token.trakheesi_token_Key||"")')
print("idx", idx)
print(t[idx - 2000 : idx])

# find all `,zr=` assignments in file
for m in re.finditer(r",zr=function\(\w\)\{", t):
    start = m.start()
    end = min(len(t), start + 400)
    body = t[start : end]
    if "decrypt" in body.lower() or "7!" in body or "ElDE" in body or "parse" in body:
        print("--- candidate ---")
        print(body)