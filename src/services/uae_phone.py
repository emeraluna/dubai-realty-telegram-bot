from __future__ import annotations

import re


def digits_only(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")


def canonical_uae_mobile(phone: str) -> str | None:
    d = digits_only(phone)
    if not d:
        return None
    if len(d) == 12 and d.startswith("9715"):
        return d
    if len(d) == 11 and d.startswith("971") and d[3] == "5":
        return d
    if len(d) == 10 and d.startswith("05"):
        return "971" + d[1:]
    if len(d) == 9 and d.startswith("5"):
        return "971" + d
    if len(d) == 13 and d.startswith("009715"):
        return d[2:]
    return None


def is_uae_mobile_input(text: str) -> bool:
    stripped = text.strip()
    if stripped.startswith("+") and "971" in stripped:
        return canonical_uae_mobile(stripped) is not None
    if re.match(r"^0?5\d{8}$", digits_only(stripped)):
        return True
    d = digits_only(stripped)
    return len(d) in {9, 10, 11, 12, 13} and canonical_uae_mobile(stripped) is not None


def uae_phone_variants(phone: str) -> list[str]:
    canonical = canonical_uae_mobile(phone)
    if not canonical:
        return [phone.strip()] if phone.strip() else []
    local = canonical[3:]
    found: set[str] = {
        phone.strip(),
        canonical,
        f"+{canonical}",
        f"00{canonical}",
        local,
        f"0{local}",
        f"+971 {local[:2]} {local[2:5]} {local[5:]}",
    }
    return sorted(x for x in found if x)