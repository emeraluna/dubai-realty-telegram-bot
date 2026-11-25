from __future__ import annotations

import json
import re
from typing import Any
import httpx

from config import get_settings
from scrapers.concurrency import source_concurrency
from scrapers.errors import ExtractionError
from scrapers.payload import ListingPayload
from scrapers.madmoun_cache import load_cached_integration_by_guid
from scrapers.madmoun_html import parse_madmoun_visible_text
from scrapers.trakheesi_integration import integration_to_listing_payload
from scrapers.madmoun_playwright import fetch_madmoun_integration_json
from scrapers.trakheesi_recaptcha import fetch_listing_validation_captcha
from scrapers.trakheesi_runtime import load_trakheesi_public_config, parse_listing_guid_from_validation_url
from scrapers.actor_maps import MadmounIntegrationRecord
from services.permit_candidates import collect_permit_candidates, extract_owner_fields_from_unknown

_JSON_RE = re.compile(r"\{[\s\S]{20,50000}\}")

def _parse_payload(text: str) -> Any | None:
    stripped = text.strip()
    if not stripped:
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    for match in _JSON_RE.finditer(text):
        fragment = match.group(0)
        try:
            return json.loads(fragment)
        except json.JSONDecodeError:
            continue
    return None


def _owner_from_madmoun_result(result: Any) -> tuple[str | None, str | None]:
    return extract_owner_fields_from_unknown(result)


async def _post_json(url: str, body: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=httpx.Timeout(90.0), follow_redirects=True) as client:
        response = await client.post(url, json=body, headers=headers)
        if response.status_code >= 400:
            raise ExtractionError(
                code="madmoun_http_error",
                message=f"status={response.status_code}",
                extractor="madmoun",
                source="trakheesi",
            )
        data = response.json()
        if not isinstance(data, dict):
            raise ExtractionError(
                code="madmoun_invalid",
                message="response is not an object",
                extractor="madmoun",
                source="trakheesi",
            )
        return data


def _integration_headers(settings: Any, config: Any) -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Origin": "https://trakheesi.dubailand.gov.ae",
        "Referer": "https://trakheesi.dubailand.gov.ae/",
        "consumer-id": settings.trakheesi_integration_consumer_id or config.integration_consumer_id,
        "authorizationKey": settings.trakheesi_listing_guid_auth_key or config.listing_guid_auth_key,
    }
    token = (settings.trakheesi_session_token or "").strip()
    if token:
        headers["Token"] = token
    return headers


async def _fetch_by_listing_guid(guid: str, *, validation_url: str | None = None) -> dict[str, Any]:
    settings = get_settings()
    config = await load_trakheesi_public_config()

    headers = _integration_headers(settings, config)

    integration_url = f"{(settings.trakheesi_integration_api_base or config.integration_api_base).rstrip('/')}/{config.integration_post_path.lstrip('/')}"
    captcha_tokens: list[str | None] = []
    solved = await fetch_listing_validation_captcha(validation_url)
    if solved:
        captcha_tokens.append(solved)
    captcha_tokens.append(None)

    data: dict[str, Any] = {}
    for captcha in captcha_tokens:
        payload = {"ListingGUID": guid, "CaptchaToken": captcha or ""}
        if not captcha:
            continue

        async def _integration_call(p: dict[str, Any] = payload) -> dict[str, Any]:
            return await _post_json(integration_url, p, headers)

        try:
            data = await source_concurrency.run("trakheesi", _integration_call)
            if data.get("result"):
                return data
        except ExtractionError:
            continue

    revamp_url = f"{(settings.trakheesi_revamp_api_base or config.revamp_api_base).rstrip('/')}/{config.validate_guid_path.lstrip('/')}"
    body_guid = {"ListingGUID": guid, "authorizationKey": headers["authorizationKey"]}

    async def _revamp_call() -> dict[str, Any]:
        return await _post_json(revamp_url, body_guid, headers)

    try:
        data = await source_concurrency.run("trakheesi", _revamp_call)
        if data.get("result"):
            return data
    except ExtractionError:
        pass
    return data


