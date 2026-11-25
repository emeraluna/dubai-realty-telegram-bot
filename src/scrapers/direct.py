from __future__ import annotations

import json
import re
from typing import Any

import httpx

from scrapers.base import BaseExtractor
from scrapers.browser_headers import browser_headers
from scrapers.concurrency import source_concurrency
from scrapers.embed_json import extract_embedded_nodes
from scrapers.errors import ExtractionError
from scrapers.payload import ListingPayload
from services.lookup_request import LookupRequest
from services.owner_broker_guard import strip_broker_owner
from services.permit_candidates import extract_owner_fields_from_unknown

_JSON_LD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(?P<body>.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
_NEXT_DATA_RE = re.compile(
    r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(?P<body>.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


def _walk(obj: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(obj, dict):
        found.append(obj)
        for value in obj.values():
            found.extend(_walk(value))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(_walk(item))
    return found


def _pick_contact(nodes: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    name_keys = (
        "ownerName",
        "owner_name",
        "landlordName",
        "landlord_name",
        "landlord",
    )
    phone_keys = (
        "ownerPhone",
        "owner_phone",
        "landlordPhone",
        "landlord_phone",
        "landlordMobile",
        "landlord_mobile",
    )

    owner_name: str | None = None
    owner_phone: str | None = None

    for node in nodes:
        contacts = node.get("contact_options") or node.get("contactOptions")
        if isinstance(contacts, list):
            for item in contacts:
                if not isinstance(item, dict):
                    continue
                kind = str(item.get("type") or item.get("contact_type") or "").lower()
                if kind and kind not in {"owner", "landlord", "seller"}:
                    continue
                name = item.get("name") or item.get("contact_name")
                phone = item.get("value") or item.get("phone") or item.get("telephone")
                if isinstance(name, str) and name.strip():
                    owner_name = owner_name or name.strip()
                if isinstance(phone, str) and phone.strip():
                    owner_phone = owner_phone or phone.strip()
        for key in name_keys:
            val = node.get(key)
            if isinstance(val, str) and val.strip():
                owner_name = owner_name or val.strip()
        for key in phone_keys:
            val = node.get(key)
            if isinstance(val, str) and val.strip():
                owner_phone = owner_phone or val.strip()
        if isinstance(node.get("contactPoint"), dict):
            contact_point = node["contactPoint"]
            role = str(contact_point.get("role") or contact_point.get("@type") or "").lower()
            if "agent" not in role and "broker" not in role:
                if not owner_name and isinstance(contact_point.get("name"), str):
                    owner_name = contact_point.get("name", "").strip() or owner_name
                if not owner_phone and isinstance(contact_point.get("telephone"), str):
                    owner_phone = contact_point.get("telephone", "").strip() or owner_phone

    return owner_name, owner_phone


def _pick_permit(nodes: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    permit_number: str | None = None
    permit_status: str | None = None
    for node in nodes:
        for key in ("permitNumber", "permit_number", "trakheesi", "licenseNumber"):
            val = node.get(key)
            if val is not None and str(val).strip():
                permit_number = str(val).strip()
                break
        rera = node.get("rera")
        if isinstance(rera, dict):
            primary = rera.get("number") or rera.get("permitNumber")
            if primary is not None and str(primary).strip():
                permit_number = permit_number or str(primary).strip()
            issued = rera.get("issued_license_number")
            if issued is not None and str(issued).strip() and not permit_number:
                permit_number = str(issued).strip()
            status = rera.get("status") or rera.get("permitStatus")
            if status is not None and str(status).strip():
                permit_status = permit_status or str(status).strip()
        if permit_number and permit_status:
            break
    return permit_number, permit_status


def _extract_fields(nodes: list[dict[str, Any]], req: LookupRequest) -> ListingPayload:
    owner_name, owner_phone = _pick_contact(nodes)

    building = None
    community = None
    developer = None
    unit_number = None
    floor = None
    plot_number = None
    size_sqft = None

    scraped_permit, scraped_status = _pick_permit(nodes)
    permit_number = scraped_permit
    permit_status = scraped_status
    rera_blob: dict[str, Any] | None = None
    validation_url: str | None = None

    for node in nodes:
        building = building or node.get("building") or node.get("buildingName")
        community = community or node.get("community") or node.get("location")
        developer = developer or node.get("developer") or node.get("developerName")
        raw_unit = node.get("unitNumber") or node.get("unit_number") or node.get("unit")
        if isinstance(raw_unit, str):
            cleaned = raw_unit.strip()
            if cleaned and cleaned.lower() not in {"sqft", "sqm", "unit"}:
                unit_number = unit_number or cleaned
        elif raw_unit is not None and not isinstance(raw_unit, (dict, list)):
            unit_number = unit_number or str(raw_unit).strip()
        floor = floor or node.get("floor")
        plot_number = plot_number or node.get("plotNumber")
        permit_status = permit_status or node.get("permitStatus")
        location = node.get("location")
        if isinstance(location, dict):
            building = building or location.get("name") or location.get("building")
        rera = node.get("rera")
        if isinstance(rera, dict):
            rera_blob = rera_blob or rera
            validation_url = validation_url or rera.get("permit_validation_url")
        if size_sqft is None:
            size = node.get("sizeSqft") or node.get("size") or node.get("floorSize")
            if isinstance(size, (int, float)):
                size_sqft = float(size)

    owner_from_tree, phone_from_tree = extract_owner_fields_from_unknown(nodes)
    if owner_from_tree:
        owner_name = owner_name or owner_from_tree
    if phone_from_tree:
        owner_phone = owner_phone or phone_from_tree

    payload = ListingPayload(
        source=req.source,
        source_url=req.raw_input.strip(),
        source_listing_id=req.external_id,
        unit_number=str(unit_number).strip() if unit_number else None,
        floor=str(floor).strip() if floor else None,
        building=str(building).strip() if building else None,
        community=str(community).strip() if community else None,
        developer=str(developer).strip() if developer else None,
        size_sqft=size_sqft,
        plot_number=str(plot_number).strip() if plot_number else None,
        permit_number=str(permit_number).strip() if permit_number else None,
        permit_status=str(permit_status).strip() if permit_status else None,
        owner_name=owner_name,
        owner_phone=owner_phone,
        raw_payload={
            "direct": {
                "node_count": len(nodes),
                "rera": rera_blob,
                "permit_validation_url": validation_url,
            }
        },
    )
    return strip_broker_owner(payload)


def parse_listing_html(html: str, req: LookupRequest) -> ListingPayload:
    nodes: list[dict[str, Any]] = []

    for match in _JSON_LD_RE.finditer(html):
        body = match.group("body").strip()
        if not body:
            continue
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            continue
        nodes.extend(_walk(data))

    next_match = _NEXT_DATA_RE.search(html)
    if next_match:
        try:
            next_data = json.loads(next_match.group("body"))
            nodes.extend(_walk(next_data))
        except json.JSONDecodeError:
            pass

    nodes.extend(extract_embedded_nodes(html))

    if not nodes:
        raise ExtractionError(
            code="direct_parse_empty",
            message="no JSON-LD or __NEXT_DATA__ payload found",
            extractor="direct",
            source=req.source,
        )

    return _extract_fields(nodes, req)


class DirectParserExtractor(BaseExtractor):
    name = "direct"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    def supports(self, req: LookupRequest) -> bool:
        return req.source in ("propertyfinder", "bayut")

    async def _fetch(self, req: LookupRequest) -> ListingPayload:
        url = req.raw_input.strip()
        if not url.startswith("http"):
            url = f"https://{url}"

        headers = browser_headers(referer=url)
        alt_hosts = []
        if "www.propertyfinder.ae" in url:
            alt_hosts.append(url.replace("www.propertyfinder.ae", "m.propertyfinder.ae", 1))
        if "www.bayut.com" in url:
            alt_hosts.append(url.replace("www.bayut.com", "m.bayut.com", 1))

        async def _call() -> str:
            client = self._client or httpx.AsyncClient(
                timeout=httpx.Timeout(60.0),
                follow_redirects=True,
                headers=headers,
            )
            own_client = self._client is None
            try:
                candidates = [url, *alt_hosts]
                last_status = 0
                for candidate in candidates:
                    response = await client.get(candidate, headers=browser_headers(referer=candidate))
                    last_status = response.status_code
                    if response.status_code < 400:
                        return response.text
                raise ExtractionError(
                    code="direct_http_error",
                    message=f"status={last_status}",
                    extractor=self.name,
                    source=req.source,
                )
            finally:
                if own_client:
                    await client.aclose()

        html = await source_concurrency.run(req.source, _call)
        return parse_listing_html(html, req)