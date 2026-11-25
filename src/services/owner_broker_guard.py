from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from scrapers.payload import ListingPayload


def _digits(phone: str | None) -> str:
    if not phone:
        return ""
    return re.sub(r"\D", "", phone)


def _norm_name(name: str | None) -> str:
    if not name:
        return ""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _broker_from_madmoun_cache(raw: dict[str, Any] | None) -> tuple[str | None, str | None]:
    if not raw:
        return None, None
    try:
        from scrapers.madmoun_cache import load_cached_integration_by_guid
        from services.permit_candidates import collect_listing_guids
    except ImportError:
        return None, None
    guids = collect_listing_guids(raw)
    for guid in guids:
        cached = load_cached_integration_by_guid(guid)
        if not cached:
            continue
        body = cached.get("Response") if isinstance(cached.get("Response"), dict) else cached
        if not isinstance(body, dict):
            continue
        name = body.get("CardHolderNameEn") or body.get("CardHolderNameAr")
        phone = body.get("CardHolderMobile")
        if name or phone:
            return (
                str(name).strip() if name else None,
                str(phone).strip() if phone else None,
            )
    return None, None


def broker_contact_from_payload(raw: dict[str, Any] | None) -> tuple[str | None, str | None]:
    if not raw:
        return _broker_from_madmoun_cache(raw)
    integration = raw.get("trakheesi_integration")
    if isinstance(integration, dict):
        broker = integration.get("broker")
        if isinstance(broker, dict):
            name = broker.get("broker_name_en") or broker.get("broker_name_ar")
            phone = broker.get("broker_phone")
            if name or phone:
                return (
                    str(name).strip() if name else None,
                    str(phone).strip() if phone else None,
                )
        api = integration.get("api_response")
        if isinstance(api, dict):
            body = api.get("Response") if isinstance(api.get("Response"), dict) else api
            if isinstance(body, dict):
                name = body.get("CardHolderNameEn") or body.get("CardHolderNameAr")
                phone = body.get("CardHolderMobile")
                if name or phone:
                    return (
                        str(name).strip() if name else None,
                        str(phone).strip() if phone else None,
                    )
    madmoun = raw.get("madmoun_validation")
    if isinstance(madmoun, dict):
        api = madmoun.get("api_response")
        if isinstance(api, dict):
            result = api.get("result") if isinstance(api.get("result"), dict) else api
            if isinstance(result, dict):
                name = result.get("CardHolderNameEn") or result.get("CardHolderNameAr")
                phone = result.get("CardHolderMobile")
                if name or phone:
                    return (
                        str(name).strip() if name else None,
                        str(phone).strip() if phone else None,
                    )
    name, phone = _broker_from_madmoun_cache(raw)
    if name or phone:
        return name, phone
    return None, None


def owner_matches_broker(
    owner_name: str | None,
    owner_phone: str | None,
    *,
    raw_payload: dict[str, Any] | None,
) -> bool:
    broker_name, broker_phone = broker_contact_from_payload(raw_payload)
    if not broker_name and not broker_phone:
        return False
    name_match = bool(
        owner_name
        and broker_name
        and _norm_name(owner_name) == _norm_name(broker_name)
    )
    phone_match = bool(
        owner_phone
        and broker_phone
        and _digits(owner_phone) == _digits(broker_phone)
    )
    if name_match and phone_match:
        return True
    if phone_match and (not owner_name or not broker_name):
        return True
    return False


def strip_broker_owner(payload: ListingPayload) -> ListingPayload:
    from scrapers.payload import ListingPayload as LP

    if not owner_matches_broker(payload.owner_name, payload.owner_phone, raw_payload=payload.raw_payload):
        return payload
    data = payload.model_dump()
    data["owner_name"] = None
    data["owner_phone"] = None
    return LP(**data)