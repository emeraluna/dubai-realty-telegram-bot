from __future__ import annotations

import re
from re import Pattern
from urllib.parse import urlparse

from config import get_settings
from services.lookup_request import LookupRequest
from services.uae_phone import canonical_uae_mobile, is_uae_mobile_input


class InputParseError(ValueError):
    pass


_PF_HOST = re.compile(
    r"^(?:https?://)?(?:[a-z0-9-]+\.)*propertyfinder\.ae(?::\d+)?(?:/|$)",
    re.IGNORECASE,
)
_BAYUT_HOST = re.compile(
    r"^(?:https?://)?(?:[a-z0-9-]+\.)*bayut\.com(?::\d+)?(?:/|$)",
    re.IGNORECASE,
)
_PF_LISTING_ID = re.compile(r"(\d+)\.html", re.IGNORECASE)
_BAYUT_LISTING_ID = re.compile(r"details-(\d+)\.html", re.IGNORECASE)
_BAYUT_LISTING_ID_FALLBACK = re.compile(r"/(\d+)\.html", re.IGNORECASE)


def _permit_pattern(min_len: int, max_len: int) -> Pattern[str]:
    return re.compile(
        rf"^(?:permit\s*:\s*)?(\d{{{min_len},{max_len}}})\s*$",
        re.IGNORECASE,
    )


def _ensure_url_scheme(text: str) -> str:
    stripped = text.strip()
    if re.match(r"^https?://", stripped, re.IGNORECASE):
        return stripped
    if _PF_HOST.match(stripped) or _BAYUT_HOST.match(stripped):
        return f"https://{stripped.lstrip('/')}"
    return stripped


def _extract_pf_listing_id(url: str) -> str | None:
    match = _PF_LISTING_ID.search(url)
    return match.group(1) if match else None


def _extract_bayut_listing_id(url: str) -> str | None:
    match = _BAYUT_LISTING_ID.search(url)
    if match:
        return match.group(1)
    match = _BAYUT_LISTING_ID_FALLBACK.search(url)
    return match.group(1) if match else None


def _parse_propertyfinder(raw_input: str, candidate: str) -> LookupRequest | None:
    if not _PF_HOST.match(candidate):
        return None
    listing_id = _extract_pf_listing_id(candidate)
    if listing_id is None:
        raise InputParseError("propertyfinder listing id not found in url")
    return LookupRequest(
        source="propertyfinder",
        external_id=listing_id,
        raw_input=raw_input,
    )


def _parse_bayut(raw_input: str, candidate: str) -> LookupRequest | None:
    if not _BAYUT_HOST.match(candidate):
        return None
    listing_id = _extract_bayut_listing_id(candidate)
    if listing_id is None:
        raise InputParseError("bayut listing id not found in url")
    return LookupRequest(
        source="bayut",
        external_id=listing_id,
        raw_input=raw_input,
    )


def _resolve_permit_bounds(
    permit_min_length: int | None,
    permit_max_length: int | None,
) -> tuple[int, int]:
    if permit_min_length is not None and permit_max_length is not None:
        return permit_min_length, permit_max_length
    settings = get_settings()
    pmin = permit_min_length if permit_min_length is not None else settings.trakheesi_permit_min_length
    pmax = permit_max_length if permit_max_length is not None else settings.trakheesi_permit_max_length
    return pmin, pmax


def _parse_dld_phone(raw_input: str) -> LookupRequest | None:
    stripped = raw_input.strip()
    if not is_uae_mobile_input(stripped):
        return None
    canonical = canonical_uae_mobile(stripped)
    if not canonical:
        return None
    return LookupRequest(
        source="dld_phone",
        external_id=canonical,
        raw_input=raw_input,
    )


def _parse_trakheesi(raw_input: str, permit_min: int, permit_max: int) -> LookupRequest | None:
    pattern = _permit_pattern(permit_min, permit_max)
    match = pattern.match(raw_input.strip())
    if not match:
        return None
    permit = match.group(1)
    if is_uae_mobile_input(permit):
        return None
    return LookupRequest(
        source="trakheesi",
        external_id=permit,
        raw_input=raw_input,
    )


def parse_lookup_input(
    text: str,
    *,
    permit_min_length: int | None = None,
    permit_max_length: int | None = None,
) -> LookupRequest:
    if text is None or not str(text).strip():
        raise InputParseError("empty input")

    raw_input = str(text)
    stripped = raw_input.strip()

    phone = _parse_dld_phone(raw_input)
    if phone is not None:
        return phone

    if not re.search(r"[\s/]", stripped) and not stripped.lower().startswith("permit"):
        pmin, pmax = _resolve_permit_bounds(permit_min_length, permit_max_length)
        permit_result = _parse_trakheesi(raw_input, pmin, pmax)
        if permit_result is not None:
            return permit_result

    candidate = _ensure_url_scheme(stripped)
    parsed = urlparse(candidate)
    if parsed.scheme in ("http", "https") and parsed.netloc:
        path = parsed.path or "/"
        if not path.endswith("/") and path != "/":
            path = path.rstrip("/")
        normalized = f"{parsed.scheme}://{parsed.netloc}{path}"
        if parsed.query:
            normalized = f"{normalized}?{parsed.query}"
    else:
        normalized = candidate

    pf = _parse_propertyfinder(raw_input, normalized)
    if pf is not None:
        return pf

    bayut = _parse_bayut(raw_input, normalized)
    if bayut is not None:
        return bayut

    pmin, pmax = _resolve_permit_bounds(permit_min_length, permit_max_length)

    permit = _parse_trakheesi(raw_input, pmin, pmax)
    if permit is not None:
        return permit

    raise InputParseError("unrecognized input")


def route_lookup_input(text: str) -> LookupRequest:
    return parse_lookup_input(text)