import httpx

t = httpx.get("https://trakheesi.dubailand.gov.ae/rev/static/js/main.0dad9b96.js", timeout=60).text
for needle in ("consumer-id", "consumerId", "authorizationKey", "nR.post"):
    i = t.find(needle)
    if i >= 0:
        print("===", needle, "===")
        print(t[i : i + 600])