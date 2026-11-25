import httpx

t = httpx.get("https://trakheesi.dubailand.gov.ae/rev/static/js/main.0dad9b96.js", timeout=60).text
idx = 0
while True:
    i = t.find("ElDEQZ", idx)
    if i < 0:
        break
    print(t[i - 100 : i + 200])
    print("---")
    idx = i + 1