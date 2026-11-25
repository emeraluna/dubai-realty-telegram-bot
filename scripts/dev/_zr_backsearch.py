import re

import httpx

t = httpx.get("https://trakheesi.dubailand.gov.ae/rev/static/js/main.0dad9b96.js", timeout=60).text
idx = t.find("tR=xr.create")
window = t[max(0, idx - 80000) : idx]
# all function zr definitions in window
for m in re.finditer(r"function zr\(\w\)\{", window):
    start = m.start()
    snippet = window[start : start + 500]
    print("---", start, "---")
    print(snippet)
    print()

for m in re.finditer(r"zr=function\(\w\)\{", window):
    start = m.start()
    snippet = window[start : start + 500]
    print("--- arrow", start, "---")
    print(snippet)
    print()