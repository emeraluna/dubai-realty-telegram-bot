import httpx

t = httpx.get("https://trakheesi.dubailand.gov.ae/rev/static/js/main.0dad9b96.js", timeout=60).text
idx = t.find("tR=xr.create")
print(t[idx : idx + 1200])