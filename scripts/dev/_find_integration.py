import re

import httpx

GUID = "qnzrseuxs57ltl64cp5jt82t2ip0cbe2o54hxgcqfpngnsxme"
t = httpx.get("https://trakheesi.dubailand.gov.ae/rev/static/js/main.0dad9b96.js", timeout=60).text

for label, pat in [
    ("integration create", r"integration_api[^;]{0,400}create\([^)]+\)"),
    ("FkhqRz6", r".{0,200}FkhqRz6DBs.{0,200}"),
    ("listing_guid auth", r"listing_guid_validation[^;]{0,500}"),
    ("nR=", r"nR=[^,]{0,300}"),
]:
    m = re.search(pat, t)
    if m:
        print("===", label, "===")
        print(m.group(0)[:800])
        print()

# Find function that posts ListingGUID
for m in re.finditer(r"ListingGUID", t):
    start = max(0, m.start() - 120)
    end = min(len(t), m.end() + 200)
    snippet = t[start:end]
    if "Captcha" in snippet or "post" in snippet.lower():
        print("--- snippet ---")
        print(snippet)
        print()