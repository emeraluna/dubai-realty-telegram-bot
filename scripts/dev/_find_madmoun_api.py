import re
import httpx

t = httpx.get("https://trakheesi.dubailand.gov.ae/rev/static/js/main.0dad9b96.js", timeout=60).text
for m in re.finditer(r"validateListingDetailsUsingGuid[^\"']{0,200}", t):
    print(m.group(0)[:200])
print("---")
for m in re.finditer(r"IntegrationController[^\"']{0,200}", t):
    print(m.group(0)[:200])
print("--- auth keys ---")
for m in re.finditer(r"listing_guid_validation_authorization_key[^\"']{0,120}", t):
    print(m.group(0))
for m in re.finditer(r"REACT_APP_[A-Z0-9_]+", t):
    s = m.group(0)
    if "API" in s or "URL" in s or "BASE" in s or "LISTING" in s or "GUID" in s:
        print(s)