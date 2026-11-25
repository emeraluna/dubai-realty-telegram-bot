from __future__ import annotations

import re
from typing import Any

_MADMOUN_URL = re.compile(
    r"https?://(?:[a-z0-9-]+\.)*dubailand\.gov\.ae[^\s\"'<>]*(?:madmoun|validation)[^\s\"'<>]*",
    re.IGNORECASE,
)
_DIGIT_BLOB = re.compile(r"\d{5,20}")

_PERMIT_FIELD_NAMES = frozenset(
    {
        "permitnumber",
        "trakheesi",
        "licensenumber",
        "issuedlicensenumber",
        "permitno",
        "madmoun",
        "dldpermit",
    }
)
_VALIDATION_FIELD_NAMES = frozenset(
    {
        "permitvalidationurl",
        "validationurl",
        "trakheesiurl",
        "madmounurl",
    }
)
_OWNER_NAME_KEYS = frozenset(
    {
        "ownername",
        "owner_name",
        "landlordname",
        "landlord_name",
        "titledeedownername",
        "propertyownername",
    }
)
_OWNER_PHONE_KEYS = frozenset(
    {
        "ownerphone",
        "owner_phone",
        "landlordphone",
        "landlord_phone",
        "mobilenumber",
        "mobile_number",
        "ownermobile",
        "propertyownerphone",
    }
)
_BROKER_KEYS = frozenset(
    {
        "brokername",
        "brokermobile",
        "brokeremail",
        "brokerid",
        "agentname",
        "agentphone",
        "agentmobile",
        "agentemail",
        "authorityname",
        "cardholdername",
        "cardholdernameen",
        "cardholdernamear",
        "cardholdermobile",
        "cardholderemail",
        "cardholdernumber",
    }
)
_TRANSACTION_KEYS = frozenset({"transactionnumber", "transaction_number", "listingtransactionnumber"})


def _norm_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.lower())


def _add_candidate(bucket: set[str], value: Any) -> None:
    if value is None:
        return
    text = str(value).strip()
    if not text:
        return
    digits = "".join(_DIGIT_BLOB.findall(text))
    if len(digits) >= 5:
        bucket.add(digits)


def collect_permit_candidates(*payloads: dict[str, Any] | None) -> list[str]:
    found: set[str] = set()

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            for key, val in obj.items():
                nk = _norm_key(str(key))
                if nk in _BROKER_KEYS:
                    continue
                if nk in _PERMIT_FIELD_NAMES:
                    _add_candidate(found, val)
                walk(val)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)
        elif isinstance(obj, str):
            for match in _DIGIT_BLOB.findall(obj):
                if 10 <= len(match) <= 20:
                    found.add(match)

    for payload in payloads:
        if payload:
            walk(payload)

    return sorted(found, key=lambda x: (len(x), x))


def collect_validation_urls(*payloads: dict[str, Any] | None) -> list[str]:
    urls: set[str] = set()

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            for key, val in obj.items():
                nk = _norm_key(str(key))
                if nk in _VALIDATION_FIELD_NAMES and isinstance(val, str):
                    for match in _MADMOUN_URL.finditer(val):
                        urls.add(match.group(0))
                walk(val)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)
        elif isinstance(obj, str):
            for match in _MADMOUN_URL.finditer(obj):
                urls.add(match.group(0))

    for payload in payloads:
        if payload:
            walk(payload)

    return sorted(urls)


def _owner_field_walk(node: Any, *, name: str | None, phone: str | None) -> tuple[str | None, str | None]:
    if isinstance(node, dict):
        for key, val in node.items():
            nk = _norm_key(str(key))
            if nk in _BROKER_KEYS:
                continue
            if nk in _OWNER_NAME_KEYS and isinstance(val, str) and val.strip():
                name = name or val.strip()
            if nk in _OWNER_PHONE_KEYS and isinstance(val, str) and val.strip():
                phone = phone or val.strip()
            name, phone = _owner_field_walk(val, name=name, phone=phone)
    elif isinstance(node, list):
        for item in node:
            name, phone = _owner_field_walk(item, name=name, phone=phone)
    return name, phone


def extract_owner_fields_from_unknown(obj: Any) -> tuple[str | None, str | None]:
    return _owner_field_walk(obj, name=None, phone=None)


def collect_listing_guids(*payloads: dict[str, Any] | None) -> list[str]:
    found: set[str] = set()

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            for key, val in obj.items():
                nk = _norm_key(str(key))
                if nk in {"listingguid", "listing_guid", "khevjujtdig"} and isinstance(val, str) and val.strip():
                    found.add(val.strip())
                walk(val)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)
        elif isinstance(obj, str):
            for match in re.finditer(r"khevJujtDig=([a-z0-9]+)", obj, re.I):
                found.add(match.group(1))

    for payload in payloads:
        if payload:
            walk(payload)
    return sorted(found)


def collect_real_estate_numbers(*payloads: dict[str, Any] | None) -> list[str]:
    found: set[str] = set()

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            for key, val in obj.items():
                nk = _norm_key(str(key))
                if nk in {"realestatenumber", "realestate_number", "realestateno"}:
                    _add_candidate(found, val)
                walk(val)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    for payload in payloads:
        if payload:
            walk(payload)
            integration = payload.get("trakheesi_integration") if isinstance(payload, dict) else None
            if isinstance(integration, dict):
                broker = integration.get("broker")
                if isinstance(broker, dict):
                    _add_candidate(found, broker.get("RealEstateNumber"))
    return sorted(found, key=lambda x: (-len(x), x))


def collect_transaction_numbers(*payloads: dict[str, Any] | None) -> list[str]:
    found: set[str] = set()

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            for key, val in obj.items():
                nk = _norm_key(str(key))
                if nk in _TRANSACTION_KEYS:
                    _add_candidate(found, val)
                if nk == "listingdetails" and isinstance(val, dict):
                    txn = val.get("Transaction Number") or val.get("transaction number")
                    if isinstance(txn, str):
                        _add_candidate(found, txn)
                walk(val)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    for payload in payloads:
        if payload:
            walk(payload)
            sections = payload.get("madmoun_validation", {}) if isinstance(payload, dict) else {}
            visible = sections.get("visible") if isinstance(sections, dict) else None
            if isinstance(visible, dict):
                listing = visible.get("sections", {}).get("Listing Details", {})
                if isinstance(listing, dict):
                    txn = listing.get("Transaction Number")
                    if isinstance(txn, str):
                        _add_candidate(found, txn)
    return sorted(found, key=lambda x: (-len(x), x))