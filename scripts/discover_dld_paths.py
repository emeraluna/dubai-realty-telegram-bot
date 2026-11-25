"""Discover Trakheesi/DLD API path fragments from the public JS bundle."""
import re
import sys
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parents[1] / "data" / "dld_api_paths.txt"
URL = "https://trakheesi.dubailand.gov.ae/rev/static/js/main.0dad9b96.js"
NEEDLES = (
    r"Owner[A-Za-z]{0,30}",
    r"propertyOwner[^\"']{0,40}",
    r"titleDeed[^\"']{0,40}",
    r"RealEstateNumber[^\"']{0,80}",
    r"validateListing[^\"']{0,60}",
    r"getProperty[^\"']{0,60}",
    r"cardHolder[^\"']{0,40}",
    r"/[a-z0-9]{8,12}/[a-z0-9]{8,12}/[a-z0-9]{8,12}",
)


def main() -> int:
    text = httpx.get(URL, timeout=120).text
    seen: set[str] = set()
    lines: list[str] = []
    for pat in NEEDLES:
        for m in re.finditer(pat, text, re.I):
            sn = text[max(0, m.start() - 40) : m.end() + 80].replace("\n", " ")
            if sn in seen:
                continue
            seen.add(sn)
            lines.append(f"{pat}: {sn[:200]}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines[:200]), encoding="utf-8")
    print(f"wrote {len(lines)} snippets -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())