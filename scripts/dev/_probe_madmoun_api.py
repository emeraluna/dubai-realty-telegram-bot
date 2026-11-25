import re

import httpx

token = "qnzrseuxs57ltl64cp5jt82t2ip0cbe2o54hxgcqfpngnsxme"
bases = [
    f"https://trakheesi.dubailand.gov.ae/rev/madmoun/listing/validation?khevJujtDig={token}",
    f"https://trakheesi.dubailand.gov.ae/rev/api/madmoun/listing/validation?khevJujtDig={token}",
    f"https://b2c.dubailand.gov.ae/mv-portal-service/public/permit/validation/{token}",
    f"https://b2c.dubailand.gov.ae/mv-portal-service/public/permit/madmoun/{token}",
]

js = httpx.get("https://trakheesi.dubailand.gov.ae/rev/static/js/main.0dad9b96.js", timeout=60).text
paths = sorted(set(re.findall(r'"(/[^"]{5,80})"', js)))
for path in paths:
    if any(k in path.lower() for k in ("madmoun", "permit", "listing", "validation")):
        bases.append("https://trakheesi.dubailand.gov.ae" + path.replace("{token}", token))

headers = [
    {"Accept": "application/json"},
    {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"},
]
for url in bases:
    for hdr in headers:
        try:
            r = httpx.get(url, headers=hdr, timeout=30, follow_redirects=True)
        except Exception as exc:
            print("ERR", url, exc)
            continue
        ct = r.headers.get("content-type", "")
        if r.status_code < 400 and "json" in ct:
            print("HIT", r.status_code, url, r.text[:500])
        elif r.status_code < 400 and r.text.lstrip().startswith("{"):
            print("HIT-JSON", r.status_code, url, r.text[:500])