from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

from scrapers.errors import ExtractionError
from scrapers.payload import ListingPayload

_ROOT = Path(__file__).resolve().parents[2]
_REGISTRY = _ROOT / "data" / "owner_registry.csv"


@lru_cache(maxsize=1)
def _rows() -> list[dict[str, str]]:
    if not _REGISTRY.is_file():
        return []
    with _REGISTRY.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def _pick(row: dict[str, str], *names: str) -> str | None:
    lowered = {k.strip().lower(): v.strip() for k, v in row.items() if k and v is not None}
    for name in names:
        val = lowered.get(name.lower())
        if val:
            return val
    return None


def lookup_owner_file(listing_fields: dict[str, object]) -> ListingPayload:
    rows = _rows()
    if not rows:
        raise ExtractionError(
            code="owner_registry_missing",
            message="data/owner_registry.csv not found or empty",
            extractor="owner_registry",
            source="manual",
        )

    permit = str(listing_fields.get("permit_number") or "").strip()
    txn = str(listing_fields.get("transaction_number") or "").strip()
    guid = str(listing_fields.get("listing_guid") or "").strip()
    estate = str(listing_fields.get("real_estate_number") or "").strip()
    building = str(listing_fields.get("building") or "").strip().lower()
    unit = str(listing_fields.get("unit_number") or "").strip()
    pf_id = str(listing_fields.get("source_listing_id") or "").strip()

    for row in rows:
        owner_name = _pick(row, "owner_name", "owner name", "owner")
        owner_phone = _pick(row, "owner_phone", "owner phone", "phone", "mobile")
        if not owner_name or not owner_phone:
            continue
        if owner_name.upper().startswith("REPLACE"):
            continue
        row_permit = _pick(row, "ad_license", "permit", "permit_number", "license")
        row_txn = _pick(row, "transaction_number", "transaction", "permit_number_trakheesi")
        row_guid = _pick(row, "listing_guid", "guid")
        row_estate = _pick(row, "real_estate_number", "real_estate")
        row_building = (_pick(row, "building", "building_name") or "").lower()
        row_unit = _pick(row, "unit", "unit_number")
        row_pf = _pick(row, "pf_listing_id", "listing_id", "external_id")

        if permit and row_permit and permit == row_permit:
            pass
        elif txn and row_txn and txn == row_txn:
            pass
        elif guid and row_guid and guid == row_guid:
            pass
        elif estate and row_estate and estate == row_estate:
            pass
        elif pf_id and row_pf and pf_id == row_pf:
            pass
        elif building and row_building and building == row_building and (not row_unit or row_unit == unit):
            pass
        else:
            continue

        return ListingPayload(
            source="manual",
            owner_name=owner_name,
            owner_phone=owner_phone,
            permit_number=row_permit or permit or None,
            unit_number=row_unit or unit or None,
            building=row_building.title() if row_building else (building.title() if building else None),
            raw_payload={"owner_registry_file": {"path": str(_REGISTRY), "matched_row": row}},
        )

    raise ExtractionError(
        code="owner_registry_no_match",
        message="no registry row matched listing keys",
        extractor="owner_registry",
        source="manual",
    )


def lookup_owner_by_phone(phone: str) -> ListingPayload:
    from services.uae_phone import canonical_uae_mobile, digits_only, uae_phone_variants

    canonical = canonical_uae_mobile(phone)
    if not canonical:
        raise ExtractionError(
            code="owner_registry_bad_phone",
            message="invalid UAE mobile",
            extractor="owner_registry",
            source="manual",
        )
    needle = {digits_only(v) for v in uae_phone_variants(canonical)}
    rows = _rows()
    for row in rows:
        row_phone = _pick(row, "owner_phone", "owner phone", "phone", "mobile", "dld_mobile")
        if not row_phone:
            continue
        if digits_only(row_phone) not in needle:
            continue
        owner_name = _pick(row, "owner_name", "owner name", "owner")
        owner_phone = row_phone
        if not owner_name:
            continue
        return ListingPayload(
            source="manual",
            owner_name=owner_name,
            owner_phone=canonical_uae_mobile(owner_phone) or owner_phone,
            permit_number=_pick(row, "ad_license", "permit", "permit_number", "license"),
            building=_pick(row, "building", "building_name"),
            unit_number=_pick(row, "unit", "unit_number"),
            raw_payload={"owner_registry_file": {"path": str(_REGISTRY), "matched_row": row, "by_phone": True}},
        )
    raise ExtractionError(
        code="owner_registry_phone_miss",
        message="no registry row for phone",
        extractor="owner_registry",
        source="manual",
    )