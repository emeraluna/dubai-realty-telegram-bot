from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from db.schemas import ListingUpsertPayload
from services.lookup_request import LookupRequest

CONTACT_FIELDS = frozenset({"owner_name", "owner_phone"})

ENRICHMENT_FIELDS = frozenset(
    {
        "unit_number",
        "floor",
        "building",
        "community",
        "developer",
        "size_sqft",
        "plot_number",
        "permit_number",
        "permit_status",
        "owner_name",
        "owner_phone",
    }
)


class ListingPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source: str | None = None
    source_url: str | None = None
    source_listing_id: str | None = None
    unit_number: str | None = None
    floor: str | None = None
    building: str | None = None
    community: str | None = None
    developer: str | None = None
    size_sqft: float | None = None
    plot_number: str | None = None
    permit_number: str | None = None
    permit_status: str | None = None
    owner_name: str | None = None
    owner_phone: str | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)

    def missing_enrichment_fields(self) -> set[str]:
        data = self.model_dump()
        return {key for key in ENRICHMENT_FIELDS if not data.get(key)}

    def needs_enrichment(self) -> bool:
        return bool(self.missing_enrichment_fields())

    def to_upsert(self, req: LookupRequest) -> ListingUpsertPayload:
        data = self.model_dump()
        data["source"] = self.source or req.source
        data["source_listing_id"] = self.source_listing_id or req.external_id
        if not data.get("source_url"):
            data["source_url"] = req.raw_input if req.source != "trakheesi" else None
        if req.source == "trakheesi" and not data.get("permit_number"):
            data["permit_number"] = req.external_id
        return ListingUpsertPayload(**data)


def merge_payloads(base: ListingPayload, patch: ListingPayload) -> ListingPayload:
    merged = base.model_dump()
    patch_data = patch.model_dump()

    merged["raw_payload"] = {
        **(merged.get("raw_payload") or {}),
        **(patch_data.get("raw_payload") or {}),
    }

    for key, value in patch_data.items():
        if key == "raw_payload" or value is None:
            continue
        current = merged.get(key)
        if key in CONTACT_FIELDS:
            if not current or (isinstance(value, str) and len(str(value).strip()) > len(str(current).strip())):
                merged[key] = value
        elif current is None:
            merged[key] = value

    return ListingPayload(**merged)