def _payload_from_api(guid: str, data: dict[str, Any], *, url: str | None) -> ListingPayload:
    result = data.get("result") or data
    if isinstance(result, dict) and isinstance(result.get("_visible_text"), str):
        visible = parse_madmoun_visible_text(result["_visible_text"])
        permit_digits = None
        for section in visible.get("sections", {}).values():
            if not isinstance(section, dict):
                continue
            for label, val in section.items():
                nk = re.sub(r"[^a-z0-9]", "", str(label).lower())
                if nk in {"license", "licensenumber", "permitnumber"} and isinstance(val, str):
                    digits = "".join(ch for ch in val if ch.isdigit())
                    if digits:
                        permit_digits = digits
        return ListingPayload(
            source="trakheesi",
            permit_number=permit_digits,
            raw_payload={
                "madmoun_validation": {
                    "url": url,
                    "listing_guid": guid,
                    "visible": visible,
                }
            },
        )

    try:
        record = MadmounIntegrationRecord.model_validate(result)
        record_payload = record.to_listing_payload()
        if record_payload.owner_name and record_payload.owner_phone:
            return record_payload.model_copy(
                update={
                    "raw_payload": {
                        "madmoun_validation": {
                            "url": url,
                            "listing_guid": guid,
                            "api_response": data,
                        }
                    }
                }
            )
    except Exception:
        record_payload = None

    owner_name, owner_phone = _owner_from_madmoun_result(result)
    if record_payload:
        owner_name = owner_name or record_payload.owner_name
        owner_phone = owner_phone or record_payload.owner_phone
    permit_candidates = collect_permit_candidates(result if isinstance(result, dict) else {"result": result})
    permit_digits = next((c for c in permit_candidates if c.isdigit() and len(c) >= 10), None)
    if permit_digits is None:
        permit_digits = next((c for c in permit_candidates if c.isdigit()), None)

    if not owner_name and not owner_phone and not permit_digits:
        raise ExtractionError(
            code="madmoun_no_owner",
            message="madmoun api returned no owner or permit fields",
            extractor="madmoun",
            source="trakheesi",
        )

    return ListingPayload(
        source="trakheesi",
        permit_number=permit_digits,
        owner_name=owner_name,
        owner_phone=owner_phone,
        raw_payload={
            "madmoun_validation": {
                "url": url,
                "listing_guid": guid,
                "api_response": data,
            }
        },
    )


async def fetch_madmoun_validation(url: str) -> ListingPayload:
    guid = parse_listing_guid_from_validation_url(url)
    if guid:
        cached = load_cached_integration_by_guid(guid)
        if cached:
            try:
                return integration_to_listing_payload(guid, cached, url=url)
            except Exception:
                pass
        if get_settings().madmoun_playwright_enabled:
            try:
                data = await fetch_madmoun_integration_json(url)
                return _payload_from_api(guid, data, url=url)
            except ExtractionError:
                pass
            except Exception:
                pass
        try:
            data = await _fetch_by_listing_guid(guid, validation_url=url)
            return _payload_from_api(guid, data, url=url)
        except ExtractionError:
            pass
        except Exception:
            pass

    async def _call() -> str:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(90.0),
            follow_redirects=True,
            headers={
                "User-Agent": "dubai-realty-bot/0.1",
                "Accept": "application/json, text/html, */*",
            },
        ) as client:
            try:
                response = await client.get(url)
            except httpx.HTTPError as exc:
                raise ExtractionError(
                    code="madmoun_connect_error",
                    message=str(exc),
                    extractor="madmoun",
                    source="trakheesi",
                ) from exc
            if response.status_code >= 400:
                raise ExtractionError(
                    code="madmoun_http_error",
                    message=f"status={response.status_code}",
                    extractor="madmoun",
                    source="trakheesi",
                )
            return response.text

    body = await source_concurrency.run("trakheesi", _call)
    parsed = _parse_payload(body)
    if parsed is None:
        if get_settings().madmoun_playwright_enabled:
            try:
                data = await fetch_madmoun_integration_json(url)
                if guid:
                    return _payload_from_api(guid, data, url=url)
            except ExtractionError:
                pass
            except Exception:
                pass
        visible = parse_madmoun_visible_text(body)
        if visible:
            permit_digits = None
            for section in visible.get("sections", {}).values():
                if not isinstance(section, dict):
                    continue
                for label, val in section.items():
                    nk = re.sub(r"[^a-z0-9]", "", str(label).lower())
                    if nk in {"license", "licensenumber", "permitnumber"} and isinstance(val, str):
                        digits = "".join(ch for ch in val if ch.isdigit())
                        if digits:
                            permit_digits = digits
            return ListingPayload(
                source="trakheesi",
                permit_number=permit_digits,
                raw_payload={"madmoun_validation": {"url": url, "visible": visible}},
            )
        raise ExtractionError(
            code="madmoun_parse_empty",
            message="no JSON in validation response",
            extractor="madmoun",
            source="trakheesi",
        )

    owner_name, owner_phone = extract_owner_fields_from_unknown(parsed)
    permit_candidates = collect_permit_candidates(parsed if isinstance(parsed, dict) else {"root": parsed})
    permit_digits = next((c for c in permit_candidates if c.isdigit() and len(c) >= 10), None)
    if permit_digits is None:
        permit_digits = next((c for c in permit_candidates if c.isdigit()), None)

    return ListingPayload(
        source="trakheesi",
        permit_number=permit_digits,
        owner_name=owner_name,
        owner_phone=owner_phone,
        raw_payload={"madmoun_validation": {"url": url, "parsed": parsed}},
    )