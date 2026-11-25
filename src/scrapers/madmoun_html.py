from __future__ import annotations

import re
from typing import Any

_SECTION = re.compile(
    r"(Listing Details|Authority Information|Broker Information|Property Details)\n",
    re.IGNORECASE,
)
_PAIR = re.compile(r"^([A-Za-z0-9 #]+)\n([^\n]+)$", re.MULTILINE)


def parse_madmoun_visible_text(body: str) -> dict[str, Any]:
    """Parse Madmoun SPA text after validation (broker/agency only — not owner)."""
    text = re.sub(r"\r\n", "\n", body.strip())
    if "verified by Dubai Land Department" not in text and "Listing Details" not in text:
        return {}

    sections: dict[str, dict[str, str]] = {}
    current = "root"
    sections[current] = {}

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if _SECTION.match(line + "\n"):
            current = line.strip()
            sections.setdefault(current, {})
            continue
        # pairs are often label on one line, value on next — handled below

    blocks = re.split(
        r"(Listing Details|Authority Information|Broker Information|Property Details)\n",
        text,
        flags=re.IGNORECASE,
    )
    if len(blocks) >= 3:
        for i in range(1, len(blocks), 2):
            title = blocks[i].strip()
            content = blocks[i + 1] if i + 1 < len(blocks) else ""
            pairs: dict[str, str] = {}
            lines = [ln.strip() for ln in content.split("\n") if ln.strip()]
            j = 0
            while j < len(lines):
                label = lines[j]
                if j + 1 < len(lines):
                    pairs[label] = lines[j + 1]
                    j += 2
                else:
                    pairs[label] = ""
                    j += 1
            sections[title] = pairs

    return {"sections": sections, "verified": "verified by dubai land department" in text.lower()}