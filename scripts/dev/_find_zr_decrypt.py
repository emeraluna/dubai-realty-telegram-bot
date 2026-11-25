import httpx

t = httpx.get("https://trakheesi.dubailand.gov.ae/rev/static/js/main.0dad9b96.js", timeout=60).text
idx = t.find("tR.interceptors.request.use")
chunk = t[idx - 5000 : idx + 500]
# find short zr=function
import re

for m in re.finditer(r"zr=function\(\w+\)\{[^}]+\}", chunk):
    print(m.group(0))
for m in re.finditer(r"function zr\(\w\)\{[^}]{1,200}\}", t):
    s = m.group(0)
    if "atob" in s or "decode" in s.lower() or "Crypto" in s or "AES" in s:
        print("crypto zr:", s[:400])