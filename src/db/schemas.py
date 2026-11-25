from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ListingUpsertPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source: str
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