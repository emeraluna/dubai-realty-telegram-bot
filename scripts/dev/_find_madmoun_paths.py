import re
import httpx

t = httpx.get("https://trakheesi.dubailand.gov.ae/rev/static/js/main.0dad9b96.js", timeout=60).text
for pat in ("madmoun", "validation", "khev", "listing"):
    hits = sorted(set(re.findall(rf"[^\"']{{0,30}}{pat}[^\"']{{0,80}}", t, flags=re.I)))
    print(f"--- {pat} ({len(hits)}) ---")
    for h in hits[:25]:
        print(h)